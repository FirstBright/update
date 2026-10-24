# Roadmap: from PC app to home server

Written 2026-10-25. Records where this project is going. The PC app stays the
working system until the server version is ready.

## What I want (final goal)

- A home **super server** running **Proxmox**.
- On it, an **Ubuntu VM** that hosts a **website with a local LLM**.
- A companion asks for a train ticket (on the website, in plain language).
- The server handles it. Several people can use it at the same time, so each
  request would run in its own **container**.
- Each person gets the result as an **alert on their own phone**.

Containers per person are complicated, so the **simpler target** is:
the server only **collects each person's request** (route, date, time window),
**watches for seats**, and **alerts that person's phone**. The person can then
book in the Korail app, or later the server can book for them.

## Now: the PC app is the fallback/bridge

This can't change yet, so today every person runs the app on their own PC:

- `코레일_실행.bat` installs, updates and runs the app.
- Korail ID/password are entered in the app and saved in `korail_credentials.txt`.
- **Phone alerts already work per person** through one shared **Telegram bot**:
  the person scans a QR code and presses Start, and their chat is saved on their
  PC. No typing, no extra app (Telegram uses normal phone push, so no extra
  battery). ntfy is an optional second channel.

## Already shaped for the server

These parts can be reused on the server without rewriting:

| Piece | How the server reuses it |
|---|---|
| `korail_reserve.py` | Container entrypoint as-is. Input: CLI args (`--dep --arr --date --time-from --time-to --adults --seat-class --poll-interval --max-wait [--live]`). Credentials: env `KORAIL_ID` / `KORAIL_PASSWORD` (never args). Output: one stdout line `KORAIL_RESULT:{json}` with `status` = `reserved` / `preview` / `timeout` / `no_trains`. Exit code 0 = success, 1 = failure. |
| `korail_notify.py` | `notify()` sends to Telegram (`TELEGRAM_CHAT_ID`) and/or ntfy. The server calls the same function. |
| Telegram bot + chat IDs | The server uses the **same bot token** and each person's saved chat ID, so phones need no new setup. The bot can also become the request channel (step 3). |

## Steps

1. **Done:** PC app with one launcher, login screen, and per-person phone alerts.
2. **Move the bot to the server:** the VM runs the Telegram bot itself
   (long polling, so no public port or domain is needed). PCs then stop reading
   bot updates.
3. **Simple server mode (the target above):** a person messages the bot or uses a
   small web form with route/date/time. The server watches for seats and replies
   in that person's Telegram chat. No booking, so no need to store their Korail
   password.
4. **Containers for booking:** for each request run
   `docker run --rm -e KORAIL_ID -e KORAIL_PASSWORD korail-reserve <args>`,
   read the `KORAIL_RESULT` line, and alert the person. Limit how many run at
   once.
5. **Local LLM front-end:** the LLM turns "내일 아침 9시쯤 익산 가는 표" into the
   same request fields as step 3/4. The LLM never sees passwords.

## Open questions / risks

- **Passwords on the server:** storing companions' Korail passwords centrally
  needs encryption and their consent. Step 3 avoids this entirely.
- **Korail limits:** many searches or logins from one home IP may get blocked.
  Keep poll intervals ≥ 10s and limit parallel jobs.
- **Device ID:** `KORAIL_DYNAPATH_DEVICE_ID` should be fixed per person, not
  random per container.
- **Payment:** a reservation holds the seat, but payment still happens in the
  Korail app before the deadline. Alerts must say that clearly.
- **Remote access:** Telegram needs none (the server polls Telegram). Only the
  website or a self-hosted ntfy would need port forwarding, Tailscale or a
  Cloudflare Tunnel.
- **Bot token is shared** in the zip: anyone with it can send as the bot. If it
  leaks, `/revoke` it in @BotFather and send a new `korail_bot.txt`.
