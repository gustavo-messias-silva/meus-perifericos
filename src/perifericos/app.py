"""Aplicativo GTK para configurar periféricos."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib

from perifericos.prefs import load, set_autostart
from perifericos.window import MainWindow


class PerifericosApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id="io.perifericos.App")
        self.window: MainWindow | None = None
        self.proc: subprocess.Popen | None = None
        self._reader: threading.Thread | None = None
        self.restore = "--restore" in sys.argv
        self._announced_restore = False

    def do_activate(self) -> None:
        if self.window is None:
            self.window = MainWindow(
                self,
                on_write=self.enqueue_write,
                on_stop_solaar=self.enqueue_stop_solaar,
                on_autostart=self.toggle_autostart,
                on_reapply=self.reapply,
                autostart=bool(load().get("autostart")),
            )
            self._start_worker()
            self.send({"cmd": "apply" if self.restore else "poll"})
            GLib.timeout_add_seconds(4, self._poll)
            if os.environ.get("PERIFERICOS_SMOKE") == "1":
                GLib.timeout_add(3500, self._smoke_quit)
        self.window.present()

    def do_shutdown(self) -> None:
        self.send({"cmd": "stop"})
        if self.proc is not None and self.proc.poll() is None:
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        Adw.Application.do_shutdown(self)

    def enqueue_write(self, device_id: str, name: str, value, key) -> None:
        self.send({"cmd": "write", "id": device_id, "name": name, "value": value, "key": key})

    def enqueue_stop_solaar(self) -> None:
        self.send({"cmd": "stop-solaar"})

    def toggle_autostart(self, enabled: bool) -> None:
        set_autostart(enabled)
        if self.window is not None:
            if enabled:
                self.window.show_notice("Vai abrir ao entrar na sessão e restaurar o que está salvo.")
            else:
                self.window.show_notice("Não abre mais sozinho.")

    def reapply(self) -> None:
        self.send({"cmd": "apply"})

    def _poll(self) -> bool:
        self.send({"cmd": "poll"})
        return True

    def _smoke_quit(self) -> bool:
        if self.window is not None:
            self.window.close()
        return False

    def _start_worker(self) -> None:
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "perifericos.worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._reader = threading.Thread(target=self._read_output, name="hidpp", daemon=True)
        self._reader.start()

    def send(self, payload: dict) -> None:
        if self.proc is None or self.proc.stdin is None or self.proc.poll() is not None:
            return
        try:
            self.proc.stdin.write(json.dumps(payload) + "\n")
            self.proc.stdin.flush()
        except BrokenPipeError:
            return

    def _read_output(self) -> None:
        assert self.proc is not None and self.proc.stdout is not None
        for line in self.proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            GLib.idle_add(self._deliver, message)

    def _deliver(self, message: dict) -> bool:
        if self.window is None:
            return False
        if not message.get("ok"):
            self.window.show_error(message.get("error") or "Falha ao falar com o dispositivo.")
            return False
        snapshot = message.get("snapshot")
        if snapshot:
            self.window.show_snapshot(snapshot)
            if snapshot.get("restored") and not self._announced_restore:
                self._announced_restore = True
                count = snapshot.get("restored")
                self.window.show_notice(f"Configuração salva reaplicada em {count} aparelho(s).")
        return False


def main() -> None:
    app = PerifericosApp()
    raise SystemExit(app.run(sys.argv))
