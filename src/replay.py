"""Erken tespit: gece yeniden oynatilarak her kartin NE ZAMAN olusacagi olculur.

Boru hattinin kendisi toplu calisir — gecenin tamami okunur, kartlar uretilir.
Bu modul ayni boru hattini artan zaman dilimleri uzerinde tekrar calistirarak
su soruyu cevaplar: *arac o gece canli calisiyor olsaydi, her kok nedeni kacinci
dakikada soylerdi?*

Olculen buyukluk, kart basina **tespit gecikmesi**: kokun ilk siddetli alarmi
ile o kokun ilk kez kart olarak belirdigi an arasindaki fark.

Kartlar toplu kosuda oldugu gibi uretilir; burada yeni bir algoritma yok.
Tek fark girdinin `t` anina kadar kirpilmis olmasi — yani sonuclar canli
calisan bir sistemin o anda gorebilecegi seyle ayni.
"""

from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd

from .clustering import ASGARI_KUME
from .ingest import veriyi_hazirla
from .pipeline import calistir
from .scoring import VARSAYILAN_ESIK

# Dilim adimi. 2 saatlik pencerede 120 sn ~60 kosu demek; daha ince adim
# gecikme olcumunu keskinlestirir ama suryi dogrusal buyutur.
VARSAYILAN_ADIM_SN = 120

# Bu sayidan az alarm iceren dilimler atlanir. Poisson taban hizi cok az
# gozlemle anlamsizlasir ve bos dilim boru hattinda bolme hatasi uretir.
ASGARI_DILIM_ALARMI = 30


@dataclass
class TespitKaydi:
    """Bir kok nedenin ilk kez kart olarak belirdigi an."""

    kok_neden: str
    kok_alarm_tipi: str
    kok_ilk_alarm: pd.Timestamp
    kart_olusma_ani: pd.Timestamp
    gecikme_sn: float
    kart_alarm_sayisi: int
    toplu_kosuda_var: bool = True

    @property
    def gecikme_metni(self) -> str:
        dk, sn = divmod(int(self.gecikme_sn), 60)
        return "%d dk %02d sn" % (dk, sn) if dk else "%d sn" % sn

    def sozluk(self) -> dict:
        return {
            "kok_neden": self.kok_neden,
            "kok_alarm_tipi": self.kok_alarm_tipi,
            "kok_ilk_alarm": self.kok_ilk_alarm.strftime("%H:%M:%S"),
            "kart_olusma_ani": self.kart_olusma_ani.strftime("%H:%M:%S"),
            "gecikme_sn": round(self.gecikme_sn, 1),
            "gecikme_metni": self.gecikme_metni,
            "kart_alarm_sayisi": self.kart_alarm_sayisi,
            "toplu_kosuda_var": self.toplu_kosuda_var,
        }


@dataclass
class ErkenTespitSonucu:
    kayitlar: List[TespitKaydi] = field(default_factory=list)
    # (an, o ana kadar islenen alarm, o an acik kart sayisi)
    zaman_serisi: List[tuple] = field(default_factory=list)
    adim_sn: int = VARSAYILAN_ADIM_SN
    dilim_sayisi: int = 0
    toplu_kart_sayisi: int = 0

    @property
    def ortalama_gecikme_sn(self) -> Optional[float]:
        if not self.kayitlar:
            return None
        return sum(k.gecikme_sn for k in self.kayitlar) / len(self.kayitlar)

    @property
    def en_hizli(self) -> Optional[TespitKaydi]:
        return min(self.kayitlar, key=lambda k: k.gecikme_sn, default=None)

    def ozet(self) -> dict:
        return {
            "adim_sn": self.adim_sn,
            "dilim_sayisi": self.dilim_sayisi,
            "tespit_edilen_kok": len(self.kayitlar),
            "toplu_kosudaki_kart": self.toplu_kart_sayisi,
            "ortalama_gecikme_sn": (
                round(self.ortalama_gecikme_sn, 1)
                if self.ortalama_gecikme_sn is not None
                else None
            ),
            "kayitlar": [k.sozluk() for k in self.kayitlar],
        }


