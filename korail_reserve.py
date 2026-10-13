"""
Poll KORAIL for an available train in a date/time window and reserve it
(hold only — does NOT pay). Uses korail-mobile-api.

Credentials come from (in order): --id/--password CLI args, KORAIL_ID /
KORAIL_PASSWORD env vars, korail_credentials.txt, or an interactive prompt.

By default this runs as a DRY RUN: it finds a bookable train and builds the
reservation request but does not send it. Pass --live to actually place the
hold on your account.

Example:
    python korail_reserve.py --dep 서울 --arr 부산 --date 20261010 \
        --time-from 090000 --time-to 120000 --live
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time

from korail_common import build_client_config, load_credentials
from korail_desktop_alert import launch_alert
from korail_notify import PRIORITY_DEFAULT, PRIORITY_URGENT, notify
from korail_mobile_api import (
    KorailApiError,
    KorailAppError,
    KorailAuthError,
    KorailClient,
    KorailNoDirectTrainError,
    KorailPassengerCounts,
    KorailSeatClass,
    KorailSeatUnavailableError,
    KorailSessionExpiredError,
    KorailSoldOutError,
    TrainSearchQuery,
)

MIN_POLL_INTERVAL_SECONDS = 5
SHUTDOWN_DELAY_SECONDS = 300


def _ui_result(status: str, **details) -> None:
    print("KORAIL_RESULT:" + json.dumps({"status": status, **details}, ensure_ascii=False), flush=True)

# IRT010110 ("잔여석없음") isn't in korail_mobile_api's known error-code tables
# (its own comment notes 0 APK sightings), so it surfaces as a bare KorailAppError
# instead of KorailSoldOutError. Observed live: the search listing still showed the
# seat as bookable but it was gone by the time the reservation POST landed.
SEAT_GONE_CODES = frozenset({"IRT010110"})


def _is_seat_gone(exc: KorailAppError) -> bool:
    if isinstance(exc, (KorailSoldOutError, KorailSeatUnavailableError)):
        return True
    return exc.code in SEAT_GONE_CODES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Poll KORAIL and reserve (hold) the first available train in a time window."
    )
    parser.add_argument("--id", default=None, help="KORAIL id (default: from korail_credentials.txt)")
    parser.add_argument("--dep", required=True, help="Departure station name or code, e.g. 서울")
    parser.add_argument("--arr", required=True, help="Arrival station name or code, e.g. 부산")
    parser.add_argument("--date", required=True, help="Travel date, YYYYMMDD")
    parser.add_argument("--time-from", default="000000", help="Earliest departure time HHMMSS (default: 000000)")
    parser.add_argument("--time-to", default="235959", help="Latest departure time HHMMSS (default: 235959)")
    parser.add_argument(
        "--seat-class",
        choices=["general", "special"],
        default="general",
        help="Seat class to book (default: general)",
    )
    parser.add_argument("--adults", type=int, default=1, help="Number of adult passengers (default: 1)")
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=20,
        help=f"Seconds between search attempts (default: 20, minimum: {MIN_POLL_INTERVAL_SECONDS})",
    )
    parser.add_argument(
        "--max-wait",
        type=int,
        default=30,
        help="Give up after this many minutes with no seat found (default: 30)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Actually submit the reservation. Without this flag, only a dry-run preview is produced.",
    )
    parser.add_argument(
        "--no-dynapath",
        dest="dynapath",
        action="store_false",
        help="Disable the anti-automation DynaPath token (on by default)",
    )
    parser.set_defaults(dynapath=True)
    parser.add_argument(
        "--allowed-codes",
        nargs="+",
        choices=["11"],
        default=["11"],
        help="Allowed reservation code (11 only)",
    )
    parser.add_argument(
        "--shutdown-after",
        action="store_true",
        help=f"With --live: shut down the PC {SHUTDOWN_DELAY_SECONDS // 60} min after the run ends "
        "(success, give-up, or error). Cancel with: shutdown /a",
    )
    return parser.parse_args()


KORAIL_URL = "https://www.letskorail.com/"

# SetThreadExecutionState flags: keep the system awake while this process runs.
# Windows drops the request automatically when the process exits.
_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001


def _prevent_sleep() -> None:
    if sys.platform != "win32":
        return
    import ctypes

    ctypes.windll.kernel32.SetThreadExecutionState(_ES_CONTINUOUS | _ES_SYSTEM_REQUIRED)


def _hhmm(hhmmss: str | None) -> str:
    return f"{hhmmss[:2]}:{hhmmss[2:4]}" if hhmmss and len(hhmmss) >= 4 else (hhmmss or "?")


def _route(args: argparse.Namespace) -> str:
    d = args.date
    return f"{args.dep}→{args.arr} {d[4:6]}/{d[6:8]}"


def _no_trains(args: argparse.Namespace) -> int:
    window = f"{_hhmm(args.time_from)}~{_hhmm(args.time_to)}"
    message = "선택한 시간 범위에 출발하는 직통 열차가 없습니다. 날짜나 출발 시간 범위를 변경해주세요."
    print(f"{_route(args)} {window}: {message}")
    _ui_result("no_trains", route=_route(args), departure=window)
    return 1


def _pick_train(trains, seat_class: KorailSeatClass, time_to: str, allowed_codes: list[str]):
    code_attr = "special_reservation_code" if seat_class is KorailSeatClass.SPECIAL else "general_reservation_code"
    for train in trains:
        if train.departure_time and train.departure_time > time_to:
            continue
        code = getattr(train, code_attr)
        # 예약 허용 코드는 11로 제한합니다.
        if code and code in allowed_codes:
            return train
    return None


def _schedule_shutdown() -> None:
    minutes = SHUTDOWN_DELAY_SECONDS // 60
    print(f"\nPC will shut down in {minutes} min. To cancel, run:  shutdown /a")
    try:
        subprocess.run(
            ["shutdown", "/s", "/t", str(SHUTDOWN_DELAY_SECONDS), "/c", "Korail bot finished - shutting down"],
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"Shutdown scheduling failed: {exc}")
        return
    notify(
        f"💤 {minutes}분 뒤 PC가 꺼집니다",
        "취소하려면 PC에서 명령 프롬프트에 shutdown /a 입력",
        priority=PRIORITY_DEFAULT,
        tags=["zzz"],
    )


def main() -> int:
    args = parse_args()
    # Dry runs end within seconds, so shutting down after one would only surprise you.
    shutdown = args.shutdown_after and args.live
    try:
        code = _run(args)
    except KeyboardInterrupt:
        # Stopped by hand: you're at the PC, so don't turn it off.
        print("Stopped by user.")
        return 130
    except Exception:
        if shutdown:
            _schedule_shutdown()
        raise
    if shutdown:
        _schedule_shutdown()
    return code


def _run(args: argparse.Namespace) -> int:
    args.poll_interval = max(args.poll_interval, MIN_POLL_INTERVAL_SECONDS)
    member_id, password = load_credentials(args.id)
    seat_class = KorailSeatClass.SPECIAL if args.seat_class == "special" else KorailSeatClass.GENERAL

    _prevent_sleep()
    client = KorailClient(build_client_config(enable_dynapath=args.dynapath))
    try:
        try:
            client.login(member_id, password)
        except KorailAuthError as exc:
            print(f"Login failed: {exc}")
            return 1
        print("Login succeeded. Searching...")

        deadline = time.monotonic() + args.max_wait * 60
        query = TrainSearchQuery(
            args.dep, args.arr, args.date,
            departure_time=args.time_from,
            passengers=args.adults,
            include_srt=True,
        )
        print(
            f"Search: {args.dep} -> {args.arr}, {args.date}, "
            f"{args.time_from}~{args.time_to}, adults={args.adults}, "
            f"seat={args.seat_class}, allowed codes={args.allowed_codes}, includes SRT."
        )

        found = None
        hold = None
        attempt = 0
        while time.monotonic() < deadline:
            attempt += 1

            if found is None:
                try:
                    result = client.search_trains(query)
                    candidates = list(result.trains)
                    page = result.next_page()
                    while page is not None:
                        try:
                            next_result = client.search_trains(query, continuation=page)
                        except KorailNoDirectTrainError:
                            # End of pagination must not discard trains already found.
                            break
                        if not next_result.trains:
                            break
                        if (
                            next_result.trains[0].departure_time
                            and next_result.trains[0].departure_time > args.time_to
                        ):
                            break
                        candidates.extend(next_result.trains)
                        page = next_result.next_page()

                    candidates = [
                        train for train in candidates
                        if train.departure_time
                        and args.time_from <= train.departure_time <= args.time_to
                    ]
                    if not candidates:
                        return _no_trains(args)
                    found = _pick_train(candidates, seat_class, args.time_to, args.allowed_codes)
                    if found is None and attempt == 1:
                        print(f"Search returned {len(candidates)} trains. First 20 statuses:")
                        for train in candidates[:20]:
                            print(
                                f"  {train.train_no} dep={train.departure_time} "
                                f"general={train.general_reservation_code!r} "
                                f"special={train.special_reservation_code!r} "
                                f"general status={train.raw.get('h_gen_rsv_nm', '')!r} "
                                f"special status={train.raw.get('h_spe_rsv_nm', '')!r} "
                                f"outside end time={bool(train.departure_time and train.departure_time > args.time_to)}"
                            )
                except KorailNoDirectTrainError:
                    return _no_trains(args)
                except KorailSessionExpiredError:
                    print("Session expired mid-poll, logging back in...")
                    client.clear_session()
                    client.login(member_id, password)
                    continue
                except KorailApiError as exc:
                    print(
                        f"Search stopped: {type(exc).__name__}, "
                        f"code={exc.code!r}: {exc}. This is not a no-seat result."
                    )
                    raise

            if found is None:
                print(f"[{attempt}] no bookable train yet in window, retrying in {args.poll_interval}s...")
                time.sleep(args.poll_interval)
                continue

            print(
                f"Found train {found.train_no}, departs {found.departure_time}, "
                f"arrives {found.arrival_time} - attempting reservation."
            )

            passengers = KorailPassengerCounts(adult=args.adults)

            if not args.live:
                # korail-mobile-api 2.x has no MutationConsent gate — client.reserve()
                # sends immediately — so this script's own --live flag is the only
                # dry-run guarantee: never call client.reserve() unless it's set.
                reservation_code = (
                    found.special_reservation_code
                    if seat_class is KorailSeatClass.SPECIAL
                    else found.general_reservation_code
                )
                print("\nDRY RUN — nothing was sent to KORAIL. Preview:")
                print(f"  train: {found.train_no}, departs {found.departure_time}, arrives {found.arrival_time}")
                print(f"  seat class: {seat_class.name}, reservation code: {reservation_code}")
                print(f"  price: {(found.general_availability_name or '').replace(chr(10), ' ')}")
                print("Re-run with --live to actually place this reservation.")
                _ui_result("preview", route=_route(args), departure=_hhmm(found.departure_time))
                return 0

            try:
                hold = client.reserve(found, passengers=passengers, seat_class=seat_class)
                break
            except KorailAppError as exc:
                if not _is_seat_gone(exc):
                    raise
                print(f"Seat vanished before the reservation went through ({exc}); resuming search...")
                found = None
                time.sleep(args.poll_interval)
                continue

        if hold is None:
            _ui_result("timeout", route=_route(args))
            print("Gave up: no bookable train appeared in the requested window before --max-wait elapsed.")
            notify(
                "⌛ 예약 못 잡음 · 모니터링 종료",
                f"{_route(args)} {_hhmm(args.time_from)}~{_hhmm(args.time_to)}\n"
                f"{args.max_wait}분 동안 예약 가능한 좌석이 나오지 않았습니다.",
                priority=PRIORITY_DEFAULT,
                tags=["hourglass"],
            )
            return 1

        print("\nReservation placed (not paid yet):")
        print(f"  PNR: {hold.pnr_no}")
        print(f"  total fare: {hold.total_fare}")
        print(f"  payment deadline: {hold.payment_deadline_date} {hold.payment_deadline_time}")
        print(f"  {hold.payment_deadline_notice or ''}")
        print("\nGo pay for it in the KORAIL app/site before the deadline, or it will auto-cancel.")
        deadline_date = hold.payment_deadline_date or ""
        deadline_time = hold.payment_deadline_time or ""
        deadline_label = (
            f"{deadline_date[4:6]}/{deadline_date[6:8]} {_hhmm(deadline_time)} (한국시간)"
            if len(deadline_date) == 8 and len(deadline_time) >= 4
            else "코레일 앱에서 확인하세요"
        )
        _ui_result(
            "reserved", route=_route(args), departure=_hhmm(found.departure_time),
            train=found.train_no, deadline=deadline_label, fare=str(hold.total_fare),
        )
        launch_alert({
            "route": _route(args), "departure": _hhmm(found.departure_time),
            "deadline": deadline_label,
        })
        notified = notify(
            f"✅ 예약 성공 · 결제 필요 | {args.dep}→{args.arr} {_hhmm(found.departure_time)}",
            f"⏰ 결제 마감: {deadline_label}\n"
            "지금 코레일 앱에서 예약 내역을 열고 결제하세요.\n"
            "현재 미결제 예약입니다. 기한 내 결제하지 않으면 자동 취소됩니다.\n\n"
            f"{_route(args)} 열차 {found.train_no}\n"
            f"{_hhmm(found.departure_time)} 출발 → {_hhmm(found.arrival_time)} 도착 · 성인 {args.adults}명\n"
            f"예약번호: {hold.pnr_no} · 금액: {hold.total_fare}원\n"
            "알림을 누르면 코레일 웹사이트가 열립니다.",
            priority=PRIORITY_URGENT,
            tags=["tada", "train"],
            click=KORAIL_URL,
        )
        if not notified:
            print("[알림 경고] 예약은 성공했지만 모바일 알림을 보내지 못했습니다. 코레일 앱에서 결제하세요.")
        return 0
    finally:
        try:
            client.logout()
        except KorailApiError:
            pass
        client.close()


if __name__ == "__main__":
    sys.exit(main())
