# Jüri Soru-Cevap

## 1. Neden bu algoritmayı seçtiniz?

Brifing açıklanabilir kök neden istiyor. Saf severity filtresi neden-sonuç
üretmiyor; DBSCAN ise dependency yönünü ve karar gerekçesini kaybediyor.
Poisson sapması + dependency grafiği, her aşamada ölçülebilir kanıt veriyor.

## 2. Neden 0,35 sinyal eşiği?

Tip ve servis yoğunlaşma skorlarının veri dağılımındaki taban gürültü ile olay
kümeleri arasındaki boşlukta. Eşik parametrik; yükseltildiğinde dışlanan alarmın
arttığı regression testiyle doğrulanıyor.

## 3. Root cause nasıl seçiliyor?

Açıklama oranı (%35), ilk güçlü sinyalden sonra gelen alarm oranı (%40) ve
kök alarm imzası (%25) birlikte sıralanıyor. Ham “ilk alarm” veya yalnız en
yüksek severity kullanılmıyor.

## 4. False merge nasıl engelleniyor?

Bir kümenin açıklanamayan artığı kendi güçlü köküne sahipse köklerin grafikte
bağlılığı ölçülüyor. Kopuk kökler ayrılıyor. X-Factor kapalıyken 4, açıkken 5
kart; `session-service` bağımsız kart olarak ortaya çıkıyor.

## 5. False split nasıl engelleniyor?

Bağlı artık yalnızca kümenin %40'ından büyükse ve imzası en az 0,35 ise
ayrılıyor. Küçük/geç gelen kuyruklar aynı olayda tutuluyor; en az 8 alarm
desteği olmayan parçalar gerekçeli korelasyon dışı sinyal oluyor.

## 6. AI burada ne yaptı?

Claude veri keşfi, alternatif yaklaşım, ilk uygulama ve belgeleri üretti.
Codex final QA'da veri muhasebesi, negatif test, güvenlik, determinism ve
dokümantasyon tutarlılığını denetledi; üç mantık hatasını testlerle düzeltti.

## 7. İnsan hangi kararı verdi?

Kapsamı, zaman bütçesini, yaklaşım ve X-Factor onayını, kodlamaya ve final
QA düzeltmelerine başlama yetkisini insan verdi. AI önerileri veri ve test
kanıtı olmadan kabul edilmedi.

## 8. X-Factor nedir?

Eşzamanlı ve ortak mağduru olan olayları, kökleri arasındaki dependency yolu
üzerinden yeniden ayıran grafik ayrışma testidir.

## 9. X-Factor gerçekten işe yarıyor mu?

Evet, ölçülebilir fark 4→5 karttır. `session-service` yalnız test açıkken
bağımsız kök olur; komut ve regression testi repodadır.

## 10. Bütün alarmlar işlendi mi?

Evet. 3000 = 994 karta atanmış + 2006 açıkça dışlanmış. Kayıp 0, duplicate ID
0, birden fazla karta atanan alarm 0.

## 11. Noise alarm önemliyse ne olur?

Eleme yalnız tip adına dayanmaz; tip/servis yoğunlaşması ve severity birlikte
skorlanır. Eşik değiştirilebilir. Kart desteği bulamayan yüksek skorlu alarm da
silinmez; `korelasyon_disi` sınıfında gerekçesiyle görünür.

## 12. Confidence nasıl hesaplanıyor?

Seçilen kökün açıklama oranı %55, kendi imza gücü %25 ve küme büyüklüğü %20.
Final QA, önceki sürümün yanlışlıkla karşı hipotez imzasını kullandığını buldu
ve regression testiyle düzeltti.

## 13. Sistem deterministic mi?

Evet. Satırlar karıştırıldığında semantik sonuç değişmiyor; iki ardışık JSON
çıktısı byte düzeyinde aynı. Runtime yalnız terminal performans göstergesidir.

## 14. En büyük limitation ne?

Dependency grafiği arıza yayılımını modelliyor, yük yayılımını değil. Bu nedenle
OLAY-05'te `batch-scheduler` gerçek tetikleyici olabilir; kartta karşı hipotezdir.

## 15. Production'a götürseniz ilk neyi değiştirirdiniz?

Doğrulanmış geçmiş olay etiketleriyle eşikleri kalibre eder, streaming ingest,
kalıcı aksiyon deposu, graph versioning ve gözlemlenebilirlik metrikleri eklerdik.
