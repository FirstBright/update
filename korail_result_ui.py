"""Persistent browser result dialog, separate from the polling log."""

from html import escape

import streamlit as st


@st.dialog("코레일 실행 결과", width="large", dismissible=False)
def show_result(result: dict) -> None:
    status = result["status"]
    title, subtitle, color = {
        "reserved": ("✅ 예약 성공", "지금 코레일 앱에서 결제하세요", "#087443"),
        "preview": ("🧪 테스트 완료", "좌석 발견 · 실제 예약은 하지 않았습니다", "#1757a6"),
        "timeout": ("⌛ 예약 못 잡음", "대기 시간이 끝났습니다", "#765000"),
        "no_trains": ("🚆 해당 시간에 열차 없음", "날짜나 출발 시간 범위를 변경해주세요", "#765000"),
        "error": ("⚠️ 실행 중단", "코레일 앱에서 예약 내역을 확인하세요", "#a92b22"),
    }[status]
    route = escape(str(result.get("route", "")))
    departure = escape(str(result.get("departure", "")))
    details = ""
    if status == "reserved":
        deadline = escape(str(result.get("deadline", "앱에서 확인")))
        fare = escape(str(result.get("fare", "")))
        details = (
            f'<p style="font-size:clamp(24px,3vw,40px);font-weight:800">결제 마감: {deadline}</p>'
            f'<p style="font-size:24px">금액: {fare}원 · 아직 결제되지 않았습니다</p>'
            '<p>기한 내 미결제 시 자동 취소됩니다.</p>'
        )
    st.html(
        f'<section role="alert" style="background:{color};color:white;text-align:center;'
        'padding:48px 24px;border-radius:20px;min-height:40vh;display:flex;'
        'flex-direction:column;justify-content:center">'
        f'<div style="font-size:clamp(48px,7vw,96px);font-weight:900;line-height:1.2">{title}</div>'
        f'<p style="font-size:clamp(24px,3vw,42px);font-weight:700">{subtitle}</p>'
        f'<p style="font-size:28px">{route} {departure}</p>{details}</section>'
    )
    if status == "reserved":
        st.caption("이 창은 확인 버튼을 누를 때까지 유지됩니다. 결제 완료 여부는 코레일 앱에서 확인하세요.")
    if status == "no_trains":
        st.caption("선택한 시간 범위에 출발하는 직통 열차가 없어 모니터링을 종료했습니다.")
    if st.button("확인 · 결과 창 닫기", type="primary", use_container_width=True):
        st.session_state.pop("reservation_result", None)
        st.rerun()
