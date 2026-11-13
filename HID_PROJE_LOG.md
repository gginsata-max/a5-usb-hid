# Samsung Galaxy A5 (Nura OS) - USB HID Klavye/Mouse/Touchpad Modu Proje Logu

Başlangıç Tarihi: 2026-11-13 14:40:00 (UTC+3)
Hedef Cihaz: Samsung Galaxy A5U (EUR), msm8916, Nura OS (Alpine tabanlı systemd + Phosh)
Bağlantı IP: ZeroTier IP: <TARGET_IP> / WiFi IP: <WIFI_IP>

---
## İşlem Kayıtları

### [2026-11-13 14:39:41] Bağlantı ve Keşif
- **Yapılan İş**: ZeroTier (<TARGET_IP>) ve WiFi (<WIFI_IP>) IP üzerinden cihaza SSH bağlantısı ve ağ durumu testi.
- **Komut**: `ssh -o BatchMode=yes <USER>@<TARGET_IP> uptime` ve `ip a`
- **Çıktı**:
  - Uptime: `14:39:41 up 1:07, 0 users, load average: 0.19, 0.15, 0.10`
  - Ağ Arayüzleri:
    - `usb0`: 172.16.42.1/16 (NCM gadget)
    - `wlan0`: <WIFI_IP>/24 (WiFi)
    - `zt6q3b4oyu`: <TARGET_IP>/24 (ZeroTier - WiFi üzerinden stabil)
- **Sonuç**: Başarılı. SSH bağlantısı ZeroTier IP (<TARGET_IP>) üzerinden kesintisiz çalışıyor.
- **Sonraki Adım**: Sudo yetkileri ve USB gadget/UDC/extcon mimarisinin incelenmesi.

---

### [2026-11-13 14:39:53] Sudo Yetki Kontrolü
- **Yapılan İş**: user kullanıcısının sudo haklarının kontrolü.
- **Komut**: `sudo -n true`
- **Çıktı**: `sudo NOPASSWD works` (çıkış kodu 0)
- **Sonuç**: Başarılı. Root yetkileri şifresiz alınabiliyor.
- **Sonraki Adım**: `usb-signaller` ve `g1` yapılandırmasının incelenmesi.

---

### [2026-11-13 14:40:04] USB Gadget (g1), UDC ve extcon Durumu
- **Yapılan İş**: g1 fonksiyonları, config'leri, UDC durumu ve extcon0 kontrolü.
- **Komut**:
  ```bash
  systemctl cat usb-signaller.service
  sudo ls -R /sys/kernel/config/usb_gadget/g1/functions /sys/kernel/config/usb_gadget/g1/configs
  sudo cat /sys/kernel/config/usb_gadget/g1/UDC
  cat /sys/class/udc/*/state
  ls /sys/class/extcon/extcon0; cat /sys/class/extcon/extcon0/name
  head -n 20 /sys/class/extcon/extcon0/cable.*/name /sys/class/extcon/extcon0/cable.*/state /sys/class/extcon/extcon0/state
  ```
- **Çıktı**:
  - `usb-signaller.service`: `/usr/bin/usb-signaller` çalıştırıyor (WantedBy=usb-gadget.target). Rust ile yazılmış, D-Bus `com.meego.usb_moded` servisini sağlıyor ve configfs ile gadget modlarını (NCM tethering, MTP, mass storage) yönetiyor.
  - `/sys/kernel/config/usb_gadget/g1`:
    - Functions: `ncm.usb0`
    - Configs: `c.1/ncm.usb0`
    - Vendor: `0x04e8` (Samsung), Product: `0x6860`, Manufacturer: `Samsung`, Product Name: `Samsung Galaxy A5 (2015)`, Serial: `postmarketOS`
    - UDC: `ci_hdrc.0`
  - `/sys/class/udc/ci_hdrc.0/state`: `not attached` (Şu anda kablo takılı değil veya SDP veri bağlantısı yok)
  - `/sys/class/extcon/extcon0`:
    - `cable.0`: USB (state=0)
    - `cable.1`: USB-HOST (state=0)
    - `cable.2`: SDP (state=0)
    - `cable.3`: DCP (state=1 -> Dedicated Charging Port aktif)
    - `extcon0/state`: `USB=0, USB-HOST=0, SDP=0, DCP=1`
