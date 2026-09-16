"""Terminal arayuzu.

    python -m src.cli                 olay kartlarini bas
    python -m src.cli --json          kartlari JSON olarak bas
    python -m src.cli --x-factor      ayrisma testi karsilastirmasi
    python -m src.cli --gurultu 20    elenen alarmlardan ornek goster
"""

import argparse
import json
import sys

from .ingest import VeriDogrulamaHatasi
from .pipeline import ayrisma_karsilastirmasi, calistir
from .replay import VARSAYILAN_ADIM_SN, erken_tespit

# Windows konsolu varsayilan olarak cp1252 kullaniyor ve Turkce karakterlerde
# kiriliyor. Ciktiyi UTF-8'e sabitliyoruz.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

CIZGI = "=" * 78


def _kart_bas(k):
    print(CIZGI)
    bayrak = "  [ayrisma testi ile ayrildi]" if k.ayrisma_ile_bolundu else ""
    print("%s  %s%s" % (k.kart_id, k.baslik, bayrak))
    print(CIZGI)
    print("  Zaman        : %s  ->  %s" % (k.baslangic[11:], k.bitis[11:]))
    print("  Alarm        : %d" % k.alarm_sayisi)
    print("  Azami siddet : %d" % k.azami_siddet)
    print("  Servisler    : %s" % ", ".join(k.etkilenen_servisler[:8]))
    if len(k.etkilenen_servisler) > 8:
        print("                 (+%d servis daha)" % (len(k.etkilenen_servisler) - 8))
    print()
    print("  KOK NEDEN HIPOTEZI: %s  (%s)" % (k.kok_neden, k.kok_alarm_tipi))
    print()
    print("  KANIT")
    for c in k.kanit:
        print("    - %s" % c)
    print()
    print("  GEREKCE")
    for satir in _sar(k.gerekce, 72):
        print("    %s" % satir)
    print()
    print("  GUVEN: %s (%.2f)" % (k.guven.upper(), k.guven_skoru))
    print()
    print("  KARSI HIPOTEZ")
    for satir in _sar(k.karsi_hipotez, 72):
        print("    %s" % satir)
    if k.saha_gorevi:
        print()
        print("  SAHA GOREVI")
        for g in k.saha_gorevi:
            print("    %s  —  %d host (%d kritik), azami siddet %d"
                  % (g["konum"], g["host_sayisi"], g["kritik_host"],
                     g["azami_siddet"]))
            hostlar = ", ".join(g["hostlar"])
            if g["host_kirpildi"]:
                hostlar += ", …"
            for satir in _sar(hostlar, 66):
                print("      %s" % satir)
    if k.sinirlar:
        print()
        print("  SINIRLAR")
        for s in k.sinirlar:
            for satir in _sar(s, 72):
                print("    %s" % satir)
    if k.aksiyon:
        print()
        print("  AKSIYON %s  [%s]" % (k.aksiyon.aksiyon_id, k.aksiyon.durum.upper()))
        print("    Sahip : %s" % k.aksiyon.sahip)
        for satir in _sar(k.aksiyon.aciklama, 70):
            print("    %s" % satir)
    print()


def _sar(metin, genislik):
    kelimeler = metin.split()
    satirlar, mevcut = [], ""
    for k in kelimeler:
        if len(mevcut) + len(k) + 1 > genislik:
            satirlar.append(mevcut)
            mevcut = k
        else:
            mevcut = (mevcut + " " + k).strip()
    if mevcut:
        satirlar.append(mevcut)
    return satirlar


def main(argv=None):
    p = argparse.ArgumentParser(description="S-A1 Alarm Firtinasi — olay kartlari")
    p.add_argument("--json", action="store_true", help="kartlari JSON bas")
    p.add_argument("--x-factor", action="store_true",
                   help="ayrisma testi acik/kapali karsilastirmasi")
    p.add_argument("--gurultu", type=int, metavar="N", default=0,
                   help="elenen alarmlardan N ornek goster")
    p.add_argument("--esik", type=float, default=None, help="sinyal esigi")
    p.add_argument("--ayrisma-kapali", action="store_true",
                   help="ayrisma testini devre disi birak")
    p.add_argument("--erken-tespit", action="store_true",
                   help="geceyi yeniden oynat, her kartin olusma anini olc")
    p.add_argument("--adim", type=int, default=VARSAYILAN_ADIM_SN,
                   metavar="SN", help="erken tespit dilim adimi (saniye)")
    a = p.parse_args(argv)

    try:
        return _komutu_calistir(a)
    except VeriDogrulamaHatasi as exc:
        print("HATA: %s" % exc, file=sys.stderr)
        return 2
    except ValueError as exc:
        print("HATA: %s" % exc, file=sys.stderr)
        return 2


