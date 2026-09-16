"""Uctan uca boru hatti: ham alarm -> olay kartlari + metrikler."""

import time
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

    sure = time.time() - t0
    ozet = skor_ozeti(skorlanmis)
    kart_alarm = sum(k.alarm_sayisi for k in kartlar)

    metrikler = {
        **ozet,
        "kart_sayisi": len(kartlar),
        "indirgeme_orani": round(len(kartlar) / len(skorlanmis), 6),
        "indirgeme_carpani": round(len(skorlanmis) / max(len(kartlar), 1), 1),
        "kartlara_giren_alarm": kart_alarm,
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
