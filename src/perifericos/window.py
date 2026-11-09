"""Janela principal."""

from __future__ import annotations

from typing import Any, Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk

from perifericos.present import GROUPS, kind_label

_ICONS = {
    "mouse": "input-mouse-symbolic",
    "headset": "audio-headphones-symbolic",
    "keyboard": "input-keyboard-symbolic",
    "trackball": "input-mouse-symbolic",
    "touchpad": "input-touchpad-symbolic",
}

_GROUP_HELP = {
    "profiles": "Com um perfil interno ativo, ele passa a mandar no DPI, na taxa e nos botões.",
    "pointer": "Estes valores valem com o perfil interno desativado.",
    "buttons": "1 é o clique mais raso. Háptico em 0 desliga o clique.",
    "audio": "O headset aplica o ajuste na hora.",
}

_CSS = """
progressbar.battery trough {
  min-height: 8px;
  min-width: 120px;
  border-radius: 99px;
}
progressbar.battery progress {
  min-height: 8px;
  border-radius: 99px;
}
progressbar.battery.ok progress { background-color: @success_color; }
progressbar.battery.warn progress { background-color: @warning_color; }
progressbar.battery.critical progress { background-color: @error_color; }
progressbar.battery.charging progress { background-color: @accent_color; }
.dpi-readout { font-weight: 700; }
scale.full slider {
  min-width: 18px;
  min-height: 18px;
}
"""


