#!/usr/bin/env python3
"""
hidgadget-daemon.py - USB HID Keyboard / Mouse / Touchpad Daemon for Samsung Galaxy A5 (Nura OS)
Author: Antigravity
License: GPL-3.0-or-later
"""

import os
import sys
import time
import json
import signal
import struct
import asyncio
import subprocess
from typing import Dict, Set

SOCKET_PATH = "/run/hidgadget.sock"
CONFIGFS_BASE = "/sys/kernel/config/usb_gadget"
GADGET_NAME = "hid1"
GADGET_PATH = os.path.join(CONFIGFS_BASE, GADGET_NAME)
EXTCON_PATH = "/sys/class/extcon/extcon0"

# Standard USB HID Descriptors
KBD_DESC = bytes.fromhex(
    "05010906a101050719e029e715002501750195088102950175088103"
    "95057501050819012905910295017503910395067508150025650507"
    "190029658100c0"
)

MOUSE_DESC = bytes.fromhex(
    "05010902a1010901a100050919012903150025019503750181029501"
    "750581030501093009311581257f75089502810609381581257f7508"
    "95018106c0c0"
)

TOUCH_DESC = bytes.fromhex(
    "050d0904a1010922a100094215002501750195018102093281029506"
    "81030501093015002610277510950181020931150026102775109501"
    "8102c0c0"
)

# Key mapping tables for text input
US_KEYMAP = {
    'a': (0x04, 0), 'b': (0x05, 0), 'c': (0x06, 0), 'd': (0x07, 0),
    'e': (0x08, 0), 'f': (0x09, 0), 'g': (0x0A, 0), 'h': (0x0B, 0),
    'i': (0x0C, 0), 'j': (0x0D, 0), 'k': (0x0E, 0), 'l': (0x0F, 0),
    'm': (0x10, 0), 'n': (0x11, 0), 'o': (0x12, 0), 'p': (0x13, 0),
    'q': (0x14, 0), 'r': (0x15, 0), 's': (0x16, 0), 't': (0x17, 0),
    'u': (0x18, 0), 'v': (0x19, 0), 'w': (0x1A, 0), 'x': (0x1B, 0),
    'y': (0x1C, 0), 'z': (0x1D, 0),
    'A': (0x04, 0x02), 'B': (0x05, 0x02), 'C': (0x06, 0x02), 'D': (0x07, 0x02),
    'E': (0x08, 0x02), 'F': (0x09, 0x02), 'G': (0x0A, 0x02), 'H': (0x0B, 0x02),
    'I': (0x0C, 0x02), 'J': (0x0D, 0x02), 'K': (0x0E, 0x02), 'L': (0x0F, 0x02),
    'M': (0x10, 0x02), 'N': (0x11, 0x02), 'O': (0x12, 0x02), 'P': (0x13, 0x02),
    'Q': (0x14, 0x02), 'R': (0x15, 0x02), 'S': (0x16, 0x02), 'T': (0x17, 0x02),
    'U': (0x18, 0x02), 'V': (0x19, 0x02), 'W': (0x1A, 0x02), 'X': (0x1B, 0x02),
    'Y': (0x1C, 0x02), 'Z': (0x1D, 0x02),
    '1': (0x1E, 0), '2': (0x1F, 0), '3': (0x20, 0), '4': (0x21, 0),
    '5': (0x22, 0), '6': (0x23, 0), '7': (0x24, 0), '8': (0x25, 0),
    '9': (0x26, 0), '0': (0x27, 0),
    '\n': (0x28, 0), '\t': (0x2B, 0), ' ': (0x2C, 0),
    '-': (0x2D, 0), '=': (0x2E, 0), '[': (0x2F, 0), ']': (0x30, 0),
    '\\': (0x31, 0), ';': (0x33, 0), '\'': (0x34, 0), '`': (0x35, 0),
    ',': (0x36, 0), '.': (0x37, 0), '/': (0x38, 0),
    '!': (0x1E, 0x02), '@': (0x1F, 0x02), '#': (0x20, 0x02), '$': (0x21, 0x02),
    '%': (0x22, 0x02), '^': (0x23, 0x02), '&': (0x24, 0x02), '*': (0x25, 0x02),
    '(': (0x26, 0x02), ')': (0x27, 0x02), '_': (0x2D, 0x02), '+': (0x2E, 0x02),
    '{': (0x2F, 0x02), '}': (0x30, 0x02), '|': (0x31, 0x02), ':': (0x33, 0x02),
    '"': (0x34, 0x02), '~': (0x35, 0x02), '<': (0x36, 0x02), '>': (0x37, 0x02),
    '?': (0x38, 0x02),
}

