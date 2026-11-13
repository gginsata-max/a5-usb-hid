#!/bin/sh
set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "Hata: install.sh root olarak çalıştırılmalıdır (örn: sudo ./install.sh)" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "=== Samsung Galaxy A5 USB HID Kurulumu Başlıyor ==="

# 1. Betikleri /usr/local/bin dizinine yükle
echo "[1/6] Yürütülebilir dosyalar kopyalanıyor..."
install -m 755 "$SCRIPT_DIR/hidgadget-daemon.py" /usr/local/bin/hidgadget-daemon.py
install -m 755 "$SCRIPT_DIR/hidgadget-restore.sh" /usr/local/bin/hidgadget-restore.sh
install -m 755 "$SCRIPT_DIR/hidgadget-gui.py" /usr/local/bin/hidgadget-gui.py

# 2. Systemd servisini yükle
echo "[2/6] Systemd servisi yükleniyor..."
install -m 644 "$SCRIPT_DIR/hidgadget.service" /etc/systemd/system/hidgadget.service
systemctl daemon-reload

# 3. Polkit ve Sudoers kurallarını yükle
echo "[3/6] Polkit ve Sudoers izin kuralları yapılandırılıyor..."
mkdir -p /etc/polkit-1/rules.d
install -m 644 "$SCRIPT_DIR/50-hidgadget.rules" /etc/polkit-1/rules.d/50-hidgadget.rules

mkdir -p /etc/sudoers.d
install -m 440 "$SCRIPT_DIR/10-hidgadget-sudoers" /etc/sudoers.d/10-hidgadget

# 4. Masaüstü kısayolu ve ikonu yükle
echo "[4/6] Masaüstü kısayolu ve ikonu yükleniyor..."
mkdir -p /usr/share/applications
install -m 644 "$SCRIPT_DIR/org.nura.hidgadget.desktop" /usr/share/applications/org.nura.hidgadget.desktop

mkdir -p /usr/share/icons/hicolor/scalable/apps
install -m 644 "$SCRIPT_DIR/org.nura.hidgadget.svg" /usr/share/icons/hicolor/scalable/apps/org.nura.hidgadget.svg

# 5. Önbellekleri güncelle
echo "[5/6] İkon ve masaüstü önbellekleri yenileniyor..."
gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
update-desktop-database /usr/share/applications 2>/dev/null || true

# 6. Kernel modülü kontrolü
echo "[6/6] usb_f_hid kernel modülü doğrulanıyor..."
modprobe usb_f_hid || true

echo "=== Kurulum Başarıyla Tamamlandı! ==="
echo "Uygulama Phosh menüsünde 'USB HID Kontrol' adıyla listelenecektir."
echo "Terminalden başlatmak için: /usr/local/bin/hidgadget-gui.py"
