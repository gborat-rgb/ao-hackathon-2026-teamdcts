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

ALARM_SUTUNLARI = {
    "alarm_id", "timestamp", "source_system", "host", "service", "severity",
    "alarm_type", "message", "veri_merkezi", "kabin", "ortam",
}
ENVANTER_SUTUNLARI = {
    "host", "servis", "veri_merkezi", "kabin", "ortam", "is_kritikligi",
}
BAGIMLILIK_SUTUNLARI = {
    "kaynak_servis", "hedef_servis", "bagimlilik_tipi", "kritiklik",
}


class VeriDogrulamaHatasi(ValueError):
    """Eksik, bozuk veya birbiriyle tutarsiz veri paketi."""


def _csv_oku(yol: Path, ad: str) -> pd.DataFrame:
    try:
        return pd.read_csv(yol)
    except FileNotFoundError as exc:
        raise VeriDogrulamaHatasi(
            "%s bulunamadi: %s" % (ad, yol)
        ) from exc
    except (pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise VeriDogrulamaHatasi(
            "%s okunamadi; CSV bicimi bozuk: %s" % (ad, exc)
        ) from exc


def _sutunlari_dogrula(df: pd.DataFrame, zorunlu: set, ad: str) -> None:
    eksik = sorted(zorunlu - set(df.columns))
    if eksik:
        raise VeriDogrulamaHatasi(
            "%s zorunlu sutunlari eksik: %s" % (ad, ", ".join(eksik))
        )


def _bos_degerleri_dogrula(df: pd.DataFrame, sutunlar: set, ad: str) -> None:
    bos = [s for s in sorted(sutunlar) if df[s].isna().any()]
    if bos:
        raise VeriDogrulamaHatasi(
            "%s kritik alanlarda bos deger iceriyor: %s"
            % (ad, ", ".join(bos))
        )


def alarmlari_yukle(dizin: Path = VERI_DIZINI) -> pd.DataFrame:
    """Alarm akisinin tamamini okur. Ornekleme yapilmaz."""
    df = _csv_oku(Path(dizin) / "alarms.csv", "alarms.csv")
    _sutunlari_dogrula(df, ALARM_SUTUNLARI, "alarms.csv")
    if df.empty:
        raise VeriDogrulamaHatasi("alarms.csv bos; islenecek alarm yok")
    _bos_degerleri_dogrula(
        df,
        {"alarm_id", "timestamp", "host", "service", "severity", "alarm_type"},
        "alarms.csv",
    )

    tekrar = df.loc[df["alarm_id"].duplicated(), "alarm_id"].astype(str).tolist()
    if tekrar:
        raise VeriDogrulamaHatasi(
            "alarms.csv tekrar eden alarm_id iceriyor: %s"
            % ", ".join(tekrar[:5])
        )

    zaman = pd.to_datetime(df["timestamp"], format="ISO8601", errors="coerce")
    gecersiz_zaman = df.loc[zaman.isna(), "alarm_id"].astype(str).tolist()
    if gecersiz_zaman:
        raise VeriDogrulamaHatasi(
            "alarms.csv gecersiz timestamp iceriyor; alarm_id: %s"
            % ", ".join(gecersiz_zaman[:5])
        )
    df["timestamp"] = zaman

    siddet = pd.to_numeric(df["severity"], errors="coerce")
    gecersiz_siddet = siddet.isna() | ~siddet.between(1, 5) | (siddet % 1 != 0)
    if gecersiz_siddet.any():
        ids = df.loc[gecersiz_siddet, "alarm_id"].astype(str).tolist()
        raise VeriDogrulamaHatasi(
            "alarms.csv severity 1-5 arasi tam sayi olmali; alarm_id: %s"
            % ", ".join(ids[:5])
        )
    df["severity"] = siddet.astype(int)
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def envanter_yukle(dizin: Path = VERI_DIZINI) -> pd.DataFrame:
    df = _csv_oku(Path(dizin) / "host_inventory.csv", "host_inventory.csv")
    _sutunlari_dogrula(df, ENVANTER_SUTUNLARI, "host_inventory.csv")
    if df.empty:
        raise VeriDogrulamaHatasi("host_inventory.csv bos")
    _bos_degerleri_dogrula(df, ENVANTER_SUTUNLARI, "host_inventory.csv")
    tekrar = df.loc[df["host"].duplicated(), "host"].astype(str).tolist()
    if tekrar:
        raise VeriDogrulamaHatasi(
            "host_inventory.csv tekrar eden host iceriyor: %s"
            % ", ".join(tekrar[:5])
        )
    return df


def bagimliliklari_yukle(dizin: Path = VERI_DIZINI) -> pd.DataFrame:
    df = _csv_oku(
        Path(dizin) / "service_dependencies.csv", "service_dependencies.csv"
    )
    _sutunlari_dogrula(df, BAGIMLILIK_SUTUNLARI, "service_dependencies.csv")
    _bos_degerleri_dogrula(df, BAGIMLILIK_SUTUNLARI, "service_dependencies.csv")
    gecersiz_tip = ~df["bagimlilik_tipi"].isin({"senkron", "asenkron"})
    if gecersiz_tip.any():
        raise VeriDogrulamaHatasi(
            "service_dependencies.csv gecersiz bagimlilik_tipi iceriyor: %s"
            % ", ".join(sorted(df.loc[gecersiz_tip, "bagimlilik_tipi"].unique()))
        )
    return df


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
        cift = (a, b) if a < b else (b, a)
        # Ayni servis cifti farkli arama derinlikleriyle sorgulanabilir.
        # Derinligi anahtara katmamak, onceki dar aramadaki None sonucunu daha
        # genis aramaya tasiyarak var olan bir yolu "kopuk" gosterebilir.
        anahtar = (cift[0], cift[1], max_atlama)
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

    bilinmeyen_host = sorted(set(alarmlar["host"]) - set(envanter["host"]))
    if bilinmeyen_host:
        raise VeriDogrulamaHatasi(
            "alarms.csv envanterde olmayan host iceriyor: %s"
            % ", ".join(bilinmeyen_host[:5])
        )

    host_servis = envanter.set_index("host")["servis"]
    beklenen_servis = alarmlar["host"].map(host_servis)
    uyusmayan = alarmlar[beklenen_servis != alarmlar["service"]]
    if not uyusmayan.empty:
        ornek = uyusmayan.iloc[0]
        raise VeriDogrulamaHatasi(
            "alarm host/servis eslesmesi envanterle uyusmuyor: %s (%s)"
            % (ornek["host"], ornek["alarm_id"])
        )

    bilinen_servis = set(envanter["servis"])
    bagimlilik_servisleri = set(bagimliliklar["kaynak_servis"]) | set(
        bagimliliklar["hedef_servis"]
    )
    bilinmeyen_servis = sorted(bagimlilik_servisleri - bilinen_servis)
    if bilinmeyen_servis:
        raise VeriDogrulamaHatasi(
            "service_dependencies.csv envanterde olmayan servis iceriyor: %s"
            % ", ".join(bilinmeyen_servis[:5])
        )

    alarmlar = alarmlar.merge(
        envanter[["host", "is_kritikligi"]],
        on="host",
        how="left",
        validate="many_to_one",
    )
    grafik = BagimlilikGrafigi(bagimliliklar)
    # Kabin basina envanterdeki host sayisi. Kabin seviyesi kok neden adayinin
    # "kabindeki host'larin kaci alarm veriyor" testi icin gerekli.
    grafik.kabin_host_sayisi = (
        envanter.groupby(["veri_merkezi", "kabin"])["host"].nunique().to_dict()
    )
    return alarmlar, envanter, grafik
