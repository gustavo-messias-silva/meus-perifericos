"""Converte ajustes do HID++ em uma estrutura pronta para a interface."""

from __future__ import annotations

from typing import Any

KIND_TOGGLE = 0x01
KIND_CHOICE = 0x02
KIND_RANGE = 0x04
KIND_MAP_CHOICE = 0x0A
KIND_PACKED_RANGE = 0x20
KIND_GRAPHIC_EQ = 0x21
KIND_MULTIPLE_RANGE = 0x40

MAP_KINDS = {KIND_MAP_CHOICE, KIND_PACKED_RANGE, KIND_GRAPHIC_EQ, KIND_MULTIPLE_RANGE}

GROUPS = (
    ("profiles", "Perfis"),
    ("pointer", "Ponteiro"),
    ("buttons", "Botões"),
    ("audio", "Áudio"),
    ("other", "Outros"),
)

_CATALOG: dict[str, tuple[str, str]] = {
    "dpi": ("Sensibilidade (DPI)", "Velocidade do cursor. Com um perfil interno ativo, o mouse pode ignorar este valor."),
    "dpi_extended": (
        "Sensibilidade (DPI)",
        "Velocidade do cursor. Com um perfil interno ativo, o mouse pode ignorar este valor.",
    ),
    "report_rate": ("Taxa de atualização", "Com que frequência o mouse informa o movimento."),
    "report_rate_extended": ("Taxa de atualização", "Com que frequência o mouse informa o movimento."),
    "pointer_speed": ("Velocidade do ponteiro", "Aceleração aplicada pelo dispositivo."),
    "onboard_profiles": (
        "Perfis internos",
        "Um perfil interno passa a mandar no DPI, na taxa e nos botões. Deixe desativado para valer o que está aqui.",
    ),
    "analog-button-tuning_actuation-0": ("Atuação do esquerdo", "1 é o clique mais raso e o máximo é o mais fundo."),
    "analog-button-tuning_actuation-1": ("Atuação do direito", "1 é o clique mais raso e o máximo é o mais fundo."),
    "analog-button-tuning_rapid-trigger-0": ("Rapid trigger do esquerdo", "Quanto o botão precisa soltar para armar de novo."),
    "analog-button-tuning_rapid-trigger-1": ("Rapid trigger do direito", "Quanto o botão precisa soltar para armar de novo."),
    "analog-button-tuning_haptics-0": ("Háptico do esquerdo", "0 desliga o clique háptico."),
    "analog-button-tuning_haptics-1": ("Háptico do direito", "0 desliga o clique háptico."),
    "headset-sidetone": ("Retorno do microfone", "Quanto da sua voz volta no fone. 0 desliga."),
    "headset-mic-snr": ("Realce do microfone", "Reforça a voz em relação ao ruído de fundo."),
    "headset-auto-sleep": ("Desligar sozinho", "Minutos parado até o headset dormir. 0 deixa ligado."),
    "headset-onboard-eq": ("Equalizador", "Ganho de cada banda, de -12 a 12."),
    "headset-mic-gain": ("Ganho do microfone", "Volume de captação."),
    "headset-mix-balance": ("Balanço do mix", "Equilíbrio entre o jogo e o chat."),
}

_RATE_HZ = {
    "8ms": "125 Hz · 8 ms",
    "4ms": "250 Hz · 4 ms",
    "2ms": "500 Hz · 2 ms",
    "1ms": "1000 Hz · 1 ms",
    "500us": "2000 Hz · 0,5 ms",
    "250us": "4000 Hz · 0,25 ms",
    "125us": "8000 Hz · 0,125 ms",
}

_WORD = {
    "Disabled": "Desativado",
    "LOW": "Baixa",
    "MEDIUM": "Média",
    "HIGH": "Alta",
    "Off": "Desligado",
    "Low": "Baixo",
    "Medium": "Médio",
    "High": "Alto",
    "Maximum": "Máximo",
}

_FIELD = {
    "X": "Eixo X",
    "Y": "Eixo Y",
    "LOD": "Altura do sensor",
}