class MainWindow(Adw.ApplicationWindow):
    def __init__(
        self,
        application: Adw.Application,
        on_write: Callable,
        on_stop_solaar: Callable,
        on_autostart: Callable | None = None,
        on_reapply: Callable | None = None,
        autostart: bool = False,
    ) -> None:
        super().__init__(application=application, title="Periféricos")
        self.set_default_size(1080, 720)
        self._on_write = on_write
        self._on_stop_solaar = on_stop_solaar
        self._on_autostart = on_autostart
        self._on_reapply = on_reapply
        self._devices: list[dict[str, Any]] = []
        self._selected: str | None = None
        self._rows: dict[str, Adw.ActionRow] = {}
        self._page_signature: tuple | None = None
        self._loading = False
        self._battery_label: Gtk.Label | None = None
        self._battery_state: Gtk.Label | None = None
        self._level: Gtk.ProgressBar | None = None
        self._linked_axes: dict[str, bool] = {}
        self._pending: dict[tuple, Any] = {}
        _install_css()

        self.toast = Adw.ToastOverlay()
        self.banner = Adw.Banner(
            title="O Solaar também está aberto e pode sobrescrever o que você mudar aqui.",
            button_label="Fechar o Solaar",
            revealed=False,
        )
        self.banner.connect("button-clicked", lambda *_: self._on_stop_solaar())

        self.device_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.device_list.add_css_class("navigation-sidebar")
        self.device_list.connect("row-selected", self._on_row_selected)

        sidebar_header = Adw.HeaderBar()
        sidebar_title = Adw.WindowTitle(title="Periféricos", subtitle="Logitech")
        sidebar_header.set_title_widget(sidebar_title)
        sidebar = Adw.ToolbarView()
        sidebar.add_top_bar(sidebar_header)
        sidebar.set_content(self.device_list)

        self.stack = Gtk.Stack()
        self.empty = Adw.StatusPage(
            icon_name="preferences-desktop-peripherals-symbolic",
            title="Nenhum periférico Logitech",
            description="Conecte o receptor Bolt ou ligue o mouse e o headset. Aparelhos já pareados aparecem mesmo desligados.",
        )
        self.stack.add_named(self.empty, "empty")
        self.detail = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.stack.add_named(self.detail, "detail")
        self.stack.set_visible_child_name("empty")

        content_header = Adw.HeaderBar()
        self.content_title = Adw.WindowTitle(title="Periféricos", subtitle="")
        content_header.set_title_widget(self.content_title)
        content_header.pack_end(self._menu_button(autostart))
        content = Adw.ToolbarView()
        content.add_top_bar(content_header)
        content.set_content(self.stack)

        self.split = Adw.OverlaySplitView(sidebar=sidebar, content=content, max_sidebar_width=320, min_sidebar_width=240)

        layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        layout.append(self.banner)
        layout.append(self.split)
        self.toast.set_child(layout)
        self.set_content(self.toast)

    def _menu_button(self, autostart: bool) -> Gtk.MenuButton:
        popover = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)
        switch = Adw.SwitchRow(
            title="Iniciar com o sistema",
            subtitle="Ao entrar na sessão, restaura o que foi salvo no mouse e no headset.",
            active=autostart,
        )
        switch.connect("notify::active", self._toggle_autostart)
        board = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        board.add_css_class("boxed-list")
        board.append(switch)
        reapply = Gtk.Button(label="Reaplicar configurações salvas")
        reapply.connect("clicked", lambda *_: self._reapply(popover))
        note = Gtk.Label(
            label="Cada ajuste é gravado na hora, neste usuário e no aparelho.",
            wrap=True,
            xalign=0,
        )
        note.add_css_class("caption")
        note.add_css_class("dim-label")
        note.set_max_width_chars(36)
        box.append(board)
        box.append(reapply)
        box.append(note)
        popover.set_child(box)
        button = Gtk.MenuButton(icon_name="open-menu-symbolic", popover=popover)
        button.set_tooltip_text("Sessão e configurações salvas")
        return button

    def _toggle_autostart(self, widget, _param) -> None:
        if self._loading or self._on_autostart is None:
            return
        self._on_autostart(bool(widget.get_active()))

    def _reapply(self, popover: Gtk.Popover) -> None:
        popover.popdown()
        if self._on_reapply is not None:
            self._on_reapply()

    def show_notice(self, message: str) -> None:
        self.toast.add_toast(Adw.Toast(title=message, timeout=4))

    def show_error(self, message: str) -> None:
        toast = Adw.Toast(title=message, timeout=6)
        self.toast.add_toast(toast)

    def show_snapshot(self, snapshot: dict[str, Any]) -> None:
        self.banner.set_revealed(bool(snapshot.get("solaar")))
        devices = list(snapshot.get("devices") or [])
        receivers = snapshot.get("receivers") or []
        if not devices and receivers:
            names = ", ".join(item["name"] for item in receivers)
            self.empty.set_description(f"{names} conectado, sem dispositivo pareado no momento.")
        self._sync_sidebar(devices)
        if not devices:
            self.stack.set_visible_child_name("empty")
            self._selected = None
            self._page_signature = None
            return
        if self._selected not in {device["id"] for device in devices}:
            online = next((device for device in devices if device.get("online")), devices[0])
            self._selected = online["id"]
            self._select_row(online["id"])
        self._show_selected()

    def _sync_sidebar(self, devices: list[dict[str, Any]]) -> None:
        incoming = {device["id"] for device in devices}
        if incoming != set(self._rows):
            self._loading = True
            while child := self.device_list.get_row_at_index(0):
                self.device_list.remove(child)
            self._rows.clear()
            for device in devices:
                row = self._make_row(device)
                self.device_list.append(row)
                self._rows[device["id"]] = row
            self._devices = devices
            self._loading = False
            if self._selected in self._rows:
                self._select_row(self._selected)
            return
        self._devices = devices
        for device in devices:
            row = self._rows[device["id"]]
            row.set_subtitle(self._subtitle(device))
            charge = getattr(row, "charge_label", None)
            if charge is not None:
                charge.set_label(_charge_text(device))

    def _make_row(self, device: dict[str, Any]) -> Adw.ActionRow:
        row = Adw.ActionRow(title=device["name"], subtitle=self._subtitle(device), activatable=True)
        icon_name = _ICONS.get(device.get("kind") or "", "preferences-desktop-peripherals-symbolic")
        row.add_prefix(Gtk.Image.new_from_icon_name(icon_name))
        charge = Gtk.Label(label=_charge_text(device), xalign=1)
        charge.add_css_class("dim-label")
        charge.add_css_class("numeric")
        row.add_suffix(charge)
        row.charge_label = charge
        row.device_id = device["id"]
        return row

    def _subtitle(self, device: dict[str, Any]) -> str:
        kind = kind_label(device.get("kind"))
        if not device.get("online"):
            return f"{kind} · desligado"
        return kind

    def _select_row(self, device_id: str) -> None:
        row = self._rows.get(device_id)
        if row is not None:
            self.device_list.select_row(row)

    def _on_row_selected(self, _list, row) -> None:
        if self._loading or row is None:
            return
        device_id = getattr(row, "device_id", None)
        if device_id and device_id != self._selected:
            self._selected = device_id
            self._page_signature = None
            self._show_selected()

    def _current(self) -> dict[str, Any] | None:
        for device in self._devices:
            if device["id"] == self._selected:
                return device
        return None

    def _show_selected(self) -> None:
        device = self._current()
        if device is None:
            self.stack.set_visible_child_name("empty")
            return
        self.stack.set_visible_child_name("detail")
        self.content_title.set_title(device["name"])
        self.content_title.set_subtitle(self._subtitle(device))
        signature = _signature(device)
        if signature != self._page_signature:
            self._page_signature = signature
            self._rebuild(device)
        else:
            self._refresh_header(device)

    def _rebuild(self, device: dict[str, Any]) -> None:
        while child := self.detail.get_first_child():
            self.detail.remove(child)
        self._battery_label = None
        self._battery_state = None
        self._level = None
        if not device.get("online"):
            self.detail.append(_offline_page(device))
            return

        page = Adw.PreferencesPage()
        if isinstance(device.get("battery"), int):
            page.add(self._battery_group(device))

        grouped: dict[str, list[dict]] = {key: [] for key, _title in GROUPS}
        for setting in device.get("settings") or []:
            grouped.setdefault(setting["group"], []).append(setting)
        onboard = _setting_value(device, "onboard_profiles")
        for key, title in GROUPS:
            items = grouped.get(key) or []
            if not items:
                continue
            group = Adw.PreferencesGroup(title=title)
            help_text = _group_help(key, onboard)
            if help_text:
                group.set_description(help_text)
            rows = []
            for setting in items:
                rows.extend(self._setting_widgets(device, setting))
            group.add(_boxed(rows))
            page.add(group)

        if not device.get("settings"):
            page.add(Adw.PreferencesGroup(description="Este aparelho não expôs ajustes configuráveis."))
        self.detail.append(page)

    def _battery_group(self, device: dict[str, Any]) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(title="Bateria")
        box = Gtk.Box(spacing=12)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_margin_start(12)
        box.set_margin_end(12)
        self._battery_label = Gtk.Label(xalign=0)
        self._battery_label.add_css_class("title-2")
        self._battery_label.add_css_class("numeric")
        state = Gtk.Label(xalign=0)
        state.add_css_class("dim-label")
        state.set_hexpand(True)
        self._battery_state = state
        self._level = Gtk.ProgressBar()
        self._level.add_css_class("battery")
        self._level.set_valign(Gtk.Align.CENTER)
        box.append(self._battery_label)
        box.append(state)
        box.append(self._level)
        group.add(_boxed([box]))
        self._paint_battery(device)
        return group

    def _paint_battery(self, device: dict[str, Any]) -> None:
        level = device.get("battery")
        if not isinstance(level, int):
            return
        if self._battery_label is not None:
            self._battery_label.set_label(f"{level}%")
        if self._battery_state is not None:
            self._battery_state.set_label(_battery_state(device))
        if self._level is None:
            return
        self._level.set_fraction(max(0, min(level, 100)) / 100)
        for name in ("ok", "warn", "critical", "charging"):
            self._level.remove_css_class(name)
        self._level.add_css_class(_battery_tone(level, device.get("battery_status")))

    def _refresh_header(self, device: dict[str, Any]) -> None:
        self._paint_battery(device)

    def _setting_widgets(self, device: dict[str, Any], setting: dict[str, Any]) -> list[Gtk.Widget]:
        if setting["kind"] == "map":
            return self._map_widgets(device, setting)
        if setting["kind"] == "toggle":
            row = Adw.SwitchRow(title=setting["title"], active=bool(setting["value"]))
            row.set_sensitive(device.get("online", False))
            row.connect("notify::active", lambda widget, _param, s=setting: self._emit_toggle(widget, s))
            return [row]
        if setting["kind"] == "choice":
            return [self._choice_row(device, setting["title"], setting["options"], setting["value"], setting, None)]
        if setting["kind"] == "range" and setting["min"] is not None:
            return [self._range_row(device, setting["title"], setting["value"], setting["min"], setting["max"], setting, None)]
        row = Adw.ActionRow(title=setting["title"], subtitle=str(setting["value"] or "—"))
        return [row]

    def _map_widgets(self, device: dict[str, Any], setting: dict[str, Any]) -> list[Gtk.Widget]:
        fields = sorted(setting["fields"], key=_field_order)
        axes = {field["title"]: field for field in fields}
        link = "Eixo X" in axes and "Eixo Y" in axes and axes["Eixo X"].get("options")
        widgets: list[Gtk.Widget] = []
        scales: dict[str, Gtk.Scale] = {}
        readouts: dict[str, Gtk.Label] = {}
        rows: dict[str, Gtk.Widget] = {}
        titles: dict[str, Gtk.Label] = {}
        linked = False
        if link:
            same = axes["Eixo X"].get("value") == axes["Eixo Y"].get("value")
            linked = self._linked_axes.setdefault(device["id"], same)
            switch = Adw.SwitchRow(title="Mesmo DPI nos dois eixos", active=linked)
            switch.connect(
                "notify::active",
                lambda widget, _param, dev=device["id"]: self._set_linked(
                    dev, widget.get_active(), scales, readouts, rows, titles, axes, setting
                ),
            )
            widgets.append(switch)
        for field in fields:
            title = field["title"]
            if field["options"] and len(field["options"]) > 24:
                row, scale, readout, title_label = self._indexed_scale(
                    device, setting, title, field["options"], field["value"], field["key"], scales, readouts
                )
                if linked and title == "Eixo X":
                    title_label.set_label("DPI")
                if linked and title == "Eixo Y":
                    row.set_visible(False)
                scales[title] = scale
                readouts[title] = readout
                rows[title] = row
                titles[title] = title_label
                widgets.append(row)
            elif field["options"]:
                widgets.append(self._choice_row(device, title, field["options"], field["value"], setting, field["key"]))
            elif field["min"] is not None:
                widgets.append(self._range_row(device, title, field["value"], field["min"], field["max"], setting, field["key"]))
            else:
                widgets.append(Adw.ActionRow(title=title, subtitle=str(field["value"])))
        return widgets

    def _set_linked(self, device_id, active, scales, readouts, rows, titles, axes, setting) -> None:
        self._linked_axes[device_id] = active
        if "Eixo Y" in rows:
            rows["Eixo Y"].set_visible(not active)
        if "Eixo X" in titles:
            titles["Eixo X"].set_label("DPI" if active else "Eixo X")
        if not active or "Eixo X" not in scales or "Eixo Y" not in scales:
            return
        position = int(round(scales["Eixo X"].get_value()))
        self._loading = True
        scales["Eixo Y"].set_value(position)
        self._loading = False
        options = axes["Eixo X"]["options"]
        position = max(0, min(position, len(options) - 1))
        readouts["Eixo Y"].set_label(_readout(setting, options[position]["label"]))
        self._schedule_write(setting["name"], options[position]["value"], axes["Eixo Y"]["key"])

    def _choice_row(self, device, title, options, value, setting, key) -> Adw.ComboRow:
        labels = [option["label"] for option in options]
        row = Adw.ComboRow(title=title, model=Gtk.StringList.new(labels))
        selected = 0
        for index, option in enumerate(options):
            if option["value"] == value:
                selected = index
                break
        self._loading = True
        row.set_selected(selected)
        self._loading = False
        row.set_sensitive(bool(device.get("online")))
        row.connect(
            "notify::selected",
            lambda widget, _param, s=setting, opts=options, field=key: self._emit_choice(widget, s, opts, field),
        )
        return row

    def _range_row(self, device, title, value, minimum, maximum, setting, key) -> Adw.SpinRow:
        adjustment = Gtk.Adjustment(value=value or minimum, lower=minimum, upper=maximum, step_increment=1, page_increment=1)
        row = Adw.SpinRow(title=title, adjustment=adjustment)
        row.set_sensitive(bool(device.get("online")))
        row.connect(
            "notify::value",
            lambda widget, _param, s=setting, field=key: self._emit_range(widget, s, field),
        )
        return row

    def _indexed_scale(self, device, setting, title, options, value, key, scales, readouts):
        index = 0
        for position, option in enumerate(options):
            if option["value"] == value:
                index = position
                break
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_top(10)
        box.set_margin_bottom(8)
        box.set_margin_start(12)
        box.set_margin_end(12)
        header = Gtk.Box(spacing=12)
        name = Gtk.Label(label=title, xalign=0)
        name.set_hexpand(True)
        name.add_css_class("heading")
        readout = Gtk.Label(label=_readout(setting, options[index]["label"]), xalign=1)
        readout.add_css_class("title-3")
        readout.add_css_class("numeric")
        readout.add_css_class("dpi-readout")
        header.append(name)
        header.append(readout)
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, max(len(options) - 1, 1), 1)
        scale.add_css_class("full")
        scale.set_draw_value(False)
        scale.set_hexpand(True)
        scale.set_value(index)
        scale.set_sensitive(bool(device.get("online")))
        ends = Gtk.Box()
        low = Gtk.Label(label=options[0]["label"], xalign=0)
        high = Gtk.Label(label=options[-1]["label"], xalign=1)
        low.add_css_class("caption")
        low.add_css_class("dim-label")
        high.add_css_class("caption")
        high.add_css_class("dim-label")
        high.set_hexpand(True)
        ends.append(low)
        ends.append(high)
        box.append(header)
        box.append(scale)
        box.append(ends)

        def changed(widget, s=setting, opts=options, field=key, label=readout, axis=title):
            if self._loading:
                return
            position = int(round(widget.get_value()))
            position = max(0, min(position, len(opts) - 1))
            label.set_label(_readout(s, opts[position]["label"]))
            self._schedule_write(s["name"], opts[position]["value"], field)
            if axis in ("Eixo X", "Eixo Y") and self._linked_axes.get(device["id"]):
                self._mirror_axis(device, s, opts, position, axis, scales, readouts)

        scale.connect("value-changed", changed)
        return box, scale, readout, name

    def _mirror_axis(self, device, setting, options, position, source, scales, readouts) -> None:
        other = "Eixo Y" if source == "Eixo X" else "Eixo X"
        other_field = next((field for field in setting["fields"] if field["title"] == other), None)
        other_scale = scales.get(other)
        if other_scale is not None:
            self._loading = True
            other_scale.set_value(position)
            if other in readouts:
                readouts[other].set_label(_readout(setting, options[position]["label"]))
            self._loading = False
        if other_field is None:
            return
        self._schedule_write(setting["name"], options[position]["value"], other_field["key"])

    def _emit_toggle(self, widget, setting) -> None:
        if self._loading:
            return
        self._schedule_write(setting["name"], bool(widget.get_active()), None)

    def _emit_choice(self, widget, setting, options, key) -> None:
        if self._loading:
            return
        index = widget.get_selected()
        if index < 0 or index >= len(options):
            return
        self._schedule_write(setting["name"], options[index]["value"], key)

    def _emit_range(self, widget, setting, key) -> None:
        if self._loading:
            return
        self._schedule_write(setting["name"], int(round(widget.get_value())), key)

    def _schedule_write(self, name: str, value: Any, key: int | None) -> None:
        device_id = self._selected
        if not device_id:
            return
        self._pending[(device_id, name, key)] = value
        if getattr(self, "_write_source", None):
            GLib.source_remove(self._write_source)

        def fire():
            self._write_source = None
            pending = list(self._pending.items())
            self._pending.clear()
            for (dev, setting_name, field), stored in pending:
                self._on_write(dev, setting_name, stored, field)
            return False

        self._write_source = GLib.timeout_add(160, fire)


