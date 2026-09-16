# S-A1 "Alarm Fırtınası" — Çözüm Planı

**Takım:** Fail-i Over
**Analiz tarihi:** 16 Eylül 2026, 14:44
**Teslim:** 17:30 — planın yazıldığı anda kalan süre **2 sa 46 dk**

---

## 1. Problemin ilk yorumu

Brifingin kendi ifadesiyle asıl güçlük alarm sayısı değil, **neden-sonuç
ilişkisinin görünmez olması**. Yani problem bir "filtreleme" problemi değil,
bir **nedensellik atfetme** problemidir.

Bu ayrım çözümün şeklini belirliyor: alarmları sadece azaltan bir çözüm
(örneğin severity eşiği) gerekçe üretemez ve puanlama ölçütlerinin ikisini
(kök neden isabeti, gürültü elemesi) doğrudan kaybeder.

Ölçülecek dört şey ve her birinin karşılığı:

| Jüri ölçütü | Çözümde karşılığı |
|---|---|
| İndirgeme oranı | 3000 alarm → ≤15 kart |
| Kök neden isabeti | Küme içi kök aday sıralaması |
| **Yanlış birleştirme** | Bağımlılık grafiğinde ayrışma testi |
| Gürültü elemesi | Alarm başına gerekçeli eleme skoru |

---

## 2. Veri keşfi bulguları

Tümü `senaryo_paketi/` üzerinde doğrulandı; hiçbiri varsayım değildir.

### 2.1 Veri sağlığı

