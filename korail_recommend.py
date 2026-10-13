"""
Print the top-N ranked itineraries for one leg of a day-trip (outbound: home->destination,
scored for a ~09:00 departure; return: destination->home, scored for a ~17:00-18:00 arrival),
as JSON on stdout. Direct trains, or one-transfer itineraries if no direct train exists.
Read-only -- no reservation, payment, or cancellation calls are made.

Used by app.py's route-picker section (invoked as a subprocess, same pattern as
korail_reserve.py), but also runnable standalone:

    python korail_recommend.py --home 동탄 --destination 순천 --leg outbound --date 20261010
    python korail_recommend.py --home 동탄 --destination 순천 --leg return --date 20261010
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys

from korail_common import build_client_config, load_credentials
from korail_mobile_api import KorailApiError, KorailAuthError, KorailClient
from korail_routes import best_outbound, best_return, outbound_score, return_score


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rank one leg of a KORAIL day-trip for a route/date.")
    parser.add_argument("--id", default=None, help="KORAIL id (default: from korail_credentials.txt)")
    parser.add_argument("--home", required=True, help="Home station name or code")
    parser.add_argument("--destination", required=True, help="Destination station name or code")
    parser.add_argument(
        "--leg",
        choices=["outbound", "return"],
        required=True,
        help="outbound = home->destination (~09:00 departure); return = destination->home (~17-18:00 arrival)",
    )
    parser.add_argument(
        "--date",
        default=(datetime.date.today() + datetime.timedelta(days=1)).strftime("%Y%m%d"),
        help="Travel date, YYYYMMDD (default: tomorrow)",
    )
    parser.add_argument(
        "--seat-class", choices=["general", "special"], default="general", help="Seat class to check availability for"
    )
    parser.add_argument("--top-n", type=int, default=3, help="How many ranked options to return (default: 3)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    member_id, password = load_credentials(args.id)

    client = KorailClient(build_client_config())
    try:
        try:
            client.login(member_id, password)
        except KorailAuthError as exc:
            print(json.dumps({"error": f"login failed: {exc}"}))
            return 1

        try:
            if args.leg == "outbound":
                options = best_outbound(client, args.home, args.destination, args.date, args.seat_class, args.top_n)
                leg_score = outbound_score
            else:
                options = best_return(client, args.destination, args.home, args.date, args.seat_class, args.top_n)
                leg_score = return_score
        except KorailApiError as exc:
            print(json.dumps({"error": f"search failed: {exc}"}))
            return 1

        payload = [
            {
                "score": leg_score(it),
                "is_reservable": it.is_reservable(args.seat_class),
                "is_direct": it.is_direct,
                "departure_time": it.departure_time,
                "arrival_time": it.arrival_time,
                "duration_minutes": it.duration_minutes,
                "legs": [
                    {
                        "train_no": leg.train_no,
                        "train_class_name": leg.train_class_name,
                        "departure_station_name": leg.departure_station_name,
                        "arrival_station_name": leg.arrival_station_name,
                        "departure_time": leg.departure_time,
                        "arrival_time": leg.arrival_time,
                    }
                    for leg in it.legs
                ],
            }
            for it in options
        ]
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    finally:
        try:
            client.logout()
        except KorailApiError:
            pass
        client.close()


if __name__ == "__main__":
    sys.exit(main())