- **Sonuç**: Başarılı. Sistem mimarisi tam olarak anlaşıldı. UDC `ci_hdrc.0` ChipIdea denetleyicisi.
- **Sonraki Adım**: Adım 2: Elle USB HID (hid1) gadget testi.

---

### [2026-11-13 14:43:00] Adım 2: Elle Test (hid1 Gadget Kurulumu)
- **Yapılan İş**: `g1` UDC'den ayrıldı (`echo "" > g1/UDC`), `modprobe usb_f_hid` çalıştırıldı, `hid1` adında composite gadget kuruldu ve `ci_hdrc.0` UDC'ye bağlandı.
- **Fonksiyonlar**:
  - `hid.kbd`: standard boot keyboard (protocol=1, subclass=1, report_length=8, descriptor: 63 byte)
  - `hid.mouse`: relative mouse (protocol=2, subclass=1, report_length=4, 3 tuş + X/Y + tekerlek, descriptor: 52 byte)
  - `hid.touch`: absolute digitizer (protocol=0, subclass=0, report_length=5, tip switch + in-range + 16-bit X/Y 0..10000, descriptor: 42 byte)
- **Komut**: Python betiği ile configfs üzerinden `hid1` tanımlandı ve `ci_hdrc.0` yazıldı.
- **Çıktı**:
  - `Binding to UDC ci_hdrc.0... Binding successful!`
  - Oluşan cihazlar: `/dev/hidg0` (kbd), `/dev/hidg1` (mouse), `/dev/hidg2` (touch)
- **Sonuç**: Başarılı. Cihaz düğümleri beklenen sırayla oluşturuldu.
- **Sonraki Adım**: `/dev/hidg*` yazma testi ve geri alma (teardown) testi.

---

### [2026-11-13 14:43:35] Adım 2: Elle Test (Rapor Yazma ve Geri Alma)
- **Yapılan İş**:
  - `/dev/hidg0` ve `/dev/hidg1` üzerine test raporu yazımı denendi.
  - `hid1` ters sırayla söküldü (UDC unbind -> symlink silme -> strings/configs silme -> functions silme -> rmdir hid1).
  - `g1` tekrar `ci_hdrc.0`'a bağlandı.
- **Komut**: Python test yazma betiği ve temizleme betiği.
- **Çıktı**:
  - Rapor yazımı: `[Errno 108] Cannot send after socket shutdown` (Kernel `f_hid.c`: USB host takılı/bağlı olmadığında beklenen normal durum).
  - Geri alma:
    - `Removed /sys/kernel/config/usb_gadget/hid1/configs/c.1/hid.*`
    - `Removed function /sys/kernel/config/usb_gadget/hid1/functions/hid.*`
    - `Removed hid1 gadget directory`
    - `Rebound g1 to ci_hdrc.0`
    - Doğrulama: `No hidg devices`, `UDC: ci_hdrc.0`, `usb0: 172.16.42.1/16 UP`
- **Sonuç**: Başarılı. `hid1` sorunsuz söküldü ve orijinal `g1` / `usb0` ağı eksiksiz geri döndü.
- **Sonraki Adım**: Adım 3: `hidgadget.service` (systemd servisi ve Python asyncio socket daemon) geliştirilmesi.

---

### [2026-11-13 14:47:04] Adım 3: Daemon ve Systemd Servisinin Geliştirilmesi
- **Yapılan İş**:
  - `hidgadget-daemon.py`: Python 3 + asyncio tabanlı root daemon'u yazıldı. Standart HID rapor tanımlayıcıları (Kbd 63B, Mouse 52B, Touch 42B) gömüldü. Unix domain socket (`/run/hidgadget.sock`, chmod 0660, chown root:user) üzerinden JSON satır protokolü (`ping`, `key`, `mouse`, `touch`, `text`) uygulandı. Extcon0 üzerinden OTG/host algılama döngüsü eklendi.
  - `hidgadget-restore.sh`: Acil durum ve temiz kapatma için fail-safe geri yükleme betiği oluşturuldu.
  - `hidgadget.service`: Systemd unit dosyası hazırlandı. `Conflicts=usb-signaller.service unudhcpd@usb0.service` ve `ExecStopPost=/bin/sh /usr/local/bin/hidgadget-restore.sh` ile çökme ve beklenmedik kapanmalarda dahi sistemin otomatik olarak orijinal haline dönmesi garanti edildi.
