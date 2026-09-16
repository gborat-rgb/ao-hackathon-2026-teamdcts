# Fazlar

**Takım:** Fail-i Over · **Senaryo:** S-A1 Alarm Fırtınası · 16 Eylül 2026

---

## Faz 0 — Ön hazırlık (senaryo açılmadan önce)

**Durum:** Tamamlandı

**Çıktı:**
- Git erişimi doğrulandı. Port 22 kurumsal ağdan kapalı çıktı; `ssh.github.com:443`
  üzerinden çözüldü, host anahtarı parmak iziyle doğrulanarak eklendi.
- `requirements.txt` oluşturuldu, sürümler kurulu ortamdan okundu.
- `submission.json` içindeki `Python 3.11+` iddiası düzeltildi — gerçek ortam 3.9.2.

**Karar:** Ortam Python 3.9 tavanına kilitli (`numpy 2.0.x` son seri).
Yarışma sırasında `pip install -U` çalıştırılmayacak.

---

## Faz 1 — Veri Keşfi (14:45 – 15:10)

**Durum:** Tamamlandı · **Kod yazılmadı**

**Çıktı:** `docs/plan.md` §2

- 3000 satır, eksik değer yok, `alarms.json` ile `alarms.csv` birebir aynı
- Beş olay adayı tespit edildi ve ilk-görülme sıralaması + bağımlılık
  grafiğiyle doğrulandı
- Dört tuzak ölçülerek bulundu: severity ayırt etmiyor (%34), alarm tipi
  olaylar arasında paylaşılıyor, OLAY-03/04 çakışık ve ortak mağdur
  paylaşıyor, `source_system` ayırt edici değil

**Karar:** Bu dört ölçüm kolay yolları kapattı ve yöntem seçimini belirledi.

---

## Faz 2 — Yaklaşım Seçimi (15:10 – 15:15)

**Durum:** Tamamlandı

**Çıktı:** `docs/plan.md` §4 — üç alternatif değerlendirildi

| Alternatif | Karar |
|---|---|
| A) Denetimsiz kümeleme (DBSCAN/HDBSCAN) | **Reddedildi** — açıklanamaz, OLAY-03/04'ü birleştirir |
| B) Sabit pencereli kural korelasyonu | **Yetersiz** — yavaş gelişen olayları böler |
| C) Grafik farkında nedensel kümeleme | **Seçildi** |

**Karar:** Belirleyici argüman brifingin kendi cümlesi — *"gerekçesiz doğru
hipotez, gerekçeli yanlıştan daha az puan alır."* Açıklanamayan yöntem
yapısal olarak kaybediyor. İnsan onayı alındıktan sonra kodlamaya geçildi.

---

## Faz 3 — Boru Hattı Çekirdeği (15:15 – 15:40)

**Durum:** Tamamlandı

**Çıktı:** `src/ingest.py`, `src/scoring.py`, `src/clustering.py`

- Bağımlılık grafiği `hedef → kaynak` yönünde kuruldu (etki yönü)
- Poisson sapması tabanlı skorlama: 1888/3000 alarm gerekçeli olarak elendi
- Union-find kümeleme dört ham küme üretti, dördü de keşifteki pencerelerle örtüştü

**Karar ve düzeltmeler — kök atfı üç turda oturdu:**

1. İlk sürüm `dns-resolver` ve `log_rotate` gibi anlamsız kökler verdi.
   *Neden:* ham "ilk alarm" gürültüyle kirleniyordu.
   *Düzeltme:* öncelik ve imza yalnızca `severity ≥ 4` üzerinden.
2. Kabin kökü eklendi (OLAY-01'in servis karşılığı yok), ilk kapı olarak
   grafik bileşen sayısı kullanıldı. *Bu kapı gerçek kabin arızasını eledi.*
   *Düzeltme:* host kapsamı ölçüldü — gerçek arızada %100, diğer tüm
   kabin/küme çiftlerinde en fazla %56. Kapı bununla değiştirildi.
3. Ayrışma eşiği (%15) gerçek ayrımı kaçırıyordu; artık oranı %11'di.
   *Düzeltme:* eşiği düşürmek yerine ölçüt değiştirildi → **grafik kopukluğu**.

**Sonuç:** Beş olayın beşi de doğru kökle çıktı. X-Factor ölçülebilir hale
geldi: ayrışma kapalı 4 kart, açık 5 kart.

---

## Faz 4 — Kartlar, Aksiyon ve CLI (15:40 – 15:55)

**Durum:** Tamamlandı

**Çıktı:** `src/cards.py`, `src/pipeline.py`, `src/cli.py`

- `SONUÇ → KANIT → GEREKÇE → GÜVEN/SINIRLAR` yapısı; ölçülen ile çıkarılan
  ayrı alanlarda
- Sahipli aksiyon, `acik → devam_ediyor → kapandi`, zaman damgalı geçmiş
- CLI üç görünüm: kartlar, X-Factor, gürültü denetimi

**Karar:** CLI arayüzden **önce** yazıldı. Gerekçe `docs/plan.md` §8'deki
risk maddesi: Streamlit'e zaman kalmazsa demo yine yapılabilsin.

---

## Faz 5 — Arayüz (15:55 – 16:10)

**Durum:** Tamamlandı

**Çıktı:** `src/app.py` — dört sekme

- Kenar çubuğundaki ayrışma anahtarı, X-Factor'ü canlı göstermek için
- `streamlit.testing.AppTest` ile doğrulandı: sıfır exception, 5 kart,
  aksiyon durum geçişi ve geçmişi uçtan uca çalışıyor

**Karar:** `st.plotly_chart(width=...)` parametresi geçersizmiş, sessizce
plotly config'e düşüyordu; imza kontrol edilip `use_container_width` ile
değiştirildi.

---

## Faz 6 — Test (16:10 – 16:15)

**Durum:** Tamamlandı

**Çıktı:** `tests/test_pipeline.py` — 19 test, hepsi geçiyor

Testler mevcut çıktının fotoğrafını çekmiyor, **tutması gereken özellikleri**
sabitliyor: tüm veri işleniyor mu, her alarm gerekçeli sınıflandırılmış mı,
kart sayısı kabul kriterinde mi, OLAY-03 ile OLAY-04 ayrı mı, gürültü elemesi
iki yönlü mü (yayvan tipler eleniyor **ve** yoğunlaşan tipler tutuluyor).

---

## Faz 7 — Dokümantasyon ve Teslim (16:15 – )

**Durum:** Devam ediyor

**Çıktı:** `docs/mimari.md`, `README.md`, `AI_JURI.md`, `docs/fazlar.md`,
`demo/` (yeniden üretilebilir CLI çıktıları + demo akışı), `submission.json`

**Açık iş:** Canlı arayüzden ekran görüntüleri elle alınacak. Otomatik almak
için `playwright` denendi; bağımlılığı `greenlet` C++ derleyici istiyor,
ortamda yok. Adımlar `demo/demo-notes.md` içinde.
