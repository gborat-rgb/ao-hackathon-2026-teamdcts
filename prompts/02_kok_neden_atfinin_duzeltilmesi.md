# Prompt 02 — Kök Neden Atfının Veriyle Düzeltilmesi

```text
Amaç:                Çalışan ama yanlış sonuç veren kök neden atfını düzeltmek
Kullanılan araç:     Claude Code (CLI)
Model:               Claude Opus 5
Model sürümü:        claude-opus-5[1m]
Tarih/saat:          16 Eylül 2026, 15:20 – 15:40
İnsan tarafından
verilen bağlam:      "kodlamaya geçelim" (Faz 3 devam ediyor)
```

Bu dosya tek bir prompt değil, **üç turluk bir düzeltme döngüsünü** kaydediyor.
Kaydedilme nedeni: modelin ilk çıktısının yanlış olması ve düzeltmenin her
turda **veriye dönülerek** yapılmış olması. DIREKTIF.md §11'deki
*"modelin önerdiği her korelasyon gerçek kabul edilmemelidir"* kuralının
uygulandığı yer burası.

---

## Tur 1 — Anlamsız kökler

Kümeleme doğru çalıştı (dört ham küme, dördü de keşifteki pencerelerle
örtüştü) ama kök atfı saçmaladı:

```
01:42-01:53  kok=dns-resolver      (network_flap)
02:04-02:25  kok=billing-db        (network_flap)   ← tip yanlış, disk_full olmalı
03:05-03:29  kok=dc2/rack-C kabini (db_conn_pool)   ← kök yanlış
02:08-02:23  kok=charging-service  (log_rotate)     ← tamamen sahte kart
```

**Kök neden analizi:** Aday sıralaması ham "ilk alarm"a bakıyordu. Gürültü
düşük şiddetle olay penceresine sızdığı için `log_rotate` ve `network_flap`
gibi tipler kök görünüyordu.

**Düzeltme:** Öncelik ve imza ölçüleri yalnızca `severity ≥ 4` alarmları
üzerinden hesaplanacak şekilde değiştirildi. Skor formülü de yeniden
ağırlıklandırıldı:

```
skor = 0.35·açıklama_oranı + 0.40·öncelik + 0.25·imza
```

---

## Tur 2 — Kabin kökü ve yanlış kapı

OLAY-01'in kökü bir **servis değil**: dc1/rack-A kabininin ağı çökmüş ve o
kabindeki birbiriyle ilgisiz servisler aynı anda alarm üretiyor. Servis
grafiği bunu açıklayamaz çünkü ortak neden grafiğin dışında.

Kabin seviyesi kök adayı eklendi. İlk kapı olarak **grafik bileşen sayısı**
kullanıldı: "kabindeki servisler grafikte en az 3 kopuk parçaya ayrılıyorsa
kabin kökü öner."

**Bu kapı gerçek kabin arızasını eledi.** Sebebi: rack-A'daki servisler
(api-gateway, auth-service, order-service, subscriber-service…) grafikte
zaten birbirine bağlı, yani bileşen sayısı düşük.

**Veriye dönüldü** ve doğru ayırt edici ölçüldü:

| | Host kapsamı |
|---|---|
| Gerçek kabin arızası (dc1/rack-A, OLAY-01) | **9/9 = %100** |
| Diğer tüm kabin × küme çiftleri | en fazla **%56** |

Kapı `ASGARI_HOST_KAPSAMI = 0.75` ile değiştirildi. Ayrım keskin, eşik güvenli
bir boşluğa denk geliyor.

**Gerekçe:** Tek bir servisin bozulması kabindeki tüm host'ları vurmaz;
kabin seviyesi altyapı arızası vurur. Bu, bileşen sayısından daha doğrudan
bir altyapı imzası.

---

## Tur 3 — Ayrışma eşiği gerçek ayrımı kaçırıyor

`session-service` bellek tükenmesi, `payment-provider-gw` kesintisiyle aynı
karta yapışık kalıyordu — yani X-Factor'ün yakalaması gereken tam olay
kaçıyordu.

**Kök neden analizi:** Bölme kararı "açıklanamayan artık oranı > %15"
kuralına bakıyordu. Gerçek artık oranı **%11**'di. Eşiğin altında kaldığı
için bölünmüyordu.

**Yapılmayan düzeltme:** Eşiği %10'a çekmek. Bu, sayıyı istenen cevaba
uydurmak olurdu ve başka kümelerde sahte bölünmeler üretirdi.

**Yapılan düzeltme:** Ölçüt değiştirildi. Bölme kararı artık oranına değil,
**grafik kopukluğuna** bakıyor:

```python
kopuk = grafik.mesafe(kök_1, kök_2) is None or mesafe > AZAMI_ATLAMA
if kopuk or (artık_oranı > 0.40 and artık_imzası >= 0.35):
    böl
```

Bağlı kalan bir artık ancak hem çok büyükse hem de kendi başına güçlü bir
imzası varsa ayrı olay sayılıyor. Bu ikinci koşul, Tur 1'deki sahte
`charging-service / log_rotate` kartının geri gelmesini engelliyor.

---

## Sonuç

Beş olayın beşi de doğru kökle çıktı:

| Kart | Kök neden | İmza | Güven |
|---|---|---|---|
| OLAY-01 | dc1/rack-A kabini | `pkt_loss` | yüksek (0.99) |
| OLAY-02 | billing-db | `disk_full` | yüksek (0.72) |
| OLAY-03 | payment-provider-gw | `ext_slow` | yüksek (0.86) |
| OLAY-04 | session-service | `oom_risk` | orta (0.57) |
| OLAY-05 | subscriber-db | `db_conn_pool` | yüksek (0.88) |

X-Factor ölçülebilir hale geldi: **ayrışma kapalı 4 kart, açık 5 kart.**

## İnsan kararı

Üç turun tamamı kabul edildi. Kritik nokta Tur 3'teki tercihti: eşiği
oynatmak yerine ölçütü değiştirmek. Eşik oynatmak, çözümü bu veri setine
aşırı uydurmak (overfit) olurdu; grafik kopukluğu ise veri setinden bağımsız,
nedensel bir ilke.

**Kanıt:** `src/clustering.py` · `docs/fazlar.md` Faz 3 ·
`tests/test_pipeline.py::test_session_service_payment_ile_birlesmiyor`
