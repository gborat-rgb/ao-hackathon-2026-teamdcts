"""Olay karti uretimi, aciklama ve aksiyon takibi.

Aciklama yapisi DIREKTIF.md 13. maddedeki sirayi izler:

    SONUC -> KANIT -> GEREKCE -> GUVEN / SINIRLAR

Onemli ayrim: kartta gecen her sayi veriden OLCULMUSTUR. Model tarafindan
uretilen tek sey bu sayilari birlestiren dogal dil cumlesidir. Kanit ile
cikarimin karismamasi icin kart yapisinda ayri alanlarda tutulurlar.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional

import pandas as pd

# Kok neden tipine gore onerilen ilk aksiyon. Alarm tipi koduyla eslesir;
# eslesme yoksa genel bir inceleme aksiyonu uretilir.
AKSIYON_KATALOGU = {
    "network_down": ("Ag ekibi", "Kabin ust switch'ini ve uplink durumunu kontrol et"),
    "pkt_loss": ("Ag ekibi", "Kabin ust switch'ini ve uplink durumunu kontrol et"),
    "network_flap": ("Ag ekibi", "Link kararsizligini ve port hatalarini incele"),
    "disk_full": ("Veritabani ekibi", "Disk alanini genislet, eski WAL/log dosyalarini temizle"),
    "disk_warn": ("Sistem ekibi", "Disk buyume egilimini incele"),
    "db_conn_pool": ("Veritabani ekibi", "Baglanti havuzu limitini ve acik oturumlari incele"),
    "db_write_fail": ("Veritabani ekibi", "Yazma hatalarinin kaynagini ve disk durumunu kontrol et"),
    "ext_unreach": ("Entegrasyon ekibi", "Dis saglayici durumunu dogrula, devre kesiciyi devreye al"),
    "ext_slow": ("Entegrasyon ekibi", "Dis saglayici gecikmesini olc, zaman asimi degerlerini gozden gecir"),
    "oom_risk": ("Uygulama ekibi", "Heap kullanimini incele, servisi kontrollu yeniden baslat"),
    "mem_high": ("Uygulama ekibi", "Bellek profilini cikar"),
    "gc_pressure": ("Uygulama ekibi", "GC ayarlarini ve nesne yasam suresini incele"),
    "batch_overlap": ("Toplu is ekibi", "Cakisan is penceresini kaydir, zamanlayiciyi duzelt"),
    "batch_slow": ("Toplu is ekibi", "Uzun suren isin sorgu planini incele"),
    "thread_pool": ("Uygulama ekibi", "Is parcacigi havuzu boyutunu ve bloke cagrilari incele"),
    "cpu_high": ("Sistem ekibi", "CPU tuketen sureci tespit et"),
}

VARSAYILAN_AKSIYON = ("Nobetci muhendis", "Kok neden hipotezini dogrula ve ilgili ekibe yonlendir")

DURUMLAR = ["acik", "devam_ediyor", "kapandi"]


@dataclass
class Aksiyon:
    """Kart uzerinde acilan ve durumu izlenebilen is kaydi."""

    aksiyon_id: str
    kart_id: str
    sahip: str
    aciklama: str
    durum: str = "acik"
    acilis: str = ""
    guncelleme: str = ""
    gecmis: List[dict] = field(default_factory=list)

    def durum_degistir(self, yeni_durum: str, not_: str = "") -> None:
        if yeni_durum not in DURUMLAR:
            raise ValueError(
                "gecersiz durum: %s (gecerli: %s)" % (yeni_durum, DURUMLAR)
            )
        onceki = self.durum
        self.durum = yeni_durum
        an = datetime.now().isoformat(timespec="seconds")
        self.guncelleme = an
        self.gecmis.append(
            {"an": an, "onceki": onceki, "yeni": yeni_durum, "not": not_}
        )


@dataclass
class OlayKarti:
    kart_id: str
    baslik: str
    kok_neden: str
    kok_alarm_tipi: str
    baslangic: str
    bitis: str
    alarm_sayisi: int
    etkilenen_servisler: List[str]
    etkilenen_host_sayisi: int
    azami_siddet: int
    kanit: List[str]
    gerekce: str
    guven: str
    guven_skoru: float
    karsi_hipotez: str
    sinirlar: List[str]
    ayrisma_ile_bolundu: bool
    aksiyon: Optional[Aksiyon] = None

    def sozluk(self):
        d = asdict(self)
        if self.aksiyon:
            d["aksiyon"] = asdict(self.aksiyon)
        return d


def _guven_seviyesi(aciklama_orani: float, boyut: int, imza: float) -> tuple:
    """Kok neden hipotezinin guven seviyesi.

    Uc girdi: aciklama orani, kume buyuklugu, kok imzasinin gucu.
    """
    skor = 0.55 * aciklama_orani + 0.25 * imza + 0.20 * min(boyut / 100.0, 1.0)
    if skor >= 0.70:
        return "yuksek", round(skor, 3)
    if skor >= 0.45:
        return "orta", round(skor, 3)
    return "dusuk", round(skor, 3)


def _kanit_topla(kume, grafik) -> List[str]:
    """Karti destekleyen OLCULMUS gercekler. Cikarim icermez."""
    a = kume.alarmlar
    kanit = []

    agir = a[a["severity"] >= 4]
    kanit.append(
        "%d alarm, %d servis, %d host"
        % (len(a), a["service"].nunique(), a["host"].nunique())
    )
    kanit.append(
        "en yuksek siddet %d; sev>=4 olan %d alarm (%.0f%%)"
        % (a["severity"].max(), len(agir), 100 * len(agir) / len(a))
    )

    if kume.kok_zamani is not None:
        once = a[a["timestamp"] < kume.kok_zamani]
        kanit.append(
            "kok alarm %s'de; kumenin %%%.0f'i bu andan sonra geliyor"
            % (
                kume.kok_zamani.strftime("%H:%M:%S"),
                100 * (1 - len(once) / len(a)),
            )
        )

    ilk_tipler = (
        agir.sort_values("timestamp")["alarm_type"].drop_duplicates().head(4).tolist()
    )
    if ilk_tipler:
        kanit.append("siddetli alarmlarin gelis sirasi: " + " -> ".join(ilk_tipler))

    kanit.append(
        "bagimlilik grafiginde kokun asagi akisi kumenin %%%.0f'ini acikliyor"
        % (100 * kume.aciklama_orani)
    )

    # Kabin koku ise host kapsamini kanit olarak ver.
    if "/" in kume.kok_servis and "kabini" in kume.kok_servis:
        yer = kume.kok_servis.split(" ")[0]
        dc, kabin = yer.split("/")
        kabin_alarmlari = a[(a["veri_merkezi"] == dc) & (a["kabin"] == kabin)]
        toplam = grafik.kabin_host_sayisi.get((dc, kabin), 0)
        if toplam:
            kanit.append(
                "%s kabinindeki %d host'un %d'u alarm uretiyor (%%%.0f)"
                % (
                    yer,
                    toplam,
                    kabin_alarmlari["host"].nunique(),
                    100 * kabin_alarmlari["host"].nunique() / toplam,
                )
            )

    return kanit


def _gerekce_uret(kume, grafik) -> str:
    """Kanitlari nedensel bir cumleye baglar. Bu alan CIKARIMDIR."""
    a = kume.alarmlar
    agir = a[a["severity"] >= 4]
    sira = (
        agir.sort_values("timestamp")["alarm_type"].drop_duplicates().head(3).tolist()
    )
    zincir = " -> ".join(sira) if sira else kume.kok_alarm_tipi

    sure_dk = (kume.bitis - kume.baslangic).total_seconds() / 60.0
    gelisim = "ani patlama" if sure_dk <= 12 else "zamana yayilan gelisim"

    return (
        "Kumenin ilk siddetli alarmi %s uzerinde %s tipinde ve %s'de uretildi. "
        "Sonrasinda gelen alarmlar (%s) bagimlilik grafiginde bu noktanin asagi "
        "akisinda kalan servislerde yogunlasiyor; kokun asagi akisi kumenin "
        "%%%.0f'ini acikliyor. Olayin sekli %s (%.0f dakika). Bu nedenle %s "
        "turev etki degil, kok neden olarak degerlendirildi."
        % (
            kume.kok_servis,
            kume.kok_alarm_tipi,
            kume.kok_zamani.strftime("%H:%M:%S") if kume.kok_zamani is not None else "?",
            zincir,
            100 * kume.aciklama_orani,
            gelisim,
            sure_dk,
            kume.kok_servis,
        )
    )


def _sinirlar(kume, pencere_bitisi) -> List[str]:
    s = []
    if (pencere_bitisi - kume.bitis).total_seconds() < 180:
        s.append(
            "Olay gozlem penceresinin sonunda hala aktif gorunuyor; "
            "bitis zamani kesin degil."
        )
    if kume.aciklama_orani < 0.75:
        s.append(
            "Kumenin %%%.0f'i kok nedenin asagi akisinda degil; "
            "ikinci bir etken olabilir."
            % (100 * (1 - kume.aciklama_orani))
        )
    if kume.boyut < 30:
        s.append("Kume kucuk; istatistiksel dayanak sinirli.")
    return s


def kart_uret(kume, grafik, sira: int, pencere_bitisi) -> OlayKarti:
    a = kume.alarmlar
    imza = kume.karsi_hipotez.get("imza", 0.5) if kume.karsi_hipotez else 0.5
    guven, skor = _guven_seviyesi(kume.aciklama_orani, kume.boyut, imza)

    kh = kume.karsi_hipotez or {}
    karsi = (
        "%s (aciklama orani %%%.0f) — kok olarak bu da degerlendirildi, "
        "ancak daha gec basladigi icin ikinci sirada."
        % (kh.get("etiket", "-"), 100 * kh.get("aciklama_orani", 0))
        if kh
        else "Belirgin bir alternatif kok adayi cikmadi."
    )

    sahip, aksiyon_metni = AKSIYON_KATALOGU.get(
        kume.kok_alarm_tipi, VARSAYILAN_AKSIYON
    )
    kart_id = "OLAY-%02d" % sira
    aksiyon = Aksiyon(
        aksiyon_id="AKS-%02d" % sira,
        kart_id=kart_id,
        sahip=sahip,
        aciklama="%s (%s)" % (aksiyon_metni, kume.kok_servis),
        acilis=datetime.now().isoformat(timespec="seconds"),
    )

    return OlayKarti(
        kart_id=kart_id,
        baslik="%s kaynakli olay — %s"
        % (kume.kok_servis, kume.kok_alarm_tipi),
        kok_neden=kume.kok_servis,
        kok_alarm_tipi=kume.kok_alarm_tipi,
        baslangic=kume.baslangic.strftime("%Y-%m-%d %H:%M:%S"),
        bitis=kume.bitis.strftime("%Y-%m-%d %H:%M:%S"),
        alarm_sayisi=kume.boyut,
        etkilenen_servisler=kume.servisler,
        etkilenen_host_sayisi=int(a["host"].nunique()),
        azami_siddet=int(a["severity"].max()),
        kanit=_kanit_topla(kume, grafik),
        gerekce=_gerekce_uret(kume, grafik),
        guven=guven,
        guven_skoru=skor,
        karsi_hipotez=karsi,
        sinirlar=_sinirlar(kume, pencere_bitisi),
        ayrisma_ile_bolundu=kume.ayrisma_ile_bolundu,
        aksiyon=aksiyon,
    )


def kartlari_uret(kumeler, grafik, pencere_bitisi) -> List[OlayKarti]:
    return [
        kart_uret(k, grafik, i + 1, pencere_bitisi)
        for i, k in enumerate(kumeler)
    ]