- 3000 satır, **eksik değer yok**, `alarm_id` 3000/3000 benzersiz
- `alarms.json` ile `alarms.csv` birebir aynı (3000/3000 id kesişimi) → **CSV ile çalışılacak**
- Pencere: 10 Eylül 2026, 01:30:20 – 03:30:20 (tam 2 saat)
- 27 servis, 56 host, 25 alarm tipi (sözlükte 26 kod listeli, veride 25'i görülüyor)

### 2.2 Zaman yapısı — 2 dakikalık yoğunluk

Gürültü tabanı ~30 alarm/2dk. Üzerine binen yapılar:

```
01:42–01:52   ani patlama, tepe 138/2dk      → OLAY-1
02:04–02:26   yayvan plato, ~60/2dk          → OLAY-2  (yavaş gelişen)
02:38–02:56   ikinci patlama, tepe 89/2dk    → OLAY-3 + OLAY-4 (çakışık)
03:04–03:28   hafif yükselti                 → OLAY-5  (yavaş gelişen)
```

### 2.3 Tespit edilen olaylar

Her biri ilk-görülme sıralaması ve bağımlılık grafiğiyle doğrulandı.

**OLAY-1 · dc1/rack-A kabin ağ arızası · 01:42–01:54**
Zincir: `network_down (01:42:13)` → `pkt_loss` → `network_flap` → `latency_high`
→ `http_5xx` → `conn_refused` → `timeout` → `thread_pool`.
**Lokalite kanıtı kesin:** ağ alarmlarının 55/56'sı dc1/rack-A'da ve o kabindeki
**9 host'un 9'u da** etkilenmiş. Diğer kabinlerde karşılığı yok.

**OLAY-2 · billing-db disk dolması · 02:05–02:32** *(yavaş gelişen)*
Zincir: `disk_full (02:05:06, sev 5.0, ao-034/035/036-billing)` → `db_write_fail`
→ `db_conn_pool` → `txn_fail`.
Grafik doğrulaması: `billing-service → billing-db`, `invoice-batch → billing-db`,
`payment-service → billing-service`. Gözlenen etkilenen servisler bu yayılımla
birebir örtüşüyor (billing-service 81, invoice-batch 26, billing-db 25, payment-service 23).

**OLAY-3 · payment-provider-gw dış servis kesintisi · 02:40–02:58**
Zincir: `ext_unreach + ext_slow (02:40:28, sev 5.0, ao-052/053/054-payment)` →
`timeout` → `http_5xx` → `txn_fail`.
Grafik: `payment-service → payment-provider-gw`, `order-service → payment-service`,
`mobile-bff → order-service`. Gözlenen: payment-service 85, mobile-bff 87, order-service 57.

**OLAY-4 · session-service bellek tükenmesi · 02:38–02:52** *(OLAY-3 ile çakışık, bağımsız)*
`oom_risk (02:38:47, sev 4.8, ao-012/013/014-session)`, yalnızca session-service.

**OLAY-5 · toplu iş çakışması → subscriber-db kaynak yarışı · 03:05–03:28** *(yavaş gelişen)*
Zincir: `batch_overlap (03:05:28, batch-scheduler)` → `batch_slow (reconciliation, report)`
→ `db_conn_pool` → subscriber-db/subscriber-service `cpu_high`, `latency_high`.
Grafik: `reconciliation-batch → subscriber-db`, `report-batch → subscriber-db`.

### 2.4 Gürültü profili

Zamanda düzgün yayılmış, düşük şiddetli, hiçbir olay zincirine bağlanmayan tipler:
`cert_expiry` (220, sev 1.9), `mem_high` (240, sev 2.0), `cpu_high` (230, sev 2.2),
`network_flap` (202, sev 2.3), `log_rotate` (196, sev 2.0), `ntp_drift` (193, sev 2.0),
`disk_warn` (189, sev 1.9), `backup_warn` (177, sev 2.1).

Kabaca **1600–1900 alarm** bu sınıfta. Ama eleme *tip adına göre* yapılamaz — bkz. 2.5.

### 2.5 Tuzaklar — çözümü bunlar şekillendiriyor

Bu dördü keşif sırasında ölçülerek bulundu ve tasarımı doğrudan kısıtlıyor:

1. **Severity tek başına yetmez.** Olay pencerelerinin *içindeki* alarmların
   yalnızca %34'ü sev≥4. Pencere dışında da 50 adet sev≥4 var. Eşik koyan çözüm
   hem olay alarmlarını kaçırır hem gürültü alır.
2. **Alarm tipi olaylar arasında paylaşılıyor.** `cpu_high`, `network_flap`,
   `db_conn_pool`, `latency_high` hem olaylarda hem gürültüde geçiyor.
   `db_conn_pool` tek başına üç ayrı olayda görünüyor (billing, subscriber, reconciliation).
3. **OLAY-3 ile OLAY-4 hem zamanda çakışıyor hem ortak mağdur paylaşıyor.**
   İkisi de `mobile-bff`'i etkiliyor (biri order-service üzerinden, diğeri
   doğrudan `mobile-bff → session-service` kenarıyla). Sadece zaman+servis
   benzerliğine bakan her kümeleme bunları **birleştirir** ve "yanlış birleştirme"
   ölçütünden puan kaybeder. Grafikte `payment-provider-gw`'den `session-service`'e
   giden yol **yoktur** — ayrımın dayanağı budur.
4. **`source_system` ayırt edici değil.** Beş sistemin severity dağılımı neredeyse
   birebir aynı. Öznitelik olarak kullanılmayacak.

---

## 3. Hipotezler

| # | Hipotez | Durum |
|---|---|---|
| H1 | Veride 4–6 bağımsız gerçek olay var | **Destekleniyor** — 5 aday bulundu |
| H2 | Kök neden alarmı, kümenin zamansal olarak ilkidir | **Kısmen** — 5/5 olayda ilk yüksek-şiddetli alarm kök; ama düşük şiddetli gürültü daha önce geliyor, ham "ilk" yanıltıcı |
| H3 | Bağımlılık grafiği yayılımı açıklıyor | **Güçlü destek** — 4 olayda etkilenen servis listesi grafik komşuluğuyla örtüşüyor |
| H4 | Gürültü, tipinin kendi taban hızından sapmayan alarmdır | **Destekleniyor** — gürültü tipleri %11–16 yoğunlaşma, olay tipleri %75–100 |
| H5 | Lokalite (kabin/dc) bazı olaylarda kök nedeni tek başına ele veriyor | **Destekleniyor** — OLAY-1'de 9/9 kabin doluluğu |

---

## 4. Alternatif yaklaşımlar

### A) Denetimsiz kümeleme (DBSCAN/HDBSCAN, gömülü öznitelikler)

Alarmları vektörleştirip yoğunluk tabanlı kümele.

