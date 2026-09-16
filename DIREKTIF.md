# AO Hackathon 2026 — Model Çalışma Direktifi

Bu repository, AO Hackathon 2026 kapsamında geliştirilecek çözümün ana çalışma alanıdır.

Hackathon başlangıcında senaryo ve sentetik veri paketi sağlanacaktır. Senaryo önceden bilinmemektedir. Bu nedenle bu dosyanın amacı belirli bir çözümü tarif etmek değil; kullanılan AI modellerinin repo içinde **disiplinli, izlenebilir, açıklanabilir ve teslim kurallarına uygun** çalışmasını sağlamaktır.

Bu direktif; Claude, Codex ve kullanılan diğer AI modelleri için ortak çalışma kurallarıdır.

---

# 1. Temel Çalışma Prensibi

Öncelik sırası:

1. Problemi doğru anlamak
2. Veriyi keşfetmek
3. Hipotez üretmek
4. Alternatif çözüm yaklaşımlarını değerlendirmek
5. İnsan tarafından seçilen yaklaşımı uygulamak
6. Modüler ve test edilebilir kod üretmek
7. Sonuçları ölçmek
8. Kararların nedenlerini açıklamak
9. Kritik AI kullanımını belgelemek
10. Teslim dosyalarını güncel tutmak

Kod üretimine geçmeden önce problem ve veri yapısı anlaşılmalıdır.

Varsayım yapılması gerekiyorsa varsayım açıkça belirtilmelidir.

Veride bulunmayan bilgi uydurulmamalıdır.

---

# 2. Repository Ana Çalışma Alanıdır

Tüm kalıcı proje çıktıları bu repository altında tutulmalıdır.

Repository dışında geçici analiz yapılabilir; ancak çözümün parçası haline gelen kod, dokümantasyon, kritik prompt, mimari karar veya demo çıktısı uygun repository dizinine taşınmalıdır.

Ana yapı:

```text
ao-hackathon-2026-teamdcts/
├── README.md
├── AI_JURI.md
├── submission.json
├── .env.example
├── DIREKTIF.md
├── docs/
├── prompts/
├── demo/
└── src/
```

Her dosya kendi amacı doğrultusunda kullanılmalıdır.

---

# 3. README.md

README.md projenin insan tarafından okunacak ana dokümantasyonudur.

README.md aşağıdaki bilgileri mutlaka içermelidir:

- Proje adı
- Tek cümlelik proje özeti
- Çözülen problem
- Çözümün nasıl çalıştığı
- Mimari yaklaşımın kısa özeti
- Kurulum adımları
- Çalıştırma komutu
- Kullanılan tüm AI araçları
- Kullanılan model adları ve sürümleri
- Kullanılan MCP sunucuları
- Entegre edilen API'ler
- Demo / ekran görüntüleri
- Deploy URL varsa bağlantısı
- Bilinen sınırlar

README.md yalnızca yarışma sonunda hazırlanacak bir dosya olarak görülmemelidir.

Proje geliştikçe güncel tutulmalıdır.

README içeriği gerçek çalışan çözümle tutarlı olmalıdır.

---

# 4. AI_JURI.md

AI_JURI.md, çözümün AI Jüriye anlatıldığı ana değerlendirme dosyasıdır.

Bu dosyada yalnızca iddia yazılmamalıdır.

Mümkün olan her iddianın yanında repository içinden kanıt verilmelidir.

Önerilen yapı:

```markdown
# AI Jüri Özeti

## 1. AI Stratejimiz ve İş Akışı

Hangi AI aracını hangi amaçla kullandık?

Hangi kararları AI önerdi?

Hangi kararları insanlar verdi?

Kanıt:
- prompts/
- DIREKTIF.md
- docs/plan.md
- docs/fazlar.md
- ilgili commit geçmişi

## 2. Problemi Nasıl Çözdük

Yaklaşımımız nedir?

Ürettiğimiz çıktı nedir?

Hangi sonuçları ölçtük?

Kanıt:
- src/
- docs/mimari.md
- demo/

## 3. X-Factor

Çözümümüzün sıradan bir veri işleme veya dashboard çözümünden farklı olan en önemli AI özelliği nedir?

Kanıt:
- src/<dosya>:<satır aralığı>
- ilgili prompt
- ilgili demo çıktısı

## 4. Çalıştırma

Çözüm tek komutla nasıl çalıştırılır?

Beklenen çıktı nedir?

## 5. Bilinen Sınırlar

Neyi yapamadık?

Neden yapamadık?

Hangi varsayımları kullandık?
```

AI_JURI.md gerçek uygulama tamamlandıkça güncellenmelidir.

Kanıtsız pazarlama ifadelerinden kaçınılmalıdır.

---

# 5. submission.json

