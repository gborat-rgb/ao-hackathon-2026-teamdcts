# Alarm Fırtınası → Olay Kartları

**Takım:** Fail-i Over · **Senaryo:** AO Hackathon 2026 · S-A1

İki saatlik pencerede gelen 3000 alarmı, nöbetçi mühendisin okuyup harekete
geçebileceği **5 olay kartına** indirger; her kartın kök neden hipotezini
kanıtı, gerekçesi ve karşı hipoteziyle birlikte gösterir.

---

## Çözülen problem

Alarm ekranındaki güçlük sayı değil, **neden-sonuç ilişkisinin görünmemesi**.
Hangi alarmın kök neden, hangisinin türev etki, hangisinin bağımsız gürültü
olduğu ayırt edilemediği için müdahale sırası yanlış kurulur.

Bu yüzden çözüm bir filtre değil, bir **nedensellik atfetme** aracı:

```
3000 alarm  →  1888'i gerekçeli olarak gürültü  →  1112 sinyal  →  5 olay kartı
```

---

## Nasıl çalışıyor

Dört aşamalı boru hattı. Her aşama bir sayı üretir, böylece her karar
denetlenebilir.

**1. Sinyal/gürültü skorlaması** (`src/scoring.py`)
Her alarm, kendi tipinin ve servisinin o dakikada beklenenden ne kadar fazla
göründüğüyle ölçülür (Poisson sapması). Bu ölçü nadir ama yoğunlaşan tipleri
(`network_down`: 12 alarm, hepsi tek kovada) öne çıkarır, sık ama yayvan
olanları (`cert_expiry`: 220 alarm, dağılmış) tabanda bırakır. Çıktı ikili
karar değil skordur — elenen her alarm gerekçesini taşır.

**2. Nedensel kümeleme** (`src/clustering.py`)
Alarmlar hem zamanda hem bağımlılık grafiğinde yakınsa birleşir. Bağlantı
geçişken olduğu için pencere uyarlanabilir: yavaş gelişen olaylar (20 dakikaya
yayılan disk dolması) tek parça kalır.

**3. Ayrışma testi** — X-Factor
Bir kümenin açıklanamayan artığı kendi köküne sahipse ve bu kök birincil kökle
grafikte **bağlı değilse**, küme bölünür.

**4. Kök neden sıralaması ve kart üretimi** (`src/cards.py`)
Adaylar açıklama oranı, öncelik ve imza gücüyle sıralanır. Birinci kök,
ikincisi karşı hipotez olur.

Ayrıntılı mimari: **[`docs/mimari.md`](docs/mimari.md)**
Analiz ve yaklaşım seçimi: **[`docs/plan.md`](docs/plan.md)**

---

## X-Factor — grafik ayrışma testi

02:38–02:58 arasında iki bağımsız olay aynı anda gerçekleşiyor:
`payment-provider-gw` dış servis kesintisi ve `session-service` bellek
tükenmesi. **İkisi de `mobile-bff`'i etkiliyor.** Zaman ve servis benzerliğine
bakan her kümeleme bunları tek olay sayar ve "yanlış birleştirme" ölçütünden
puan kaybeder.

Bağımlılık grafiğinde bu iki kök arasında **yol yoktur** (mesafe 4 > 2).
Ayrım buna dayanır ve ölçülebilir:

| Ayrışma testi | Üretilen kart |
|---|---|
| Kapalı | 4 |
| **Açık** | **5** ← `session-service` ortaya çıkıyor |

```bash
python -m src.cli --x-factor
```

Kod: `src/clustering.py` → `ayristir()` ve `_kokler_kopuk_mu()`
Test: `tests/test_pipeline.py::test_session_service_payment_ile_birlesmiyor`

---

## Kurulum

```bash
git clone git@github.com:gborat-rgb/ao-hackathon-2026-teamdcts.git
cd ao-hackathon-2026-teamdcts
pip install -r requirements.txt
```

Python **3.9.2** ile geliştirildi ve doğrulandı. `numpy 2.0.x`, Python 3.9'u
destekleyen son seridir; pinleri yükseltmek ortamı kırar.

---

## Çalıştırma

```bash
# Olay kartları (terminal)
python -m src.cli

# X-Factor ölçümü
python -m src.cli --x-factor

# Gürültü denetimi — neden elendi
python -m src.cli --gurultu 25

# Makine okunur çıktı
python -m src.cli --json

# Web arayüzü
streamlit run src/app.py
```

Testler:

```bash
python -m pytest tests/ -q        # 19 test
```

---

## Sonuçlar

Tam veri seti üzerinde ölçüldü (üç koşunun ortalaması):

