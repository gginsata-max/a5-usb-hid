#!/usr/bin/env python3
"""
hidgadget-gui.py - Mobile-friendly GTK4 / Libadwaita Interface for USB HID Mode
Target: Samsung Galaxy A5 (Nura OS, Phosh, 720x1280)
Author: Antigravity
License: GPL-3.0-or-later
"""

import os
import sys
import json
import time
import socket
import subprocess
import threading

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gdk

SOCKET_PATH = "/run/hidgadget.sock"

# HID Key Codes for the GUI Keypad
HID_KEYCODES = {
    'ESC': 0x29, 'TAB': 0x2B, 'ENTER': 0x28, 'BACKSPACE': 0x2A, 'DEL': 0x4C,
    'SPACE': 0x2C, 'INS': 0x49, 'HOME': 0x4A, 'END': 0x4D, 'PGUP': 0x4B, 'PGDN': 0x4E,
    'UP': 0x52, 'DOWN': 0x51, 'LEFT': 0x50, 'RIGHT': 0x4F,
    'F1': 0x3A, 'F2': 0x3B, 'F3': 0x3C, 'F4': 0x3D, 'F5': 0x3E, 'F6': 0x3F,
    'F7': 0x40, 'F8': 0x41, 'F9': 0x42, 'F10': 0x43, 'F11': 0x44, 'F12': 0x45,
}

# Special keyval mapping to HID code
GDK_SPECIAL_KEYS = {
    Gdk.KEY_BackSpace: 0x2A,
    Gdk.KEY_Return: 0x28,
    Gdk.KEY_KP_Enter: 0x58,
    Gdk.KEY_Tab: 0x2B,
    Gdk.KEY_ISO_Left_Tab: 0x2B,
    Gdk.KEY_Escape: 0x29,
    Gdk.KEY_Delete: 0x4C,
    Gdk.KEY_Home: 0x4A,
    Gdk.KEY_End: 0x4D,
    Gdk.KEY_Page_Up: 0x4B,
    Gdk.KEY_Page_Down: 0x4E,
    Gdk.KEY_Up: 0x52,
    Gdk.KEY_Down: 0x51,
    Gdk.KEY_Left: 0x50,
    Gdk.KEY_Right: 0x4F,
    Gdk.KEY_space: 0x2C,
}

MODIFIERS = {
    'CTRL': 0x01,
    'SHIFT': 0x02,
    'ALT': 0x04,
    'SUPER': 0x08,
}

class HIDClient:
    def __init__(self):
        self.sock = None
        self.lock = threading.Lock()

    def connect(self) -> bool:
        with self.lock:
            if self.sock:
                try:
                    self.sock.close()
                except Exception:
                    pass
                self.sock = None

            if not os.path.exists(SOCKET_PATH):
                return False

            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.settimeout(0.5)
                s.connect(SOCKET_PATH)
                self.sock = s
                return True
            except Exception as e:
                self.sock = None
                return False

    def is_connected(self) -> bool:
        with self.lock:
            return self.sock is not None

    def send_cmd(self, cmd: dict) -> bool:
        with self.lock:
            if not self.sock:
                return False
            try:
                msg = (json.dumps(cmd) + "\n").encode('utf-8')
                self.sock.sendall(msg)
                return True
            except Exception:
                try:
                    self.sock.close()
                except Exception:
                    pass
                self.sock = None
                return False

    def close(self):
        with self.lock:
            if self.sock:
                try:
                    self.sock.close()
                except Exception:
                    pass
                self.sock = None


