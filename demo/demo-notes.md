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
| `05_test_sonuclari.txt` | 19 testin sonucu |

Bu dosyaların hepsi komutla yeniden üretilebilir — dekoratif değil, gerçek çıktı.

Ekran görüntüleri (`*.png`) canlı arayüzden alınır; alma adımları aşağıda.

---

## Canlı demo akışı (4–5 dakika)

### 1. Problemi göster (30 sn)

```bash
wc -l senaryo_paketi/alarms.csv     # 3001 satır
```

> "Nöbetçi mühendis iki saatlik pencerede 3000 alarm görüyor. Sorun sayı değil;
> hangisinin kök neden, hangisinin türev etki, hangisinin gürültü olduğunun
> görünmemesi."

### 2. Terminal çözümü (60 sn)

```bash
python -m src.cli
```

Gösterilecek:
- Başlıktaki indirgeme: **3000 alarm → 5 kart, 600×, 0.37 sn**
- **OLAY-01** kartında kanıt satırı: *"dc1/rack-A kabinindeki 9 host'un 9'u alarm üretiyor (%100)"*
- Kanıt ile gerekçenin ayrı bloklar olması — ölçülen sayı ile çıkarım karışmıyor
- Her kartın karşı hipotezi

### 3. X-Factor — ayrışma testi (90 sn) ⭐

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

### 4. Arayüz ve aksiyon izleme (90 sn)

```bash
streamlit run src/app.py
```

- **Olay Kartları** sekmesi: OLAY-01'i aç, kanıt/gerekçe/güven/karşı hipotez
- **Aksiyon**: OLAY-03'ün durumunu `acik → devam_ediyor → kapandi` yap,
  durum geçmişinin kartta göründüğünü göster *(opsiyonel gereksinim)*
- **X-Factor** sekmesi: kenar çubuğundan ayrışma testini **kapat**, kart
  sayısının 5'ten 4'e düştüğünü ve session-service'in kaybolduğunu göster,
  sonra tekrar aç
- **Gürültü Denetimi** sekmesi: bir alarm seç, *"neden elendi"* sütununu göster
- **Zaman Çizelgesi** sekmesi: sinyal/gürültü ayrımı ve işaretlenmiş olay pencereleri

### 5. Sınırları söyle (30 sn)

> "OLAY-05'in kökünü subscriber-db olarak verdik, batch-scheduler'ı karşı
> hipotez olarak bıraktık. Bağımlılık grafiği arıza yayılımını modelliyor,
> yük yayılımını değil — yük ters yönde akıyor. Bunu biliyoruz ve kartta yazıyor."

---

## Ekran görüntüsü alma adımları

Uygulama çalışıyorsa `http://localhost:8501` adresinde. Değilse:

```bash
streamlit run src/app.py
```

Alınacak görüntüler ve dosya adları:

| Dosya | Ne çekilecek |
|---|---|
| `06_arayuz_kartlar.png` | Olay Kartları sekmesi, OLAY-01 açık (üstteki 4 metrik görünsün) |
| `07_arayuz_xfactor.png` | X-Factor sekmesi, "4 kart / 5 kart" karşılaştırması |
| `08_arayuz_gurultu.png` | Gürültü Denetimi sekmesi, skor dağılımı grafiği dahil |
| `09_arayuz_zaman.png` | Zaman Çizelgesi sekmesi, olay pencereleri işaretli |
| `10_aksiyon_kapandi.png` | Bir aksiyon `kapandi` durumunda, durum geçmişi görünür |

Her görüntü çözümün gerçek bir özelliğini göstermeli; süsleme eklenmemeli.
