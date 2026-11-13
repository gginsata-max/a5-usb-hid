#!/bin/sh
set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "Hata: uninstall.sh root olarak çalıştırılmalıdır (örn: sudo ./uninstall.sh)" >&2
    exit 1
fi

echo "=== Samsung Galaxy A5 USB HID Kaldırma Başlıyor ==="

# 1. Servisi durdur
echo "[1/5] hidgadget servisi durduruluyor..."
systemctl stop hidgadget.service 2>/dev/null || true
systemctl disable hidgadget.service 2>/dev/null || true

# 2. Gadget'ı sök ve USB ağını kesin olarak geri getir
echo "[2/5] USB gadget sökülüyor ve orijinal ağ servisleri geri getiriliyor..."
if [ -x /usr/local/bin/hidgadget-restore.sh ]; then
    /usr/local/bin/hidgadget-restore.sh || true
fi

# 3. Yüklenen dosyaları sil
echo "[3/5] Yüklenen sistem dosyaları temizleniyor..."
rm -f /usr/local/bin/hidgadget-daemon.py
rm -f /usr/local/bin/hidgadget-restore.sh
rm -f /usr/local/bin/hidgadget-gui.py
rm -f /etc/systemd/system/hidgadget.service
rm -f /etc/polkit-1/rules.d/50-hidgadget.rules
rm -f /etc/sudoers.d/10-hidgadget
rm -f /usr/share/applications/org.nura.hidgadget.desktop
rm -f /usr/share/icons/hicolor/scalable/apps/org.nura.hidgadget.svg

# 4. Systemd ve önbellekleri güncelle
echo "[4/5] Systemd ve masaüstü önbellekleri güncelleniyor..."
systemctl daemon-reload
gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
update-desktop-database /usr/share/applications 2>/dev/null || true

# 5. Orijinal ağ servislerini doğrula
echo "[5/5] USB tethering/ağ servisleri kontrol ediliyor..."
systemctl start usb-signaller.service unudhcpd@usb0.service 2>/dev/null || true
sleep 1
nmcli con up "Developer mode" 2>/dev/null || true

echo "=== Kaldırma İşlemi Tamamlandı! Sistem Orijinal Haline Döndü ==="
