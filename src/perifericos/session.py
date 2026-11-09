"""Conversa com receptores HID++ e com o áudio USB numa thread só."""

from __future__ import annotations

import os
import signal
from pathlib import Path
from typing import Any

from perifericos.audio import describe_usb_audio, find_usb_audio, write_volume
from perifericos.present import battery_phrase, describe_setting, known_from_config, merge_offline, receiver_label
from perifericos.solaar_path import ensure_solaar


class SolaarMissing(RuntimeError):
    pass


def solaar_pids() -> list[int]:
    """Processos do aplicativo Solaar, sem confundir com este programa."""
    me = os.getpid()
    found = []
    proc = Path("/proc")
    if not proc.is_dir():
        return found
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid == me:
            continue
        try:
            raw = (entry / "cmdline").read_bytes()
        except OSError:
            continue
        parts = [part for part in raw.decode(errors="ignore").split("\0") if part]
        if any(Path(part).name == "solaar" for part in parts):
            found.append(pid)
    return found


def stop_solaar() -> int:
    stopped = 0
    for pid in solaar_pids():
        try:
            os.kill(pid, signal.SIGTERM)
            stopped += 1
        except OSError:
            continue
    return stopped


class Session:
    def __init__(self) -> None:
        self.nodes: list[Any] = []
        self._open_paths: set[str] = set()
        self._described: dict[str, dict[str, Any]] = {}
        self._ready = False
        self.error: str | None = None

    def ensure(self) -> None:
        if self._ready:
            return
        if ensure_solaar() is None:
            raise SolaarMissing(
                "Não encontrei o Solaar. Instale com pipx install solaar e abra este app de novo."
            )
        self._ready = True

    def poll(self) -> dict[str, Any]:
        self._sync_open()
        live = []
        receivers = []
        for node in list(self.nodes):
            if not getattr(node, "isDevice", False):
                product = str(getattr(node, "product_id", "")).upper()
                if product in {"0AF7"}:
                    continue
                receivers.append(
                    {
                        "name": receiver_label(product),
                        "path": getattr(node, "path", ""),
                        "serial": getattr(node, "serial", None),
                    }
                )
            for device in _iter_devices(node):
                described = self._describe(device)
                if described and not _asleep_headset(described):
                    live.append(described)
        live = _with_usb_audio(live)
        devices = merge_offline(live, _known_devices())
        return {"receivers": receivers, "devices": devices, "solaar": bool(solaar_pids()), "restored": False}

    def apply_saved(self) -> dict[str, Any]:
        """Empurra para os aparelhos ligados o que já está gravado."""
        self._sync_open()
        restored = 0
        for node in list(self.nodes):
            for device in _iter_devices(node):
                if not _ensure_online(device):
                    continue
                if _push_saved(device):
                    restored += 1
                self._described.pop(_device_id(device), None)
        snapshot = self.poll()
        snapshot["restored"] = restored
        return snapshot

    def write(self, device_id: str, setting_name: str, value: Any, key: int | None = None) -> dict[str, Any]:
        if str(device_id).startswith("alsa:"):
            return self._write_usb(device_id, setting_name, value)
        device = self._device_by_id(device_id)
        if device is None or not getattr(device, "online", False):
            raise RuntimeError("O dispositivo não está conectado.")
        setting = _find_setting(device, setting_name)
        if setting is None:
            raise RuntimeError(f"Ajuste indisponível: {setting_name}")
        _apply(setting, value, key)
        described = self._describe(device, refresh=True)
        self._described[device_id] = described
        snapshot = self.poll()
        for item in snapshot["devices"]:
            if item["id"] == device_id:
                item["settings"] = described["settings"]
                item["battery"] = described["battery"]
                item["battery_status"] = described["battery_status"]
                item["battery_text"] = described["battery_text"]
        return snapshot

    def _write_usb(self, device_id: str, setting_name: str, value: Any) -> dict[str, Any]:
        try:
            number = int(str(device_id).split(":", 1)[1])
        except (IndexError, ValueError) as exc:
            raise RuntimeError("O aparelho USB não está conectado.") from exc
        card = next((item for item in find_usb_audio() if item["card"] == number), None)
        if card is None:
            raise RuntimeError("O aparelho USB não está conectado.")
        control = next((item["control"] for item in card["controls"] if item["name"] == setting_name), None)
        if control is None:
            raise RuntimeError(f"Ajuste indisponível: {setting_name}")
        write_volume(card["card"], control, int(value))
        return self.poll()

    def close(self) -> None:
        for node in self.nodes:
            _close_node(node)
        self.nodes.clear()
        self._open_paths.clear()
        self._described.clear()

    def _sync_open(self) -> None:
        self.ensure()
        from logitech_receiver import base

        infos = list(base.receivers_and_devices())
        paths = {info.path for info in infos}
        self._close_missing(paths)
        for info in infos:
            if info.path not in self._open_paths:
                node = self._open(info)
                if node is not None:
                    if hasattr(node, "_dongle_features"):
                        try:
                            node.notify_devices()
                        except Exception:
                            pass
                    self.nodes.append(node)
                    self._open_paths.add(info.path)

    def _open(self, info: Any) -> Any:
        from logitech_receiver import base
        from logitech_receiver import device as device_mod
        from logitech_receiver import receiver as receiver_mod

        try:
            if not info.isDevice:
                return receiver_mod.create_receiver(base, info)
            if getattr(info, "centurion", False):
                bridge = device_mod.create_centurion_receiver(base, info, None)
                if bridge is not None:
                    return bridge
            return device_mod.create_device(base, info, None)
        except OSError as exc:
            self.error = f"Sem permissão para abrir {info.path}. Confira as regras udev do Solaar. ({exc})"
            return None

    def _close_missing(self, paths: set[str]) -> None:
        kept = []
        for node in self.nodes:
            path = getattr(node, "path", None)
            if path in paths:
                kept.append(node)
                continue
            _close_node(node)
            if path:
                self._open_paths.discard(path)
                stale = [key for key in self._described if key.startswith(f"{path}:")]
                for key in stale:
                    self._described.pop(key, None)
        self.nodes = kept

    def _device_by_id(self, device_id: str) -> Any:
        for node in self.nodes:
            for device in _iter_devices(node):
                if _device_id(device) == device_id:
                    return device
        return None

    def _describe(self, device: Any, refresh: bool = False) -> dict[str, Any] | None:
        device_id = _device_id(device)
        online = bool(getattr(device, "online", False))
        if not online:
            try:
                online = bool(device.ping())
            except Exception:
                online = False
        previous = self._described.get(device_id)
        if previous and not refresh and (not online or previous.get("settings")):
            battery, status = _battery(device) if online else (None, None)
            previous["online"] = online
            previous["battery"] = battery
            previous["battery_status"] = status
            previous["battery_text"] = battery_phrase(battery, status) if online else "Desconectado"
            return previous

        settings = []
        if online:
            try:
                raw = device.settings
            except Exception:
                raw = []
            for item in _flatten(raw):
                described = describe_setting(item)
                if described:
                    settings.append(described)
        battery, status = _battery(device) if online else (None, None)
        wpid = str(getattr(device, "wpid", "") or "").upper()
        snapshot = {
            "id": device_id,
            "name": str(getattr(device, "name", "") or "Periférico"),
            "kind": str(getattr(device, "kind", "") or ""),
            "wpid": wpid,
            "serial": str(getattr(device, "serial", "") or ""),
            "online": online,
            "battery": battery,
            "battery_status": status,
            "battery_text": battery_phrase(battery, status) if online else "Desconectado",
            "settings": settings,
        }
        self._described[device_id] = snapshot
        return snapshot


