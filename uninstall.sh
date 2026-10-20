#!/bin/sh
set -eu
[ "$(id -u)" -eq 0 ] || exec sudo "$0" "$@"
VER=1.0.0
systemctl disable --now avell-cc-restore.service 2>/dev/null || true
modprobe -r avell_dchu 2>/dev/null || true
dkms remove -m avell-dchu -v "$VER" --all 2>/dev/null || true
rm -rf /usr/src/avell-dchu-$VER /usr/lib/avell-cc /usr/libexec/avell-cc /var/lib/avell-cc
rm -f /usr/bin/avellctl /usr/bin/avell-control-center \
      /usr/share/polkit-1/actions/br.com.avell.controlcenter.policy \
      /usr/share/applications/avell-control-center.desktop \
      /etc/systemd/system/avell-cc-restore.service \
      /etc/modules-load.d/avell-dchu.conf
systemctl daemon-reload
echo "Removido."