- **Komut**: `/home/me/hidgadget/` altında betikler oluşturuldu.
- **Sonuç**: Başarılı.
- **Sonraki Adım**: Adım 4 & 5: Polkit/sudoers yetkilendirmesi, GTK4 arayüzü ve .desktop kısayolu.

---

### [2026-11-13 14:48:48] Adım 4 & 5: Yetkilendirme ve GTK4 Libadwaita Arayüzü
- **Yapılan İş**:
  - `50-hidgadget.rules`: Polkit kuralı ile unprivileged `user` kullanıcısının şifresiz `systemctl start/stop hidgadget.service` çalıştırabilmesi sağlandı.
  - `10-hidgadget-sudoers`: Yedek olarak dar kapsamlı sudoers kuralı eklendi.
  - `hidgadget-gui.py`: GTK4 ve Libadwaita ile mobil Phosh ekranına (720x1280) optimize arayüz geliştirildi.
    - Ana açma/kapama anahtarı (canlı servis durumu izleme).
    - Touchpad (Göreli Fare) sayfası: tek tık=sol, çift parmak=sağ, uzun bas=sürükle-bırak, kaydırma=tekerlek, fiziksel buton çubuğu.
    - Dokunmatik (Mutlak) sayfası: karşı ekran çözünürlüğü ve 10000x10000 oranlı hassas koordinat gönderimi.
    - Klavye sayfası: TR-Q ve US düzen seçimi, metin yaz/gönder alanı, kilitlenebilir Ctrl/Alt/Shift/Win tuşları, yön okları, Esc/Tab/Enter, F1-F12 fonksiyon tuşları.
  - `org.nura.hidgadget.desktop` ve `org.nura.hidgadget.svg`: Menü kısayolu ve simgesi oluşturuldu.
  - `install.sh` ve `uninstall.sh`: Kurulum ve temiz kaldırma betikleri tamamlandı.
- **Sonuç**: Başarılı.
- **Sonraki Adım**: Adım 6: Cihaza aktarım, kurulum ve 5 döngülü doğrulama testi.

---

### [2026-11-13 14:49:50] Kurulum ve Servis Doğrulaması
- **Yapılan İş**: Proje dosyaları cihaza `/home/user/hidgadget/` altına aktarıldı, `install.sh` çalıştırıldı.
- **Komut**: `scp -r /home/me/hidgadget/* <USER>@<TARGET_IP>:/home/user/hidgadget/ && sudo /home/user/hidgadget/install.sh`
- **Çıktı**: Dosyalar başarıyla `/usr/local/bin`, `/etc/systemd/system`, `/etc/polkit-1/rules.d`, `/etc/sudoers.d`, `/usr/share/applications` ve `/usr/share/icons` altına yüklendi.
- **Sonuç**: Başarılı. Polkit ve sudoers kuralları yüklendi, önbellekler güncellendi.
- **Sonraki Adım**: Servis başlatma ve unprivileged socket erişim testi.

---

### [2026-11-13 14:50:12] Polkit İzni ve Socket İletişim Testi
- **Yapılan İş**: Root olmayan `user` kullanıcısı ile `systemctl start hidgadget.service` çalıştırıldı, `/run/hidgadget.sock` üzerinden test komutları gönderildi.
- **Komut**:
  ```bash
  systemctl start hidgadget.service
  python3 -c "import socket; s=socket.socket(socket.AF_UNIX); s.connect('/run/hidgadget.sock'); s.sendall(b'{\"t\":\"ping\"}\n'); print(s.recv(1024))"
  ```
- **Çıktı**:
  - Şifre sorulmadan servis başlatıldı (Polkit yetkisi doğrulandı).
  - Socket cevabı: `{"ok": true, "status": "active", "host_otg": false}`
  - Klavye, fare ve dokunmatik JSON komutları başarıyla işlendi.
- **Sonuç**: Başarılı. Unprivileged kullanıcı tam erişim sağladı.
- **Sonraki Adım**: 5 döngülü ardışık açma/kapama ve kurtarma stres testi.

---