submission.json makine tarafından okunacak proje künyesidir.

README.md ve AI_JURI.md içindeki bilgilerin kısa ve yapılandırılmış özetidir.

Dosya geçerli JSON formatında olmalıdır.

Beklenen temel yapı:

```json
{
  "takim": {
    "ad": "",
    "uyeler": [],
    "iletisim": ""
  },
  "proje": {
    "ad": "",
    "ozet": "",
    "deploy_url": null
  },
  "calistirma": {
    "komut": "",
    "on_kosullar": [],
    "veri_yolu": "./data"
  },
  "ai_kullanimi": {
    "platform": "SAKA",
    "modeller": [],
    "mcp_sunuculari": [],
    "apiler": [],
    "insan_ai_is_bolumu": ""
  },
  "cozum": {
    "yaklasim": "",
    "x_factor": "",
    "olctugumuz_metrikler": {}
  },
  "sunum": {
    "demo_akisi": []
  }
}
```

submission.json ile README.md ve AI_JURI.md arasında çelişki olmamalıdır.

Model, submission.json güncellerken yalnızca doğrulanmış bilgileri kullanmalıdır.

---

# 6. docs/ Dizini

`docs/` klasörü proje düşüncesinin ve teknik kararların kayıt alanıdır.

En az aşağıdaki dosyalar kullanılmalıdır:

```text
docs/
├── plan.md
├── fazlar.md
└── mimari.md
```

## docs/plan.md

Plan dosyası aşağıdakileri içermelidir:

- Problemin ilk yorumu
- Hedef
- Başarı kriterleri
- İlk hipotezler
- Alternatif çözüm yaklaşımları
- Seçilen yaklaşım
- Seçim gerekçesi
- Yapılacak işler
- Riskler
- Zaman kısıtları

Plan, senaryo açıldıktan sonra ilk analiz aşamasında oluşturulmalıdır.

---

## docs/fazlar.md

Geliştirme sürecinin aşamaları burada tutulmalıdır.

Örnek:

```markdown
# Fazlar

## Faz 1 — Veri Keşfi
Durum:
Çıktı:
Karar:

## Faz 2 — Baseline Çözüm
Durum:
Çıktı:
Karar:

## Faz 3 — AI / X-Factor
Durum:
Çıktı:
Karar:

## Faz 4 — Demo
Durum:
Çıktı:

## Faz 5 — Teslim
Durum:
```

Dosya yarışma boyunca güncellenebilir.

---

## docs/mimari.md

Gerçek uygulama mimarisi burada açıklanmalıdır.

İçerik gerektiği ölçüde şunları kapsamalıdır:

- Bileşenler
- Veri akışı
- Kullanılan modeller
- API çağrıları
- Analiz pipeline'ı
- UI
- Veri giriş/çıkış noktaları
- Modüller arası ilişki
- X-Factor'ın mimarideki yeri
- Tasarım tercihleri
- Alternatifler ve trade-off'lar

Mimari dokümanı gerçek kodla uyumlu olmalıdır.

---

# 7. prompts/ Dizini

`prompts/` dizini AI kullanımının kanıt alanıdır.

Her küçük konuşma veya her terminal komutu burada saklanmamalıdır.

Yalnızca çözümün yönünü, kalitesini veya mimarisini anlamlı biçimde etkileyen **kritik prompt'lar** kaydedilmelidir.

Örnek:

```text
prompts/
├── prompt01_problem_analysis.save
├── prompt02_data_exploration.save
├── prompt03_architecture.save
├── prompt04_root_cause_analysis.save
├── prompt05_xai_explanation.save
└── prompt06_model_comparison.save
```

Dosya uzantısı `.save`, `.md` veya uygun başka bir metin formatı olabilir.

Tutarlılık tercih edilir.

Her kritik prompt dosyasında mümkünse şu metadata bulunmalıdır:

```text
Amaç:
Kullanılan araç:
Model:
Model sürümü:
Tarih/saat:
İnsan tarafından verilen bağlam:

PROMPT:
...

Önemli çıktı:
...

İnsan kararı:
...
```

Bir prompt farklı modellerle karşılaştırıldıysa sonuç belgelenmelidir.

Örneğin:

```text
Claude:
- yaklaşım A
- güçlü yön
- zayıf yön

Codex:
- yaklaşım B
- güçlü yön
- zayıf yön

İnsan kararı:
Yaklaşım B seçildi.

Gerekçe:
...
```

Prompt klasörü chat log dump alanı değildir.

Amaç AI'nın nasıl yönlendirildiğini ve insan-AI iş bölümünü gösterebilmektir.

---

# 8. demo/ Dizini

`demo/` çalışan çözümün görsel kanıtlarının tutulduğu alandır.

Buraya uygun olduğu ölçüde şunlar eklenebilir:

