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
- **Phone alerts already work per person**: the app creates a random ntfy topic
  for each PC and shows a QR code. The person subscribes to it in the ntfy app.

## Already shaped for the server

These parts can be reused on the server without rewriting:

| Piece | How the server reuses it |
|---|---|
| `korail_reserve.py` | Container entrypoint as-is. Input: CLI args (`--dep --arr --date --time-from --time-to --adults --seat-class --poll-interval --max-wait [--live]`). Credentials: env `KORAIL_ID` / `KORAIL_PASSWORD` (never args). Output: one stdout line `KORAIL_RESULT:{json}` with `status` = `reserved` / `preview` / `timeout` / `no_trains`. Exit code 0 = success, 1 = failure. |
| `korail_notify.py` | Sends to `NTFY_SERVER` + `NTFY_TOPIC`. Self-host ntfy on the VM and change only `NTFY_SERVER`. |
| Per-person ntfy topic | Each companion's phone is already subscribed to their own topic, so the server can message the same topic. |

## Steps

1. **Done:** PC app with one launcher, login screen, and per-person phone alerts.
2. **Self-host ntfy** on the Ubuntu VM (Docker image `binwiederhier/ntfy`).
   Set `NTFY_SERVER=https://<server>` in each PC's `korail_credentials.txt`.
   Phones re-subscribe once to the new server.
3. **Simple server mode (the target above):** a small web form on the VM where a
   person enters route/date/time. The server watches for seats and alerts that
   person's ntfy topic. No booking, so no need to store their Korail password.
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
- **Remote access:** phones need to reach ntfy from outside the home
  (port forwarding, Tailscale or Cloudflare Tunnel).