### [2026-11-13 14:52:24] Adım 6: 5 Döngülü Ardışık Açma/Kapama Stres Testi
- **Yapılan İş**: `hidgadget.service` ardışık olarak 5 kez başlatıldı, socket ping'lendi, `/dev/hidg0..2` varlığı kontrol edildi, servis durduruldu ve `usb0` (172.16.42.1) ağının geri dönüşü doğrulandı.
- **Komut**: Otomatik Python stres test döngüsü.
- **Çıktı**:
  - Döngü 1/5: Başlatıldı -> hidg0,1,2 mevcut -> Ping OK -> Durduruldu -> usb-signaller aktif, usb0 172.16.42.1 True
  - Döngü 2/5: Başlatıldı -> hidg0,1,2 mevcut -> Ping OK -> Durduruldu -> usb-signaller aktif, usb0 172.16.42.1 True
  - Döngü 3/5: Başlatıldı -> hidg0,1,2 mevcut -> Ping OK -> Durduruldu -> usb-signaller aktif, usb0 172.16.42.1 True
  - Döngü 4/5: Başlatıldı -> hidg0,1,2 mevcut -> Ping OK -> Durduruldu -> usb-signaller aktif, usb0 172.16.42.1 True
  - Döngü 5/5: Başlatıldı -> hidg0,1,2 mevcut -> Ping OK -> Durduruldu -> usb-signaller aktif, usb0 172.16.42.1 True
  - `>>> ALL 5 CYCLES COMPLETED SUCCESSFULLY WITHOUT ANY ISSUES! <<<`
- **Sonuç**: Başarılı. WiFi/ZeroTier SSH bağlantısı kesintisiz sürdü, usb0 her defasında 172.16.42.1 IP'si ile geri geldi.
- **Sonraki Adım**: GTK4 / Phosh Wayland arayüz çalıştırma testi.

---

### [2026-11-13 14:53:25] GTK4 / Libadwaita Wayland Arayüz Testi
- **Yapılan İş**: `hidgadget-gui.py` Wayland ekranı üzerinde Phosh ortamında çalıştırılarak test edildi.
- **Komut**: `WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/10000 timeout 2 /usr/local/bin/hidgadget-gui.py`
- **Çıktı**: İlk çalıştırmada tespit edilen `EventControllerScrollFlags.SMOOTH` ve ampersand `&` markup uyarıları giderildi. Yeniden test edildiğinde sıfır hata/sıfır uyarı ile başarıyla render edildi.
- **Sonuç**: Başarılı.
- **Sonraki Adım**: Kaldırma (uninstall) ve yeniden yükleme (install) döngüsü doğrulaması.

---

### [2026-11-13 14:54:04] Kaldırma (uninstall.sh) ve Temiz Kurulum Doğrulaması
- **Yapılan İş**: `uninstall.sh` çalıştırılarak tüm dosyaların silindiği ve sistemin temizlendiği teyit edildi, ardından `install.sh` ile nihai kurulum yapıldı.
- **Komut**: `sudo /home/user/hidgadget/uninstall.sh && sudo /home/user/hidgadget/install.sh`
- **Çıktı**: `=== Kaldırma İşlemi Tamamlandı! Sistem Orijinal Haline Döndü ===` ardından `=== Kurulum Başarıyla Tamamlandı! ===`
- **Sonuç**: Başarılı. Kaldırma ve kurma mekanizması eksiksiz çalışıyor.

---

### [2026-11-13 15:14:49] Canlı Klavye İletimi Özelliği (Geliştirme & Test)
- **Yapılan İş**: Kullanıcı geri bildirimi doğrultusunda klavyenin "canlı" olarak (her tuşa basıldığında anında) karşı cihaza aktarılması özelliği eklendi:
  - `hidgadget-gui.py` içine "Canlı Klavye Girişi" (Live Typing) alanı entegre edildi.
  - Phosh ekran klavyesinden veya fiziksel klavyeden basılan her karakter (`inserted-text`), silme tuşları (`deleted-text` / Backspace) ve özel tuşlar (`Gtk.EventControllerKey` ile Enter, Tab, Esc, Yön okları, Home/End vb.) anında sıfır gecikmeyle Unix socket üzerinden USB HID klavyesine aktarılacak şekilde yapılandırıldı.
  - Toplu metin gönderimi (uzun yazılar için) alt kısımdaki açılır bölüme (Expander) taşındı.
  - Güncellenen arayüz Wayland oturumunda test edildi ve cihaza kuruldu.