# TR-Q keymapping additions/overrides
TR_KEYMAP = dict(US_KEYMAP)
TR_KEYMAP.update({
    # Turkish specific letters
    'ç': (0x37, 0), 'Ç': (0x37, 0x02),
    'ğ': (0x2F, 0), 'Ğ': (0x2F, 0x02),
    'ı': (0x11, 0), 'I': (0x11, 0x02),
    'i': (0x34, 0), 'İ': (0x34, 0x02),
    'ö': (0x33, 0), 'Ö': (0x33, 0x02),
    'ş': (0x30, 0), 'Ş': (0x30, 0x02),
    '@': (0x14, 0x40), # AltGr + Q
    '€': (0x08, 0x40), # AltGr + E
    '#': (0x20, 0x40), # AltGr + 3
    '$': (0x21, 0x40), # AltGr + 4
})

# Linux Input Event (evdev) to USB HID keycode mapping
# struct input_event: 24 bytes on 64-bit Linux (timeval: 16 bytes, type: u16, code: u16, value: s32)
EV_KEY = 1
EV_SYN = 0

LINUX_TO_HID_MODS = {
    29: 0x01,   # KEY_LEFTCTRL
    42: 0x02,   # KEY_LEFTSHIFT
    56: 0x04,   # KEY_LEFTALT
    125: 0x08,  # KEY_LEFTMETA
    97: 0x10,   # KEY_RIGHTCTRL
    54: 0x20,   # KEY_RIGHTSHIFT
    100: 0x40,  # KEY_RIGHTALT
    126: 0x80,  # KEY_RIGHTMETA
}

LINUX_TO_HID_KEYS = {
    1: 0x29,   # KEY_ESC
    2: 0x1E,   # KEY_1
    3: 0x1F,   # KEY_2
    4: 0x20,   # KEY_3
    5: 0x21,   # KEY_4
    6: 0x22,   # KEY_5
    7: 0x23,   # KEY_6
    8: 0x24,   # KEY_7
    9: 0x25,   # KEY_8
    10: 0x26,  # KEY_9
    11: 0x27,  # KEY_0
    12: 0x2D,  # KEY_MINUS
    13: 0x2E,  # KEY_EQUAL
    14: 0x2A,  # KEY_BACKSPACE
    15: 0x2B,  # KEY_TAB
    16: 0x14,  # KEY_Q
    17: 0x1A,  # KEY_W
    18: 0x08,  # KEY_E
    19: 0x15,  # KEY_R
    20: 0x17,  # KEY_T
    21: 0x1C,  # KEY_Y
    22: 0x18,  # KEY_U
    23: 0x0C,  # KEY_I
    24: 0x12,  # KEY_O
    25: 0x13,  # KEY_P
    26: 0x2F,  # KEY_LEFTBRACE
    27: 0x30,  # KEY_RIGHTBRACE
    28: 0x28,  # KEY_ENTER
    30: 0x04,  # KEY_A
    31: 0x16,  # KEY_S
    32: 0x07,  # KEY_D
    33: 0x09,  # KEY_F
    34: 0x0A,  # KEY_G
    35: 0x0B,  # KEY_H
    36: 0x0D,  # KEY_J
    37: 0x0E,  # KEY_K
    38: 0x0F,  # KEY_L
    39: 0x33,  # KEY_SEMICOLON
    40: 0x34,  # KEY_APOSTROPHE
    41: 0x35,  # KEY_GRAVE
    43: 0x31,  # KEY_BACKSLASH
    44: 0x1D,  # KEY_Z
    45: 0x1B,  # KEY_X
    46: 0x06,  # KEY_C
    47: 0x19,  # KEY_V
    48: 0x05,  # KEY_B
    49: 0x11,  # KEY_N
    50: 0x10,  # KEY_M
    51: 0x36,  # KEY_COMMA
    52: 0x37,  # KEY_DOT
    53: 0x38,  # KEY_SLASH
    55: 0x55,  # KEY_KPASTERISK
    57: 0x2C,  # KEY_SPACE
    58: 0x39,  # KEY_CAPSLOCK
    59: 0x3A,  # KEY_F1
    60: 0x3B,  # KEY_F2
    61: 0x3C,  # KEY_F3
    62: 0x3D,  # KEY_F4
    63: 0x3E,  # KEY_F5
    64: 0x3F,  # KEY_F6
    65: 0x40,  # KEY_F7
    66: 0x41,  # KEY_F8
    67: 0x42,  # KEY_F9
    68: 0x43,  # KEY_F10
    87: 0x44,  # KEY_F11
    88: 0x45,  # KEY_F12
    96: 0x58,  # KEY_KPENTER
    102: 0x4A, # KEY_HOME
    103: 0x52, # KEY_UP
    104: 0x4B, # KEY_PAGEUP
    105: 0x50, # KEY_LEFT
    106: 0x4F, # KEY_RIGHT
    107: 0x4D, # KEY_END
    108: 0x51, # KEY_DOWN
    109: 0x4E, # KEY_PAGEDOWN
    110: 0x49, # KEY_INSERT
    111: 0x4C, # KEY_DELETE
}

