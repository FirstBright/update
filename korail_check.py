"""
Quick health-check script for yakisoba0728/korail-mobile-api.

Usage:
    python korail_check.py --id 01012345678
    (password is prompted securely; never pass it as a CLI arg)

What it does:
    1. Logs in to KORAIL with the given credentials.
    2. Runs a harmless read-only train search to confirm the API still responds.
    3. Logs out and reports a clear pass/fail result.

No reservation, payment, or cancellation calls are ever made.
"""

from __future__ import annotations

import argparse
import datetime
import sys

from korail_common import build_client_config, load_credentials
from korail_mobile_api import (
    KorailAuthContinuationRequired,
    KorailAuthError,
    KorailClient,
    KorailDynaPathRequiredError,
    KorailApiError,
    TrainSearchQuery,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check that korail-mobile-api still works.")
    parser.add_argument(
        "--id",
        default=None,
        help="KORAIL membership number, email, or phone (default: from korail_credentials.txt)",
    )
    parser.add_argument("--dep", default="동탄", help="Departure station name or code (default: 동탄)")
    parser.add_argument("--arr", default="동대구", help="Arrival station name or code (default: 동대구)")
    parser.add_argument(
        "--date",
        default=(datetime.date.today() + datetime.timedelta(days=1)).strftime("%Y%m%d"),
        help="Search date YYYYMMDD (default: tomorrow)",
    )
    parser.add_argument(
        "--no-dynapath",
        dest="dynapath",
        action="store_false",
        help="Disable the anti-automation DynaPath token (on by default; KORAIL currently requires it)",
    )
    parser.set_defaults(dynapath=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    member_id, password = load_credentials(args.id)

    client = KorailClient(build_client_config(enable_dynapath=args.dynapath))
    try:
        try:
            client.login(member_id, password)
        except KorailAuthContinuationRequired as exc:
            print("Login requires additional web-based verification (2FA/CAPTCHA-style step).")
            print(f"Redirect URL: {exc.redirect_url}")
            print("This library does not automate that step; the check cannot proceed.")
            return 2
        except KorailDynaPathRequiredError:
            print("Server demanded a DynaPath anti-automation token.")
            print("Re-run with --dynapath to enable it.")
            return 2
        except KorailAuthError as exc:
            print(f"Login failed: {exc}")
            print("This usually means wrong ID/password, or KORAIL changed its auth flow.")
            return 1

        print("Login succeeded.")

        query = TrainSearchQuery(args.dep, args.arr, args.date)
        try:
            result = client.search_trains(query)
        except KorailApiError as exc:
            print(f"Login worked, but the train-search call failed: {exc}")
            print("The API surface may have changed even though auth still works.")
            return 1

        trains = result.trains
        if not trains:
            print("Search call succeeded but returned no trains (may just be no service that day).")
        else:
            print(f"Search call succeeded, showing up to 5 of {len(result.trains)} result(s):")
            for train in trains:
                gen_status = train.raw.get("h_gen_rsv_nm", "정보없음")      # 일반실 상태 (좌석많음, 매진 등)
                spe_status = train.raw.get("h_spe_rsv_nm", "정보없음")      # 특실 상태
                stnd_status = train.raw.get("h_stnd_rsv_nm", "정보없음")    # 입석 상태
                free_status = train.raw.get("h_free_rsv_nm", "정보없음")    # 자유석 상태
                wait_cnt = train.raw.get("h_rsv_wait_ps_cnt", "0")          # 예약대기 대기인원
                
                price_info = train.general_availability_name.replace("\n", " ")
                
                print(f"  [{train.departure_time[:2]}:{train.departure_time[2:4]}] 열차 {train.train_no} | 가격: {price_info}")
                print(f"    └ 일반: {gen_status} | 특실: {spe_status} | 입석: {stnd_status} | 자유석: {free_status} | 예약대기: {int(wait_cnt)}명")
        print("\nResult: korail-mobile-api appears to still work end-to-end.")
        return 0
    finally:
        try:
            client.logout()
        except KorailApiError:
            pass
        client.close()


if __name__ == "__main__":
    sys.exit(main())
