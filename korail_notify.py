"""
Push notifications to your phone via Telegram and/or ntfy (https://ntfy.sh).

Settings (env var, korail_credentials.txt, or the shared korail_bot.txt):
    TELEGRAM_BOT_TOKEN  the maintainer's bot (shared korail_bot.txt, never in git)
    TELEGRAM_CHAT_ID    this person's chat; saved when they press Start in the bot
    NTFY_TOPIC   optional — the topic you subscribed to in the ntfy app.
                 Anyone who knows the name can read it, so make it long/random.
    NTFY_SERVER  optional — default https://ntfy.sh (set if you self-host)
    NTFY_TOKEN   optional — access token, only for protected topics/servers

Whatever is not configured is skipped, so the scripts work without any of it.
A failed notification only prints a warning; it never stops a reservation.

Send a test message:
    python korail_notify.py --test
"""

from __future__ import annotations

import argparse
import json
import secrets
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

import certifi

from korail_common import load_setting

DEFAULT_SERVER = "https://ntfy.sh"
TELEGRAM_API = "https://api.telegram.org"
TIMEOUT_SECONDS = 10

# Windows adds some root certificates to its store only when a Windows program
# first needs them, so Python may not see e.g. Telegram's GoDaddy root yet
# ("self-signed certificate in certificate chain"). Trust certifi's roots as well.
SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.load_verify_locations(certifi.where())

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
    """Send one push to every configured channel. True if at least one succeeded."""
    sent_telegram = _notify_telegram(title, message, click)
    sent_ntfy = _notify_ntfy(title, message, priority, tags, click)
    return sent_telegram or sent_ntfy


def _notify_telegram(title: str, message: str, click: str | None) -> bool:
    chat_id = load_setting("TELEGRAM_CHAT_ID")
    if not chat_id or not load_setting("TELEGRAM_BOT_TOKEN"):
        return False
    text = f"{title}\n\n{message}" + (f"\n\n{click}" if click else "")
    try:
        telegram_api("sendMessage", {"chat_id": chat_id, "text": text})
        return True
    except Exception as exc:  # never let a notification break the caller
        print(f"[알림 경고] 텔레그램 전송 실패: {exc}")
        return False


def _notify_ntfy(
    title: str, message: str, priority: int, tags: list[str] | None, click: str | None,
) -> bool:
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
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS, context=SSL_CONTEXT) as response:
            response.read()
        return True
    except Exception as exc:  # never let a notification break the caller
        print(f"[알림 경고] ntfy 전송 실패: {exc}")
        return False


def telegram_api(method: str, params: dict) -> object:
    """Call the Telegram Bot API and return its `result`; raises on any failure."""
    token = load_setting("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN이 설정되지 않았습니다.")
    request = urllib.request.Request(
        f"{TELEGRAM_API}/bot{token}/{method}",
        data=json.dumps(params, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS, context=SSL_CONTEXT) as response:
            body = json.loads(response.read())
    except urllib.error.HTTPError as error:
        # Don't let the token-bearing URL end up in logs.
        raise RuntimeError(f"Telegram HTTP {error.code}") from None
    except urllib.error.URLError as error:
        raise RuntimeError(f"Telegram 연결 실패: {error.reason}") from None
    if not body.get("ok"):
        raise RuntimeError(body.get("description", "Telegram error"))
    return body["result"]


def telegram_link_code() -> str:
    """A one-time code the person sends to the bot via the Start button."""
    return secrets.token_urlsafe(9)


def telegram_start_link(code: str) -> str:
    username = telegram_api("getMe", {})["username"]
    return f"https://t.me/{username}?start={urllib.parse.quote(code)}"


def find_telegram_chat(code: str) -> int | None:
    """Return the chat that sent "/start <code>", if it arrived in the last 24h.

    Updates are read without confirming them, so other PCs sharing the bot can
    still find their own codes.
    """
    for update in telegram_api("getUpdates", {"limit": 100, "allowed_updates": ["message"]}):
        message = update.get("message") or {}
        if message.get("text", "").split() == ["/start", code]:
            return message["chat"]["id"]
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Phone notification helper")
    parser.add_argument("--test", action="store_true", help="Send a test notification")
    args = parser.parse_args()
    if not args.test:
        parser.print_help()
        return 0

    if not load_setting("TELEGRAM_CHAT_ID") and not load_setting("NTFY_TOPIC"):
        print("알림이 설정되지 않았습니다. 앱 화면의 '휴대폰 알림 설정'에서 텔레그램을 연결하세요.")
        return 1

    ok = notify("🧪 알림 테스트 · 실제 예약 아님", "알림이 정상적으로 도착했습니다. 열차를 예약한 것은 아닙니다.", tags=["test_tube"])
    print("테스트 알림 전송 " + ("성공" if ok else "실패"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