- **Artı:** Kural yazmadan çalışır, "AI" görünür.
- **Eksi:** Kümenin *neden* o küme olduğu açıklanamaz — açıklanabilirlik puanı gider.
  Bağımlılık grafiğini kullanamaz. 2.5'teki 3 numaralı tuzağa doğrudan düşer:
  OLAY-3 ve OLAY-4 zaman+servis uzayında bitişik olduğu için **birleştirilir**.
  Hiperparametre ayarı 2h45'te riskli.
- **Karar:** Ana yöntem olarak reddedildi.

### B) Saf kural tabanlı korelasyon (zaman penceresi + servis eşleşmesi)

Sabit pencerede aynı servisin alarmlarını topla.

- **Artı:** 30 dakikada yazılır, tamamen açıklanabilir.
- **Eksi:** Sabit pencere yavaş gelişen OLAY-2 ve OLAY-5'i ya böler ya kaçırır.
  Gürültü elemesi için gerekçe üretemez ("eşiğin altındaydı" gerekçe değildir).
  Kök neden sıralaması yapamaz.
- **Karar:** Tek başına yetersiz; ancak (C)'nin içinde taban katman olarak yaşıyor.

### C) Bağımlılık-grafiği farkında nedensel kümeleme + gerekçeli gürültü skorlaması ⟵ **SEÇİLDİ**

Dört aşamalı, her aşaması sayı üreten boru hattı:

1. **Sinyal/gürültü skorlaması** — her alarm için, kendi tipinin taban hızına
   göre aşırılık (excess-over-baseline) × şiddet × yerel yoğunluk.
   Çıktı bir *skor*, ikili karar değil → eleme gerekçesi otomatik oluşur.
2. **Nedensel kümeleme** — sinyal alarmları zamansal yakınlık **ve** bağımlılık
   grafiği mesafesi birlikte kullanılarak birleştirilir. Uyarlanabilir pencere
   (aktivite düşene kadar genişler) yavaş gelişen olayları yakalar.