def _install_css() -> None:
    display = Gdk.Display.get_default()
    if display is None:
        return
    provider = Gtk.CssProvider()
    provider.load_from_data(_CSS.encode())
    Gtk.StyleContext.add_provider_for_display(display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


def _boxed(widgets: list) -> Gtk.ListBox:
    board = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
    board.add_css_class("boxed-list")
    for widget in widgets:
        if isinstance(widget, Gtk.ListBoxRow):
            board.append(widget)
            continue
        row = Gtk.ListBoxRow(activatable=False, selectable=False)
        row.set_child(widget)
        row.set_visible(widget.get_visible())
        widget.connect("notify::visible", lambda child, _param, holder=row: holder.set_visible(child.get_visible()))
        board.append(row)
    return board


def _charge_text(device: dict[str, Any]) -> str:
    level = device.get("battery")
    if device.get("online") and isinstance(level, int):
        return f"{level}%"
    return ""


def _battery_state(device: dict[str, Any]) -> str:
    text = device.get("battery_text") or ""
    if "·" in text:
        return text.split("·", 1)[1].strip()
    return text


def _battery_tone(level: int, status: str | None) -> str:
    if str(status or "").upper() == "RECHARGING":
        return "charging"
    if level <= 15:
        return "critical"
    if level <= 30:
        return "warn"
    return "ok"


def _offline_page(device: dict[str, Any]) -> Adw.StatusPage:
    kind = device.get("kind")
    if kind == "headset":
        description = "Ligue o headset para ajustar o retorno do microfone, o equalizador e o desligamento."
    elif kind == "mouse":
        description = "Ligue o mouse para ajustar o DPI, a taxa e os botões."
    else:
        description = "Ligue o aparelho para ler e alterar a configuração."
    icon = _ICONS.get(kind or "", "preferences-desktop-peripherals-symbolic")
    return Adw.StatusPage(icon_name=icon, title=f"{device['name']} está desligado", description=description)


def _setting_value(device: dict[str, Any], name: str):
    for setting in device.get("settings") or []:
        if setting.get("name") == name:
            return setting.get("value")
    return None


def _group_help(key: str, onboard) -> str:
    if key == "pointer" and onboard not in (None, 0):
        return "O perfil interno está ativo e pode ignorar o DPI e a taxa."
    return _GROUP_HELP.get(key, "")


def _field_order(field: dict[str, Any]) -> int:
    title = field.get("title")
    if title == "Eixo X":
        return 0
    if title == "Eixo Y":
        return 1
    if len(field.get("options") or []) > 24:
        return 2
    return 3


def _readout(setting: dict[str, Any], label: str) -> str:
    if "dpi" in setting.get("name", ""):
        return f"{label} DPI"
    return label


def _signature(device: dict[str, Any]) -> tuple:
    settings = []
    for setting in device.get("settings") or []:
        fields = tuple((field["key"], len(field.get("options") or []), field.get("min"), field.get("max")) for field in setting.get("fields") or [])
        settings.append((setting["name"], setting["kind"], len(setting.get("options") or []), fields))
    return (device["id"], bool(device.get("online")), tuple(settings))
