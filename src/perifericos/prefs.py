"""Preferências do aplicativo e início junto com a sessão."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import yaml

DEFAULTS = {"autostart": False}


def config_path() -> Path:
    override = os.environ.get("PERIFERICOS_CONFIG")
    if override:
        return Path(override)
    return Path.home() / ".config" / "perifericos" / "config.yaml"


def autostart_path() -> Path:
    override = os.environ.get("PERIFERICOS_AUTOSTART")
    if override:
        return Path(override)
    return Path.home() / ".config" / "autostart" / "perifericos.desktop"


def load() -> dict:
    path = config_path()
    data = dict(DEFAULTS)
    if not path.is_file():
        return data
    try:
        loaded = yaml.safe_load(path.read_text()) or {}
    except Exception:
        return data
    if isinstance(loaded, dict):
        data.update({key: loaded[key] for key in DEFAULTS if key in loaded})
    data["autostart"] = bool(data["autostart"]) and autostart_path().is_file()
    return data


def save(data: dict) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    stored = {key: data.get(key, DEFAULTS[key]) for key in DEFAULTS}
    path.write_text(yaml.safe_dump(stored, sort_keys=False, allow_unicode=True))


def executable() -> str:
    found = shutil.which("perifericos")
    if found:
        return found
    return str(Path.home() / ".local" / "bin" / "perifericos")


def set_autostart(enabled: bool) -> None:
    path = autostart_path()
    if not enabled:
        path.unlink(missing_ok=True)
        current = load()
        current["autostart"] = False
        save(current)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "[Desktop Entry]",
                "Type=Application",
                "Name=Periféricos",
                "Comment=Restaura a configuração salva do mouse e do headset",
                f"Exec={executable()} --restore",
                "Icon=perifericos",
                "Terminal=false",
                "X-GNOME-Autostart-enabled=true",
                "",
            ]
        )
    )
    current = load()
    current["autostart"] = True
    save(current)