3. **Ayrışma testi (X-Factor'ün çekirdeği)** — bir küme, grafikte birbirine
   bağlanmayan iki bileşene ayrılıyorsa **bölünür**. OLAY-3/OLAY-4 ayrımı bu
   testle garanti altına alınır.
4. **Kök neden sıralaması** — küme içindeki her aday için "bu adayı kök kabul
   edersem kümenin yüzde kaçını grafikte aşağı doğru açıklayabiliyorum" hesaplanır.
   En yüksek açıklama oranı kök, ikincisi **karşı hipotez** olarak kartta kalır.

- **Artı:** Dört jüri ölçütünün dördünü de doğrudan hedefler. Her karar bir
  sayıya dayandığı için §13'teki `SONUÇ → KANIT → GEREKÇE → GÜVEN` yapısı
  zorlamadan çıkar. Gürültü denetim görünümü (bonus) 1. aşamadan bedavaya gelir.
- **Eksi:** (A) ve (B)'den daha fazla parça; süre riski var.
- **Risk azaltma:** Parçalar sırayla çalışır durumda tutulacak — 1+2 bittiğinde
  zaten teslim edilebilir bir çözüm var, 3 ve 4 üzerine ekleniyor.

**Seçim gerekçesi:** Brifing "gerekçesiz doğru hipotez, gerekçeli yanlıştan daha
az puan alır" diyor. Bu cümle yöntem seçimini tek başına belirliyor: açıklanamayan
kümeleme (A) yapısal olarak kaybediyor. (C), (B)'nin açıklanabilirliğini korurken
yavaş gelişen olay ve yanlış birleştirme problemlerini çözüyor.

---

## 5. X-Factor

**Ayrışma testi + karşı hipotezli kök neden sıralaması.**

Sıradan bir korelasyon aracının yapamadığı şey: *iki olayın aynı anda olup aynı
servisi vurduğunu fark edip yine de ayırmak.* OLAY-3 ve OLAY-4 bunun kanıtı —
ikisi de 02:38–02:58'de, ikisi de `mobile-bff`'i etkiliyor, ama kökleri arasında
grafik yolu yok.

Ölçülebilir iddia: **ayrışma testi kapalıyken bu iki olay tek kartta birleşir,
açıkken ayrı kartlara çıkar.** Demoda bu anahtar açılıp kapatılarak gösterilecek.

İkinci bileşen: her kart kendi **karşı hipotezini** ve elenen alarmların
**neden elendiğini** taşır (bonus gereksinimlerin ikisi).

---

## 6. Başarı kriterleri

| Kriter | Hedef | Nasıl ölçülecek |
|---|---|---|
| İndirgeme | 3000 → ≤15 kart | kart sayısı / 3000 |
| Olay yakalama | 5/5 aday olay ayrı kartta | kartların kök servisi ile §2.3 karşılaştırması |
| Yanlış birleştirme | 0 | ayrışma testi açık/kapalı kart sayısı farkı |
| Gürültü elemesi | ≥%50 alarm gerekçeli elenmiş | elenen sayısı ve skor dağılımı |
| Çalışma süresi | < 10 sn (3000 alarm, uçtan uca) | süre ölçümü |

---

## 7. Yapılacak işler — 2 sa 46 dk bütçesi

Sıra §18'deki önceliğe uyuyor: önce çalışan baseline, en son dokümantasyon.

| Zaman | İş | Biten çıktı |
|---|---|---|
| 14:45–15:15 | `src/` iskelet, veri yükleme, sinyal/gürültü skorlaması | CLI'dan skor dağılımı basılıyor |
| 15:15–15:45 | Nedensel kümeleme + uyarlanabilir pencere | CLI'dan N küme listeleniyor |
| 15:45–16:05 | Ayrışma testi + kök neden sıralaması | Kümeler kök adayı ve karşı hipotezle çıkıyor |
| 16:05–16:25 | Olay kartı + aksiyon kaydı (sahip/durum) | Kart JSON'u üretiliyor, aksiyon durumu değişiyor |
| 16:25–16:55 | Streamlit arayüzü + gürültü denetim sekmesi | Canlı demo ayakta |
| 16:55–17:15 | Ekran görüntüleri, README, AI_JURI, submission, metrikler | Teslim dosyaları güncel |
| 17:15–17:30 | Tampon, son kontrol (§19 listesi), son commit+push | Teslim |

Her dilim sonunda commit atılacak; yetişmeyen dilim varsa o ana kadarki hâl
zaten çalışır durumda olacak.

---

## 8. Riskler

| Risk | Etki | Önlem |
|---|---|---|
| Streamlit'e zaman kalmaması | Canlı demo yok — kabul kriteri düşer | Boru hattı **önce CLI** olarak bitirilecek; arayüz ince bir katman. CLI tek başına demo edilebilir |
| Ayrışma testi fazla bölme yapması (>15 kart) | Kabul kriteri ihlali | Eşik parametrik; kart sayısı üst sınırı zorlanacak, artan kartlar "düşük güven" grubunda toplanacak |
| Kök neden sıralamasının yanlış çıkması | Puan kaybı | Karşı hipotez zaten kartta; brifing gerekçeli yanlışı kabul ediyor |
| Doğrulama verisi bizim 5 olayla örtüşmemesi | İsabet puanı düşer | Olay sayısı sabit kodlanmayacak, veriden türetilecek |
| Son dakika commit'inin kaçması | Teslim edilmemiş sayılır | 17:15'te zorunlu ara teslim; sonrası iyileştirme |

---

## 9. Varsayımlar

Aşağıdakiler veriden **türetildi**, bize söylenmedi — yanlış çıkabilirler:

1. Olay sayısı 5'tir. Brifing sayıyı vermiyor; bu bizim çıkarımımız.
2. OLAY-3 ile OLAY-4 bağımsızdır. Dayanak: grafikte aralarında yol yok.
   Ortak bir altyapı nedeni (aynı kabin, aynı hypervisor) veride görünmüyor.
3. `ortam` alanı tüm satırlarda `prod` olduğu için ayırt edici değildir, kullanılmayacak.
4. Gözlem penceresi kapalıdır; 03:30'dan sonra devam eden olaylar görülemez.
   OLAY-5 pencere sonunda hâlâ aktif görünüyor — kartında bu belirtilecek.
