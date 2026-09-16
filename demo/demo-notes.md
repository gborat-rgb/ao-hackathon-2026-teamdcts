# Demo Notları

**Takım:** Fail-i Over · **Senaryo:** S-A1 Alarm Fırtınası

---

## Bu klasörde ne var

| Dosya | Ne gösteriyor |
|---|---|
| `01_olay_kartlari.txt` | Tam CLI çıktısı — 5 olay kartı, kanıt/gerekçe/güven/karşı hipotez ile |
| `02_x_factor.txt` | Ayrışma testi ölçümü: 4 kart → 5 kart |
| `03_gurultu_denetimi.txt` | Elenen alarmlardan 25 örnek ve her birinin eleme gerekçesi |
| `04_kartlar.json` | Kartların makine okunur hâli |
| `05_test_sonuclari.txt` | 60 testin sonucu |
| `11_erken_tespit.txt` | Geceyi yeniden oynatma: kartların oluşma anı ve gecikme |

Bu dosyaların hepsi komutla yeniden üretilebilir — dekoratif değil, gerçek çıktı.

Ekran görüntüleri (`*.png`) canlı arayüzden alınır; alma adımları aşağıda.

---

## Canlı demo akışı (7 dakika)

### 1. Problemi göster (45 sn)

```bash
wc -l senaryo_paketi/alarms.csv     # 3001 satır
```

> "Nöbetçi mühendis iki saatlik pencerede 3000 alarm görüyor. Sorun sayı değil;
> hangisinin kök neden, hangisinin türev etki, hangisinin gürültü olduğunun
> görünmemesi."

### 2. Terminal çözümü ve veri muhasebesi (1 dk 45 sn)

```bash
python -m src.cli
```

Gösterilecek:
- Başlıktaki indirgeme: **3000 alarm → 5 kart, 600×**
- Muhasebe: **994 karta atanmış + 2006 açıkça dışlanmış = 3000; kayıp 0**
- **OLAY-01** kartında kanıt satırı: *"dc1/rack-A kabinindeki 9 host'un 9'u alarm üretiyor (%100)"*
- Kanıt ile gerekçenin ayrı bloklar olması — ölçülen sayı ile çıkarım karışmıyor
- Her kartın karşı hipotezi

### 3. X-Factor — ayrışma testi (1 dk 30 sn) ⭐

```bash
python -m src.cli --x-factor
```

Anlatılacak:

> "02:38–02:58 arasında iki şey aynı anda oluyor: payment-provider-gw dış servis
> kesintisi ve session-service bellek tükenmesi. İkisi de mobile-bff'i vuruyor.
> Zaman ve servis benzerliğine bakan her kümeleme bunları tek olay sayar."

Çıktı:
```
Ayrisma testi KAPALI : 4 kart
Ayrisma testi ACIK   : 5 kart
Test acilinca ortaya cikan kok neden: session-service
```

> "Ayrımın dayanağı bağımlılık grafiği: payment-provider-gw ile session-service
> arasında nedensel yol yok. Kopuk kökler ayrı olaydır."

### 4. Arayüz ve aksiyon izleme (2 dk)

```bash
streamlit run src/app.py
```

- **Yönetici özeti** (sayfa açılır açılmaz, 20 sn): `3.000 ham → −2.006
  dışlanan → 994 korele → 5 olay → 600×` şeridi; altında kayıp 0, çift
  atama 0 ve çalışma süresi. Hepsi pipeline metriklerinden gelir.
- **Olaylar** sekmesi: her satırda kök, şiddet/güven, kapsam, sahip, durum ve
  ilk aksiyon. OLAY-01'in ayrıntısı açık gelir: kanıt, gerekçe, karşı
  hipotez, zaman çizgisi, saha yönlendirmesi
- **Aksiyon**: OLAY-03'ün durumunu `AÇIK → MÜDAHALEDE → KAPANDI` yap,
  durum geçmişinin kartta göründüğünü göster *(opsiyonel gereksinim)*
- **X-Factor** sekmesi: yan yana **4 / 5** kartı; altında "False merge nasıl
  engellendi?" paneli — ayrışma kapalıyken `session-service` alarmlarının
  27/27'si OLAY-03'e gömülüyor, 15 dk zaman çakışması, grafik mesafesi 4 >
  eşik 2, açıkken iki ayrı sahip. Sonra kenar çubuğundan ayrışma testini
  **kapat**, üstteki olay sayısının 5'ten 4'e düştüğünü göster, tekrar aç
- **Gürültü Denetimi** sekmesi: skorlama gürültüsü 1.888 · korelasyon dışı
  118 · toplam 2.006; filtreyle `korelasyon_disi` seç, `eleme_gerekcesi`
  sütununu göster
- **Zaman Çizelgesi** sekmesi: sinyal/gürültü ayrımı ve işaretlenmiş olay pencereleri
- **Mobil / saha görünümü** anahtarı (isteğe bağlı): üç sayılık şerit ve
  kök · konum · sahip · durum listesi

### 5. Test kanıtı, performans ve sınırlar (1 dk)

```bash
python -m pytest tests/ -q
```

> "60 test; veri muhasebesi, determinism, bozuk veri, duplicate ID,
> dependency cycle, satır sırası, erken tespit ve arayüzün pipeline
> metrikleriyle birebir eşleşmesi dahil. Aynı ortamda 7 koşu ortalaması
> 0.625 saniye; demo hedefi olan 10 saniyenin rahat altında."

> "OLAY-05'in kökünü subscriber-db olarak verdik, batch-scheduler'ı karşı
> hipotez olarak bıraktık. Bağımlılık grafiği arıza yayılımını modelliyor,
> yük yayılımını değil — yük ters yönde akıyor. Bunu biliyoruz ve kartta yazıyor."

---

## Ekran görüntüsü kanıtları

Executive arayüz güncellemesinden sonra gerçek yerel Streamlit oturumundan
(varsayılan ayarlar: eşik 0.35, ayrışma açık) headless Chromium ile alındı:

| Dosya | Görünüm | Ne gösteriyor |
|---|---|---|
| `06_arayuz_kartlar.png` | 1600×1100 | Yönetici özeti, 8 KPI, Olaylar sekmesi, OLAY-01 ayrıntısı açık |
| `07_arayuz_xfactor.png` | 1600×1400 | X-Factor: 4 / 5 kart ve ölçülen false merge paneli |
| `08_arayuz_gurultu.png` | 1600×1100 | Gürültü Denetimi özeti, gerekçeli tablo, skor dağılımı |
| `09_arayuz_zaman.png` | 1600×1400 | Zaman Çizelgesi, olay pencereleri ve kart özeti |
| `10_aksiyon_kapandi.png` | 1600×1100 | OLAY-01 aksiyonu `KAPANDI`, durum geçmişi görünür |
| `12_arayuz_mobil.png` | 390×844 | Mobil / saha görünümü |

Görüntüler dekoratif değildir; aynı özellikler canlı demoda tekrar üretilebilir.