def _olay_baslangici(kart) -> pd.Timestamp:
    """Olayin basladigi an — gecikme bu noktadan olculur.

    Referans olarak kartin KENDI baslangici kullanilir, kokun veri setindeki
    ilk alarmi degil. Cunku ayni servis/kabin gece boyunca arka plan gurultusu
    da uretiyor; ilk sev>=4 gurultusunu referans almak gecikmeyi saatlerce
    sisirirdi. Kartin baslangici, o olaya ait ilk alarmdir.
    """
    return pd.Timestamp(kart.baslangic)


def erken_tespit(dizin=None, adim_sn=VARSAYILAN_ADIM_SN,
                 esik=VARSAYILAN_ESIK, ayrisma_acik=True,
                 asgari_kume=ASGARI_KUME) -> ErkenTespitSonucu:
    """Geceyi yeniden oynatir ve her kokun ilk tespit anini olcer."""
    if adim_sn <= 0:
        raise ValueError("adim_sn pozitif olmali, verilen: %r" % adim_sn)

    veri = veriyi_hazirla() if dizin is None else veriyi_hazirla(dizin)
    alarmlar, envanter, grafik = veri

    baslangic = alarmlar["timestamp"].min()
    bitis = alarmlar["timestamp"].max()
    adim = pd.Timedelta(seconds=adim_sn)

    sonuc = ErkenTespitSonucu(adim_sn=adim_sn)
    ilk_gorulme = {}

    kesim = baslangic + adim
    while kesim < bitis:
        dilim = alarmlar[alarmlar["timestamp"] <= kesim]
        if len(dilim) < ASGARI_DILIM_ALARMI:
            kesim += adim
            continue

        sonuc.dilim_sayisi += 1
        kismi = calistir(
            esik=esik,
            ayrisma_acik=ayrisma_acik,
            asgari_kume=asgari_kume,
            veri=(dilim, envanter, grafik),
        )
        sonuc.zaman_serisi.append(
            (kesim, len(dilim), len(kismi.kartlar))
        )

        for kart in kismi.kartlar:
            if kart.kok_neden in ilk_gorulme:
                continue
            kok_t = _olay_baslangici(kart)
            ilk_gorulme[kart.kok_neden] = TespitKaydi(
                kok_neden=kart.kok_neden,
                kok_alarm_tipi=kart.kok_alarm_tipi,
                kok_ilk_alarm=kok_t,
                kart_olusma_ani=kesim,
                gecikme_sn=(kesim - kok_t).total_seconds(),
                kart_alarm_sayisi=kart.alarm_sayisi,
            )

        kesim += adim

    # Toplu kosu referansi: canli akista yakalanan kokler ile gecenin
    # tamami okunduktan sonra uretilen kartlar ayni mi?
    toplu = calistir(
        esik=esik, ayrisma_acik=ayrisma_acik, asgari_kume=asgari_kume,
        veri=veri,
    )
    toplu_kokler = {k.kok_neden for k in toplu.kartlar}
    sonuc.toplu_kart_sayisi = len(toplu.kartlar)

    for kok, kayit in ilk_gorulme.items():
        kayit.toplu_kosuda_var = kok in toplu_kokler

    # Toplu kosuda olup replay'de hic yakalanamayan kok kalmamali; kalirsa
    # bu, canli calisan bir sistemin kaciracagi olay demektir ve raporlanir.
    for kok in sorted(toplu_kokler - set(ilk_gorulme)):
        kart = next(k for k in toplu.kartlar if k.kok_neden == kok)
        sonuc.kayitlar.append(TespitKaydi(
            kok_neden=kok,
            kok_alarm_tipi=kart.kok_alarm_tipi,
            kok_ilk_alarm=_olay_baslangici(kart),
            kart_olusma_ani=bitis,
            gecikme_sn=(bitis - _olay_baslangici(kart)).total_seconds(),
            kart_alarm_sayisi=kart.alarm_sayisi,
        ))

    sonuc.kayitlar.extend(ilk_gorulme.values())
    sonuc.kayitlar.sort(key=lambda k: k.kart_olusma_ani)
    return sonuc
