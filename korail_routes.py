"""Rank direct/transfer KORAIL itineraries by schedule fit, train speed, and total travel time.

Used by the route-picker section of app.py: given a departure/arrival station pair and a
date, search direct trains first and fall back to one-transfer itineraries only when no
direct train exists (same behavior as the KORAIL app), then rank the results.
"""

from __future__ import annotations

from dataclasses import dataclass

from korail_mobile_api import (
    KorailClient,
    KorailNoDirectTrainError,
    TrainSearchQuery,
)

# Observed train_class_name values for fast trains; anything else (무궁화호, ITX-새마을, ...)
# is treated as slow and penalized.
FAST_TRAIN_CLASSES = {"KTX", "KTX-산천", "SRT"}

# Reservation codes (h_gen_rsv_cd / h_spe_rsv_cd): "11" plenty, "12" limited/mixed, "13" 매진
# (sold out). Same convention app.py already uses for --allowed-codes.
RESERVABLE_CODES = {"11", "12"}

TARGET_DEPARTURE = "090000"
TARGET_ARRIVAL = "180000"

# Equivalent-minutes penalty for a leg that isn't KTX/SRT. Chosen so that one slow leg
# outweighs a schedule that's merely "close" to the target times, but a same-length detour
# to catch a fast train is still preferred over a much longer ride at a nicer hour.
SLOW_TRAIN_PENALTY_MINUTES = 60

# Weighing duration and time-of-day fit equally would let them cancel out: for any
# itinerary that departs after TARGET_DEPARTURE and arrives before TARGET_ARRIVAL,
# time_fit == (TARGET_ARRIVAL - TARGET_DEPARTURE) - duration_minutes, so a 1:1 sum is a
# constant and duration silently stops affecting the ranking in exactly the common case.
# DURATION_WEIGHT > TIME_FIT_WEIGHT keeps shorter trips winning even inside that window.
DURATION_WEIGHT = 2.0
TIME_FIT_WEIGHT = 1.0


@dataclass(frozen=True)
class Leg:
    train_no: str
    train_class_name: str | None
    departure_station_name: str | None
    arrival_station_name: str | None
    departure_time: str
    arrival_time: str
    general_reservation_code: str | None = None
    special_reservation_code: str | None = None


@dataclass(frozen=True)
class Itinerary:
    legs: tuple[Leg, ...]

    @property
    def is_direct(self) -> bool:
        return len(self.legs) == 1

    @property
    def departure_time(self) -> str:
        return self.legs[0].departure_time

    @property
    def arrival_time(self) -> str:
        return self.legs[-1].arrival_time

    @property
    def duration_minutes(self) -> int:
        return _minutes_between(self.departure_time, self.arrival_time)

    @property
    def train_classes(self) -> tuple[str, ...]:
        return tuple(leg.train_class_name or "" for leg in self.legs)

    def is_reservable(self, seat_class: str = "general") -> bool:
        """Whether every leg currently has a bookable (non-매진) seat in this class."""
        attr = "general_reservation_code" if seat_class == "general" else "special_reservation_code"
        return all(getattr(leg, attr) in RESERVABLE_CODES for leg in self.legs)


def _minutes(hhmmss: str) -> int:
    return int(hhmmss[0:2]) * 60 + int(hhmmss[2:4])


def _minutes_between(dep: str, arr: str) -> int:
    start, end = _minutes(dep), _minutes(arr)
    if end < start:
        end += 24 * 60
    return end - start


def _leg_from_summary(train) -> Leg:
    return Leg(
        train_no=train.train_no,
        train_class_name=train.train_class_name,
        departure_station_name=train.departure_station_name,
        arrival_station_name=train.arrival_station_name,
        departure_time=train.departure_time,
        arrival_time=train.arrival_time,
        general_reservation_code=train.general_reservation_code,
        special_reservation_code=train.special_reservation_code,
    )


def _collect_direct(client: KorailClient, query: TrainSearchQuery) -> list[Itinerary]:
    itineraries: list[Itinerary] = []
    page = client.search_trains(query)
    while True:
        itineraries.extend(Itinerary(legs=(_leg_from_summary(t),)) for t in page.trains)
        cont = page.next_page()
        if cont is None:
            return itineraries
        page = client.search_trains(query, continuation=cont)