| Metrik | Değer |
|---|---|
| İşlenen alarm | 3000 (tamamı, örnekleme yok) |
| Gürültü elenen | 1888 (**%63**) |
| Üretilen kart | **5** (kabul kriteri ≤15) |
| İndirgeme | **600×** |
| Uçtan uca süre | **0,37 sn** |
| Test | 19/19 geçiyor |

### Bulunan olaylar

| Kart | Kök neden | İmza | Alarm | Güven |
|---|---|---|---|---|
| OLAY-01 | `dc1/rack-A` kabin ağ arızası | `pkt_loss` | 473 | yüksek |
| OLAY-02 | `billing-db` disk dolması | `disk_full` | 167 | yüksek |
| OLAY-03 | `payment-provider-gw` dış kesinti | `ext_slow` | 260 | yüksek |
| OLAY-04 | `session-service` bellek tükenmesi | `oom_risk` | 27 | orta |
| OLAY-05 | `subscriber-db` bağlantı havuzu | `db_conn_pool` | 67 | yüksek |

OLAY-01'in kanıtı özellikle keskin: `dc1/rack-A` kabinindeki **9 host'un 9'u
da** alarm üretiyor, diğer tüm kabin/küme çiftlerinde bu oran en fazla %56.

---

## Kullanılan AI araçları

| Araç | Model | Sürüm | Ne için |
|---|---|---|---|
| Claude Code (CLI) | Claude Opus 5 | `claude-opus-5[1m]` | Veri keşfi, yaklaşım karşılaştırması, uygulama, test, dokümantasyon |

**Platform:** SAKA (Turkcell kurumsal sarmalayıcı)
**MCP sunucusu:** kullanılmadı
**Harici API:** kullanılmadı — çözüm tamamen çevrimdışı çalışır

### İnsan / AI iş bölümü

| Karar | Kim verdi |
|---|---|
| Yaklaşım seçimi (3 alternatif arasından) | AI önerdi, **insan onayladı** |
| Kabin seviyesi kök neden fikri | AI, veri keşfindeki 9/9 bulgusundan türetti |
| Ayrışma testinin X-Factor olması | AI önerdi, **insan onayladı** |
| Eşik ve ağırlık değerleri | AI, veriye bakarak seçti |
| Kapsam ve zaman bütçesi | **İnsan** |

Kritik promptlar: [`prompts/`](prompts/)
Model çalışma kuralları: [`DIREKTIF.md`](DIREKTIF.md), [`CLAUDE.md`](CLAUDE.md)

---

## Kullanılan kütüphaneler

`pandas` `numpy` `scipy` · `scikit-learn` · `streamlit` `plotly` `altair`
`matplotlib` · `pydantic` `requests` `python-dotenv` · `pytest` · `shap`

Tam sürüm listesi: [`requirements.txt`](requirements.txt)

> Not: `scikit-learn` ve `shap` ortama kuruldu ve keşif aşamasında denendi,
> ancak **son çözümde kullanılmıyor**. Kümeleme, denetimsiz bir modelden
> değil, bağımlılık grafiğinden türetiliyor — gerekçesi `docs/plan.md` §4'te.

---

## Demo

[`demo/`](demo/) klasöründe yeniden üretilebilir çıktılar ve demo akışı var:
`01_olay_kartlari.txt`, `02_x_factor.txt`, `03_gurultu_denetimi.txt`,
`04_kartlar.json`, `05_test_sonuclari.txt`, `demo-notes.md`.

Deploy URL yok — çözüm yerelde çalışır.

---

## Bilinen sınırlar

1. **Olay sayısı veriden türetildi**, bize söylenmedi. Doğrulama verisi farklı
   sayıda olay içerebilir.
2. **OLAY-05'in kökü tartışmalı.** Bağımlılık grafiği *arıza* yayılımını
   modelliyor, *yük* yayılımını değil; yük bağımlılık kenarının ters yönünde
   akar. Bu yüzden toplu iş çakışması `batch-scheduler` yerine `subscriber-db`
   kökü altında çıkıyor, `batch-scheduler` karşı hipotez olarak kartta duruyor.
3. **Gözlem penceresi kapalı.** 03:30 sonrası görülemiyor; OLAY-05 pencere
   sonunda hâlâ aktif ve kartında belirtiliyor.
4. **Gürültü elemesinde sızıntı var.** `cert_expiry` ve `backup_warn`'dan
   birkaç alarm sinyal tarafında kalıyor.
5. **Aksiyon durumu kalıcı değil** — Streamlit oturum belleğinde tutuluyor;
   kalıcı veritabanı senaryoda kapsam dışı bırakılmıştı.
6. **Ekran görüntüleri elle alınmalı.** Otomatik almak için `playwright`
   denendi, `greenlet` C++ derleyici istediği ve ortamda bulunmadığı için
   kurulamadı. Adımlar `demo/demo-notes.md` içinde.