class HIDDaemon:
    def __init__(self):
        self.running = False
        self._shutdown_done = False
        self.udc_name = "ci_hdrc.0"
        self.dev_kbd = None
        self.dev_mouse = None
        self.dev_touch = None
        self.active_keys: Set[int] = set()
        self.active_mods: int = 0
        self.active_mouse_btn: int = 0
        self.touch_down: bool = False
        self.server = None
        self.evdev_fds: Dict[str, int] = {}
        self.evdev_task = None

    def find_udc(self) -> str:
        udcs = os.listdir("/sys/class/udc")
        if udcs:
            return udcs[0]
        return "ci_hdrc.0"

    def ensure_module(self):
        try:
            with open("/proc/modules", "r") as f:
                if "usb_f_hid" in f.read():
                    return
        except Exception:
            pass
        subprocess.run(["modprobe", "usb_f_hid"], check=True)

    def stop_usb_networking(self):
        # Conflicts= in systemd already stops them, but double-check UDCs
        if os.path.exists(CONFIGFS_BASE):
            for entry in os.listdir(CONFIGFS_BASE):
                if entry == GADGET_NAME:
                    continue
                udc_file = os.path.join(CONFIGFS_BASE, entry, "UDC")
                if os.path.isfile(udc_file):
                    try:
                        with open(udc_file, "r") as f:
                            content = f.read().strip()
                        if content:
                            with open(udc_file, "w") as f:
                                f.write("\n")
                    except Exception as e:
                        print(f"Warning clearing UDC for {entry}: {e}")

    def create_gadget(self):
        self.ensure_module()
        self.stop_usb_networking()
        self.udc_name = self.find_udc()
        print(f"Setting up HID gadget '{GADGET_NAME}' on UDC '{self.udc_name}'...")

        os.makedirs(GADGET_PATH, exist_ok=True)
        with open(os.path.join(GADGET_PATH, "idVendor"), "w") as f: f.write("0x1d6b\n")
        with open(os.path.join(GADGET_PATH, "idProduct"), "w") as f: f.write("0x0104\n")
        with open(os.path.join(GADGET_PATH, "bcdDevice"), "w") as f: f.write("0x0100\n")
        with open(os.path.join(GADGET_PATH, "bcdUSB"), "w") as f: f.write("0x0200\n")

        s_dir = os.path.join(GADGET_PATH, "strings", "0x409")
        os.makedirs(s_dir, exist_ok=True)
        with open(os.path.join(s_dir, "serialnumber"), "w") as f: f.write("A5_HID_01\n")
        with open(os.path.join(s_dir, "manufacturer"), "w") as f: f.write("Samsung\n")
        with open(os.path.join(s_dir, "product"), "w") as f: f.write("Galaxy A5 HID Device\n")

        c_dir = os.path.join(GADGET_PATH, "configs", "c.1")
        os.makedirs(os.path.join(c_dir, "strings", "0x409"), exist_ok=True)
        with open(os.path.join(c_dir, "strings", "0x409", "configuration"), "w") as f:
            f.write("Config 1: HID Composite\n")
        with open(os.path.join(c_dir, "MaxPower"), "w") as f: f.write("250\n")

        # 1. Keyboard
        kbd_func = os.path.join(GADGET_PATH, "functions", "hid.kbd")
        os.makedirs(kbd_func, exist_ok=True)
        with open(os.path.join(kbd_func, "protocol"), "w") as f: f.write("1\n")
        with open(os.path.join(kbd_func, "subclass"), "w") as f: f.write("1\n")
        with open(os.path.join(kbd_func, "report_length"), "w") as f: f.write("8\n")
        with open(os.path.join(kbd_func, "report_desc"), "wb") as f: f.write(KBD_DESC)

        # 2. Mouse
        mouse_func = os.path.join(GADGET_PATH, "functions", "hid.mouse")
        os.makedirs(mouse_func, exist_ok=True)
        with open(os.path.join(mouse_func, "protocol"), "w") as f: f.write("2\n")
        with open(os.path.join(mouse_func, "subclass"), "w") as f: f.write("1\n")
        with open(os.path.join(mouse_func, "report_length"), "w") as f: f.write("4\n")
        with open(os.path.join(mouse_func, "report_desc"), "wb") as f: f.write(MOUSE_DESC)

        # 3. Touch
        touch_func = os.path.join(GADGET_PATH, "functions", "hid.touch")
        os.makedirs(touch_func, exist_ok=True)
        with open(os.path.join(touch_func, "protocol"), "w") as f: f.write("0\n")
        with open(os.path.join(touch_func, "subclass"), "w") as f: f.write("0\n")
        with open(os.path.join(touch_func, "report_length"), "w") as f: f.write("5\n")
        with open(os.path.join(touch_func, "report_desc"), "wb") as f: f.write(TOUCH_DESC)

        # Link functions
        for name in ["hid.kbd", "hid.mouse", "hid.touch"]:
            target = os.path.join(GADGET_PATH, "functions", name)
            link = os.path.join(c_dir, name)
            if not os.path.exists(link):
                os.symlink(target, link)

        # Bind to UDC
        with open(os.path.join(GADGET_PATH, "UDC"), "w") as f:
            f.write(f"{self.udc_name}\n")

        print("Gadget bound to UDC successfully.")
        # Settle devices
        time.sleep(0.2)
        self.dev_kbd = "/dev/hidg0"
        self.dev_mouse = "/dev/hidg1"
        self.dev_touch = "/dev/hidg2"

    def remove_gadget(self):
        print(f"Removing HID gadget '{GADGET_NAME}'...")
        c_dir = os.path.join(GADGET_PATH, "configs", "c.1")
        try:
            udc_f = os.path.join(GADGET_PATH, "UDC")
            if os.path.exists(udc_f):
                with open(udc_f, "w") as f:
                    f.write("\n")
        except Exception as e:
            print(f"Error unbinding UDC: {e}")

        # Unlink functions
        for name in ["hid.kbd", "hid.mouse", "hid.touch"]:
            link = os.path.join(c_dir, name)
            if os.path.islink(link) or os.path.exists(link):
                try: os.unlink(link)
                except Exception: pass

        # Remove config strings & dir
        s_c = os.path.join(c_dir, "strings", "0x409")
        if os.path.exists(s_c):
            try: os.rmdir(s_c)
            except Exception: pass
        if os.path.exists(c_dir):
            try: os.rmdir(c_dir)
            except Exception: pass

        # Remove functions
        for name in ["hid.kbd", "hid.mouse", "hid.touch"]:
            f_dir = os.path.join(GADGET_PATH, "functions", name)
            if os.path.exists(f_dir):
                try: os.rmdir(f_dir)
                except Exception: pass

        # Remove strings & gadget dir
        s_g = os.path.join(GADGET_PATH, "strings", "0x409")
        if os.path.exists(s_g):
            try: os.rmdir(s_g)
            except Exception: pass
        if os.path.exists(GADGET_PATH):
            try: os.rmdir(GADGET_PATH)
            except Exception: pass

        print("Restoring USB networking...")
        subprocess.run(["systemctl", "start", "usb-signaller", "unudhcpd@usb0"], check=False)
        time.sleep(0.5)
        # Ensure Developer mode or usb0 gets IP
        subprocess.run(["nmcli", "con", "up", "Developer mode"], check=False)
        print("Restoration complete.")

    def write_hid(self, device_path: str, data: bytes) -> bool:
        try:
            fd = os.open(device_path, os.O_WRONLY | os.O_NONBLOCK)
            try:
                os.write(fd, data)
                return True
            finally:
                os.close(fd)
        except OSError as e:
            # Errno 108: Cannot send after socket shutdown (Host not connected / suspended)
            # Errno 11: EAGAIN
            # Errno 19: ENODEV
            return False

    def handle_key(self, code: int, mods: int, down: bool):
        self.active_mods = mods
        if down:
            if code != 0:
                self.active_keys.add(code)
        else:
            if code == 0:
                self.active_keys.clear()
            else:
                self.active_keys.discard(code)

        # 8-byte report: [mods, 0, key1, key2, key3, key4, key5, key6]
        report = bytearray(8)
        report[0] = self.active_mods & 0xFF
        keys_list = list(self.active_keys)[:6]
        for i, k in enumerate(keys_list):
            report[2 + i] = k & 0xFF

        self.write_hid(self.dev_kbd, bytes(report))

    def handle_text(self, text: str, layout: str = "tr"):
        keymap = TR_KEYMAP if layout == "tr" else US_KEYMAP
        for ch in text:
            if ch in keymap:
                code, mods = keymap[ch]
                # Press
                rep = bytearray(8)
                rep[0] = mods
                rep[2] = code
                self.write_hid(self.dev_kbd, bytes(rep))
                time.sleep(0.01)
                # Release
                self.write_hid(self.dev_kbd, bytes(8))
                time.sleep(0.01)
            else:
                # Unsupported character, skip
                pass

    def handle_mouse(self, dx: int, dy: int, btn: int, wheel: int):
        self.active_mouse_btn = btn
        # 4-byte report: [btn, dx, dy, wheel] (signed 8-bit ints)
        def to_s8(val):
            return max(-127, min(127, val)) & 0xFF

        report = bytes([
            btn & 0x07,
            to_s8(dx),
            to_s8(dy),
            to_s8(wheel)
        ])
        self.write_hid(self.dev_mouse, report)

    def handle_touch(self, x: int, y: int, down: bool):
        self.touch_down = down
        # 5-byte report: [flags, x_lo, x_hi, y_lo, y_hi]
        # flags: bit 0: Tip Switch (1=down), bit 1: In Range (1=in range)
        flags = 0x03 if down else 0x00
        x_clamped = max(0, min(10000, x))
        y_clamped = max(0, min(10000, y))
        report = bytes([
            flags,
            x_clamped & 0xFF,
            (x_clamped >> 8) & 0xFF,
            y_clamped & 0xFF,
            (y_clamped >> 8) & 0xFF
        ])
        self.write_hid(self.dev_touch, report)

    def check_extcon_host(self) -> bool:
        host_cable = os.path.join(EXTCON_PATH, "cable.1", "state")
        if os.path.exists(host_cable):
            try:
                with open(host_cable, "r") as f:
                    return f.read().strip() == "1"
            except Exception:
                pass
        return False

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        buffer = ""
        try:
            while self.running:
                data = await reader.readline()
                if not data:
                    break
                line = data.decode('utf-8', errors='replace').strip()
                if not line:
                    continue

                try:
                    cmd = json.loads(line)
                    t = cmd.get("t")

                    if t == "ping":
                        resp = {"ok": True, "status": "active", "host_otg": self.check_extcon_host()}
                        writer.write((json.dumps(resp) + "\n").encode('utf-8'))
                        await writer.drain()

                    elif t == "key":
                        code = int(cmd.get("code", 0))
                        mods = int(cmd.get("mods", 0))
                        down = bool(cmd.get("down", False))
                        self.handle_key(code, mods, down)

                    elif t == "text":
                        text = str(cmd.get("text", ""))
                        layout = str(cmd.get("layout", "tr"))
                        self.handle_text(text, layout)

                    elif t == "mouse":
                        dx = int(cmd.get("dx", 0))
                        dy = int(cmd.get("dy", 0))
                        btn = int(cmd.get("btn", self.active_mouse_btn))
                        wheel = int(cmd.get("wheel", 0))
                        self.handle_mouse(dx, dy, btn, wheel)

                    elif t == "touch":
                        x = int(cmd.get("x", 0))
                        y = int(cmd.get("y", 0))
                        down = bool(cmd.get("down", False))
                        self.handle_touch(x, y, down)

                except json.JSONDecodeError:
                    pass
                except Exception as e:
                    print(f"Error executing command: {e}")

        except asyncio.CancelledError:
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def extcon_monitor(self):
        while self.running:
            if self.check_extcon_host():
                print("WARNING: USB OTG Host mode detected on extcon0! Shutting down HID gadget.")
                self.running = False
                break
            await asyncio.sleep(1.0)

    def on_evdev_data_ready(self, fd: int):
        # Read 24-byte input_event struct(s)
        try:
            while True:
                data = os.read(fd, 24)
                if not data or len(data) < 24:
                    break
                # struct input_event: timeval (16 bytes), type (H), code (H), value (i)
                sec, usec, ev_type, ev_code, ev_val = struct.unpack("qqHHi", data)
                if ev_type == EV_KEY:
                    # Modifier key
                    if ev_code in LINUX_TO_HID_MODS:
                        mod_bit = LINUX_TO_HID_MODS[ev_code]
                        if ev_val == 1 or ev_val == 2:  # Press or Repeat
                            self.active_mods |= mod_bit
                        elif ev_val == 0:  # Release
                            self.active_mods &= ~mod_bit
                        self.handle_key(0, self.active_mods, False)
                    # Normal key
                    elif ev_code in LINUX_TO_HID_KEYS:
                        hid_key = LINUX_TO_HID_KEYS[ev_code]
                        if ev_val == 1 or ev_val == 2:  # Press or Repeat
                            self.handle_key(hid_key, self.active_mods, True)
                        elif ev_val == 0:  # Release
                            self.handle_key(hid_key, self.active_mods, False)
        except BlockingIOError:
            pass
        except Exception as e:
            print(f"Error reading evdev: {e}")

    async def evdev_monitor(self):
        loop = asyncio.get_running_loop()
        while self.running:
            import glob
            dev_paths = glob.glob("/dev/input/event*")
            for dev in dev_paths:
                if dev not in self.evdev_fds:
                    # Ignore touchscreens, vibrators, hall sensors
                    # We check /proc/bus/input/devices or device name
                    try:
                        fd = os.open(dev, os.O_RDONLY | os.O_NONBLOCK)
                        # We register file descriptor for reading
                        loop.add_reader(fd, self.on_evdev_data_ready, fd)
                        self.evdev_fds[dev] = fd
                        print(f"Hooked input device: {dev}")
                    except Exception as e:
                        pass
            await asyncio.sleep(2.0)

    async def run(self):
        self.running = True
        self.create_gadget()

        if os.path.exists(SOCKET_PATH):
            try: os.unlink(SOCKET_PATH)
            except Exception: pass

        self.server = await asyncio.start_unix_server(self.handle_client, path=SOCKET_PATH)
        # Set permissions: rw-rw---- and chown to root:user (10000)
        try:
            os.chmod(SOCKET_PATH, 0o660)
            os.chown(SOCKET_PATH, 0, 10000)
        except Exception as e:
            print(f"Failed setting socket permissions: {e}")

        print(f"HID Daemon listening on {SOCKET_PATH}")

        monitor_task = asyncio.create_task(self.extcon_monitor())
        self.evdev_task = asyncio.create_task(self.evdev_monitor())
        try:
            async with self.server:
                while self.running:
                    await asyncio.sleep(0.5)
        finally:
            monitor_task.cancel()
            if self.evdev_task:
                self.evdev_task.cancel()
            self.shutdown()

    def shutdown(self):
        if self._shutdown_done:
            return
        self._shutdown_done = True
        self.running = False

        # Remove readers and close evdev fds
        try:
            loop = asyncio.get_running_loop()
            for fd in self.evdev_fds.values():
                try:
                    loop.remove_reader(fd)
                    os.close(fd)
                except Exception:
                    pass
        except Exception:
            for fd in self.evdev_fds.values():
                try: os.close(fd)
                except Exception: pass
        self.evdev_fds.clear()

        if os.path.exists(SOCKET_PATH):
            try: os.unlink(SOCKET_PATH)
            except Exception: pass
        self.remove_gadget()


def main():
    if os.geteuid() != 0:
        print("Error: hidgadget-daemon must be run as root.", file=sys.stderr)
        sys.exit(1)

    daemon = HIDDaemon()

    def sig_handler(sig, frame):
        print(f"Received signal {sig}, exiting...")
        daemon.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    try:
        asyncio.run(daemon.run())
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        daemon.shutdown()

if __name__ == "__main__":
    main()
