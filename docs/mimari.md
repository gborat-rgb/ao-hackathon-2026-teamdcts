# Mimari

**Takım:** Fail-i Over · **Senaryo:** S-A1 Alarm Fırtınası

Bu doküman çalışan koda karşılık gelir. Her bölüm ilgili dosyayı işaret eder.

---

## 1. Genel akış

```
senaryo_paketi/                  ingest.py         scoring.py
  alarms.csv        ────────►  veriyi_hazirla  ──►  skorla
  host_inventory.csv             (+ grafik)         her alarma
  service_dependencies.csv                          sinyal skoru
                                                         │
                                      ┌──────────────────┴────────┐
                                      ▼                           ▼
                              sinyal adayı (1112)       skor gürültüsü (1888)
                                      │                           │
                              clustering.py                       │
                                 kumele()                         │
                            zaman + grafik yakınlığı              │
                                      │                           │
                                ayristir()                        │
                        grafik ayrışma testi (X-Factor)           │
                                      │                           │
                         pipeline.py muhasebe kapısı               │
                         994 atanmış + 118 dışarıda                │
                                      │                           │
                                  cards.py                        │
                         kart + kanıt + gerekçe + aksiyon         │
                                      │                           │
                          ┌───────────┴───────────┐               │
                          ▼                       ▼               ▼
                       cli.py                  app.py      gürültü denetimi
                    terminal çıktısı        Streamlit UI     (app.py sekme 3)
```

Tek yönlü, durumsuz bir boru hattı. Kalıcı veritabanı yok (kapsam dışı
bırakılmıştı); aksiyon durumu Streamlit oturum belleğinde tutuluyor.

---

## 2. Bileşenler

### `src/ingest.py` — veri girişi ve bağımlılık grafiği

Üç dosyayı okur, host envanterini alarmlara birleştirir.

Okuma sırasında zorunlu sütun, boş kritik alan, benzersiz `alarm_id`, ISO-8601
zaman, 1–5 tam sayı severity, host/servis envanter eşleşmesi ve dependency
servis bütünlüğü doğrulanır. Eksik veya bozuk dosya traceback yerine alanı ve
dosyayı söyleyen `VeriDogrulamaHatasi` üretir.

**Kritik tasarım kararı — etki yönü.** Veri sözlüğü `kaynak_servis`in
`hedef_servis`e bağımlı olduğunu söylüyor: *hedef bozulursa kaynak etkilenir.*
Grafiği bu yüzden `hedef → kaynak` yönünde kuruyoruz. Böylece "kök nedenin
aşağı akışı" tek bir BFS ile hesaplanabiliyor (`asagi_akis`).

Ayrıca kabin başına envanter host sayısı (`kabin_host_sayisi`) grafiğe
iliştiriliyor; kabin seviyesi kök neden testi bunu kullanıyor.

### `src/scoring.py` — sinyal / gürültü skorlaması

Her alarm için, kendi tipinin ve kendi servisinin o zaman diliminde
beklenenden ne kadar fazla göründüğü ölçülür:

```
z = (gözlenen − beklenen) / √beklenen        (Poisson sapması)
sinyal_skoru = 0.45·ẑ_tip + 0.35·ẑ_servis + 0.20·severity_norm
```

Beklenen değer, tipin tüm pencereye düzgün yayıldığı varsayımından gelir.
Bu ölçü **nadir ama yoğunlaşan** tipleri öne çıkarır (`network_down`: 12 alarm,
hepsi tek kovada) ve **sık ama yayvan** olanları tabanda bırakır
(`cert_expiry`: 220 alarm, her kovaya dağılmış).

Çıktı ikili bir karar değil, skordur. Eşiğin altında kalan her alarm
`eleme_gerekcesi` taşır — gürültü denetim görünümü bundan doğar.

**Neden severity tek başına kullanılmadı:** ölçüldü, ayırt etmiyor. Olay
pencerelerinin içindeki alarmların bile yalnızca %34'ü sev≥4
(`docs/plan.md` §2.5).

### `src/clustering.py` — nedensel kümeleme

**Aşama 1 — `kumele()`.** İki sinyal alarmı, hem zamanda yakınsa (≤180 sn)
hem de grafikte yakınsa (≤2 atlama) birleştirilir. Union-find kullanıldığı
için bağlantı geçişkendir: alarmlar gelmeye devam ettiği sürece küme uzar.
Bu, pencereyi **uyarlanabilir** yapar ve yavaş gelişen olayları (billing disk
dolması 20 dk, toplu iş çakışması 18 dk) tek parça tutar. Sabit pencereli bir
yaklaşım bunları bölerdi.

**Aşama 2 — kök neden adayları.** Her aday için üç ölçü:

| Ölçü | Anlamı |
|---|---|
| `aciklama_orani` | Bu kök kabul edilirse kümenin yüzde kaçı grafikte aşağı akışında kalıyor |
| `oncelik` | Kümenin yüzde kaçı kökün ilk **şiddetli** alarmından sonra geliyor |
| `imza` | Kökün en yoğunlaşmış alarm tipinin z skoru |

