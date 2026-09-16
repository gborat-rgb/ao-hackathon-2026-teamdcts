# AI Jüri Özeti

**Takım:** Fail-i Over · **Senaryo:** S-A1 Alarm Fırtınası
**Sonuç:** 3000 alarm → 5 olay kartı · 600× indirgeme · 0 kayıp · 39/39 test

---

## 1. AI Stratejimiz ve İş Akışı

İlk geliştirmede **Claude Code (CLI), Claude Opus 5
(`claude-opus-5[1m]`)** SAKA kurumsal sarmalayıcısı üzerinden kullanıldı.
Final kalite kapısında **OpenAI Codex desktop, GPT-5 tabanlı Codex** kullanıldı;
veri kaybı, grafik önbelleği ve güven skoru hataları burada bulundu ve regression
testleriyle düzeltildi. Çözümün çalışma zamanında MCP veya harici API yoktur;
tamamen çevrimdışı çalışır.

Çalışma düzenimiz `DIREKTIF.md`'de yarışmadan **önce** yazılmıştı: önce
problemi anla, sonra veriyi keşfet, sonra alternatif üret, sonra kodla.
Bu sıraya uyduk ve **senaryo açıldıktan sonra ilk 25 dakika hiç kod
yazılmadı** — o süre veri keşfine gitti.

### Hangi kararı AI, hangisini insan verdi

| Karar | Kim |
|---|---|
| Kapsam, zaman bütçesi, teslim önceliği | **İnsan** |
| Veri keşfi ve olay tespiti | AI, veriyi ölçerek |
| Üç alternatif yaklaşımın üretilmesi ve karşılaştırılması | AI |
| Yaklaşım seçimi | AI gerekçelendirdi, **insan onayladı** |
| Kabin seviyesi kök neden fikri | AI, keşifteki 9/9 bulgusundan türetti |
| Ayrışma testinin X-Factor yapılması | AI önerdi, **insan onayladı** |
| Eşik ve ağırlık değerleri | AI, veriye bakarak |
| Kodlamaya geçiş onayı | **İnsan** |
| Final QA'nın başlatılması ve güvenli düzeltme yetkisi | **İnsan** |
| Veri bütünlüğü ve negatif test denetimi | Codex; gerçek komut çıktılarıyla |

### AI'ın kendi önerisini veriyle çürüttüğü yerler

Bunlar iddiadan çok, çalışma biçiminin kanıtı. Dördü de commit geçmişinde
görülebilir:

1. **Denetimsiz kümeleme (DBSCAN) önerildi ve reddedildi.** Ölçüldü ki
   OLAY-03 ile OLAY-04 zaman+servis uzayında bitişik; yoğunluk tabanlı
   kümeleme bunları birleştirirdi. (`docs/plan.md` §4-A)
2. **İlk kök neden atfı yanlış çıktı.** `dns-resolver` ve `log_rotate` gibi
   anlamsız kökler üretti. Neden: ham "ilk alarm" gürültüyle kirleniyordu.
   Düzeltme: öncelik ve imza yalnızca `severity ≥ 4` üzerinden ölçülüyor.
3. **Kabin kökü için ilk kapı (grafik bileşen sayısı) gerçek arızayı eledi.**
   Veriye dönüldü, host kapsamı ölçüldü: gerçek kabin arızasında %100, diğer
   tüm kabin/küme çiftlerinde en fazla %56. Kapı bununla değiştirildi.
4. **Ayrışma eşiği gerçek ayrımı kaçırıyordu.** Artık oranı %11'di, eşik
   %15'ti — yani `session-service` payment'a yapışık kalıyordu. Çözüm eşiği
   düşürmek değil, ölçütü değiştirmek oldu: **grafik kopukluğu**.

**Kanıt:** [`DIREKTIF.md`](DIREKTIF.md) · [`docs/plan.md`](docs/plan.md) ·
[`prompts/`](prompts/) · [`docs/fazlar.md`](docs/fazlar.md) · commit geçmişi

---

## 2. Problemi Nasıl Çözdük

### Yaklaşım

Problemi bir **filtreleme** değil, **nedensellik atfetme** problemi olarak
okuduk. Gerekçe brifingin kendi cümlesi: *"gerekçesiz doğru hipotez, gerekçeli
yanlıştan daha az puan alır."* Bu cümle açıklanamayan yöntemleri yapısal
olarak eliyor.

Dört aşama, her biri sayı üretiyor:

1. **Sinyal/gürültü skorlaması** — her alarm, kendi tipinin o dakikada
   beklenenden ne kadar fazla göründüğüyle ölçülür (Poisson sapması).
   Skor, ikili karar değil → eleme gerekçesi bedavaya gelir.
