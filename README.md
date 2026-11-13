# Samsung Galaxy A5 (Nura OS) - USB HID Klavye, Fare ve Touchpad Modu

Bu proje, Nura OS (Alpine Linux tabanlı, systemd ve Phosh masaüstü ortamı) çalıştıran Samsung Galaxy A5 (msm8916) cihazını bir USB kablosu üzerinden bilgisayar veya tablet için gerçek bir **USB HID Klavye**, **Fare (Touchpad)** ve **Dokunmatik Ekran (Mutlak Digitizer)** cihazına dönüştürür.

---

## 🌟 Özellikler

1. **Çoklu Aygıt Desteği (Composite HID)**:
   - **Klavye**: Boot protokolü destekli standart 8-bayt klavye (TR-Q ve US tuş haritası).
   - **Fare (Touchpad)**: 3 tuşlu göreli fare + dikey/yatay kaydırma tekerleği (wheel).
   - **Mutlak Dokunmatik (Digitizer)**: 0..10000 koordinat hassasiyetli mutlak dokunmatik giriş modu.
2. **Kullanıcı Dostu Phosh/GTK4 Mobil Arayüz**:
   - 720x1280 dikey mobil ekrana tam uyumlu Libadwaita / GTK4 arayüzü.
   - Kolay açma/kapama (Master Switch).
   - Mod seçici (Touchpad, Dokunmatik, Klavye).
   - Touchpad alanı: Tek dokunuş (Sol Tık), Çift parmak (Sağ Tık), Uzun basış (Sürükle-Bırak), Kaydırma (Tekerlek).
   - Klavye paneli: Phosh sanal klavyesine bağımlı kalmadan Esc, Tab, Ctrl, Alt, Shift, Win/Super, yön okları, F1-F12 ve metin gönderim kutusu.
3. **Güvenli ve Geri Alınabilir Mimari**:
   - Mod kapandığında veya sistem durduğunda orijinal USB ağ servisleri (`usb-signaller`, `unudhcpd@usb0`, `usb0` Developer mode) anında ve eksiksiz geri yüklenir.
   - Extcon OTG algılama: Cihaza OTG kablosu/host takıldığında sistem donanım çakışmasını engellemek için HID modunu otomatik durdurur.
   - Sınırlı yetkilendirme (Polkit / Sudoers): Uygulamanın çalışması için kullanıcıya genel root verilmez; sadece `systemctl start/stop hidgadget.service` komutlarına izin verilir.

---

## 📁 Proje Dosya Yapısı

```
/home/me/hidgadget/
├── hidgadget-daemon.py      # Root ile çalışan asyncio Unix socket daemon'u (gadget yöneticisi)
├── hidgadget-restore.sh     # Acil durum ve temiz geri yükleme kabuk betiği
├── hidgadget.service        # Systemd servis tanımı (Conflicts ve ExecStopPost korumalı)
├── hidgadget-gui.py         # Kullanıcı arayüzü (GTK4 + Libadwaita)
├── 50-hidgadget.rules       # Polkit kuralı (şifresiz servis açma/kapama)
├── 10-hidgadget-sudoers     # Sudoers kuralı (dar kapsamlı izin)
├── org.nura.hidgadget.desktop # Phosh uygulama menüsü girdisi
├── org.nura.hidgadget.svg   # Vektörel uygulama ikonu
├── install.sh               # Otomatik kurulum betiği
├── uninstall.sh             # Tamamen kaldırma ve orijinal duruma dönüş betiği
└── README.md                # Dokümantasyon
```

---

## 🚀 Kurulum

Cihaz terminalinde (veya SSH üzerinden) proje dizininde şu komutu çalıştırın:

```bash
cd /home/me/hidgadget
chmod +x install.sh uninstall.sh hidgadget-*.py hidgadget-*.sh
sudo ./install.sh
```

Kurulum tamamlandığında uygulama Phosh uygulama çekmecesinde **"USB HID Kontrol"** adıyla görünecektir.

---

## 🎮 Kullanım

1. Telefonu USB kablosu ile kontrol etmek istediğiniz bilgisayara bağlayın.
2. Telefonda **USB HID Kontrol** uygulamasını açın (veya terminalden `hidgadget-gui.py` çalıştırın).
3. Üstteki **"USB HID Modu"** anahtarını açın.
   - Telefon USB üzerinden `Galaxy A5 HID Device` olarak bilgisayara tanıtılacaktır.
4. İstediğiniz modu seçin:
   - **Touchpad**: Parmağınızı alanda kaydırarak imleci hareket ettirin. Tek dokunuş sol tık, çift parmak sağ tık yapar. Alttaki butonları da kullanabilirsiniz.
   - **Dokunmatik**: Karşı ekranın çözünürlüğünü girip alana dokunarak mutlak fare/dokunmatik kontrolü sağlayın.
   - **Klavye**: Metin kutusuna metin yazıp "Gönder" diyerek karşı tarafa hızlıca yazdırın veya paneldeki kontrol tuşlarını (Ctrl+C, Alt+Tab, Esc, Oklar, F1-F12 vb.) kullanın.
5. İşiniz bittiğinde anahtarı kapatın; telefon derhal eski USB tethering / şarj moduna geri dönecektir.

---

## 🔄 Tamamen Geri Alma / Kaldırma

Projeyi sistemden tamamen kaldırmak ve tüm dosyaları temizlemek için:

```bash
cd /home/me/hidgadget
sudo ./uninstall.sh
```

Bu işlem:
- `hidgadget` servisini durdurur,
- `/dev/hidg*` ve `hid1` yapılandırmasını siler,
- Yüklenen tüm ikili, servis ve kural dosyalarını temizler,
- `usb-signaller` ve `usb0` ağını aktif ederek sistemi orijinal haline döndürür.