`skor = 0.35·açıklama + 0.40·öncelik + 0.25·imza`

Öncelik ve imza daima `severity ≥ 4` alarmları üzerinden ölçülür. Gürültü
düşük şiddetle sızabildiği için ham "ilk alarm" yanıltıcıdır — ilk denemede
kök `log_rotate` çıkmıştı, bu kısıt onu eledi.

**İki tür aday yarışır:**

- **Servis kökü** — `billing-db`, `payment-provider-gw`, `session-service`, `subscriber-db`
- **Kabin kökü** — `dc1/rack-A kabini`

Kabin kökü gereklidir çünkü bazı arızaların servis karşılığı yoktur: bir
kabinin ağı çöktüğünde o kabindeki *birbiriyle ilgisiz* servisler aynı anda
alarm üretir ve servis grafiği bunu açıklayamaz.

**Kabin kökü kapısı — host kapsamı.** Kabin kökü ancak kabindeki host'ların
≥%75'i alarm üretiyorsa önerilir. Veride ölçülen ayrım keskin:

| | Host kapsamı |
|---|---|
| Gerçek kabin arızası (dc1/rack-A, OLAY-01) | **%100** (9/9) |
| Diğer tüm kabin × küme çiftleri | en fazla %56 |

Bu kapı ilk denemede yoktu ve OLAY-05'e yanlışlıkla kabin kökü atanmıştı.

### Aşama 3 — ayrışma testi (X-Factor) · `ayristir()`

Bir kümenin artığı (birincil kökün açıklayamadığı üyeler) kendi köküne
sahipse **ve** bu kök birincil kökle grafikte bağlı değilse, küme bölünür.

```python
kopuk = grafik.mesafe(kök_1, kök_2) is None or mesafe > 2
if kopuk or (artık_oranı > 0.40 and artık_imzası >= 0.35):
    böl
```

Asıl ölçüt grafik kopukluğudur. Bağlı kalan bir artık, ancak hem çok büyükse
hem de kendi başına güçlü bir imzası varsa ayrı olay sayılır; aksi halde aynı
olayın geç gelen kuyruğudur ve bölmek yanlış olur. Bu ikinci koşul, billing
kümesinden sahte bir `charging-service / log_rotate` kartı türemesini
engelledi.

### `src/cards.py` — kart, açıklama, aksiyon

Kart yapısı DIREKTIF.md §13'ü izler: **SONUÇ → KANIT → GEREKÇE → GÜVEN/SINIRLAR**.

Kritik ayrım: `kanit` alanı yalnızca **veriden ölçülmüş** gerçekleri taşır,
`gerekce` alanı bunları birleştiren **çıkarımdır**. Jüri hangi sayının nereden
geldiğini ayırt edebilsin diye ayrı alanlarda tutulurlar.

Güven skoru: `0.55·açıklama + 0.25·imza + 0.20·min(boyut/100, 1)`.

Aksiyonlar kök alarm tipine göre sahiplendirilir (`AKSIYON_KATALOGU`) ve
`acik → devam_ediyor → kapandi` geçişlerini zaman damgalı geçmişle tutar.

### `src/app.py` — Streamlit arayüzü

Dört sekme: Olay Kartları (aksiyon durumu değiştirilebilir), X-Factor
karşılaştırması, Gürültü Denetimi, Zaman Çizelgesi.

Kenar çubuğundaki **sinyal eşiği** ve **ayrışma testi** anahtarları canlı
demoda parametrelerin etkisini göstermek için duruyor.

### `src/cli.py` — terminal arayüzü

Arayüzsüz de tam demo yapılabilsin diye Streamlit'ten **önce** yazıldı
(risk azaltma, `docs/plan.md` §8).

---

## 3. Veri giriş/çıkış noktaları

| Yön | Nokta |
|---|---|
| Giriş | `senaryo_paketi/alarms.csv` (3000 satır, tamamı işleniyor) |
| Giriş | `senaryo_paketi/host_inventory.csv` (56 host) |
| Giriş | `senaryo_paketi/service_dependencies.csv` (32 kenar) |
| Çıkış | Terminal kartları — `python -m src.cli` |
| Çıkış | JSON kartlar — `python -m src.cli --json` |
| Çıkış | Web arayüzü — `streamlit run src/app.py` |

`alarms.json` okunmuyor: CSV ile birebir aynı olduğu doğrulandı (3000/3000
id kesişimi), ikisini birden işlemek gereksiz.

---

## 4. Ölçülen sonuçlar

Final QA'daki yedi koşunun ortalaması, tam veri seti ve Python 3.12.14 üzerinde:

| Metrik | Değer |
|---|---|
| Toplam alarm | 3000 |
| Skor gürültüsü | 1888 (%62,9) |
| Sinyal adayı | 1112 |
| Korelasyon dışı sinyal | 118 (%3,9), gerekçeli |
| Kartlara atanan alarm | 994 |
| Açıkça dışlanan toplam | 2006 (%66,9) |
| Kayıp / çift atama | **0 / 0** |
| Üretilen kart | **5** (kabul kriteri: ≤15) |
| İndirgeme | **600×** |
| Uçtan uca süre | **0.625 sn** |
| Ayrışma testi kapalı → açık | 4 kart → **5 kart** |

Üretilen kartlar:

| Kart | Kök neden | İmza | Alarm | Güven | Ayrışma ile |
|---|---|---|---|---|---|
| OLAY-01 | dc1/rack-A kabini | `pkt_loss` | 473 | yüksek (0.99) | ✓ |
| OLAY-02 | billing-db | `disk_full` | 167 | yüksek (0.833) | |
| OLAY-03 | payment-provider-gw | `ext_slow` | 260 | yüksek (0.938) | ✓ |
| OLAY-04 | session-service | `oom_risk` | 27 | orta (0.662) | ✓ |
| OLAY-05 | subscriber-db | `db_conn_pool` | 67 | yüksek (0.759) | |

Beşi de `docs/plan.md` §2.3'te veri keşfiyle bağımsız olarak doğrulanan
olaylarla örtüşüyor.

---

## 5. X-Factor'ün mimarideki yeri

X-Factor tek bir fonksiyondur: `clustering.ayristir()` içindeki kopukluk
kontrolü (`_kokler_kopuk_mu`).

Kanıtı OLAY-03 ile OLAY-04'tür. İkisi de 02:38–02:58 arasında, ikisi de
`mobile-bff`'i etkiliyor. Zaman ve servis benzerliğine bakan her kümeleme
bunları tek olay sayar. Grafikte `payment-provider-gw` ile `session-service`
arasında yol yoktur (mesafe 4 > 2) — ayrım buna dayanır.

Ölçülebilir: anahtar kapalıyken **4 kart**, açıkken **5 kart**. Ortaya çıkan
kök `session-service`. `tests/test_pipeline.py::test_session_service_payment_ile_birlesmiyor`
bunu sabitliyor.

---

## 6. Tasarım tercihleri ve trade-off'lar

| Tercih | Alternatif | Neden |
|---|---|---|
| Poisson z-skoru | Sabit severity eşiği | Ölçüldü: severity ayırt etmiyor (%34) |
| Union-find + geçişken bağlantı | Sabit zaman penceresi | Yavaş gelişen olaylar bölünmesin |
| Grafik kopukluğu ile bölme | Artık oranı ile bölme | Oran, gerçek ayrımı (%11) kaçırıyordu |
| Host kapsamı kapısı | Grafik bileşen sayısı | Bileşen testi gerçek kabin arızasını eledi |
| Şablon tabanlı doğal dil | LLM çağrısı | Demoda ağ/anahtar bağımlılığı olmasın |
| Bellek içi durum | Veritabanı | Kapsam dışı bırakılmıştı |

**Şablon tabanlı açıklama tercihi** bilinçlidir: gerekçe cümlesi, ölçülmüş
sayılardan deterministik olarak üretiliyor. LLM çağrısı daha akıcı metin
verirdi ama demo sırasında ağ/anahtar bağımlılığı yaratır ve her koşuda
farklı metin üreterek tekrarlanabilirliği bozardı. Değiş tokuş:
akıcılıktan ödün verip denetlenebilirlik ve tekrarlanabilirlik kazandık.

---

## 7. Bilinen sınırlar

1. **Olay sayısı veriden türetildi**, bize söylenmedi. Doğrulama verisi farklı
   sayıda olay içerebilir.
2. **OLAY-05'in kökü tartışmalı.** `subscriber-db` bağlantı havuzu tükenmesi
   seçildi, `batch-scheduler` karşı hipotez olarak kartta duruyor. Gerçek
   nedensellik muhtemelen toplu iş çakışmasının veritabanını yormasıdır; ancak
   bağımlılık grafiği *arıza* yayılımını modelliyor, *yük* yayılımını değil —
   yük, bağımlılık kenarının tersi yönde akar. Bu modelleme sınırı bilinçli
   olarak kabul edildi.
3. **Gözlem penceresi kapalı.** 03:30'dan sonrası görülemiyor; OLAY-05 pencere
   sonunda hâlâ aktif ve kartında bu belirtiliyor.
4. **Gürültü elemesinde sızıntı var.** `cert_expiry` ve `backup_warn`'dan
   birkaç alarm sinyal tarafında kalıyor; kartlara girdiklerinde kanıt
   sayılarını bir miktar şişiriyorlar.
5. **Kabin kökü yalnızca kabin granülerliğinde.** Daha ince bir altyapı
   kırılımı (switch, hypervisor) veride yok.
