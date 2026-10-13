# Korail app

Windows Streamlit app using `korail-mobile-api`.
Source repository: https://github.com/FirstBright/update

## For users

1. Extract the app files into a folder.
2. Double-click `1_설치.bat` to install Python/dependencies and create a local settings file.
3. Open `korail_credentials.txt` and enter your own Korail ID and password.
4. Double-click `2_실행.bat` to start the app.

Keep `korail_credentials.txt` private. The example file contains empty settings only.

## Update the app

1. Close the running app's black console window.
2. Double-click `3_업데이트.bat` and follow the message.
3. Start `2_실행.bat` again.

If you use Bash, run `bash update.sh` instead. Windows users do not need Git or
Bash: the BAT file uses the Python installed by `1_설치.bat`.

The updater downloads the latest `main` commit from `FirstBright/update`, compares
file contents, and replaces only changed files from its explicit app-file list.
Missing app files in that list are added. Other local files are never deleted.
Your `.venv`, credentials, `.git`, Git settings, maintainer upload scripts,
`tmp`, `output`, and personal files are preserved. Existing app files that are
replaced are backed up under `output/updates/`. If a replacement fails, the updater
attempts to restore files already changed and reports any restoration failure.
Do not interrupt the update or run it while the app is reserving tickets.

The updater changes app source only. The existing launcher installs any packages
needed to satisfy `requirements.txt` when the app starts again.

No GitHub account, Git installation, or OpenAI API key is needed to update.
Updates become available after the maintainer pushes the complete app to `main`.
Until then, an empty or inaccessible repository produces a message without
replacing app files. This updater uses `main`; GitHub Releases and GitHub Actions
are not configured yet.