_KIND_LABEL = {
    "mouse": "Mouse",
    "headset": "Headset",
    "audio": "Áudio",
    "microphone": "Microfone",
    "speaker": "Alto-falante",
    "keyboard": "Teclado",
    "numpad": "Teclado numérico",
    "trackball": "Trackball",
    "touchpad": "Touchpad",
    "presenter": "Apresentador",
}

_WPID_KIND = {
    "40BD": "mouse",
    "0AF7": "headset",
}

_RECEIVERS = {
    "C54D": "Receptor Bolt",
    "C548": "Receptor Bolt",
    "C52B": "Receptor Unifying",
    "C534": "Receptor Unifying",
    "C539": "Receptor Lightspeed",
    "C53A": "Receptor Lightspeed",
    "C53F": "Receptor Lightspeed",
}

_BATTERY = {
    "DISCHARGING": "em uso",
    "RECHARGING": "carregando",
    "ALMOST_FULL": "quase cheia",
    "FULL": "cheia",
    "SLOW_RECHARGE": "carga lenta",
    "INVALID_BATTERY": "sem leitura",
    "THERMAL_ERROR": "erro térmico",
}


def kind_label(kind: str | None) -> str:
    if not kind:
        return "Periférico"
    return _KIND_LABEL.get(str(kind).lower(), str(kind).capitalize())


def receiver_label(product_id: Any) -> str:
    key = str(product_id or "").upper().removeprefix("0X")
    return _RECEIVERS.get(key, "Receptor")


def battery_phrase(level: int | None, status: str | None) -> str:
    if level is None:
        return "Bateria indisponível"
    state = _BATTERY.get(str(status or "").upper(), "")
    if state:
        return f"{level}% · {state}"
    return f"{level}%"


def group_of(name: str) -> str:
    lowered = name.lower()
    if lowered.startswith("analog") or "haptic" in lowered or lowered.startswith("divert") or "button" in lowered:
        return "buttons"
    if lowered.startswith("headset") or "sidetone" in lowered or "equalizer" in lowered:
        return "audio"
    if "profile" in lowered:
        return "profiles"
    if any(token in lowered for token in ("dpi", "report_rate", "pointer", "speed-change")):
        return "pointer"
    return "other"


def option_label(raw: Any) -> str:
    text = str(raw)
    if text in _RATE_HZ:
        return _RATE_HZ[text]
    if text in _WORD:
        return _WORD[text]
    if text.startswith("Profile "):
        return "Perfil " + text.removeprefix("Profile ")
    if text.startswith("Read-Only Profile "):
        return "Perfil somente leitura " + text.removeprefix("Read-Only Profile ")
    return text


def field_label(raw: Any) -> str:
    text = str(raw)
    if text in _FIELD:
        return _FIELD[text]
    if text.endswith("Hz"):
        return text
    return option_label(text)


def _as_int(value: Any) -> int:
    return int(value)


def _options(choices: Any) -> list[dict[str, Any]]:
    return [{"value": _as_int(choice), "label": option_label(choice)} for choice in choices]


def _choice_map(setting: Any) -> dict | None:
    validator = getattr(setting, "_validator", None)
    choices = getattr(validator, "choices", None)
    if isinstance(choices, dict):
        return choices
    return None


def _plain_choices(setting: Any) -> Any:
    try:
        choices = setting.choices
    except Exception:
        return None
    if isinstance(choices, dict):
        return None
    return choices


def _bounds(setting: Any) -> tuple[int, int] | None:
    try:
        span = setting.range
    except Exception:
        span = None
    if span:
        return int(span[0]), int(span[1])
    validator = getattr(setting, "_validator", None)
    minimum = getattr(validator, "min_value", None)
    maximum = getattr(validator, "max_value", None)
    if minimum is None or maximum is None:
        return None
    return int(minimum), int(maximum)


