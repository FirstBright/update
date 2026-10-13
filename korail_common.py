"""Shared credential loading for the korail_check / korail_reserve scripts."""

from __future__ import annotations

import getpass
import os
import re
from dataclasses import replace
from pathlib import Path

from korail_mobile_api import KorailConfig

CREDENTIALS_FILE = Path(__file__).parent / "korail_credentials.txt"

def build_client_config(enable_dynapath: bool = True) -> KorailConfig:
    """Keep default settings, optionally overriding only the Android ID."""
    if not enable_dynapath:
        return KorailConfig(disable_dynapath=True)
    config = KorailConfig()
    device_id = os.environ.get("KORAIL_DYNAPATH_DEVICE_ID")
    if device_id is None:
        return config
    if not re.fullmatch(r"[0-9a-fA-F]{16}", device_id):
        raise ValueError("KORAIL_DYNAPATH_DEVICE_ID must contain exactly 16 hex characters")
    settings = replace(config.dynapath.token_settings, device_id=device_id.lower())
    return replace(config, dynapath=replace(config.dynapath, token_settings=settings))


def _load_file() -> dict[str, str]:
    if not CREDENTIALS_FILE.exists():
        return {}
    values: dict[str, str] = {}
    for line in CREDENTIALS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def load_setting(key: str) -> str | None:
    """Read an optional setting: env var first, then korail_credentials.txt."""
    return os.environ.get(key) or _load_file().get(key) or None


def load_credentials(cli_id: str | None) -> tuple[str, str]:
    """Resolve (member_id, password).

    Priority: CLI arg > env var > korail_credentials.txt > interactive prompt.
    """
    file_values = _load_file()
    member_id = cli_id or os.environ.get("KORAIL_ID") or file_values.get("KORAIL_ID")
    if not member_id:
        member_id = input("Korail member ID: ").strip()
    if not member_id:
        raise ValueError("KORAIL_ID is required")
    password = os.environ.get("KORAIL_PASSWORD") or file_values.get("KORAIL_PASSWORD")
    if not password:
        password = getpass.getpass(f"Password for {member_id}: ")
    return member_id, password
