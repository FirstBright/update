# Korail app

Windows Streamlit app using `korail-mobile-api`.
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

Keep `korail_credentials.txt` private. Anyone who can read it can log into your
Korail account. If this folder is inside OneDrive/Dropbox, the file is synced too.

## Phone alerts

Open "📱 휴대폰 알림 설정" in the app. Install the **ntfy** app on the phone,
scan the QR code (or type the topic), and press "테스트 알림 보내기".
Each PC gets its own random topic, so each person only sees their own alerts.

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
