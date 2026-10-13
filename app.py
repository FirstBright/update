import datetime
import json
import subprocess
import sys
import streamlit as st
import os
from korail_result_ui import show_result

env = os.environ.copy()
env["PYTHONIOENCODING"] = "utf-8"

st.set_page_config(page_title="코레일 자동 예매 제어판", layout="centered")

st.title("🚆 코레일 자동 예매 봇 제어판")

QUICK_DESTINATIONS = ["익산", "순천"]
station_options = ["동탄", "익산", "나주","서울",  "동대구", "부산",  "대전", "수서", "광주송정"]
for _station in QUICK_DESTINATIONS:
    if _station not in station_options:
        station_options.append(_station)
CUSTOM_OPTION = "직접입력"

if "arr_select" not in st.session_state:
    st.session_state["arr_select"] = station_options[1]


st.subheader("1. 여정 정보")

st.caption("빠른 목적지 선택 (도착지에 반영됩니다)")
quick_cols = st.columns(len(QUICK_DESTINATIONS))
for col, station in zip(quick_cols, QUICK_DESTINATIONS):
    if col.button(station, use_container_width=True):
        st.session_state["arr_select"] = station

col1, col2 = st.columns(2)
with col1:
    dep_choice = st.selectbox("출발역", options=station_options + [CUSTOM_OPTION], index=0)
    dep = st.text_input("출발지 직접 입력", value="") if dep_choice == CUSTOM_OPTION else dep_choice
with col2:
    arr_choice = st.selectbox(
        "도착역", options=station_options + [CUSTOM_OPTION], index=None, key="arr_select"
    )
    arr = st.text_input("도착지 직접 입력", value="") if arr_choice == CUSTOM_OPTION else arr_choice

travel_date = st.date_input("탑승일", value=datetime.date.today() + datetime.timedelta(days=1))
reserve_dep, reserve_arr = dep, arr
reserve_date_str = travel_date.strftime("%Y%m%d")

st.subheader("2. 기차 출발 시간 범위")
st.caption("선택한 탑승일에 이 시간 사이에 출발하는 열차를 찾습니다. 시간은 24시간 기준입니다.")
time_options = [f"{hour:02d}:{minute:02d}" for hour in range(24) for minute in (0, 30)]
time_left, time_right = st.columns(2)
with time_left:
    departure_from = st.selectbox("출발 시간 (부터)", options=time_options, index=6 * 2)
with time_right:
    departure_to = st.selectbox("출발 시간 (까지)", options=time_options, index=10 * 2)
time_from_str = departure_from.replace(":", "") + "00"
time_to_str = departure_to.replace(":", "") + "00"
invalid_time_range = departure_from > departure_to
if invalid_time_range:
    st.error("출발 시간 범위를 확인해주세요. '까지' 시간을 '부터' 시간과 같거나 이후로 선택해주세요.")
else:
    st.info(f"{travel_date:%Y년 %m월 %d일} {departure_from}~{departure_to}에 출발하는 열차를 찾습니다.")
st.caption("예: 09:00~12:00 설정 → 오전 9시부터 낮 12시까지 출발하는 열차가 대상입니다. 도착 시간이나 프로그램 실행 시간이 아닙니다.")

# 성인 인원 선택 추가
adults_count = st.number_input("성인 승객 수", min_value=1, max_value=9, value=1, step=1)

seat_class = st.selectbox(
    "좌석 등급",
    options=["general", "special"],
    format_func=lambda x: "일반실" if x=="general" else "특실"
)

st.subheader("3. 실행 설정")
poll_interval = st.slider("좌석 확인 간격 (초)", min_value=5, max_value=60, value=10)
max_wait_minutes = st.number_input(
    "좌석을 기다릴 최대 시간 (분)",
    min_value=30, max_value=1440, value=30, step=30,
)
st.caption(f"시작 버튼을 누른 뒤 최대 {max_wait_minutes}분 동안 좌석을 찾고, 예약되거나 시간이 지나면 종료합니다.")
live_mode = st.checkbox("실제 예매 실행", value=False)
shutdown_after = st.checkbox(
    "💤 끝나면 PC 끄기 (예약 성공 / 대기시간 초과 / 오류 시 5분 뒤 종료, 실제 예매 모드에서만)",
    value=False,
    disabled=not live_mode,
)
if shutdown_after and live_mode:
    st.caption("종료를 취소하려면 PC에서 Win+R → `shutdown /a` 입력")

if st.button("모니터링 및 자동 예매 시작", type="primary", disabled=invalid_time_range):
    if not dep.strip() or not arr.strip() or dep.strip() == arr.strip():
        st.error("서로 다른 출발역과 도착역을 입력해주세요.")
        st.stop()
    st.session_state.pop("reservation_result", None)
    st.session_state["reservation_logs"] = ""
    st.success(f"좌석 확인을 시작했습니다. 최대 {max_wait_minutes}분 동안 기다립니다. (성인 {adults_count}명)")

    cmd = [
        sys.executable, "-u", "korail_reserve.py",
        "--dep", reserve_dep,
        "--arr", reserve_arr,
        "--date", reserve_date_str,
        "--time-from", time_from_str,
        "--time-to", time_to_str,
        "--adults", str(adults_count),
        "--seat-class", seat_class,
        "--poll-interval", str(poll_interval),
        "--max-wait", str(max_wait_minutes),
        "--allowed-codes", "11",
    ]

    if live_mode:
        cmd.append("--live")
        if shutdown_after:
            cmd.append("--shutdown-after")

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        errors='replace',
        env=env
    )

    output_area = st.empty()
    for line in process.stdout:
        if line.startswith("KORAIL_RESULT:"):
            try:
                result = json.loads(line.removeprefix("KORAIL_RESULT:"))
                if result.get("status") in {"reserved", "preview", "timeout", "no_trains"}:
                    st.session_state["reservation_result"] = result
            except (json.JSONDecodeError, AttributeError):
                pass
            continue
        st.session_state["reservation_logs"] += line
        output_area.code(st.session_state["reservation_logs"])
    return_code = process.wait()
    output_area.empty()
    if "reservation_result" not in st.session_state:
        st.session_state["reservation_result"] = {
            "status": "error",
            "route": f"{reserve_dep} → {reserve_arr} ({reserve_date_str})",
        }

if st.session_state.get("reservation_logs"):
    st.subheader("실행 로그")
    st.caption("결과 창을 닫아도 로그는 유지됩니다. 새 실행을 시작하면 초기화됩니다.")
    st.code(st.session_state["reservation_logs"], language="text")

if "reservation_result" in st.session_state:
    show_result(st.session_state["reservation_result"])
