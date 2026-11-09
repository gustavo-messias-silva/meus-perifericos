"""Processo separado que fala HID++.

O Solaar pede o Gdk 3 no import. A janela usa o Gtk 4, e as duas versões
não convivem no mesmo processo. Este módulo fica sem interface gráfica.
"""

from __future__ import annotations

import json
import sys

from perifericos.session import Session, SolaarMissing, stop_solaar


def main() -> None:
    session = Session()
    for line in sys.stdin:
        text = line.strip()
        if not text:
            continue
        try:
            message = json.loads(text)
            command = message.get("cmd")
            if command == "stop":
                session.close()
                return
            if command == "poll":
                snapshot = session.poll()
            elif command == "apply":
                snapshot = session.apply_saved()
            elif command == "write":
                snapshot = session.write(message["id"], message["name"], message["value"], message.get("key"))
            elif command == "stop-solaar":
                stop_solaar()
                snapshot = session.poll()
            else:
                continue
        except SolaarMissing as exc:
            _emit({"ok": False, "error": str(exc)})
            continue
        except Exception as exc:
            _emit({"ok": False, "error": str(exc)})
            continue
        if session.error:
            _emit({"ok": False, "error": session.error})
            session.error = None
        _emit({"ok": True, "snapshot": snapshot})
    session.close()


def _emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