def _asleep_headset(device: dict[str, Any]) -> bool:
    return device.get("kind") == "headset" and not device.get("online")


def _with_usb_audio(live: list[dict[str, Any]]) -> list[dict[str, Any]]:
    online_names = {device.get("name") for device in live if device.get("online")}
    online_wpids = {device.get("wpid") for device in live if device.get("online") and device.get("wpid")}
    merged = list(live)
    for card in find_usb_audio():
        described = describe_usb_audio(card)
        if described["name"] in online_names:
            continue
        if described["wpid"] and described["wpid"] in online_wpids:
            continue
        merged.append(described)
    return merged


def _known_devices() -> list[dict[str, Any]]:
    path = Path.home() / ".config" / "solaar" / "config.yaml"
    if not path.is_file():
        return []
    try:
        import yaml
    except ImportError:
        return []
    try:
        loaded = yaml.safe_load(path.read_text())
    except Exception:
        return []
    return known_from_config(loaded)


def _iter_devices(node: Any):
    if getattr(node, "isDevice", False):
        yield node
        return
    try:
        devices = list(node)
    except Exception:
        return
    yield from devices


def _flatten(settings: Any):
    for item in settings or []:
        if isinstance(item, list):
            yield from item
        else:
            yield item


def _device_id(device: Any) -> str:
    path = getattr(getattr(device, "receiver", None), "path", None) or getattr(device, "path", "direct")
    number = getattr(device, "number", 0)
    return f"{path}:{number}"