2. **Nedensel kümeleme** — zaman yakınlığı **ve** bağımlılık grafiği mesafesi
   birlikte. Geçişken bağlantı, pencereyi uyarlanabilir yapar.
3. **Ayrışma testi** — X-Factor, aşağıda.
4. **Kök neden sıralaması** — birinci kök, ikincisi karşı hipotez.

### Ölçtüğümüz sonuçlar

| Metrik | Değer | Nasıl ölçüldü |
|---|---|---|
| İşlenen alarm | 3000 (tamamı) | `test_tum_alarmlar_isleniyor` |
| Skor gürültüsü | 1888 (%62,9) | `metrikler["gurultu"]` |
| Korelasyon dışı sinyal | 118 (%3,9), gerekçeli | `test_korelasyon_disi_sinyaller_acikca_gerekceli` |
| Kartlara atanan alarm | 994 | `test_kart_atamalari_benzersiz` |
| Kayıp / çift atama | 0 / 0 | `test_alarm_muhasebesinde_kayip_yok` |
| Üretilen kart | 5 (kriter ≤15) | `test_en_fazla_onbes_kart` |
| İndirgeme | 600× | 3000 / 5 |
| Uçtan uca süre | 0,625 sn | 7 koşu ortalaması, Python 3.12.14 |
| Test | 39/39 | `pytest tests/ -q` |

### Bulunan beş olay

| Kart | Kök neden | İmza | Alarm | Güven |
|---|---|---|---|---|
| OLAY-01 | `dc1/rack-A` kabin ağ arızası | `pkt_loss` | 473 | yüksek (0.99) |
| OLAY-02 | `billing-db` disk dolması | `disk_full` | 167 | yüksek (0.833) |
| OLAY-03 | `payment-provider-gw` dış kesinti | `ext_slow` | 260 | yüksek (0.938) |
| OLAY-04 | `session-service` bellek tükenmesi | `oom_risk` | 27 | orta (0.662) |
| OLAY-05 | `subscriber-db` bağlantı havuzu | `db_conn_pool` | 67 | yüksek (0.759) |

Beşi de, boru hattı yazılmadan **önce** yapılan veri keşfinde bağımsız olarak
doğrulanmıştı (`docs/plan.md` §2.3). Yani kod, keşfi teyit etti — keşif koda
uydurulmadı.

### Açıklanabilirlik: ölçülen ile çıkarılan ayrı

Her kart `SONUÇ → KANIT → GEREKÇE → GÜVEN/SINIRLAR` yapısında
(DIREKTIF.md §13). `kanit` alanı **yalnızca veriden ölçülmüş** sayıları
taşır, `gerekce` alanı bunları birleştiren **çıkarımdır**. Jüri hangi sayının
nereden geldiğini ayırt edebilsin diye ayrı alanlarda duruyorlar.

OLAY-01'in kanıt bloğundan, doğrudan çıktıdan:

```
  KANIT
    - 473 alarm, 14 servis, 27 host
    - en yuksek siddet 5; sev>=4 olan 232 alarm (49%)
    - kok alarm 01:42:13'de; kumenin %100'i bu andan sonra geliyor
    - siddetli alarmlarin gelis sirasi: network_down -> pkt_loss -> network_flap -> latency_high
    - bagimlilik grafiginde kokun asagi akisi kumenin %98'ini acikliyor
    - dc1/rack-A kabinindeki 9 host'un 9'u alarm uretiyor (%100)
```

**Kanıt:** [`src/`](src/) · [`docs/mimari.md`](docs/mimari.md) ·
[`demo/01_olay_kartlari.txt`](demo/01_olay_kartlari.txt)

---

## 3. X-Factor — grafik ayrışma testi

### Sıradan bir çözümün yapamayacağı şey

*İki olayın aynı anda olup aynı servisi vurduğunu fark edip yine de ayırmak.*

02:38–02:58 arasında iki bağımsız olay çakışıyor: `payment-provider-gw` dış
servis kesintisi ve `session-service` bellek tükenmesi. **İkisi de
`mobile-bff`'i etkiliyor** — biri `order-service` üzerinden, diğeri doğrudan
`mobile-bff → session-service` kenarıyla.

Zaman ve servis benzerliğine bakan her kümeleme bunları tek olay sayar ve
jürinin "yanlış birleştirme" ölçütünden puan kaybeder.

### Dayanak

Bağımlılık grafiğinde `payment-provider-gw` ile `session-service` arasında
**yol yoktur** (mesafe 4 > eşik 2). Kopuk kökler ayrı olaydır.

### Ölçülebilir kanıt

