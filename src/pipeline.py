"""Uctan uca boru hatti: ham alarm -> olay kartlari + metrikler."""

import time
from collections import Counter
from dataclasses import dataclass, field
from typing import List

import pandas as pd

from .cards import OlayKarti, kartlari_uret
from .clustering import ASGARI_KUME, olaylari_cikar
from .ingest import veriyi_hazirla
from .scoring import VARSAYILAN_ESIK, skorla, skor_ozeti


@dataclass
class Sonuc:
    kartlar: List[OlayKarti]
    alarmlar: pd.DataFrame
    metrikler: dict = field(default_factory=dict)
    grafik: object = None


def calistir(dizin=None, esik=VARSAYILAN_ESIK, ayrisma_acik=True,
             asgari_kume=ASGARI_KUME) -> Sonuc:
    t0 = time.time()

    if dizin is None:
        alarmlar, envanter, grafik = veriyi_hazirla()
    else:
        alarmlar, envanter, grafik = veriyi_hazirla(dizin)

    skorlanmis = skorla(alarmlar, esik=esik)
    sinyaller = skorlanmis[skorlanmis["sinyal"]]

    kumeler = olaylari_cikar(
        sinyaller, grafik, ayrisma_acik=ayrisma_acik, asgari=asgari_kume
    )
    pencere_bitisi = skorlanmis["timestamp"].max()
    kartlar = kartlari_uret(kumeler, grafik, pencere_bitisi)

    # Her alarm icin nihai muhasebe: karta atananlar ile acikca dislananlar
    # birbirini tamamlamali; ayni alarm iki karta giremez.
    atama_ciftleri = [
        (alarm_id, kart.kart_id)
        for kume, kart in zip(kumeler, kartlar)
        for alarm_id in kume.alarmlar["alarm_id"].tolist()
    ]
    sayim = Counter(alarm_id for alarm_id, _ in atama_ciftleri)
    tekrar_atanan = sorted(alarm_id for alarm_id, adet in sayim.items() if adet > 1)
    if tekrar_atanan:
        raise RuntimeError(
            "ayni alarm birden fazla olay kartina atandi: %s"
            % ", ".join(tekrar_atanan[:5])
        )
    atamalar = dict(atama_ciftleri)
    skorlanmis["kart_id"] = skorlanmis["alarm_id"].map(atamalar).fillna("")
    skorlanmis["son_sinif"] = "puanlama_gurultusu"
    skorlanmis.loc[
        skorlanmis["sinyal"] & skorlanmis["kart_id"].eq(""), "son_sinif"
    ] = "korelasyon_disi"
    skorlanmis.loc[skorlanmis["kart_id"].ne(""), "son_sinif"] = "olay_karti"
    korelasyon_disi = skorlanmis["son_sinif"].eq("korelasyon_disi")
    skorlanmis.loc[korelasyon_disi, "eleme_gerekcesi"] = (
        "sinyal esigini gecti; ancak en az %d alarmlik aciklanabilir bir "
        "olay grubuna atanamadi" % asgari_kume
    )

    sure = time.time() - t0
    ozet = skor_ozeti(skorlanmis)
    kart_alarm = len(atamalar)
    acikca_dislanan = len(skorlanmis) - kart_alarm

    metrikler = {
        **ozet,
        "kart_sayisi": len(kartlar),
        "indirgeme_orani": round(len(kartlar) / len(skorlanmis), 6),
        "indirgeme_carpani": round(len(skorlanmis) / max(len(kartlar), 1), 1),
        "kartlara_giren_alarm": kart_alarm,
        "korelasyon_disi_sinyal": int(korelasyon_disi.sum()),
        "acikca_dislanan_alarm": acikca_dislanan,
        "acikca_dislanan_oran": round(acikca_dislanan / len(skorlanmis), 4),
        "kayip_alarm": len(skorlanmis) - kart_alarm - acikca_dislanan,
        "tekrar_atanan_alarm": len(tekrar_atanan),
        "ayrisma_ile_bolunen_kart": sum(
            1 for k in kartlar if k.ayrisma_ile_bolundu
        ),
        "calisma_suresi_sn": round(sure, 3),
    }

    return Sonuc(
        kartlar=kartlar,
        alarmlar=skorlanmis,
        metrikler=metrikler,
        grafik=grafik,
    )


def ayrisma_karsilastirmasi(dizin=None, esik=VARSAYILAN_ESIK) -> dict:
    """X-Factor olcumu: ayrisma testi acik/kapali kart sayisi farki."""
    kapali = calistir(dizin, esik=esik, ayrisma_acik=False)
    acik = calistir(dizin, esik=esik, ayrisma_acik=True)

    kapali_kokler = {k.kok_neden for k in kapali.kartlar}
    acik_kokler = {k.kok_neden for k in acik.kartlar}

    return {
        "ayrisma_kapali_kart": len(kapali.kartlar),
        "ayrisma_acik_kart": len(acik.kartlar),
        "ayrisma_ile_ortaya_cikan": sorted(acik_kokler - kapali_kokler),
        "kapali_kokler": sorted(kapali_kokler),
        "acik_kokler": sorted(acik_kokler),
    }