def _ensure_online(device: Any) -> bool:
    if getattr(device, "online", False):
        return True
    try:
        return bool(device.ping())
    except Exception:
        return False


def _push_saved(device: Any) -> bool:
    try:
        if device.persister is None:
            return False
        settings = _flatten(device.settings)
    except Exception:
        return False
    pushed = False
    for setting in settings:
        if not getattr(setting, "persist", True):
            continue
        try:
            setting._value = None
            setting.apply()
            pushed = True
        except Exception:
            continue
    return pushed


def _battery(device: Any) -> tuple[int | None, str | None]:
    try:
        battery = device.battery()
    except Exception:
        return None, None
    if not battery or isinstance(battery, int):
        return None, None
    level = getattr(battery, "level", None)
    status = getattr(battery, "status", None)
    name = getattr(status, "name", None) or (str(status) if status is not None else None)
    try:
        level_int = int(level) if level is not None else None
    except (TypeError, ValueError):
        level_int = None
    return level_int, name


def _find_setting(device: Any, name: str) -> Any:
    try:
        raw = device.settings
    except Exception:
        return None
    for item in _flatten(raw):
        if str(getattr(item, "name", "")) == name:
            return item
    return None


def _apply(setting: Any, value: Any, key: int | None) -> None:
    if key is not None and hasattr(setting, "write_key_value"):
        key_obj, stored = _resolve_field(setting, key, value)
        result = setting.write_key_value(key_obj, stored, save=True)
        if result is None and getattr(setting, "_device", None) and not setting._device.online:
            raise RuntimeError("O dispositivo recusou o ajuste.")
        return
    stored = _coerce_choice(setting, value)
    result = setting.write(stored, save=True)
    if result is None:
        raise RuntimeError("O dispositivo recusou o ajuste.")


def _resolve_field(setting: Any, key: int, value: Any):
    validator = getattr(setting, "_validator", None)
    choices = getattr(validator, "choices", None)
    key_obj: Any = key
    options = None
    if isinstance(choices, dict):
        for candidate, candidate_options in choices.items():
            if int(candidate) == int(key):
                key_obj = candidate
                options = candidate_options
                break
    if options:
        for option in options:
            if int(option) == int(value):
                return key_obj, option
    return key_obj, int(value)


def _coerce_choice(setting: Any, value: Any):
    if isinstance(value, bool) or value is None:
        return value
    try:
        choices = setting.choices
    except Exception:
        choices = None
    if not choices or isinstance(choices, dict):
        if isinstance(value, str):
            return value
        try:
            return int(value)
        except (TypeError, ValueError):
            return value
    for choice in choices:
        if int(choice) == int(value):
            return choice
    return value


def _close_node(node: Any) -> None:
    close = getattr(node, "close", None)
    if callable(close):
        try:
            close()
        except Exception:
            pass
