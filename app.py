import datetime
import io
import json
import secrets
import subprocess
import sys
import segno
import streamlit as st
import os
from korail_common import load_saved_credentials, load_setting, save_credentials, save_settings
from korail_notify import (
    DEFAULT_SERVER, find_telegram_chat, notify, telegram_api, telegram_link_code, telegram_start_link,
)
from korail_result_ui import show_result

env = os.environ.copy()
env["PYTHONIOENCODING"] = "utf-8"

st.set_page_config(page_title="코레일 자동 예매 제어판", layout="centered")

st.title("🚆 코레일 자동 예매 봇 제어판")

if "korail_id" not in st.session_state:
    _saved_id, _saved_password = load_saved_credentials()
    st.session_state["korail_id"] = _saved_id
    st.session_state["korail_password"] = _saved_password
    st.session_state["edit_credentials"] = not (_saved_id and _saved_password)

if st.session_state["edit_credentials"]:
    st.subheader("코레일 로그인 정보")
    if st.session_state.get("login_failed"):
        st.error("코레일 로그인에 실패했습니다. 아이디와 비밀번호를 다시 확인해주세요.")
    has_credentials = bool(st.session_state["korail_id"] and st.session_state["korail_password"])
    with st.form("credentials"):
        new_id = st.text_input(
            "코레일 아이디 (회원번호, 이메일 또는 휴대폰 번호)",
            value=st.session_state["korail_id"],
            autocomplete="username",
        )
        new_password = st.text_input("비밀번호", type="password", autocomplete="current-password")
        remember = st.checkbox("이 PC에 저장 (다음부터 다시 입력하지 않아도 됩니다)", value=True)
        submitted = st.form_submit_button("저장하고 계속", type="primary")
        cancelled = has_credentials and st.form_submit_button("취소")
    if cancelled:
        st.session_state["edit_credentials"] = False
        st.rerun()
    if submitted:
        new_id, new_password = new_id.strip(), new_password.strip()
        if not new_id or not new_password:
            st.error("아이디와 비밀번호를 모두 입력해주세요.")
            st.stop()
        if any(ch in new_id + new_password for ch in "\r\n"):
            st.error("아이디나 비밀번호에 줄바꿈을 넣을 수 없습니다.")
            st.stop()
        try:
            save_credentials(new_id, new_password if remember else None)
        except OSError as error:
            st.warning(f"계정 정보를 파일에 저장하지 못했습니다 ({error}). 이번 실행에서만 사용합니다.")
        st.session_state.update(
            korail_id=new_id, korail_password=new_password,
            edit_credentials=False, login_failed=False,
        )
        st.rerun()
    st.caption("저장을 선택하면 이 폴더의 korail_credentials.txt에 기록됩니다. 다른 사람과 공유하지 마세요.")
    st.stop()

_account_col, _change_col = st.columns([3, 1])
_member_id = st.session_state["korail_id"]
_account_col.caption(f"로그인 계정: {_member_id[:3] + '*' * max(len(_member_id) - 3, 0)}")
if _change_col.button("계정 변경", use_container_width=True):
    st.session_state["edit_credentials"] = True
    st.rerun()

def _qr_png(url: str) -> bytes:
    buffer = io.BytesIO()
    segno.make(url).save(buffer, kind="png", scale=5)
    return buffer.getvalue()