def _collect_transfer(client: KorailClient, query: TrainSearchQuery) -> list[Itinerary]:
    itineraries: list[Itinerary] = []
    page = client.search_transfer_trains(query)
    while True:
        itineraries.extend(
            Itinerary(legs=(_leg_from_summary(it.first), _leg_from_summary(it.second)))
            for it in page.itineraries
        )
        cont = page.next_page()
        if cont is None:
            return itineraries
        page = client.search_transfer_trains(query, continuation=cont)


def find_itineraries(
    client: KorailClient,
    dep: str,
    arr: str,
    date: str,
    earliest_departure: str = "000000",
) -> list[Itinerary]:
    """Direct trains for dep/arr/date, or transfer itineraries if none exist."""
    query = TrainSearchQuery(dep, arr, date, departure_time=earliest_departure, include_srt=True)
    try:
        return _collect_direct(client, query)
    except KorailNoDirectTrainError:
        return _collect_transfer(client, query)


def _ramp_penalty(value: int, best: int, soft_cap: int, early_weight: float, steep_weight: float) -> float:
    """Asymmetric 0..100..steep penalty used by both departure_penalty and arrival_penalty.

    0 at/before ``best``; ramps 0->100 across (best, soft_cap]; beyond soft_cap, 100 plus a
    much steeper per-minute penalty. ``early_weight`` applies a small penalty *before*
    ``best`` so an unnecessarily early time doesn't tie with one right at the target.
    """
    if value <= best:
        return (best - value) * early_weight
    if value <= soft_cap:
        return (value - best) / (soft_cap - best) * 100
    return 100 + (value - soft_cap) * steep_weight


def departure_penalty(departure_time: str) -> float:
    """0 at/before 09:00, worst-tolerable (100) at 10:00, steep beyond 10:00."""
    return _ramp_penalty(
        _minutes(departure_time), _minutes(TARGET_DEPARTURE), _minutes("100000"),
        early_weight=0.2, steep_weight=5.0,
    )


def arrival_penalty(arrival_time: str) -> float:
    """0 across 17:00-18:00 (best zone), worst-tolerable (100) at 19:00, steep beyond 19:00."""
    minutes = _minutes(arrival_time)
    best_early = _minutes("170000")
    if minutes < best_early:
        return (best_early - minutes) * 0.2
    return _ramp_penalty(minutes, _minutes(TARGET_ARRIVAL), _minutes("190000"), early_weight=0.0, steep_weight=5.0)


def _slow_leg_penalty(itinerary: Itinerary) -> float:
    return sum(0 if cls in FAST_TRAIN_CLASSES else SLOW_TRAIN_PENALTY_MINUTES for cls in itinerary.train_classes)


def outbound_score(itinerary: Itinerary) -> float:
    """Lower is better. For the home->destination leg: departure-time fit matters, not arrival."""
    return (
        TIME_FIT_WEIGHT * departure_penalty(itinerary.departure_time)
        + DURATION_WEIGHT * itinerary.duration_minutes
        + _slow_leg_penalty(itinerary)
    )


def return_score(itinerary: Itinerary) -> float:
    """Lower is better. For the destination->home leg: arrival-time fit matters, not departure."""
    return (
        TIME_FIT_WEIGHT * arrival_penalty(itinerary.arrival_time)
        + DURATION_WEIGHT * itinerary.duration_minutes
        + _slow_leg_penalty(itinerary)
    )


def _rank(
    itineraries: list[Itinerary],
    key,
    seat_class: str,
    top_n: int,
) -> list[Itinerary]:
    # Reservable itineraries always outrank sold-out ones; only the time/duration/speed
    # score, given by `key`, breaks ties within each group.
    return sorted(itineraries, key=lambda it: (not it.is_reservable(seat_class), key(it)))[:top_n]


def best_outbound(
    client: KorailClient,
    home: str,
    destination: str,
    date: str,
    seat_class: str = "general",
    top_n: int = 3,
) -> list[Itinerary]:
    """Best home->destination trains for a morning departure (target 09:00, max 10:00)."""
    itineraries = find_itineraries(client, home, destination, date)
    return _rank(itineraries, outbound_score, seat_class, top_n)


def best_return(
    client: KorailClient,
    destination: str,
    home: str,
    date: str,
    seat_class: str = "general",
    top_n: int = 3,
) -> list[Itinerary]:
    """Best destination->home trains for an evening arrival (target 17:00-18:00, max 19:00)."""
    itineraries = find_itineraries(client, destination, home, date)
    return _rank(itineraries, return_score, seat_class, top_n)
