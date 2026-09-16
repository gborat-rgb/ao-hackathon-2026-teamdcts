"""Sinyal / gurultu skorlamasi.

Amac ikili bir karar degil, her alarm icin *gerekcesi tasinabilen* bir skor
uretmek. Boylece "neden elendi" sorusu kartin yaninda cevaplanabiliyor
(bonus gereksinim) ve esik sonradan oynatilabiliyor.

Yontem: bir alarm, kendi tipinin / kendi servisinin o zaman diliminde
beklenenden ne kadar fazla gorulduguyle olculur. Beklenen deger, tipin tum
pencereye duzgun yayildigi varsayimindan gelir; sapma Poisson z-skoru ile
olculur:

    z = (gozlenen - beklenen) / sqrt(beklenen)

Bu olcu nadir ama yogunlasan tipleri (network_down: 12 adet, hepsi tek
pencerede) dogru sekilde one cikarirken, sik ama yayvan tipleri
(cert_expiry: 220 adet, her pencereye dagilmis) tabanda birakir.

Severity tek basina ayirt edici degildir (bkz. docs/plan.md 2.5) — bu yuzden
skora tek girdi olarak degil, carpan olarak girer.
"""

import numpy as np
import pandas as pd

KOVA = "2min"

# Skor bilesenlerinin agirliklari. Toplami 1 olacak sekilde secildi;
# tip yogunlasmasi en guclu ayirt edici oldugu icin en buyuk pay onda.
W_TIP = 0.45
W_SERVIS = 0.35
W_SEVERITY = 0.20

# Bu skorun altindaki alarmlar gurultu kabul edilir. Deger veriye bakilarak
# secildi: skor dagiliminda taban gurultu ile olay alarmlari arasindaki
# bosluga denk gelir. app/CLI uzerinden oynatilabilir.
VARSAYILAN_ESIK = 0.35


def _poisson_z(sayimlar: pd.Series, beklenen: float) -> pd.Series:
    """Kova basina gozlenen sayinin beklenenden sapmasi."""
    if beklenen <= 0:
        return pd.Series(0.0, index=sayimlar.index)
    return (sayimlar - beklenen) / np.sqrt(beklenen)


def _kova_z_haritasi(df: pd.DataFrame, alan: str) -> dict:
    """(alan_degeri, kova) -> z skoru."""
    kovalar = df["timestamp"].dt.floor(KOVA)
    kova_sayisi = kovalar.nunique()
    harita = {}

    for deger, g in df.groupby(alan):
        g_kova = g["timestamp"].dt.floor(KOVA)
        sayim = g_kova.value_counts()
        beklenen = len(g) / kova_sayisi
        z = _poisson_z(sayim, beklenen)
        for k, v in z.items():
            harita[(deger, k)] = float(v)

    return harita


def skorla(df: pd.DataFrame, esik: float = VARSAYILAN_ESIK) -> pd.DataFrame:
    """Her alarma sinyal skoru ve gerekcesini ekler.

    Eklenen sutunlar:
      z_tip, z_servis  — ham sapma olculeri
      sinyal_skoru     — 0..1 arasi birlesik skor
      sinyal           — skor >= esik
      eleme_gerekcesi  — gurultu ise neden elendigi (denetim gorunumu icin)
    """
    df = df.copy()
    kovalar = df["timestamp"].dt.floor(KOVA)

    tip_z = _kova_z_haritasi(df, "alarm_type")
    servis_z = _kova_z_haritasi(df, "service")

    df["z_tip"] = [
        tip_z.get((t, k), 0.0) for t, k in zip(df["alarm_type"], kovalar)
    ]
    df["z_servis"] = [
        servis_z.get((s, k), 0.0) for s, k in zip(df["service"], kovalar)
    ]

    # z skorlarini 0..1'e sikistir. 6 sigma pratikte tavan kabul edildi;
    # bunun uzeri zaten kesin sinyal.
    n_tip = (df["z_tip"] / 6.0).clip(0, 1)
    n_servis = (df["z_servis"] / 6.0).clip(0, 1)
    n_sev = (df["severity"] - 1) / 4.0

    df["sinyal_skoru"] = (
        W_TIP * n_tip + W_SERVIS * n_servis + W_SEVERITY * n_sev
    ).round(4)
    df["sinyal"] = df["sinyal_skoru"] >= esik
    df["eleme_gerekcesi"] = [
        ""
        if s
        else _gerekce(zt, zs, sev)
        for s, zt, zs, sev in zip(
            df["sinyal"], df["z_tip"], df["z_servis"], df["severity"]
        )
    ]
    return df


def _gerekce(z_tip: float, z_servis: float, severity: int) -> str:
    """Elenen alarm icin insan tarafindan okunabilir gerekce."""
    parcalar = []
    if z_tip < 1.0:
        parcalar.append(
            "tipi o dakikada beklenenden fazla gorulmuyor (z=%.1f)" % z_tip
        )
    if z_servis < 1.0:
        parcalar.append(
            "servisinde yogunlasma yok (z=%.1f)" % z_servis
        )
    if severity <= 2:
        parcalar.append("dusuk siddet (sev=%d)" % severity)
    if not parcalar:
        parcalar.append("birlesik skor esigin altinda")
    return "; ".join(parcalar)


def skor_ozeti(df: pd.DataFrame) -> dict:
    sinyal = int(df["sinyal"].sum())
    return {
        "toplam_alarm": len(df),
        "sinyal": sinyal,
        "gurultu": len(df) - sinyal,
        "gurultu_orani": round((len(df) - sinyal) / len(df), 4),
    }