```bash
$ python -m src.cli --x-factor

  Ayrisma testi KAPALI : 4 kart
  Ayrisma testi ACIK   : 5 kart

  Test acilinca ortaya cikan kok neden(ler):
    + session-service
```

Demoda bu anahtar canlı olarak kapatılıp açılıyor.

### Kod kanıtı

| Ne | Nerede |
|---|---|
| Ayrışma kararı | `src/clustering.py` — `ayristir()` |
| Kopukluk ölçüsü | `src/clustering.py` — `_kokler_kopuk_mu()` |
| Kabin kökü ve host kapsamı kapısı | `src/clustering.py` — `_lokalite_adaylari()` |
| Kök aday sıralaması | `src/clustering.py` — `_kok_adaylari()` |
| Gerekçeli son muhasebe | `src/pipeline.py` — `calistir()` |
| Testle sabitlenmesi | `tests/test_pipeline.py::test_session_service_payment_ile_birlesmiyor` |

### Bonus gereksinimler

| Bonus | Durum | Nerede |
|---|---|---|
| Kök neden gerekçesi + karşı olasılıklar | ✔ | Her kartta `gerekce` ve `karsi_hipotez` |
| Gürültü denetim görünümü | ✔ | `--gurultu` ve arayüzde 3. sekme; her alarmın kendi gerekçesi |
| Geçmiş olay örüntüleri | ✘ | Yapılmadı — veri tek pencere, geçmiş yok |

### Opsiyonel gereksinim: aksiyon izlenebilirliği

Her kart sahipli bir aksiyon açıyor; durum `acik → devam_ediyor → kapandi`
geçişleriyle izleniyor ve zaman damgalı geçmiş tutuluyor. Arayüzde canlı
değiştirilebiliyor, `streamlit.testing` ile uçtan uca doğrulandı.

---

## 4. Çalıştırma

```bash
pip install -r requirements.txt

python -m src.cli              # olay kartları (terminal)
python -m src.cli --x-factor   # X-Factor ölçümü
streamlit run src/app.py       # web arayüzü
python -m pytest tests/ -q     # 39 test
```

**Beklenen çıktı:** 3000 alarmın 1888'i skor gürültüsü olarak, 118'i ise
asgari açıklanabilir olay desteği bulamayan korelasyon dışı sinyal olarak
gerekçeli biçimde kart dışında bırakılır. Kalan 994 alarm 5 olay kartındadır;
kayıp ve çift atama sıfırdır. Her kart kök neden hipotezi, ölçülmüş kanıt,
gerekçe, güven seviyesi, karşı hipotez ve sahipli bir aksiyon taşır.

---

## 5. Bilinen Sınırlar

Hiçbiri gizlenmedi; hepsi kartların ve dokümanların içinde de duruyor.

1. **Olay sayısı veriden türetildi.** Brifing sayıyı vermedi; 5 bizim
   çıkarımımız. Doğrulama verisi farklı olabilir.
2. **OLAY-05'in kökü tartışmalı — bu bir modelleme sınırı.** Bağımlılık
   grafiği *arıza* yayılımını modelliyor (hedef bozulursa kaynak etkilenir),
   ama *yük* yayılımını değil — yük ters yönde akar. Toplu iş çakışması
   veritabanını yorduğu için gerçek tetikleyici `batch-scheduler` olabilir;
   biz `subscriber-db` dedik ve `batch-scheduler`'ı karşı hipotez olarak
   kartta bıraktık.
3. **Gürültü elemesinde sızıntı var.** `cert_expiry` ve `backup_warn`'dan
   birkaç alarm sinyal adayı tarafında kalıyor. Kart desteği bulamayanlar
   `korelasyon_disi` olarak açıkça etiketleniyor; sessiz kayıp yok.
4. **Gözlem penceresi kapalı.** 03:30 sonrası görülemiyor; OLAY-05 pencere
   sonunda hâlâ aktif ve kartında bu yazıyor.
5. **Geçmiş olay örüntüsü eşleştirmesi yapılmadı** — üçüncü bonus. Veri tek
   bir 2 saatlik pencere, karşılaştırılacak geçmiş yok.
6. **Aksiyon durumu kalıcı değil**, oturum belleğinde. Kalıcı veritabanı
   senaryoda kapsam dışı bırakılmıştı.
7. **`scikit-learn` ve `shap` kuruldu ama son çözümde kullanılmıyor.**
   Keşifte denendi, denetimsiz kümeleme gerekçeli olarak reddedildi
   (`docs/plan.md` §4-A). Ortamda durmalarının tek nedeni keşif aşamasıdır.
8. **Final QA Python 3.12.14 üzerinde tekrarlandı.** İlk geliştirme ortamı
   Python 3.9.2 bu makinede bulunmadığından aynı oturumda yeniden test edilmedi.