- Kritik ekran görüntüleri
- Dashboard görüntüleri
- RCA sonucu
- XAI açıklama ekranı
- Öncesi / sonrası karşılaştırmaları
- Önemli grafikler
- Demo akışını gösteren görseller
- Video linkini içeren README veya metin dosyası

Dosya isimleri açıklayıcı olmalıdır.

Örnek:

```text
demo/
├── 01_overview.png
├── 02_anomaly_detection.png
├── 03_root_cause.png
├── 04_xai_explanation.png
└── demo-notes.md
```

Sadece dekoratif ekran görüntüleri eklenmemelidir.

Her görüntü çözümün gerçek bir özelliğini veya sonucunu göstermelidir.

---

# 9. src/ Dizini

Tüm uygulama kaynak kodu `src/` altında tutulmalıdır.

Kod mümkün olduğunca modüler olmalıdır.

Örnek yapı yalnızca gerektiğinde kullanılabilir:

```text
src/
├── app.py
├── ingest/
├── analysis/
├── ai/
├── explain/
└── utils/
```

Senaryo belli olmadan gereksiz mimari oluşturulmamalıdır.

Kodlama sırasında:

- Büyük tek parça kodlardan kaçınılmalıdır.
- İşlevler küçük ve test edilebilir tutulmalıdır.
- Her modül çalıştırılarak doğrulanmalıdır.
- Hata alınırsa kök neden bulunmadan sonraki aşamaya geçilmemelidir.
- Kullanılmayan kod temizlenmelidir.
- Gereksiz dependency eklenmemelidir.

---

# 10. Veri Keşfi

Veri paketi teslim edildiğinde hemen kod yazmaya başlanmamalıdır.

Önce aşağıdaki analiz yapılmalıdır:

1. Dosyaları listele
2. Formatları belirle
3. Şemayı çıkar
4. Kolonları ve veri tiplerini incele
5. Zaman alanlarını belirle
6. Eksik değerleri kontrol et
7. Cardinality incele
8. Temel istatistikleri çıkar
9. Olası anomalileri belirle
10. SRE açısından anlamlı sinyalleri belirle

AI modellerinden hipotez üretmek için yararlanılabilir.

Ancak modelin önerdiği her korelasyon veya root cause gerçek kabul edilmemelidir.

Veri ile doğrulanmalıdır.

---

# 11. AI Kullanım Stratejisi

AI aşağıdaki alanlarda aktif kullanılabilir:

- Problem analizi
- Veri keşfi
- Hipotez üretimi
- Mimari alternatif üretimi
- Kod üretimi
- Refactor
- Test üretimi
- Debug
- Root Cause Analysis
- Açıklanabilirlik
- Sonuçların doğal dile çevrilmesi
- Model karşılaştırması
- Dokümantasyon

Ancak nihai mühendislik kararlarının sahibi insan ekip üyeleridir.

Model önerisi ile insan kararı birbirinden ayrılmalıdır.

---

# 12. Model Karşılaştırması

Uygun görülen kritik görevlerde aynı problem birden fazla modele verilebilir.

Amaç yalnızca "iki model kullandık" diyebilmek değildir.

Gerçek karşılaştırma yapılmalıdır.

Karşılaştırılabilecek başlıklar:

- Doğruluk
- Kod kalitesi
- Açıklama kalitesi
- Hipotez kalitesi
- Hallucination eğilimi
- Performans
- Çözüm süresi
- Root cause sıralaması
- Kullanılabilirlik

Sonuçlar gerektiğinde `docs/` veya `prompts/` altında belgelenmelidir.

Kullanılan bütün model adları ve sürümleri README.md ve ilgili teslim dosyalarına işlenmelidir.

---

# 13. Explainable AI / XAI

Çözüm herhangi bir karar, skor, root cause veya öneri üretiyorsa yalnızca sonucu vermek yeterli değildir.

Mümkün olduğunca şu yapı üretilmelidir:

```text
SONUÇ
↓
KANIT
↓
GEREKÇE
↓
GÜVEN / SINIRLAR
```

Örneğin:

```text
Olası root cause:
Database connection pool saturation

Kanıt:
- active_connections: %98
- request_p95: +%420
- CPU: normal
- GC pause: normal

Gerekçe:
Latency artışı ile connection pool saturation aynı zaman aralığında görülmektedir.
CPU ve GC tarafında aynı korelasyon görülmemektedir.

Güven:
Yüksek

Alternatif neden:
Upstream timeout
```

AI'nın yaptığı çıkarımlar ile veriden doğrudan ölçülen değerler birbirinden ayrılmalıdır.

---

# 14. Ölçüm

Mümkün olan her durumda çözümün etkisi sayısal olarak ölçülmelidir.

Kaçınılması gereken:

