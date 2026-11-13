#!/bin/sh
# hidgadget-restore.sh - Guarantees clean state and restoration of USB networking
# Can be run anytime to safely teardown hid1 and bring back usb-signaller / usb0.

set -e

echo "[hidgadget-restore] Starting emergency/clean restoration..."

# 1. Clean socket
rm -f /run/hidgadget.sock

# 2. Check and teardown hid1 gadget if still present
GADGET="/sys/kernel/config/usb_gadget/hid1"
if [ -d "$GADGET" ]; then
    echo "[hidgadget-restore] Cleaning $GADGET..."
    if [ -f "$GADGET/UDC" ]; then
        echo "" > "$GADGET/UDC" || true
    fi

    # Unlink functions from config
    for f in "$GADGET"/configs/c.1/hid.*; do
        if [ -L "$f" ] || [ -e "$f" ]; then
            rm -f "$f" || true
        fi
    done

    # Remove strings & configs
    rmdir "$GADGET/configs/c.1/strings/0x409" 2>/dev/null || true
    rmdir "$GADGET/configs/c.1" 2>/dev/null || true

    # Remove functions
    for f in "$GADGET"/functions/hid.*; do
        if [ -d "$f" ]; then
            rmdir "$f" 2>/dev/null || true
        fi
    done

    # Remove gadget strings & base dir
    rmdir "$GADGET/strings/0x409" 2>/dev/null || true
    rmdir "$GADGET" 2>/dev/null || true
fi

# 3. Ensure usb-signaller and unudhcpd are running
systemctl start usb-signaller.service unudhcpd@usb0.service 2>/dev/null || true

# 4. Give usb-signaller 1 second to create ncm interface, then activate Developer mode connection
sleep 1
nmcli con up "Developer mode" 2>/dev/null || true

echo "[hidgadget-restore] USB restoration finished."
exit 0
