# Demo Checklist

## Repository ve çalışma zamanı

- [x] Doğru branch: `main`
- [x] Bağımlılık pinleri temiz `.venv` içinde kuruldu
- [x] Dataset, inventory ve dependency dosyaları mevcut
- [x] `python -m src.cli` test edildi
- [x] `python -m src.cli --json` test edildi ve deterministik
- [x] `python -m src.cli --x-factor` test edildi
- [x] `python -m src.cli --gurultu 20` test edildi
- [x] `python -m pytest tests/ -q`: 60/60
- [x] Streamlit AppTest: 0 exception, 5 sekme, 8 KPI pipeline ile eşleşiyor

## Veri ve jüri kanıtı

- [x] 3000 = 994 karta atanmış + 2006 açıkça dışlanmış
- [x] Kayıp alarm 0
- [x] Birden fazla karta atanan alarm 0
- [x] X-Factor 4→5; `session-service` ortaya çıkıyor
- [x] Root cause, kanıt, gerekçe, güven ve karşı hipotez görünür
- [x] Aksiyon sahip/durum/geçmiş akışı test edildi
- [x] README, AI_JURI ve submission.json aynı metrikleri kullanıyor
- [x] Gerçek UI ekran görüntüleri `demo/` altında
- [x] CLI, internet/API/LLM olmadan çalışıyor

## Sahne öncesi operatör kontrolü

- [ ] Projektör çözünürlüğünü 1600×900 veya üstüne ayarla
- [ ] Terminal UTF-8 çıktısını kontrol et
- [ ] `streamlit run src/app.py` ile arayüzü önceden aç
- [ ] Tarayıcı zoom seviyesini %100 yap
- [ ] CLI fallback için `demo/01_olay_kartlari.txt` dosyasını hazır tut
- [ ] X-Factor ve aksiyon geçişini bir kez prova et