class HIDApplication(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.nura.hidgadget", flags=0)
        self.client = HIDClient()
        self.is_service_active = False
        self.active_mods = 0
        self.active_mouse_btn = 0
        self.is_dragging = False
        self.last_drag_x = 0
        self.last_drag_y = 0

    def do_activate(self):
        win = Adw.ApplicationWindow(application=self)
        win.set_title("USB HID Kontrol")
        win.set_default_size(360, 640)

        # Main Layout Box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # HeaderBar
        header = Adw.HeaderBar()
        title_widget = Adw.WindowTitle(title="USB HID Kontrol", subtitle="Galaxy A5")
        header.set_title_widget(title_widget)
        main_box.append(header)

        # Top Master Card (Toggle & Status)
        top_group = Adw.PreferencesGroup()
        top_group.set_margin_start(12)
        top_group.set_margin_end(12)
        top_group.set_margin_top(8)
        top_group.set_margin_bottom(8)

        self.master_row = Adw.ActionRow(title="USB HID Modu", subtitle="Klavye ve Fare taklit et")
        self.master_switch = Gtk.Switch()
        self.master_switch.set_valign(Gtk.Align.CENTER)
        self.master_switch.connect("state-set", self.on_master_switch_toggled)
        self.master_row.add_suffix(self.master_switch)
        top_group.add(self.master_row)

        self.status_label = Gtk.Label(label="Durum: Servis Kapalı (USB Ağı Aktif)")
        self.status_label.add_css_class("dim-label")
        self.status_label.set_margin_top(4)
        top_group.add(self.status_label)

        main_box.append(top_group)

        # View Stack & Switcher (Touchpad, Dokunmatik, Klavye)
        self.stack = Adw.ViewStack()
        self.stack.set_vexpand(True)

        # 1. Touchpad Page
        touchpad_page = self.build_touchpad_page()
        self.stack.add_titled_with_icon(touchpad_page, "touchpad", "Touchpad", "input-mouse-symbolic")

        # 2. Absolute Touchscreen Page
        touch_page = self.build_touch_page()
        self.stack.add_titled_with_icon(touch_page, "touch", "Dokunmatik", "input-touchpad-symbolic")

        # 3. Keyboard Page
        kbd_page = self.build_keyboard_page()
        self.stack.add_titled_with_icon(kbd_page, "keyboard", "Klavye", "input-keyboard-symbolic")

        # View Switcher Bar at the bottom
        switcher_bar = Adw.ViewSwitcherBar(stack=self.stack)
        switcher_bar.set_reveal(True)

        main_box.append(self.stack)
        main_box.append(switcher_bar)

        win.set_content(main_box)
        win.present()

        # Timer to monitor service status
        GLib.timeout_add_seconds(1, self.check_service_status)
        self.check_service_status()

    # --- Touchpad Page ---
    def build_touchpad_page(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_bottom(8)

        # Touchpad Area Canvas
        self.touchpad_area = Gtk.DrawingArea()
        self.touchpad_area.set_vexpand(True)
        self.touchpad_area.set_hexpand(True)
        self.touchpad_area.add_css_class("card")
        self.touchpad_area.set_draw_func(self.draw_touchpad_placeholder)

        # Gestures for Touchpad
        # 1. Drag Gesture (Movement)
        drag_gesture = Gtk.GestureDrag.new()
        drag_gesture.connect("drag-begin", self.on_touchpad_drag_begin)
        drag_gesture.connect("drag-update", self.on_touchpad_drag_update)
        drag_gesture.connect("drag-end", self.on_touchpad_drag_end)
        self.touchpad_area.add_controller(drag_gesture)

        # 2. Click / Tap Gesture (Left & Right click)
        click_gesture = Gtk.GestureClick.new()
        click_gesture.set_button(0) # All buttons
        click_gesture.connect("pressed", self.on_touchpad_click)
        self.touchpad_area.add_controller(click_gesture)

        # 3. Scroll Controller (Two-finger scroll wheel)
        scroll_flags = Gtk.EventControllerScrollFlags.VERTICAL | Gtk.EventControllerScrollFlags.HORIZONTAL
        scroll_controller = Gtk.EventControllerScroll.new(scroll_flags)
        scroll_controller.connect("scroll", self.on_touchpad_scroll)
        self.touchpad_area.add_controller(scroll_controller)

        # 4. Long Press Gesture (Drag-and-Drop)
        long_press = Gtk.GestureLongPress.new()
        long_press.connect("pressed", self.on_touchpad_long_press)
        self.touchpad_area.add_controller(long_press)

        box.append(self.touchpad_area)

        # Physical Buttons Bar (Sol, Orta, Sağ)
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_box.set_homogeneous(True)

        left_btn = Gtk.Button(label="Sol Tık")
        left_btn.add_css_class("pill")
        left_btn.connect("clicked", lambda b: self.send_mouse_click(1))

        mid_btn = Gtk.Button(label="Orta")
        mid_btn.add_css_class("pill")
        mid_btn.connect("clicked", lambda b: self.send_mouse_click(4))

        right_btn = Gtk.Button(label="Sağ Tık")
        right_btn.add_css_class("pill")
        right_btn.connect("clicked", lambda b: self.send_mouse_click(2))

        btn_box.append(left_btn)
        btn_box.append(mid_btn)
        btn_box.append(right_btn)
        box.append(btn_box)

        return box

    def draw_touchpad_placeholder(self, area, cr, width, height):
        # Draw background and instructions
        cr.set_source_rgb(0.12, 0.12, 0.14)
        cr.paint()
        cr.set_source_rgb(0.5, 0.5, 0.5)
        cr.set_font_size(14)
        text = "Touchpad Alanı\n\n• Sürükle: Fare Hareketi\n• Tek Dokun: Sol Tık\n• Çift Parmak: Sağ Tık\n• Kaydır: Tekerlek (Scroll)\n• Uzun Bas: Sürükle-Bırak"
        lines = text.split('\n')
        y = height / 2 - (len(lines) * 10)
        for line in lines:
            extents = cr.text_extents(line)
            x = (width - extents.width) / 2
            cr.move_to(x, y)
            cr.show_text(line)
            y += 22

    def on_touchpad_drag_begin(self, gesture, start_x, start_y):
        self.last_drag_x = start_x
        self.last_drag_y = start_y

    def on_touchpad_drag_update(self, gesture, offset_x, offset_y):
        cur_x = gesture.get_start_point()[1] + offset_x
        cur_y = gesture.get_start_point()[2] + offset_y
        dx = cur_x - self.last_drag_x
        dy = cur_y - self.last_drag_y
        self.last_drag_x = cur_x
        self.last_drag_y = cur_y

        # Scale sensitivity
        scale = 1.8
        sdx = int(dx * scale)
        sdy = int(dy * scale)
        if sdx != 0 or sdy != 0:
            btn = 1 if self.is_dragging else 0
            self.client.send_cmd({"t": "mouse", "dx": sdx, "dy": sdy, "btn": btn, "wheel": 0})

    def on_touchpad_drag_end(self, gesture, offset_x, offset_y):
        if self.is_dragging:
            self.is_dragging = False
            self.client.send_cmd({"t": "mouse", "dx": 0, "dy": 0, "btn": 0, "wheel": 0})

    def on_touchpad_click(self, gesture, n_press, x, y):
        btn = gesture.get_current_button()
        # Default button 1 (left) or 3 (right)
        btn_code = 2 if btn == 3 else 1
        self.send_mouse_click(btn_code)

    def on_touchpad_scroll(self, controller, dx, dy):
        wheel = int(-dy * 5)
        if wheel != 0:
            self.client.send_cmd({"t": "mouse", "dx": 0, "dy": 0, "btn": 0, "wheel": wheel})
        return True

    def on_touchpad_long_press(self, gesture, x, y):
        self.is_dragging = True
        self.client.send_cmd({"t": "mouse", "dx": 0, "dy": 0, "btn": 1, "wheel": 0})

    def send_mouse_click(self, btn_code: int):
        def _click_thread():
            self.client.send_cmd({"t": "mouse", "dx": 0, "dy": 0, "btn": btn_code, "wheel": 0})
            time.sleep(0.04)
            self.client.send_cmd({"t": "mouse", "dx": 0, "dy": 0, "btn": 0, "wheel": 0})
        threading.Thread(target=_click_thread, daemon=True).start()

    # --- Absolute Touch Page ---
    def build_touch_page(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_bottom(8)

        # Resolution Preferences
        res_group = Adw.PreferencesGroup()
        res_row = Adw.ActionRow(title="Hedef Ekran Çözünürlüğü")
        self.res_entry = Gtk.Entry(text="1920x1080")
        self.res_entry.set_valign(Gtk.Align.CENTER)
        self.res_entry.set_size_request(100, -1)
        res_row.add_suffix(self.res_entry)
        res_group.add(res_row)
        box.append(res_group)

        # Absolute Touch Canvas
        self.touch_canvas = Gtk.DrawingArea()
        self.touch_canvas.set_vexpand(True)
        self.touch_canvas.set_hexpand(True)
        self.touch_canvas.add_css_class("card")
        self.touch_canvas.set_draw_func(self.draw_touch_canvas)

        drag_touch = Gtk.GestureDrag.new()
        drag_touch.connect("drag-begin", self.on_touch_canvas_begin)
        drag_touch.connect("drag-update", self.on_touch_canvas_update)
        drag_touch.connect("drag-end", self.on_touch_canvas_end)
        self.touch_canvas.add_controller(drag_touch)

        box.append(self.touch_canvas)
        return box

    def draw_touch_canvas(self, area, cr, width, height):
        cr.set_source_rgb(0.08, 0.12, 0.16)
        cr.paint()
        cr.set_source_rgb(0.4, 0.6, 0.8)
        cr.set_line_width(2)
        cr.rectangle(10, 10, width - 20, height - 20)
        cr.stroke()

        cr.set_font_size(14)
        text = "Mutlak Dokunmatik Alan\n(Ekran Oranı: 10000x10000)"
        lines = text.split('\n')
        y = height / 2 - 10
        for line in lines:
            extents = cr.text_extents(line)
            x = (width - extents.width) / 2
            cr.move_to(x, y)
            cr.show_text(line)
            y += 20

    def on_touch_canvas_begin(self, gesture, start_x, start_y):
        self.send_absolute_touch(start_x, start_y, down=True)

    def on_touch_canvas_update(self, gesture, offset_x, offset_y):
        cur_x = gesture.get_start_point()[1] + offset_x
        cur_y = gesture.get_start_point()[2] + offset_y
        self.send_absolute_touch(cur_x, cur_y, down=True)

    def on_touch_canvas_end(self, gesture, offset_x, offset_y):
        cur_x = gesture.get_start_point()[1] + offset_x
        cur_y = gesture.get_start_point()[2] + offset_y
        self.send_absolute_touch(cur_x, cur_y, down=False)

    def send_absolute_touch(self, px: float, py: float, down: bool):
        w = max(1.0, float(self.touch_canvas.get_width()))
        h = max(1.0, float(self.touch_canvas.get_height()))
        x_norm = max(0.0, min(1.0, px / w))
        y_norm = max(0.0, min(1.0, py / h))
        tx = int(x_norm * 10000)
        ty = int(y_norm * 10000)
        self.client.send_cmd({"t": "touch", "x": tx, "y": ty, "down": down})

    # --- Keyboard Page ---
    def build_keyboard_page(self) -> Gtk.Widget:
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(8)
        box.set_margin_bottom(12)

        # Layout selector & Metin Yaz/Gönder Group
        pref_group = Adw.PreferencesGroup()
        layout_row = Adw.ComboRow(title="Hedef Klavye Düzeni")
        layout_model = Gtk.StringList.new(["Türkçe Q (TR-Q)", "İngilizce (US)"])
        layout_row.set_model(layout_model)
        layout_row.set_selected(0)
        self.layout_row = layout_row
        pref_group.add(layout_row)
        box.append(pref_group)

        # Canlı Yazım Alanı (Live Typing Input)
        live_group = Adw.PreferencesGroup(title="Canlı Klavye Girişi", description="Buraya bastığınız her tuş ve ekran klavyesi anında karşı cihaza iletilir")
        live_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        self.live_entry = Gtk.Entry()
        self.live_entry.set_placeholder_text("Canlı yazmak için buraya dokunun...")
        self.live_entry.set_hexpand(True)
        self.live_entry.add_css_class("card")
        self.live_entry.set_size_request(-1, 48)

        # Connect buffer insertion and deletion
        self._suppress_live_buffer = False
        live_buf = self.live_entry.get_buffer()
        live_buf.connect("inserted-text", self.on_live_text_inserted)
        live_buf.connect("deleted-text", self.on_live_text_deleted)

        # Connect hardware / physical key controller
        key_controller = Gtk.EventControllerKey.new()
        key_controller.connect("key-pressed", self.on_live_key_pressed)
        self.live_entry.add_controller(key_controller)

        live_card.append(self.live_entry)
        live_group.add(live_card)
        box.append(live_group)

        # Toplu Metin Gönderimi (Batch Text Box)
        batch_expander = Adw.ExpanderRow(title="Toplu Metin Gönderimi (Hazır Mesaj)")
        text_card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        text_card.set_margin_top(8)
        text_card.set_margin_bottom(8)
        self.text_entry = Gtk.Entry()
        self.text_entry.set_placeholder_text("Uzun metin yapıştırıp tek seferde gönderin...")
        self.text_entry.set_hexpand(True)
        self.text_entry.connect("activate", self.on_send_text_clicked)

        send_btn = Gtk.Button(label="Gönder")
        send_btn.add_css_class("suggested-action")
        send_btn.connect("clicked", self.on_send_text_clicked)

        text_card.append(self.text_entry)
        text_card.append(send_btn)
        batch_expander.add_row(text_card)

        pref_batch = Adw.PreferencesGroup()
        pref_batch.add(batch_expander)
        box.append(pref_batch)

        # Modifier Keys Row (Toggleable buttons)
        mod_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        mod_box.set_homogeneous(True)
        self.ctrl_toggle = Gtk.ToggleButton(label="Ctrl")
        self.alt_toggle = Gtk.ToggleButton(label="Alt")
        self.shift_toggle = Gtk.ToggleButton(label="Shift")
        self.super_toggle = Gtk.ToggleButton(label="Win")

        for t in [self.ctrl_toggle, self.alt_toggle, self.shift_toggle, self.super_toggle]:
            t.connect("toggled", self.on_modifier_toggled)
            mod_box.append(t)
        box.append(mod_box)

        # Common Action Keys Row 1
        r1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        r1.set_homogeneous(True)
        r1.append(self.make_key_btn("Esc", "ESC"))
        r1.append(self.make_key_btn("Tab", "TAB"))
        r1.append(self.make_key_btn("⌫ Sil", "BACKSPACE"))
        r1.append(self.make_key_btn("↵ Enter", "ENTER"))
        box.append(r1)

        # Common Action Keys Row 2 (Navigations)
        r2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        r2.set_homogeneous(True)
        r2.append(self.make_key_btn("Home", "HOME"))
        r2.append(self.make_key_btn("↑", "UP"))
        r2.append(self.make_key_btn("End", "END"))
        r2.append(self.make_key_btn("Del", "DEL"))
        box.append(r2)

        # Common Action Keys Row 3 (Arrows & Pg)
        r3 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        r3.set_homogeneous(True)
        r3.append(self.make_key_btn("←", "LEFT"))
        r3.append(self.make_key_btn("↓", "DOWN"))
        r3.append(self.make_key_btn("→", "RIGHT"))
        r3.append(self.make_key_btn("Space", "SPACE"))
        box.append(r3)

        # Function Keys Expander (F1-F12)
        expander = Adw.ExpanderRow(title="Fonksiyon Tuşları (F1 - F12)")
        f_box1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        f_box1.set_homogeneous(True)
        for i in range(1, 7):
            f_box1.append(self.make_key_btn(f"F{i}", f"F{i}"))

        f_box2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        f_box2.set_homogeneous(True)
        for i in range(7, 13):
            f_box2.append(self.make_key_btn(f"F{i}", f"F{i}"))

        f_wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        f_wrap.set_margin_top(6)
        f_wrap.set_margin_bottom(6)
        f_wrap.append(f_box1)
        f_wrap.append(f_box2)
        expander.add_row(f_wrap)

        pref_f = Adw.PreferencesGroup()
        pref_f.add(expander)
        box.append(pref_f)

        scroller.set_child(box)
        return scroller

    def on_live_key_pressed(self, controller, keyval, keycode, state):
        # Check if special key (Enter, BackSpace, Tab, Esc, Arrows, etc.)
        if keyval in GDK_SPECIAL_KEYS:
            hid_code = GDK_SPECIAL_KEYS[keyval]
            self.send_raw_hid_key(hid_code)
            return True
        return False

    def on_live_text_inserted(self, buffer, position, chars, n_chars):
        if self._suppress_live_buffer or not chars:
            return
        layout = "tr" if self.layout_row.get_selected() == 0 else "us"
        self.client.send_cmd({"t": "text", "text": chars, "layout": layout})

        # Clear entry buffer periodically so it stays clean for live typing
        def _clear_live():
            self._suppress_live_buffer = True
            buffer.set_text("", 0)
            self._suppress_live_buffer = False
            return False
        GLib.idle_add(_clear_live)

    def on_live_text_deleted(self, buffer, position, n_chars):
        if self._suppress_live_buffer:
            return
        # If user deleted characters via backspace or software key
        for _ in range(n_chars):
            self.send_raw_hid_key(0x2A) # Backspace

    def send_raw_hid_key(self, code: int):
        def _key_worker():
            self.client.send_cmd({"t": "key", "code": code, "mods": self.active_mods, "down": True})
            time.sleep(0.03)
            self.client.send_cmd({"t": "key", "code": code, "mods": self.active_mods, "down": False})
        threading.Thread(target=_key_worker, daemon=True).start()

    def make_key_btn(self, label: str, hid_name: str) -> Gtk.Button:
        btn = Gtk.Button(label=label)
        btn.connect("clicked", lambda b: self.send_key_press(hid_name))
        return btn

    def on_modifier_toggled(self, widget):
        mods = 0
        if self.ctrl_toggle.get_active(): mods |= MODIFIERS['CTRL']
        if self.shift_toggle.get_active(): mods |= MODIFIERS['SHIFT']
        if self.alt_toggle.get_active(): mods |= MODIFIERS['ALT']
        if self.super_toggle.get_active(): mods |= MODIFIERS['SUPER']
        self.active_mods = mods
        self.client.send_cmd({"t": "key", "code": 0, "mods": self.active_mods, "down": False})

    def send_key_press(self, hid_name: str):
        code = HID_KEYCODES.get(hid_name, 0)
        if not code:
            return

        def _press_thread():
            self.client.send_cmd({"t": "key", "code": code, "mods": self.active_mods, "down": True})
            time.sleep(0.04)
            self.client.send_cmd({"t": "key", "code": code, "mods": self.active_mods, "down": False})
        threading.Thread(target=_press_thread, daemon=True).start()

    def on_send_text_clicked(self, widget):
        text = self.text_entry.get_text()
        if not text:
            return
        layout = "tr" if self.layout_row.get_selected() == 0 else "us"
        self.client.send_cmd({"t": "text", "text": text, "layout": layout})
        self.text_entry.set_text("")

    # --- Service Management & Status ---
    def on_master_switch_toggled(self, switch, state):
        if state == self.is_service_active:
            return False

        def _toggle_worker():
            verb = "start" if state else "stop"
            # Try polkit/systemctl first, fallback to sudo systemctl
            res = subprocess.run(["systemctl", verb, "hidgadget.service"], check=False)
            if res.returncode != 0:
                subprocess.run(["sudo", "systemctl", verb, "hidgadget.service"], check=False)

            GLib.idle_add(self.check_service_status)

        threading.Thread(target=_toggle_worker, daemon=True).start()
        return True

    def check_service_status(self):
        # Check systemctl is-active
        res = subprocess.run(["systemctl", "is-active", "hidgadget.service"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        active = (res.stdout.strip() == "active")
        self.is_service_active = active

        # Update switch UI without triggering callback loop
        self.master_switch.handler_block_by_func(self.on_master_switch_toggled)
        self.master_switch.set_active(active)
        self.master_switch.handler_unblock_by_func(self.on_master_switch_toggled)

        if active:
            if not self.client.is_connected():
                self.client.connect()
            self.status_label.set_text("Durum: USB HID Modu AKTİF (Klavye/Fare Bağlı)")
            self.status_label.remove_css_class("dim-label")
            self.status_label.add_css_class("success")
        else:
            self.client.close()
            self.status_label.set_text("Durum: Kapalı (Orijinal USB Ağı / Şarj Modu)")
            self.status_label.remove_css_class("success")
            self.status_label.add_css_class("dim-label")

        return True


def main():
    app = HIDApplication()
    return app.run(sys.argv)

if __name__ == "__main__":
    main()
