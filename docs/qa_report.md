# Final QA Raporu

**Tarih:** 16 Eylül 2026
**Karar:** READY FOR JURY

## Doğrulanan ortam

- Branch: `main`
- Başlangıç HEAD: `32233d7f04b121994d9086a5c95c971aa396d75d`
- Final QA Python: `3.12.14`
- İlk geliştirme hedefi: Python `3.9.2` (bu makinede bulunmadığı için bu
  oturumda yeniden test edilmedi)
- Bağımlılıklar: `requirements.txt` pinleri değiştirilmeden temiz `.venv`
  içine kuruldu; `pip check` hatasız
- Giriş: `senaryo_paketi/alarms.csv`, `host_inventory.csv`,
  `service_dependencies.csv`
- Ana pipeline: `src.pipeline.calistir`

## Baseline

Başlangıçta çalışma ağacı temizdi. CLI, JSON ve X-Factor komutları başarılı;
mevcut testler 19/19 geçti. Buna rağmen muhasebe denetiminde 1112 sinyal
adayının yalnızca 994'ünün kartlara girdiği, 118 alarmın son sınıf ve açık
gerekçe taşımadan düştüğü görüldü. Mevcut testler bu veri kaybını ölçmüyordu.

## Gereksinim izlenebilirliği

| Gereksinim | Uygulama | Test / kanıt | Durum |
|---|---|---|---|
| Tüm alarm akışını işle | `ingest.py`, `pipeline.py` muhasebe kapısı | `test_alarm_muhasebesinde_kayip_yok` | PASS |
| Alarm grubu başına tek olay kartı | `clustering.py`, `cards.py` | 5 kart, çift atama 0 | PASS |
| Kök, servis, sayı, zaman aralığı | `OlayKarti` | `test_kartlarda_zorunlu_alanlar` | PASS |
| Sahipli ve durumlu ilk aksiyon | `Aksiyon` | `test_her_kartta_aksiyon_ve_sahip` | PASS |
| Aksiyon durumunu izleme (opsiyonel) | Streamlit session state | AppTest + `demo/10_aksiyon_kapandi.png` | PASS |
| Kök gerekçesi ve karşı olasılık | `cards.py` | her kartta `gerekce`, `karsi_hipotez` | PASS |
| Gürültü denetim görünümü | CLI + Streamlit | `demo/08_arayuz_gurultu.png` | PASS |
| Geçmiş olay örüntüsü (bonus) | Veri tek pencere | uygulanmadı | NOT TESTED |

## Doğrulanan komutlar

| Komut | Sonuç |
|---|---|
| `python -m src.cli` | PASS — 3000 alarm, 5 kart |
| `python -m src.cli --json` | PASS — geçerli ve iki koşuda özdeş JSON |
| `python -m src.cli --x-factor` | PASS — 4 kart → 5 kart |
| `python -m src.cli --gurultu 20` | PASS — her dışlanan alarm gerekçeli |
| `python -m pytest tests/ -q` | PASS — 39/39 |
| Streamlit `AppTest` | PASS — 0 exception, 4 sekme |
| `python -m json.tool submission.json` | PASS |
| `python -m pip check` | PASS |

## Veri bütünlüğü

```text
Input / processed          3000 / 3000
Scoring noise              1888
Signal candidates          1112
Assigned to cards           994
Correlation outliers        118
Explicitly excluded        2006
Lost                          0
Duplicate IDs                 0
Assigned to multiple cards    0
```

Muhasebe: `3000 = 994 karta atanmış + 2006 açıkça dışlanmış`.

CSV ve JSON aynı 3000 alarm kimliğini içeriyor. Eksik kritik alan, geçersiz
severity, bilinmeyen host, host/servis uyuşmazlığı ve dependency referans
hatası yok.

## Bulunan ve düzeltilen sorunlar

### CRITICAL — sessiz alarm kaybı

118 sinyal adayı kartlara girmiyor ve gürültü gerekçesi de taşımıyordu.
`pipeline.py` nihai atama sınıfı, kart kimliği ve accounting metrikleriyle
güncellendi. Regression testleri kayıp ve çift atamayı sıfıra sabitliyor.

