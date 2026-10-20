"""Avell Control Center - interface GTK4/libadwaita."""

import sys
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk  # noqa: E402

from . import hw  # noqa: E402

APP_ID = "br.com.avell.ControlCenterLinux"


def run_bg(window, fn, *args):
    """Executa uma escrita (pode abrir pkexec) fora da thread da UI."""
    def work():
        try:
            fn(*args)
            err = None
        except Exception as e:  # noqa: BLE001
            err = str(e)
        GLib.idle_add(window.after_write, err)
    threading.Thread(target=work, daemon=True).start()


class Window(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Avell Control Center")
        self.set_default_size(700, 640)
        self._updating = False

        self.toasts = Adw.ToastOverlay()
        stack = Adw.ViewStack()
        view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        switcher = Adw.ViewSwitcher(stack=stack,
                                    policy=Adw.ViewSwitcherPolicy.WIDE)
        header.set_title_widget(switcher)
        view.add_top_bar(header)
        view.set_content(stack)
        self.toasts.set_child(view)
        self.set_content(self.toasts)

        st = hw.status()
        if not st["driver"]:
            page = Adw.StatusPage(
                icon_name="dialog-warning-symbolic",
                title="Driver não carregado",
                description="Instale o projeto com ./install.sh ou rode\n"
                            "<tt>sudo modprobe avell_dchu</tt>")
            stack.add_titled_with_icon(page, "none", "Aviso",
                                       "dialog-warning-symbolic")
            return

        stack.add_titled_with_icon(self._page_monitor(), "monitor", "Monitor",
                                   "utilities-system-monitor-symbolic")
        stack.add_titled_with_icon(self._page_power(st), "power", "Energia",
                                   "power-profile-performance-symbolic")
        if st["kbd_type"] != "none":
            stack.add_titled_with_icon(self._page_keyboard(st), "kbd", "Teclado",
                                       "input-keyboard-symbolic")
        if "charge_end" in st:
            stack.add_titled_with_icon(self._page_battery(st), "bat", "Bateria",
                                       "battery-full-symbolic")
        stack.add_titled_with_icon(self._page_info(st), "info", "Sobre",
                                   "help-about-symbolic")

        self.refresh()
        GLib.timeout_add_seconds(2, self._tick)

    # ------------------------------------------------------------ pages
    def _page_monitor(self):
        page = Adw.PreferencesPage()
        self.sensor_group = Adw.PreferencesGroup(title="Sensores")
        page.add(self.sensor_group)
        self.sensor_rows = {}
        return page

    def _page_power(self, st):
        page = Adw.PreferencesPage()

        g = Adw.PreferencesGroup(
            title="Modo de energia",
            description="Integrado ao menu de energia do GNOME")
        self.profile_buttons = {}
        first = None
        for key in st["profile_choices"]:
            row = Adw.ActionRow(title=hw.PROFILES.get(key, key))
            btn = Gtk.CheckButton(group=first)
            first = first or btn
            btn.connect("toggled", self._on_profile, key)
            row.add_prefix(btn)
            row.set_activatable_widget(btn)
            g.add(row)
            self.profile_buttons[key] = btn
        page.add(g)

        g = Adw.PreferencesGroup(title="Ventoinhas")
        self.fan_row = Adw.ComboRow(title="Modo das ventoinhas")
        self.fan_keys = [k for k in hw.FAN_MODES if k in st["fan_modes"]
                         and k != "custom"]
        self.fan_row.set_model(Gtk.StringList.new(
            [hw.FAN_MODES[k] for k in self.fan_keys]))
        self.fan_row.connect("notify::selected", self._on_fan)
        g.add(self.fan_row)
        dust = Adw.ActionRow(title="Limpeza anti-poeira",
                             subtitle="Gira as ventoinhas ao contrário por alguns segundos")
        b = Gtk.Button(label="Executar", valign=Gtk.Align.CENTER)
        b.connect("clicked", lambda *_: run_bg(self, hw.run_anti_dust))
        dust.add_suffix(b)
        g.add(dust)
        page.add(g)
        return page

    def _page_keyboard(self, st):
        page = Adw.PreferencesPage()
        g = Adw.PreferencesGroup(title="Iluminação do teclado")
        row = Adw.ActionRow(title="Brilho")
        self.kbd_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0, st.get("kbd_max", 4), 1)
        self.kbd_scale.set_hexpand(True)
        self.kbd_scale.set_draw_value(True)
        self.kbd_scale.set_digits(0)
        self.kbd_scale.connect("value-changed", self._on_kbd)
        row.add_suffix(self.kbd_scale)
        g.add(row)

        if st["kbd_type"] in ("rgb", "perkey"):
            crow = Adw.ActionRow(title="Cor")
            self.color_btn = Gtk.ColorDialogButton(
                dialog=Gtk.ColorDialog(with_alpha=False),
                valign=Gtk.Align.CENTER)
            self.color_btn.connect("notify::rgba", self._on_color)
            crow.add_suffix(self.color_btn)
            g.add(crow)

            self.effect_row = Adw.ComboRow(
                title="Efeito",
                subtitle="Respirar e Piscar usam a cor escolhida")
            self.effect_keys = st.get("kbd_effects") or ["static"]
            self.effect_row.set_model(Gtk.StringList.new(
                [hw.EFFECT_LABELS.get(e, e) for e in self.effect_keys]))
            self.effect_row.connect("notify::selected", self._on_effect)
            g.add(self.effect_row)
        page.add(g)
        return page

    def _page_battery(self, st):
        page = Adw.PreferencesPage()
        g = Adw.PreferencesGroup(
            title="FlexiCharger",
            description="Com o carregador conectado, a bateria só volta a "
                        "carregar quando cair abaixo do início e para no limite.")
        self.charge_switch = Adw.SwitchRow(title="Proteger a bateria")
        self.charge_switch.connect("notify::active", self._on_charge)
        g.add(self.charge_switch)
        self.charge_start = Adw.SpinRow.new_with_range(0, 95, 5)
        self.charge_start.set_title("Iniciar carga abaixo de (%)")
        self.charge_end = Adw.SpinRow.new_with_range(50, 100, 5)
        self.charge_end.set_title("Parar carga em (%)")
        for r in (self.charge_start, self.charge_end):
            r.connect("notify::value", self._on_charge)
            g.add(r)
        page.add(g)
        return page

    def _page_info(self, st):
        page = Adw.PreferencesPage()
        g = Adw.PreferencesGroup(title="Sistema")
        for title, val in (("Firmware do EC", st.get("ec_version")),
                           ("Teclado", st.get("kbd_type")),
                           ("Recursos (WMI)", st.get("features"))):
            row = Adw.ActionRow(title=title, subtitle=val or "—")
            row.set_subtitle_selectable(True)
            g.add(row)
        page.add(g)
        return page

    # ----------------------------------------------------------- state
    def _tick(self):
        self._refresh_sensors()
        return True

    def _refresh_sensors(self):
        for s in hw.sensors():
            row = self.sensor_rows.get(s["label"])
            if row is None:
                row = Adw.ActionRow(title=s["label"])
                lbl = Gtk.Label(css_classes=["numeric", "title-4"])
                row.add_suffix(lbl)
                row.lbl = lbl
                self.sensor_group.add(row)
                self.sensor_rows[s["label"]] = row
            row.lbl.set_label(f"{s['temp']} °C")
            row.set_subtitle(f"Ventoinha: {s['rpm']} RPM ({s['duty']}%)")

    def refresh(self):
        st = hw.status()
        self._updating = True
        try:
            btn = self.profile_buttons.get(st.get("profile"))
            if btn:
                btn.set_active(True)
            if st.get("fan_mode") in self.fan_keys:
                self.fan_row.set_selected(self.fan_keys.index(st["fan_mode"]))
            if hasattr(self, "kbd_scale"):
                self.kbd_scale.set_value(st.get("kbd_brightness", 0))
            if hasattr(self, "color_btn") and st.get("kbd_color"):
                c = Gdk.RGBA()
                c.parse("#" + st["kbd_color"])
                self.color_btn.set_rgba(c)
            if hasattr(self, "effect_row") and st.get("kbd_effect") in self.effect_keys:
                self.effect_row.set_selected(self.effect_keys.index(st["kbd_effect"]))
            if hasattr(self, "charge_switch"):
                on = not (st["charge_start"] == 0 and st["charge_end"] == 100)
                self.charge_switch.set_active(on)
                self.charge_start.set_value(st["charge_start"] if on else 70)
                self.charge_end.set_value(st["charge_end"] if on else 90)
                self.charge_start.set_sensitive(on)
                self.charge_end.set_sensitive(on)
        finally:
            self._updating = False
        self._refresh_sensors()

    def after_write(self, err):
        if err:
            self.toasts.add_toast(Adw.Toast(title=f"Erro: {err}"))
        self.refresh()
        return False

    # -------------------------------------------------------- handlers
    def _on_profile(self, btn, key):
        if not self._updating and btn.get_active():
            run_bg(self, hw.set_profile, key)

    def _on_fan(self, row, _):
        if not self._updating:
            run_bg(self, hw.set_fan_mode, self.fan_keys[row.get_selected()])

    def _on_kbd(self, scale):
        if not self._updating:
            run_bg(self, hw.set_kbd_brightness, int(round(scale.get_value())))

    def _on_color(self, btn, _):
        if self._updating:
            return
        c = btn.get_rgba()
        hexc = "%02x%02x%02x" % (round(c.red * 255), round(c.green * 255),
                                 round(c.blue * 255))
        run_bg(self, hw.set_kbd_color, hexc)

    def _on_effect(self, row, _):
        if not self._updating:
            run_bg(self, hw.set_kbd_effect, self.effect_keys[row.get_selected()])

    def _on_charge(self, *_):
        if self._updating:
            return
        on = self.charge_switch.get_active()
        self.charge_start.set_sensitive(on)
        self.charge_end.set_sensitive(on)
        if on:
            start = int(self.charge_start.get_value())
            end = int(self.charge_end.get_value())
            if start >= end:
                return
        else:
            start, end = 0, 100
        run_bg(self, hw.set_charge_limits, start, end)


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)

    def do_activate(self):
        win = self.props.active_window or Window(self)
        win.present()


def main():
    return App().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