def describe_setting(setting: Any) -> dict[str, Any] | None:
    if getattr(setting, "display", True) is False:
        return None
    name = str(setting.name)
    title, description = _CATALOG.get(name, (str(getattr(setting, "label", name) or name), str(getattr(setting, "description", "") or "")))
    kind = int(getattr(setting, "kind", 0) or 0)
    try:
        value = setting.read(cached=False)
    except Exception as exc:
        value = None
        description = f"{description}\nNão foi possível ler: {exc}".strip()

    payload: dict[str, Any] = {
        "name": name,
        "title": title,
        "description": description,
        "group": group_of(name),
        "kind": _kind_name(kind, value),
        "value": None,
        "options": [],
        "fields": [],
        "min": None,
        "max": None,
    }

    choice_map = _choice_map(setting)
    if choice_map is not None or (isinstance(value, dict) and kind in MAP_KINDS):
        payload["kind"] = "map"
        payload["fields"] = _describe_fields(setting, choice_map or {}, value if isinstance(value, dict) else {})
        return payload

    if kind & KIND_TOGGLE or isinstance(value, bool):
        payload["kind"] = "toggle"
        payload["value"] = bool(value)
        return payload

    choices = _plain_choices(setting)
    if choices:
        options = _options(choices)
        payload["kind"] = "choice"
        payload["options"] = options
        payload["value"] = _as_int(value) if value is not None else None
        return payload

    bounds = _bounds(setting)
    if bounds is not None or isinstance(value, int):
        payload["kind"] = "range"
        payload["value"] = int(value) if value is not None else None
        if bounds:
            payload["min"], payload["max"] = bounds
        return payload

    payload["kind"] = "readonly"
    payload["value"] = None if value is None else str(value)
    return payload


def _kind_name(kind: int, value: Any) -> str:
    if isinstance(value, dict) or kind in MAP_KINDS:
        return "map"
    if kind & KIND_TOGGLE:
        return "toggle"
    if kind & KIND_CHOICE:
        return "choice"
    if kind & KIND_RANGE:
        return "range"
    return "readonly"


def _describe_fields(setting: Any, choice_map: dict, value: dict) -> list[dict[str, Any]]:
    fields = []
    keys = list(choice_map.keys()) if choice_map else list(value.keys())
    bounds = _bounds(setting)
    for key in keys:
        current = _lookup(value, key)
        field: dict[str, Any] = {
            "key": _as_int(key),
            "title": field_label(key),
            "value": _as_int(current) if current is not None and not isinstance(current, str) else current,
            "options": [],
            "min": None,
            "max": None,
        }
        choices = choice_map.get(key) if choice_map else None
        if choices:
            field["options"] = _options(choices)
            if current is not None:
                field["value"] = _as_int(current)
        elif bounds:
            field["min"], field["max"] = bounds
            if current is not None:
                field["value"] = int(current)
        fields.append(field)
    return fields


def _lookup(value: dict, key: Any) -> Any:
    if key in value:
        return value[key]
    for candidate, stored in value.items():
        try:
            if int(candidate) == int(key):
                return stored
        except (TypeError, ValueError):
            if str(candidate) == str(key):
                return stored
    return None


def known_from_config(loaded: Any) -> list[dict[str, Any]]:
    """Entradas do config.yaml do Solaar que identificam um aparelho já visto."""
    if not isinstance(loaded, list):
        return []
    found: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for entry in loaded:
        if not isinstance(entry, dict):
            continue
        name = entry.get("_NAME")
        wpid = entry.get("_wpid")
        serial = entry.get("_serial")
        if not name or not wpid or not serial:
            continue
        identity = (str(wpid).upper(), str(serial))
        if identity in seen:
            continue
        seen.add(identity)
        kind = _WPID_KIND.get(identity[0], "headset" if "LIGHTSPEED" in str(name).upper() else "mouse")
        found.append(
            {
                "id": f"offline:{identity[0]}:{identity[1]}",
                "name": str(name),
                "kind": kind,
                "wpid": identity[0],
                "serial": identity[1],
                "online": False,
                "battery": None,
                "battery_status": None,
                "battery_text": "Desconectado",
                "settings": [],
            }
        )
    return found


def merge_offline(live: list[dict[str, Any]], known: list[dict[str, Any]]) -> list[dict[str, Any]]:
    present = set()
    for device in live:
        wpid = str(device.get("wpid") or "").upper()
        serial = str(device.get("serial") or "")
        if wpid and serial:
            present.add((wpid, serial))
        if wpid and device.get("online"):
            present.add((wpid, ""))
    merged = list(live)
    for device in known:
        identity = (str(device.get("wpid") or "").upper(), str(device.get("serial") or ""))
        if identity in present or (identity[0], "") in present:
            continue
        merged.append(device)
    return merged
