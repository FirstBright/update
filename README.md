# Korail app

Windows Streamlit app using [`pykorail`](https://github.com/devgyurak/pykorail).
Source repository: https://github.com/FirstBright/update

## For users

1. Extract the app files into a folder.
2. Double-click `코레일_실행.bat`. That's all — every time.
   - First run: installs Python (if missing), creates `.venv`, installs packages.
   - Every run: checks GitHub for a newer version and applies it, installs
     packages only when `requirements.txt` changed, then opens the browser.
   - If the update check fails (offline, GitHub limit), the current version starts.
3. The first time, the browser asks for your Korail ID and password.
   With "이 PC에 저장" checked they are written to `korail_credentials.txt`
   in this folder, so you never have to type them again. Use "계정 변경" to
   change them; if login fails, the form appears again automatically.

### Mac

Double-click `코레일_실행_mac.command` instead. It does the same steps
(Python 3.11+ from python.org is installed if missing) and keeps the Mac awake
while the app runs. The first time, macOS may block it as "unidentified
developer": right-click the file → **열기(Open)** → **열기**. If it says the
file can't be run, open Terminal in the folder and run
`chmod +x 코레일_실행_mac.command` once. Pop-up desktop alerts are Windows-only;
use phone alerts on a Mac.

Keep `korail_credentials.txt` private. Anyone who can read it can log into your
Korail account. If this folder is inside OneDrive/Dropbox, the file is synced too.

## Phone alerts (Telegram, ntfy optional)

Open "📱 휴대폰 알림 설정" in the app, scan the QR code with the phone camera,
press **시작(Start)** in Telegram, then press **연결 확인**. Nothing to type.
Each person's phone is linked to their own PC; others never see their alerts.
The optional "ntfy 앱으로도 받기" button adds ntfy as a second channel.

### Maintainer: one-time bot setup

1. In Telegram, message **@BotFather** → `/newbot` → pick a name. Copy the token.
2. Create `korail_bot.txt` in the app folder with one line:
   `TELEGRAM_BOT_TOKEN=<token>`
3. Ship it inside the zip, never in git (it's in `.gitignore`; the repo is public):
   `git archive -o ..\korail.zip --add-file=korail_bot.txt HEAD`

Anyone with the token can send messages as the bot, so only share the zip with
people you trust. If it leaks, use `/revoke` in @BotFather and send a new file.

See `ROADMAP.md` for the plan to move this to a home server.

## How updates work

The updater downloads the latest `main` commit from `FirstBright/update`, compares
file contents, and replaces only changed files from its explicit app-file list.
Missing app files in that list are added. Other local files are never deleted.
Your `.venv`, credentials, `.git`, maintainer upload scripts, `tmp`, `output`,
and personal files are preserved. Replaced app files are backed up under
`output/updates/`. If a replacement fails, the updater restores files already
changed and reports any restoration failure.

Only one copy runs at a time: launching again while the app is open just opens
the browser, and no update is applied while the app is running.

Folders containing `.git` (the maintainer's working copy) skip the automatic
update so unpublished edits are never overwritten.

No GitHub account, Git installation, or API key is needed to update.
