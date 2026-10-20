"""avellctl - linha de comando do Avell Control Center para Linux."""

import argparse
import fcntl
import struct
import sys

from . import hw

# struct avell_dchu_call { u32 command; u32 out_len; u64 out_int; u8 in[256]; u8 out[256]; }
_CALL_FMT = "<IIQ256s256s"
_CALL_SIZE = struct.calcsize(_CALL_FMT)
# _IOWR('A', 0x01, struct avell_dchu_call)
_IOC_CALL = (3 << 30) | (_CALL_SIZE << 16) | (ord("A") << 8) | 0x01


def raw_call(command, payload=b""):
    req = struct.pack(_CALL_FMT, command, 0, 0, payload.ljust(256, b"\0"), b"")
    buf = bytearray(req)
    with open("/dev/avell-dchu", "rb", buffering=0) as f:
        fcntl.ioctl(f, _IOC_CALL, buf)
    _, out_len, out_int, _, out = struct.unpack(_CALL_FMT, buf)
    return out_int, out[:out_len]


def cmd_status(_):
    s = hw.status()
    if not s["driver"]:
        print("Driver avell_dchu não carregado. Rode: sudo modprobe avell_dchu")
        return 1
    print(f"EC:              {s.get('ec_version') or 'não informado pelo firmware'}")
    print(f"Recursos:        {s.get('features')}")
    print(f"Modo de energia: {s.get('profile')}  ({' '.join(s['profile_choices'])})")
    print(f"Ventoinhas:      {s.get('fan_mode')}  ({' '.join(s['fan_modes'])})")
    print(f"Teclado:         {s['kbd_type']}", end="")
    if "kbd_brightness" in s:
        print(f"  brilho {s['kbd_brightness']}/{s['kbd_max']}", end="")
    if s.get("kbd_color"):
        print(f"  cor #{s['kbd_color']}  efeito {s.get('kbd_effect')}", end="")
    print()
    if "charge_end" in s:
        print(f"Bateria:         {s['battery_capacity']}% {s['battery_status']}  "
              f"carga entre {s['charge_start']}% e {s['charge_end']}%")
    for f in hw.sensors():
        print(f"  {f['label']:<7} {f['temp']:>3} °C  {f['rpm']:>5} RPM  {f['duty']:>3}%")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="avellctl",
                                description="Avell Control Center para Linux")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("status", help="mostra o estado atual")
    sub.add_parser("sensors", help="temperaturas e ventoinhas")
    x = sub.add_parser("profile", help="modo de energia")
    x.add_argument("name", choices=list(hw.PROFILES))
    x = sub.add_parser("fan", help="modo das ventoinhas")
    x.add_argument("name", choices=list(hw.FAN_MODES))
    x = sub.add_parser("kbd", help="brilho do teclado")
    x.add_argument("level", type=int)
    x = sub.add_parser("color", help="cor do teclado RGB (ex: ff0000)")
    x.add_argument("hex")
    x = sub.add_parser("effect", help="efeito do teclado RGB")
    x.add_argument("name", choices=hw.KBD_EFFECTS)
    x = sub.add_parser("charge", help="limite de carga (FlexiCharger)")
    x.add_argument("start", type=int)
    x.add_argument("end", type=int)
    sub.add_parser("antidust", help="executa limpeza anti-poeira das ventoinhas")
    sub.add_parser("restore", help="reaplica configurações salvas (root)")
    x = sub.add_parser("raw", help="chamada _DSM bruta (root, diagnóstico)")
    x.add_argument("command", type=lambda v: int(v, 0))
    x.add_argument("bytes", nargs="*", type=lambda v: int(v, 0),
                   help="payload, ex: 0x1e")

    a = p.parse_args(argv)
    try:
        if a.cmd in (None, "status"):
            return cmd_status(a)
        if a.cmd == "sensors":
            for f in hw.sensors():
                print(f"{f['label']}: {f['temp']} °C, {f['rpm']} RPM, {f['duty']}%")
        elif a.cmd == "profile":
            hw.set_profile(a.name)
        elif a.cmd == "fan":
            hw.set_fan_mode(a.name)
        elif a.cmd == "kbd":
            hw.set_kbd_brightness(a.level)
        elif a.cmd == "color":
            hw.set_kbd_color(a.hex)
        elif a.cmd == "effect":
            hw.set_kbd_effect(a.name)
        elif a.cmd == "charge":
            hw.set_charge_limits(a.start, a.end)
        elif a.cmd == "antidust":
            hw.run_anti_dust()
        elif a.cmd == "restore":
            from . import helper
            print(helper.run(["restore"]), end="")
        elif a.cmd == "raw":
            out_int, out = raw_call(a.command, bytes(a.bytes))
            print(f"int=0x{out_int:x}")
            for i in range(0, len(out), 16):
                print(f"{i:02x}: " + " ".join(f"{b:02x}" for b in out[i:i + 16]))
    except Exception as e:  # noqa: BLE001
        print(f"erro: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