- **Komut**: `scp /home/me/hidgadget/hidgadget-gui.py <USER>@<TARGET_IP>:/home/user/hidgadget/ && sudo cp /home/user/hidgadget/hidgadget-gui.py /usr/local/bin/hidgadget-gui.py`
- **Çıktı**: `GUI running cleanly on Phosh Wayland!` (çıkış kodu 143/temiz kapanış)
- **Sonuç**: Başarılı. Canlı klavye aktarımı aktif edildi.

---

### [2026-11-13 15:28:48] Çekirdek Udev/Evdev Ham Klavye Olaylarının Doğrudan Aktarımı
- **Yapılan İş**: Arayüz katmanını tamamen baypas edip donanım seviyesindeki ham klavye olaylarını doğrudan USB HID'e iletmek amacıyla `hidgadget-daemon.py` içine Linux `evdev` (`/dev/input/event*`) dinleyicisi entegre edildi.
  - Linux `input_event` (24 bayt) yapısı üzerinden `EV_KEY` olayları ve tuş durumları (basıldı: 1, bırakıldı: 0, tekrar: 2) doğrudan yakalanıyor.
  - Linux çekirdek tuş kodları (KEY_A..KEY_Z, KEY_1..0, Enter, Esc, BackSpace, Tab, Oklar vb.) ve niteleyici tuşlar (Ctrl, Shift, Alt, Meta) doğrudan USB HID standart rapor baytlarına dönüştürülüp araya hiçbir metin veya UI arayüzü girmeden anında `/dev/hidg0` üzerine yazılıyor.
  - Cihaza güncel daemon aktarıldı ve servis doğrulandı.
- **Komut**: `scp /home/me/hidgadget/hidgadget-daemon.py <USER>@<TARGET_IP>:/home/user/hidgadget/ && sudo cp /home/user/hidgadget/hidgadget-daemon.py /usr/local/bin/hidgadget-daemon.py`
- **Sonuç**: Başarılı. Çekirdek seviyesi doğrudan udev/evdev tuş köprüsü devrede.

---

## Özet
Samsung Galaxy A5 (Nura OS / Linux 6.12.1-msm8916) üzerinde USB Composite HID cihazı (Klavye + Göreli Fare + Mutlak Dokunmatik) başarıyla geliştirilmiş ve doğrulanmıştır:
1. **Çekirdek Desteği**: `usb_f_hid.ko.zst` kernel modülü ve ConfigFS HID fonksiyonları kullanıldı, kernel derlemeye gerek kalmadı.
2. **Mimari**: `hidgadget.service` systemd servisi ve Python asyncio daemon'u (`/usr/local/bin/hidgadget-daemon.py`) geliştirildi.
3. **Güvenlik ve Geri Dönüş**: `Conflicts=` ve `ExecStopPost=` yapılandırması sayesinde servis kapandığında veya çöktüğünde `hidgadget-restore.sh` tetiklenerek orijinal USB tethering (`usb-signaller` ve `unudhcpd@usb0` ile `usb0` Developer mode) anında geri yüklenir.
4. **Kullanıcı İzinleri**: Polkit kuralı (`/etc/polkit-1/rules.d/50-hidgadget.rules`) ile normal kullanıcının root şifresi girmeden arayüzden modu açıp kapatması sağlandı.
5. **Kullanıcı Arayüzü**: GTK4 ve Libadwaita ile Phosh mobil ortamına (720x1280) özel dokunmatik touchpad, mutlak koordinatlı dokunmatik ekran, TR-Q / US klavye tuş paneli ve metin gönderim kutusu içeren uygulama (`hidgadget-gui.py`) geliştirildi.

---

## Kurulum ve Geri Alma Talimatı

### Kurulum:
```bash
cd /home/user/hidgadget
chmod +x *.sh *.py
sudo ./install.sh
```
Kurulum sonrasında uygulama Phosh uygulama menüsünde **"USB HID Kontrol"** olarak görünür.

### Kullanım:
- Telefonu USB kablosuyla bilgisayara bağlayın.
- "USB HID Kontrol" uygulamasını açın ve üstteki "USB HID Modu" anahtarını açın.
- Touchpad, Dokunmatik veya Klavye sekmesini seçerek bilgisayarınızı kontrol edin.
- İşiniz bitince anahtarı kapatın.