### MAJOR — mesafe önbelleğinde yanlış kopukluk riski

Servis çifti önbellek anahtarı arama derinliğini içermiyordu. Önce dar aramayla
`None` bulunan yol, sonraki geniş aramada da yanlışlıkla `None` kalabiliyordu.
Anahtara `max_atlama` eklendi; 4 düğümlü sentetik zincir testi eklendi.

### MAJOR — güven skoru yanlış imzayı kullanıyordu

Kart güveni seçilen kökün imzası yerine karşı hipotezin imzasıyla
hesaplanıyordu. `Kume.kok_imza` eklendi ve formül seçilen köke bağlandı.

### MAJOR — veri girişi hata sözleşmesi yoktu

Eksik/bozuk CSV, şema, timestamp, severity, duplicate ID, envanter ve
dependency tutarsızlıkları için açık `VeriDogrulamaHatasi` mesajları eklendi.
CLI traceback yerine `HATA: ...` ve exit code 2 döndürüyor.

### MINOR — JSON oynaktı

Duvar saatiyle üretilen aksiyon açılışı ve runtime alanı JSON'u değiştiriyordu.
Açılış gözlem penceresi sonuna bağlandı; runtime makine-okunur deterministik
kanıttan çıkarıldı, terminal performans çıktısında korundu.

## Performans

Aynı Python 3.12.14 yorumlayıcısı ve aynı bağımlılıklarla yedişer koşu:

```text
Before (HEAD): 0.684 sn ortalama, 0.602–0.783 sn
After:         0.625 sn ortalama, 0.591–0.680 sn
Fark:          yaklaşık %8,6 daha düşük ortalama süre
```

Değişikliğin hedefi performans değil doğruluktu; önemli sonuç performans
regresyonu olmaması ve 10 saniyelik demo hedefinin rahat geçilmesidir.

## Güvenlik ve dependency denetimi

- Takip edilen `.env`, secret, token, private key veya credential bulunmadı.
- Yerel mutlak yol, pycache/IDE artığı ve 5 MB üzeri takip edilen dosya yok.
- `.env.example` gerçek değişken gerektirmediğini açıkça belirtiyor.
- Runtime importları: pandas, numpy, streamlit, plotly; pytest test içindir.
- SciPy, scikit-learn, SHAP ve diğer keşif bağımlılıkları final runtime'da
  kullanılmıyor. Kritik dependency kuralı nedeniyle pinler bu oturumda
  kaldırılmadı veya yükseltilmedi; bu durum bilinen teknik borçtur.

## Quality gate

| Kapı | Sonuç |
|---|---|
| Data integrity | PASS |
| Unit tests | PASS |
| Integration tests | PASS |
| End-to-end | PASS |
| Negative tests | PASS |
| Determinism | PASS |
| Performance | PASS |
| Root cause quality | PASS |
| False merge protection | PASS |
| False split protection | PASS |
| Noise audit | PASS |
| X-Factor evidence | PASS |
| Security | PASS |
| README | PASS |
| AI_JURI | PASS |
| submission.json | PASS |
| Fresh-start run | PASS (Python 3.12.14) |
| Demo rehearsal | PASS |
| Git hygiene | PASS |

## Bilinen sınırlar

1. Doğrulama etiketi jüriye kapalı; beş olay veri keşfi hipotezidir.
2. OLAY-05 için `batch-scheduler`, `subscriber-db` köküne güçlü karşı
   hipotezdir; yük yayılım yönü dependency grafiğinde modellenmiyor.
3. 118 sinyal adayı açıklanabilir asgari kümeye girmediği için kart dışıdır;
   artık kayıp değil, denetlenebilir dışlamadır.
4. Geçmiş olay örüntüsü bonusu uygulanmadı.
5. Aksiyon durumu kalıcı veritabanına yazılmıyor.
6. Python 3.9.2 bu final QA makinesinde yeniden çalıştırılmadı.
