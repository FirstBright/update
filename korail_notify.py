"""
Push notifications to your phone via ntfy (https://ntfy.sh).

Settings (env var or korail_credentials.txt):
    NTFY_TOPIC   required — the topic you subscribed to in the ntfy app.
                 Anyone who knows the name can read it, so make it long/random.
    NTFY_SERVER  optional — default https://ntfy.sh (set if you self-host)
    NTFY_TOKEN   optional — access token, only for protected topics/servers

If NTFY_TOPIC is unset, notify() does nothing, so the scripts work as before.
A failed notification only prints a warning; it never stops a reservation.

Send a test message:
    python korail_notify.py --test
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
import urllib.request

from korail_common import load_setting

DEFAULT_SERVER = "https://ntfy.sh"
TIMEOUT_SECONDS = 10

# ntfy priorities: 1=min, 2=low, 3=default, 4=high, 5=urgent
PRIORITY_DEFAULT = 3
PRIORITY_HIGH = 4
PRIORITY_URGENT = 5


def notify(
    title: str,
    message: str,
    priority: int = PRIORITY_DEFAULT,
    tags: list[str] | None = None,
    click: str | None = None,
) -> bool:
    """Send one push. Returns True on success, False if skipped or failed."""
    topic = load_setting("NTFY_TOPIC")
    if not topic:
        return False
    server = (load_setting("NTFY_SERVER") or DEFAULT_SERVER).rstrip("/")

    # JSON publishing (POST to the server root) instead of Title:/Tags: headers,
    # because HTTP headers can't carry Korean text without extra encoding.
    payload = {"topic": topic, "title": title, "message": message, "priority": priority}
    if tags:
        payload["tags"] = tags
    if click:
        payload["click"] = click

    headers = {"Content-Type": "application/json; charset=utf-8"}
    token = load_setting("NTFY_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(
        server,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            response.read()
        return True
    except Exception as exc:  # never let a notification break the caller
        print(f"[알림 경고] ntfy 전송 실패: {exc}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="ntfy notification helper")
    parser.add_argument("--test", action="store_true", help="Send a test notification")
    args = parser.parse_args()
    if not args.test:
        parser.print_help()
        return 0

    topic = load_setting("NTFY_TOPIC")
    if not topic:
        suggestion = f"korail-{secrets.token_hex(8)}"
        print("NTFY_TOPIC이 설정되지 않았습니다.")
        print("korail_credentials.txt에 아래 한 줄을 추가하고, ntfy 앱에서 같은 토픽을 구독하세요:")
        print(f"    NTFY_TOPIC={suggestion}")
        return 1

    ok = notify("🧪 알림 테스트 · 실제 예약 아님", "알림이 정상적으로 도착했습니다. 열차를 예약한 것은 아닙니다.", tags=["test_tube"])
    print(f"토픽 '{topic}'(으)로 테스트 알림 전송 " + ("성공" if ok else "실패"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