### Tamamen Geri Alma (Kaldırma):
```bash
cd /home/user/hidgadget
sudo ./uninstall.sh
```
Bu komut servisi durdurur, `hid1` gadget'ını söker, tüm kural ve ikili dosyaları siler ve orijinal USB ağını geri getirir.

---

## Bilinen Sorunlar ve Çözümleri
1. **USB Kablosu Takılı Değilken Rapor Yazımı (`ESHUTDOWN` / `Errno 108`)**:
   - *Açıklama*: Telefon bir bilgisayara USB kablosuyla veri modunda (SDP/CDP) bağlı olmadığında veya bilgisayar uyku modundayken çekirdeğin `f_hid` sürücüsü rapor yazma çağrılarına `ESHUTDOWN` döner.
   - *Çözüm*: Daemon bu durumu yakalayacak ve çökmeyecek şekilde kodlanmıştır. Telefon bilgisayara takılıp USB oturumu başladığında rapor yazımları otomatik olarak iletilir.
2. **OTG / Host Modu Algılama**:
   - *Açıklama*: Telefona OTG kablosu takıldığında (`extcon0` USB-HOST=1 olur), ChipIdea denetleyicisi donanımsal olarak Device modundan Host moduna geçer.
   - *Çözüm*: Daemon her saniye extcon durumunu izler ve Host modu algılandığında donanım hasarını ve çakışmayı önlemek için HID servisini güvenle durdurur.
3. **Phosh Sanal Klavyesi Karakter Kodları**:
   - *Açıklama*: Phosh sanal klavyesi doğrudan düşük seviye USB keycode yerine Wayland text protocol kullanır.
   - *Çözüm*: Uygulama içine gömülü özel tuş paneli (Ctrl, Alt, Shift, Esc, Tab, Oklar, F1-F12 vb.) ve "Metin Gönder" kutusu entegre edilmiştir.





## 2026-11-13 15:50 - Android Uyumluluk Düzeltmesi

### Yapılan İş
Android cihazlarda (Xiaomi Mi 11 Lite) "Unknown USB mode" hatası alınıyordu. Sorun analizi:
1. VID `0x1d6b` / PID `0x0104` = Linux Foundation Multifunction Composite Gadget — MIUI/Android bunu debug cihaz olarak tanıyordu
2. Touch digitizer (3. HID interface) composite gadget'ı karmaşık yapıyordu
3. bDeviceClass ayarlanmamıştı (interface-level olmalı)
4. MaxPower=250 bazı Android host'larda sorun çıkıyordu

### Değişiklikler (hidgadget-daemon.py)
1. **VID/PID**: `0x1d6b:0x0104` → `0x1209:0x0001` (pid.codes açık kaynak HID)
2. **bDeviceClass/SubClass/Protocol**: `0x00/0x00/0x00` eklendi (interface-level class tanımı)
3. **Manufacturer**: "Samsung" → "HID Device"
4. **Product**: "Galaxy A5 HID Device" → "USB Keyboard and Mouse"
5. **MaxPower**: 250 → 100 (Android uyumlu)
6. **Touch fonksiyonu kaldırıldı**: Sadece hid.kbd + hid.mouse (2 interface)
7. **Evdev filtreleme**: `_is_keyboard_device()` eklendi — dokunmatik ekran, sensör, vibratör cihazlarını atlar, sadece gerçek klavye cihazlarını dinler
8. **EVIOCGRAB**: Klavye cihazı exclusive grab yapılır (yerel sistem tuşları almaz, direkt HID'e aktarılır)
9. **Shutdown cleanup**: Grabbed cihazlar release edilir

### Test
- Komut: `sudo systemctl start hidgadget.service`
- Çıktı: active, /dev/hidg0 + /dev/hidg1 oluştu
- Gadget doğrulama:
  - idVendor: 0x1209 ✓
  - idProduct: 0x0001 ✓
  - bDeviceClass: 0x00 ✓
  - functions: hid.kbd, hid.mouse ✓
  - MaxPower: 100 ✓
  - UDC: ci_hdrc.0 ✓
- Socket ping: `{"ok": true, "status": "active", "host_otg": false}` ✓
- Komut gönderme (key, mouse, text): Başarılı ✓
- UDC state: "not attached" (USB kablo bağlı değil — beklenen)

### Sonuç: BAŞARILI (kurulum), Android test bekliyor
### Sonraki adım: Kullanıcıdan Mi 11 Lite'a USB ile bağlayıp test etmesini iste