```text
Çözüm çok iyi çalışıyor.
```

Tercih edilen:

```text
Analiz süresi:
40 saniye → 6 saniye

Top-3 root cause doğruluğu:
%62 → %87
```

Kullanılan metriğin nasıl hesaplandığı belgelenmelidir.

---

# 15. Git ve Commit Disiplini

Commit geçmişi geliştirme sürecinin kanıtıdır.

Bu nedenle anlamlı aşamalarda commit yapılmalıdır.

Örnek commit mesajları:

```text
Analyze input dataset schema
Add baseline anomaly detection
Implement root cause ranking
Add explainable reasoning output
Compare Claude and Codex approaches
Add Streamlit demo
Document architecture and limitations
Finalize AI jury evidence
```

Kaçınılması gereken:

```text
update
fix
test
aaa
final2
```

Model kendi başına commit veya push yapacaksa önce:

```bash
git status
git diff
```

ile değişiklikleri kontrol etmelidir.

Secret, credential veya gerçek `.env` dosyası asla commit edilmemelidir.

---

# 16. .env ve Secret Yönetimi

Gerçek secret'lar yalnızca `.env` içinde tutulmalıdır.

`.env` Git'e commit edilmemelidir.

`.env.example` yalnızca değişken isimleri ve örnek placeholder değerleri içermelidir.

Örnek:

```env
SAKA_API_KEY=
OPENAI_API_KEY=
```

Gerçek müşteri veya üretim verisi hiçbir AI platformuna yüklenmemelidir.

Hackathon için verilen sentetik veri kullanılmalıdır.

---

# 17. Test ve Doğrulama

AI tarafından üretilen kod doğrudan doğru kabul edilmemelidir.

Her kritik modül:

1. Çalıştırılmalı
2. Sonucu kontrol edilmeli
3. Hata senaryoları denenmeli
4. Gerekirse test yazılmalı

Bir hata düzeltildiğinde yalnızca semptom değil kök neden anlaşılmalıdır.

---

# 18. Yarışma Süresince Öncelik

Üç saatlik geliştirme süresinde hedef mükemmel ürün değildir.

Öncelik:

```text
Çalışan Baseline
        ↓
Doğru Analiz
        ↓
X-Factor
        ↓
Açıklanabilirlik
        ↓
Canlı Demo
        ↓
Dokümantasyon
```

Çalışmayan kompleks çözüm yerine çalışan ve açıklanabilir çözüm tercih edilmelidir.

---

# 19. Teslim Öncesi Kontrol

Teslim öncesinde aşağıdakiler kontrol edilmelidir:

```text
[ ] Kod çalışıyor
[ ] Demo çalışıyor
[ ] README.md güncel
[ ] AI_JURI.md güncel
[ ] submission.json geçerli
[ ] docs/plan.md güncel
[ ] docs/fazlar.md güncel
[ ] docs/mimari.md gerçek kodla uyumlu
[ ] Kritik prompt'lar prompts/ altında
[ ] Kullanılan AI modelleri ve sürümleri yazılmış
[ ] MCP sunucuları belirtilmiş
[ ] API'ler belirtilmiş
[ ] X-Factor açıkça tanımlanmış
[ ] X-Factor için kod kanıtı verilmiş
[ ] Ölçülen metrikler yazılmış
[ ] Bilinen sınırlar yazılmış
[ ] Kritik ekran görüntüleri demo/ altında
[ ] .env commit edilmemiş
[ ] Secret bulunmuyor
[ ] git status kontrol edilmiş
[ ] Son commit teslim süresinden önce push edilmiş
```

---

# 20. Model İçin Son Talimat

Bu repository üzerinde çalışırken:

- Önce mevcut dosyaları incele.
- Mevcut yapıyı sebepsiz yere değiştirme.
- Yeni dosya oluşturmadan önce uygun dizini belirle.
- Kod ile dokümantasyonu senkron tut.
- Kritik AI etkileşimlerini belgelemeyi unutma.
- İnsan tarafından verilmemiş bilgileri gerçekmiş gibi yazma.
- Kullanılan model, araç ve sürümleri kaydet.
- Her önemli teknik kararın gerekçesini belirt.
- X-Factor için ölçülebilir ve kodla kanıtlanabilir bir özellik hedefle.
- Sonuç üretirken açıklanabilirliği önceliklendir.
- Gereksiz karmaşıklıktan kaçın.
- Çalışan ürünü ve canlı demoyu teslim dokümantasyonundan daha öncelikli tut; ancak teslim belgelerini son ana bırakma.

Bu repository yalnızca kod deposu değildir.

Aynı zamanda:

```text
Kod
+
AI çalışma geçmişi
+
Mühendislik kararları
+
Kanıt
+
Demo
+
Teslim
```

bütünüdür.