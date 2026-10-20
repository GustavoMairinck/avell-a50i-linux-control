"""Acesso ao hardware Avell via sysfs exposto pelo driver avell_dchu.

Leituras funcionam como usuário comum. Escritas são feitas diretamente
quando o processo é root; caso contrário passam pelo helper privilegiado
(pkexec + polkit), que valida os argumentos e persiste o estado.
"""

import glob
import json
import os
import subprocess

HELPER = "/usr/libexec/avell-cc/avell-cc-helper"
STATE_FILE = "/var/lib/avell-cc/state.json"

PLATFORM_DEV = "/sys/bus/platform/drivers/avell-dchu/CLV0001:00"
PLATFORM_PROFILE = "/sys/firmware/acpi/platform_profile"
PLATFORM_PROFILE_CHOICES = "/sys/firmware/acpi/platform_profile_choices"
KBD_LED = "/sys/class/leds/avell::kbd_backlight"

PROFILES = {
    "quiet": "Silencioso",
    "low-power": "Economia de energia",
    "balanced": "Entretenimento (equilibrado)",
    "performance": "Desempenho",
}
FAN_MODES = {
    "auto": "Automático",
    "silent": "Silencioso",
    "max": "Velocidade máxima",
    "maxq": "Max-Q",
    "custom": "Personalizado",
}
KBD_EFFECTS = ["static", "breathe", "cycle", "dance", "tempo", "flash",
               "wave", "random"]
EFFECT_LABELS = {
    "static": "Estático",
    "breathe": "Respirar",
    "cycle": "Arco-íris",
    "random": "Aleatório",
    "flash": "Piscar",
    "wave": "Onda",
    "dance": "Dança",
    "tempo": "Ritmo",
}


class NotLoaded(RuntimeError):
    pass


def _read(path, default=None):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return default


def _write(path, value):
    with open(path, "w") as f:
        f.write(str(value))


def _selected(text):
    """'a [b] c' -> ('b', ['a','b','c'])"""
    if text is None:
        return None, []
    items = text.split()
    cur = next((i.strip("[]") for i in items if i.startswith("[")), None)
    return cur, [i.strip("[]") for i in items]


def driver_loaded():
    return os.path.isdir(PLATFORM_DEV)


def battery_dir():
    for d in sorted(glob.glob("/sys/class/power_supply/BAT*")):
        if os.path.exists(os.path.join(d, "charge_control_end_threshold")):
            return d
    return None


def hwmon_dir():
    for d in glob.glob("/sys/class/hwmon/hwmon*"):
        if _read(os.path.join(d, "name")) == "avell_dchu":
            return d
    return None


# ---------------------------------------------------------------- leitura

def status():
    s = {"driver": driver_loaded()}
    if not s["driver"]:
        return s
    s["features"] = _read(f"{PLATFORM_DEV}/features")
    s["ec_version"] = _read(f"{PLATFORM_DEV}/ec_version")
    s["profile"] = _read(PLATFORM_PROFILE)
    s["profile_choices"] = (_read(PLATFORM_PROFILE_CHOICES) or "").split()
    s["fan_mode"], s["fan_modes"] = _selected(_read(f"{PLATFORM_DEV}/fan_mode"))
    s["kbd_type"] = _read(f"{PLATFORM_DEV}/kbd_type", "none")
    if os.path.isdir(KBD_LED):
        s["kbd_brightness"] = int(_read(f"{KBD_LED}/brightness", "0"))
        s["kbd_max"] = int(_read(f"{KBD_LED}/max_brightness", "0"))
    s["kbd_color"] = _read(f"{PLATFORM_DEV}/kbd_color")
    s["kbd_effect"], s["kbd_effects"] = _selected(_read(f"{PLATFORM_DEV}/kbd_effect"))
    bat = battery_dir()
    if bat:
        s["charge_start"] = int(_read(f"{bat}/charge_control_start_threshold", "0"))
        s["charge_end"] = int(_read(f"{bat}/charge_control_end_threshold", "100"))
        s["battery_capacity"] = _read(f"{bat}/capacity")
        s["battery_status"] = _read(f"{bat}/status")
    return s


def sensors():
    d = hwmon_dir()
    out = []
    if not d:
        return out
    for i in (1, 2, 3, 4):
        label = _read(f"{d}/fan{i}_label")
        if label is None:
            continue
        rpm = _read(f"{d}/fan{i}_input")
        pwm = _read(f"{d}/pwm{i}")
        temp = _read(f"{d}/temp{i}_input")
        out.append({
            "label": label,
            "rpm": int(rpm) if rpm else None,
            "duty": round(int(pwm) * 100 / 255) if pwm else None,
            "temp": int(temp) // 1000 if temp else None,
        })
    return out


# ---------------------------------------------------------------- escrita

def _privileged(*args):
    if os.geteuid() == 0:
        from . import helper
        return helper.run(list(args))
    r = subprocess.run(["pkexec", HELPER, *map(str, args)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or f"helper falhou ({r.returncode})")
    return r.stdout


def set_profile(name):
    return _privileged("profile", name)


def set_fan_mode(name):
    return _privileged("fan", name)


def set_kbd_brightness(level):
    return _privileged("kbd", int(level))


def set_kbd_color(hexcolor):
    return _privileged("color", hexcolor.lstrip("#"))


def set_kbd_effect(name):
    return _privileged("effect", name)


def set_charge_limits(start, end):
    return _privileged("charge", int(start), int(end))


def run_anti_dust():
    return _privileged("antidust")


# --------------------------------------------- usado pelo helper (root)

def apply(key, value):
    """Escreve diretamente no sysfs (requer root)."""
    if not driver_loaded():
        raise NotLoaded("módulo avell_dchu não carregado")
    if key == "profile":
        _write(PLATFORM_PROFILE, value)
    elif key == "fan":
        _write(f"{PLATFORM_DEV}/fan_mode", value)
    elif key == "kbd":
        _write(f"{KBD_LED}/brightness", value)
    elif key == "color":
        _write(f"{PLATFORM_DEV}/kbd_color", value)
    elif key == "effect":
        _write(f"{PLATFORM_DEV}/kbd_effect", value)
    elif key == "charge":
        bat = battery_dir()
        if not bat:
            raise RuntimeError("bateria sem suporte a limite de carga")
        start, end = value
        # ordem evita start >= end transitório
        cur_end = int(_read(f"{bat}/charge_control_end_threshold", "100"))
        if start >= cur_end:
            _write(f"{bat}/charge_control_end_threshold", end)
            _write(f"{bat}/charge_control_start_threshold", start)
        else:
            _write(f"{bat}/charge_control_start_threshold", start)
            _write(f"{bat}/charge_control_end_threshold", end)
    elif key == "antidust":
        _write(f"{PLATFORM_DEV}/anti_dust", 1)
    else:
        raise ValueError(key)


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_FILE)
