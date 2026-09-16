# Prompt 01 — Veri Keşfi ve Yaklaşım Seçimi

```text
Amaç:                Senaryo paketini analiz edip uygulanabilir bir çözüm
                     yaklaşımı seçmek; kodlamaya erken atlamamak
Kullanılan araç:     Claude Code (CLI)
Model:               Claude Opus 5
Model sürümü:        claude-opus-5[1m]
Tarih/saat:          16 Eylül 2026, 14:44
İnsan tarafından
verilen bağlam:      DIREKTIF.md (yarışmadan önce yazılmış çalışma kuralları),
                     senaryo_paketi/ klasörü
```

## PROMPT

> senaryo_paketi klasörü altına bak. önce paketi okuyup, DIREKTIF.md
> kurallarına göre en uygulanabilir çözümü seç; hemen kodlamaya atlama,
> fakat analiz sonunda doğrudan uygulanabilir plan üretsin.

İnsanın buradaki iki kısıtı belirleyici oldu: **"hemen kodlamaya atlama"** ve
**"doğrudan uygulanabilir plan"**. Birincisi keşif aşamasını zorunlu kıldı,
ikincisi analizin soyut kalmasını engelledi.

## Önemli çıktı

Model kod yazmadan önce 25 dakika veri keşfi yaptı ve **dört ölçüm** üretti.
Bu dördü kolay yaklaşımları kapattığı için asıl değerli çıktı bunlardı:

| Bulgu | Ölçüm | Sonucu |
|---|---|---|
| Severity tek başına ayırt etmiyor | Olay pencerelerinin içinde bile alarmların yalnızca %34'ü sev≥4 | Eşik tabanlı filtre elendi |
| Alarm tipi olaylar arasında paylaşılıyor | `db_conn_pool` üç ayrı olayda geçiyor | Tip tabanlı kural elendi |
| İki olay çakışık ve ortak mağdur paylaşıyor | OLAY-03/04, ikisi de `mobile-bff`'i vuruyor | Zaman+servis kümelemesi elendi |
| `source_system` ayırt edici değil | Beş sistemin severity dağılımı aynı | Öznitelik olarak kullanılmadı |

Ayrıca beş olay adayı tespit edildi ve her biri ilk-görülme sıralaması +
bağımlılık grafiğiyle doğrulandı. En keskin kanıt OLAY-01'de çıktı:
**dc1/rack-A kabinindeki 9 host'un 9'u da alarm üretiyor**, ağ alarmlarının
55/56'sı o kabinde.

Model üç alternatif üretti:

- **A) Denetimsiz kümeleme (DBSCAN/HDBSCAN)** — reddedildi. Açıklanamaz ve
  yukarıdaki üçüncü tuzağa düşüyor: OLAY-03/04'ü birleştirir.
- **B) Sabit pencereli kural korelasyonu** — yetersiz. Yavaş gelişen
  olayları (20 dk'ya yayılan disk dolması) böler, gürültü için gerekçe üretemez.
- **C) Bağımlılık grafiği farkında nedensel kümeleme** — seçildi.

## İnsan kararı

Yaklaşım **C** onaylandı, kodlamaya geçiş izni verildi.

**Gerekçe:** Brifingin kendi cümlesi — *"Doğru gerekçelendirilmiş yanlış
hipotez, gerekçesiz doğru hipotezden daha yüksek puan alabilir."* Bu cümle
seçimi tek başına belirliyor: açıklanamayan yöntem (A) yapısal olarak
kaybediyor. (C), (B)'nin açıklanabilirliğini korurken yavaş gelişen olay ve
yanlış birleştirme problemlerini çözüyor.

## Not — modelin kendi iddiasını geri çekmesi

Planın ilk taslağında X-Factor iddiası *"ayrışma kapalıyken 4 kart, açıkken
5 kart"* diye **sayıyla** yazılmıştı. Henüz ölçülmemiş bir sayıydı. Model
bunu fark edip iddiayı sayısız hâle getirdi ve gerçek değerin boru hattı
çalıştıktan sonra ölçüleceğini not etti.

Sayı sonradan ölçüldüğünde tahmin doğru çıktı (4 → 5), ama bu tesadüftü;
ölçülmeden yazılmış olması yine de hata olurdu.

**Kanıt:** `docs/plan.md` §2, §4, §5
