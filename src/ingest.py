"""Senaryo paketini okur ve bagimlilik grafigini kurar.

Veri sozlugu `kaynak_servis`in `hedef_servis`e bagimli oldugunu soyluyor:
hedef bozulursa kaynak etkilenir. Etki bu yuzden hedef -> kaynak yonunde
akar; grafigi bu yonde kuruyoruz ki "kok nedenin asagi akisi" dogrudan
hesaplanabilsin.
"""

from collections import defaultdict, deque
from pathlib import Path

import pandas as pd

VERI_DIZINI = Path(__file__).resolve().parent.parent / "senaryo_paketi"


def alarmlari_yukle(dizin: Path = VERI_DIZINI) -> pd.DataFrame:
    """Alarm akisinin tamamini okur. Ornekleme yapilmaz."""
    df = pd.read_csv(dizin / "alarms.csv", parse_dates=["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def envanter_yukle(dizin: Path = VERI_DIZINI) -> pd.DataFrame:
    return pd.read_csv(dizin / "host_inventory.csv")


def bagimliliklari_yukle(dizin: Path = VERI_DIZINI) -> pd.DataFrame:
    return pd.read_csv(dizin / "service_dependencies.csv")


class BagimlilikGrafigi:
    """Servis bagimliliklari uzerinde etki yayilimini modelleyen grafik.

    `etki_kenarlari`: hedef -> {kaynak} (bozulma bu yonde yayilir)
    `komsuluk`: yonsuz komsuluk, kumeleme mesafesi icin
    """

    def __init__(self, bagimliliklar: pd.DataFrame):
        self.etki = defaultdict(set)
        self.komsuluk = defaultdict(set)
        self.kritiklik = {}
        self.servisler = set()

        for _, r in bagimliliklar.iterrows():
            kaynak, hedef = r["kaynak_servis"], r["hedef_servis"]
            self.etki[hedef].add(kaynak)
            self.komsuluk[hedef].add(kaynak)
            self.komsuluk[kaynak].add(hedef)
            self.kritiklik[(kaynak, hedef)] = r["kritiklik"]
            self.servisler.update([kaynak, hedef])

        self._mesafe_onbellek = {}

    def asagi_akis(self, servis: str, max_atlama: int = 3) -> dict:
        """servis bozulursa etkilenebilecek servisler -> kac atlama uzakta."""
        gorulen = {servis: 0}
        kuyruk = deque([(servis, 0)])
        while kuyruk:
            s, d = kuyruk.popleft()
            if d >= max_atlama:
                continue
            for komsu in self.etki.get(s, ()):
                if komsu not in gorulen:
                    gorulen[komsu] = d + 1
                    kuyruk.append((komsu, d + 1))
        return gorulen

    def mesafe(self, a: str, b: str, max_atlama: int = 4):
        """Yonsuz en kisa yol. Yol yoksa None."""
        if a == b:
            return 0
        anahtar = (a, b) if a < b else (b, a)
        if anahtar in self._mesafe_onbellek:
            return self._mesafe_onbellek[anahtar]

        gorulen = {a}
        kuyruk = deque([(a, 0)])
        sonuc = None
        while kuyruk:
            s, d = kuyruk.popleft()
            if d >= max_atlama:
                continue
            for komsu in self.komsuluk.get(s, ()):
                if komsu == b:
                    sonuc = d + 1
                    kuyruk.clear()
                    break
                if komsu not in gorulen:
                    gorulen.add(komsu)
                    kuyruk.append((komsu, d + 1))

        self._mesafe_onbellek[anahtar] = sonuc
        return sonuc


def veriyi_hazirla(dizin: Path = VERI_DIZINI):
    """Uc dosyayi okur, host -> servis/kabin bilgisini alarmlara isler."""
    alarmlar = alarmlari_yukle(dizin)
    envanter = envanter_yukle(dizin)
    bagimliliklar = bagimliliklari_yukle(dizin)

    alarmlar = alarmlar.merge(
        envanter[["host", "is_kritikligi"]], on="host", how="left"
    )
    grafik = BagimlilikGrafigi(bagimliliklar)
    # Kabin basina envanterdeki host sayisi. Kabin seviyesi kok neden adayinin
    # "kabindeki host'larin kaci alarm veriyor" testi icin gerekli.
    grafik.kabin_host_sayisi = (
        envanter.groupby(["veri_merkezi", "kabin"])["host"].nunique().to_dict()
    )
    return alarmlar, envanter, grafik
