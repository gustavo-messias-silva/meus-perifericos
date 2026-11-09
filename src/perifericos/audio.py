"""Volume do headset quando ele entra pelo cabo USB."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

_TITLES = {
    "PCM": "Volume",
    "Master": "Volume",
    "Speaker": "Alto-falante",
    "Headphone": "Fone",
    "Headset": "Headset",
    "Mic": "Microfone",
    "Microphone": "Microfone",
    "Capture": "Microfone",
}
_CAPTURE = {"Mic", "Microphone", "Capture"}


def parse_mixer(text: str) -> list[dict]:
    """Lê a saída de `amixer scontents` e devolve volume em porcentagem."""
    controls = []
    name = None
    for line in text.splitlines():
        header = re.match(r"Simple mixer control '([^']+)'", line)
        if header:
            name = header.group(1)
            continue
        if name not in _TITLES:
            continue
        match = re.search(r"\[(\d+)%\]", line)
        if not match:
            continue
        controls.append(
            {
                "name": f"alsa-{name}",
                "title": _TITLES[name],
                "description": "",
                "group": "audio",
                "kind": "range",
                "value": int(match.group(1)),
                "options": [],
                "fields": [],
                "min": 0,
                "max": 100,
                "control": name,
            }
        )
        name = None
    return controls


def find_usb_audio() -> list[dict]:
    """Qualquer placa de som USB com volume, sem filtrar fabricante."""
    root = Path("/proc/asound")
    if not root.is_dir():
        return []
    found = []
    for card in sorted(root.glob("card[0-9]*")):
        try:
            number = int(card.name.removeprefix("card"))
            card_id = (card / "id").read_text().strip()
            usbid_path = card / "usbid"
            if not usbid_path.is_file():
                continue
            usbid = usbid_path.read_text().strip().lower()
        except (OSError, ValueError):
            continue
        controls = parse_mixer(_amixer(number))
        if not controls:
            continue
        found.append(
            {
                "card": number,
                "id": card_id,
                "usbid": usbid,
                "name": _product_name(usbid, card_id),
                "controls": controls,
            }
        )
    return found


def describe_usb_audio(card: dict) -> dict:
    usbid = card.get("usbid") or ""
    wpid = "0AF7" if usbid == "046d:0af7" else ""
    notice = "Conectado por USB."
    if wpid == "0AF7":
        notice = "Conectado por USB. Retorno, equalizador e desligamento aparecem na conexão sem fio."
    return {
        "id": f"alsa:{card['card']}",
        "name": card["name"],
                "kind": _kind(card["controls"], card["name"], usbid),
        "wpid": wpid,
        "serial": "usb",
        "online": True,
        "battery": None,
        "battery_status": None,
        "battery_text": "Conectado por USB",
        "notice": notice,
        "settings": card["controls"],
    }


def write_volume(card: int, control: str, percent: int) -> None:
    percent = max(0, min(100, int(percent)))
    subprocess.run(
        ["amixer", "-c", str(card), "sset", control, f"{percent}%"],
        check=True,
        capture_output=True,
        text=True,
    )


def _product_name(usbid: str, fallback: str) -> str:
    vendor, _, product_id = usbid.partition(":")
    root = Path("/sys/bus/usb/devices")
    if not vendor or not root.is_dir():
        return fallback
    for device in root.iterdir():
        try:
            if (device / "idVendor").read_text().strip() != vendor:
                continue
            if (device / "idProduct").read_text().strip() != product_id:
                continue
            name = (device / "product").read_text().strip()
        except OSError:
            continue
        if name:
            return name
    return fallback


def _kind(controls: list[dict], name: str, usbid: str) -> str:
    names = {item["control"] for item in controls}
    has_capture = bool(names & _CAPTURE)
    has_playback = bool(names - _CAPTURE)
    if has_capture and not has_playback:
        return "microphone"
    if has_playback and not has_capture:
        return "speaker"
    if usbid == "046d:0af7" or any(word in name.upper() for word in ("HEADSET", "HEADPHONE", "FONE")):
        return "headset"
    return "audio"


def _amixer(card: int) -> str:
    try:
        result = subprocess.run(
            ["amixer", "-c", str(card), "scontents"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return ""
    return result.stdout