_telegram_ready = bool(load_setting("TELEGRAM_BOT_TOKEN"))
_telegram_chat = load_setting("TELEGRAM_CHAT_ID")
_ntfy_topic = load_setting("NTFY_TOPIC")
_alert_ready = bool(_telegram_chat or _ntfy_topic)
with st.expander(
    "📱 휴대폰 알림 (연결됨)" if _alert_ready else "📱 휴대폰 알림 설정 · 예약되면 휴대폰으로 알려줍니다",
    expanded=not _alert_ready and _telegram_ready,
):
    st.markdown("**텔레그램**")
    if _telegram_chat:
        st.success("텔레그램이 연결되어 있습니다.")
        if st.button("텔레그램 연결 해제"):
            save_settings({"TELEGRAM_CHAT_ID": None})
            st.rerun()
    elif not _telegram_ready:
        st.info("텔레그램 알림을 쓰려면 관리자에게 받은 korail_bot.txt 파일을 이 폴더에 넣어주세요.")
    else:
        if "telegram_link" not in st.session_state:
            st.session_state["telegram_code"] = telegram_link_code()
            try:
                st.session_state["telegram_link"] = telegram_start_link(st.session_state["telegram_code"])
            except Exception as error:
                st.session_state["telegram_link"] = None
                st.error(f"텔레그램에 연결하지 못했습니다: {error}")
        _link = st.session_state["telegram_link"]
        if _link:
            _qr_col, _steps_col = st.columns([1, 2])
            _qr_col.image(_qr_png(_link))
            _steps_col.markdown(
                "1. 휴대폰 카메라로 왼쪽 QR 코드를 찍습니다.\n"
                "2. 텔레그램이 열리면 아래쪽 **시작(Start)** 을 누릅니다.\n"
                "3. 이 화면에서 **연결 확인** 을 누릅니다."
            )
            _steps_col.link_button("PC에서 텔레그램 열기", _link)
            if _steps_col.button("연결 확인", type="primary"):
                try:
                    _chat = find_telegram_chat(st.session_state["telegram_code"])
                except Exception as error:
                    _steps_col.error(f"확인하지 못했습니다: {error}")
                    _chat = None
                if _chat is not None:
                    save_settings({"TELEGRAM_CHAT_ID": str(_chat)})
                    try:
                        telegram_api("sendMessage", {"chat_id": _chat, "text": "✅ 코레일 자동예매 알림이 연결되었습니다."})
                    except Exception:
                        pass
                    st.session_state.pop("telegram_link")
                    st.rerun()
                else:
                    _steps_col.warning("아직 확인되지 않았습니다. 텔레그램에서 '시작'을 눌렀는지 확인한 뒤 다시 눌러주세요.")

    st.markdown("**ntfy 앱 (선택)**")
    if _ntfy_topic:
        _ntfy_url = f"{(load_setting('NTFY_SERVER') or DEFAULT_SERVER).rstrip('/')}/{_ntfy_topic}"
        _qr_col, _steps_col = st.columns([1, 2])
        _qr_col.image(_qr_png(_ntfy_url))
        _steps_col.markdown("ntfy 앱에서 QR 코드를 찍거나 **+** 를 눌러 아래 토픽을 구독합니다.")
        _steps_col.code(_ntfy_topic, language=None)
        if _steps_col.button("ntfy 사용 안 함"):
            save_settings({"NTFY_TOPIC": None})
            st.rerun()
    elif st.button("ntfy 앱으로도 받기"):
        # Random topic: anyone who knows the name can read it.
        save_settings({"NTFY_TOPIC": f"korail-{secrets.token_hex(8)}"})
        st.rerun()

    if _alert_ready and st.button("테스트 알림 보내기"):
        if notify("🧪 알림 테스트 · 실제 예약 아님", "알림이 정상적으로 도착했습니다.", tags=["test_tube"]):
            st.success("보냈습니다. 휴대폰을 확인해주세요.")
        else:
            st.error("알림을 보내지 못했습니다. 인터넷 연결을 확인해주세요.")

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

    # Credentials go through the environment, never the command line.
    run_env = {
        **env,
        "KORAIL_ID": st.session_state["korail_id"],
        "KORAIL_PASSWORD": st.session_state["korail_password"],
    }
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        errors='replace',
        env=run_env
    )

    output_area = st.empty()
    login_failed = False
    for line in process.stdout:
        if line.startswith("Login failed"):
            login_failed = True
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
    if login_failed:
        st.session_state.update(login_failed=True, edit_credentials=True)
        st.rerun()
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