def _erken_tespit_bas(adim_sn, ayrisma_acik):
    s = erken_tespit(adim_sn=adim_sn, ayrisma_acik=ayrisma_acik)
    print(CIZGI)
    print("ERKEN TESPIT — gece yeniden oynatildi")
    print(CIZGI)
    print("  Dilim adimi      : %d sn" % s.adim_sn)
    print("  Calistirilan kosu: %d" % s.dilim_sayisi)
    print("  Toplu kosudaki kart: %d" % s.toplu_kart_sayisi)
    if s.ortalama_gecikme_sn is not None:
        print("  Ortalama gecikme : %.0f sn (%.1f dk)"
              % (s.ortalama_gecikme_sn, s.ortalama_gecikme_sn / 60))
    print()
    print("  %-9s %-22s %-9s %s" % ("KART ANI", "KOK NEDEN", "OLAY BASI", "GECIKME"))
    for k in s.kayitlar:
        ek = "" if k.toplu_kosuda_var else "   <- ara hipotez"
        print("  %-9s %-22s %-9s %s%s"
              % (k.kart_olusma_ani.strftime("%H:%M:%S"), k.kok_neden,
                 k.kok_ilk_alarm.strftime("%H:%M:%S"), k.gecikme_metni, ek))
    print()
    ara = [k for k in s.kayitlar if not k.toplu_kosuda_var]
    if ara:
        print("  Ara hipotez: canli akista bir sure kok gorunup gecenin tamami")
        print("  okundugunda baska bir koke evrilen aday. Gizlenmiyor, isaretleniyor.")
        print()
    print("  Not: gecikme, olayin ilk alarmi ile o olayin ilk kez kart olarak")
    print("  belirdigi an arasindaki fark. Dilim adimi kadar yukari yuvarlanir.")
    return 0


def _komutu_calistir(a):
    if a.erken_tespit:
        return _erken_tespit_bas(a.adim, not a.ayrisma_kapali)

    if a.x_factor:
        k = ayrisma_karsilastirmasi()
        print(CIZGI)
        print("X-FACTOR OLCUMU — grafik ayrisma testi")
        print(CIZGI)
        print("  Ayrisma testi KAPALI : %d kart" % k["ayrisma_kapali_kart"])
        print("  Ayrisma testi ACIK   : %d kart" % k["ayrisma_acik_kart"])
        print()
        print("  Test acilinca ortaya cikan kok neden(ler):")
        for s in k["ayrisma_ile_ortaya_cikan"]:
            print("    + %s" % s)
        print()
        print("  Bu kok(ler), test kapaliyken baska bir olayla ayni karta")
        print("  konuyordu — yani yanlis birlestirme yapiliyordu.")
        return 0

    kw = {}
    if a.esik is not None:
        kw["esik"] = a.esik
    sonuc = calistir(ayrisma_acik=not a.ayrisma_kapali, **kw)

    if a.json:
        # Duvar saati performans olcumu dogasi geregi kosudan kosuya degisir.
        # Makine okunur sonuc semantik olarak deterministik kalsin diye JSON
        # kanitindan bu tek oynak alan cikarilir; terminalde raporlanmaya devam eder.
        sabit_metrikler = dict(sonuc.metrikler)
        sabit_metrikler.pop("calisma_suresi_sn", None)
        print(json.dumps(
            {"metrikler": sabit_metrikler,
             "kartlar": [k.sozluk() for k in sonuc.kartlar]},
            ensure_ascii=False, indent=2, default=str))
        return 0

    m = sonuc.metrikler
    print()
    print(CIZGI)
    print("S-A1 ALARM FIRTINASI — OLAY KARTLARI")
    print(CIZGI)
    print("  Toplam alarm     : %d" % m["toplam_alarm"])
    print("  Skor gurultusu   : %d (%%%.0f)" % (m["gurultu"], 100 * m["gurultu_orani"]))
    print("  Sinyal adayi     : %d" % m["sinyal"])
    print("  Korelasyon disi  : %d" % m["korelasyon_disi_sinyal"])
    print("  Kartlara giren   : %d" % m["kartlara_giren_alarm"])
    print("  Uretilen kart    : %d" % m["kart_sayisi"])
    print("  Indirgeme        : %d alarm -> %d kart (%.0fx)"
          % (m["toplam_alarm"], m["kart_sayisi"], m["indirgeme_carpani"]))
    print("  Calisma suresi   : %.2f sn" % m["calisma_suresi_sn"])
    print()

    for k in sonuc.kartlar:
        _kart_bas(k)

    if a.gurultu:
        print(CIZGI)
        print("GURULTU DENETIMI — elenen alarmlardan ornekler")
        print(CIZGI)
        g = sonuc.alarmlar[
            sonuc.alarmlar["son_sinif"] != "olay_karti"
        ].head(a.gurultu)
        for _, r in g.iterrows():
            print("  %s  %-18s %-14s %-20s sev=%d skor=%.2f"
                  % (r["alarm_id"], r["son_sinif"], r["alarm_type"],
                     r["service"], r["severity"], r["sinyal_skoru"]))
            print("      neden elendi: %s" % r["eleme_gerekcesi"])
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
