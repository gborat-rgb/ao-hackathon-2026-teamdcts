"""Nedensel kumeleme ve ayrisma testi.

Iki asama:

1. `kumele` — sinyal alarmlarini zamansal yakinlik VE bagimlilik grafigi
   yakinligi birlikte saglandiginda birlestirir (union-find). Baglanti
   gecisken oldugu icin pencere uyarlanabilir davranir: alarmlar gelmeye
   devam ettigi surece kume uzar, bu da yavas gelisen olaylari (billing disk
   dolmasi, toplu is cakismasi) tek parca halinde tutar.

2. `ayristir` — bir kumenin tek bir kok nedenle aciklanip aciklanamadigini
   sinar. Aciklanamayan uye kalirsa kume bolunur.

Ikinci asama cozumun ayirt edici parcasidir: 02:38-02:58 arasinda
payment-provider-gw kesintisi ile session-service bellek tukenmesi ayni anda
oluyor ve ikisi de mobile-bff'i etkiliyor. Sadece zaman+servis yakinligina
bakan bir kumeleme bunlari tek olay sayar. Grafikte iki kok arasinda yol
olmadigi icin ayrisma testi bunlari ayri tutar.
"""

from dataclasses import dataclass, field
from typing import List

import pandas as pd

# Iki alarmi ayni olaya baglamak icin izin verilen azami zaman farki.
# Gecisken baglanti sayesinde olayin toplam suresi bundan uzun olabilir.
BAGLANTI_PENCERESI_SN = 180

# Iki servisin ayni olaya ait sayilmasi icin grafikte olabilecegi azami uzaklik.
AZAMI_ATLAMA = 2

# Grafikte BAGLI kalan bir artigin ayri olay sayilabilmesi icin gereken pay.
# Kopuk artiklar bu esige bakilmadan zaten bolunur.
AYRISMA_ESIGI = 0.15
BAGLI_BOLME_ESIGI = 0.40

# Bagli bir artigin ayri olay sayilabilmesi icin gereken asgari imza gucu.
# Gurultu tipleri (log_rotate, cert_expiry) bu esigi gecemez.
ASGARI_IMZA = 0.35

# Bolunme sonrasi bir parcanin kart olabilmesi icin gereken asgari alarm.
ASGARI_KUME = 8


class _BirlesimBul:
    def __init__(self, n):
        self.ebeveyn = list(range(n))

    def bul(self, x):
        while self.ebeveyn[x] != x:
            self.ebeveyn[x] = self.ebeveyn[self.ebeveyn[x]]
            x = self.ebeveyn[x]
        return x

    def birlestir(self, a, b):
        ra, rb = self.bul(a), self.bul(b)
        if ra != rb:
            self.ebeveyn[rb] = ra


@dataclass
class Kume:
    """Bir olay adayi: alarmlar + kok neden atfi."""

    alarmlar: pd.DataFrame
    kok_servis: str = ""
    kok_alarm_tipi: str = ""
    kok_zamani: pd.Timestamp = None
    aciklama_orani: float = 0.0
    kok_imza: float = 0.0
    karsi_hipotez: dict = field(default_factory=dict)
    ayrisma_ile_bolundu: bool = False

    @property
    def boyut(self):
        return len(self.alarmlar)

    @property
    def baslangic(self):
        return self.alarmlar["timestamp"].min()

    @property
    def bitis(self):
        return self.alarmlar["timestamp"].max()

    @property
    def servisler(self):
        return sorted(self.alarmlar["service"].unique())


def kumele(sinyaller: pd.DataFrame, grafik, pencere_sn=BAGLANTI_PENCERESI_SN,
           azami_atlama=AZAMI_ATLAMA) -> List[pd.DataFrame]:
    """Sinyal alarmlarini zaman + grafik yakinligina gore birlestirir."""
    df = sinyaller.sort_values("timestamp").reset_index(drop=True)
    if df.empty:
        return []

    bb = _BirlesimBul(len(df))
    zamanlar = df["timestamp"].values
    servisler = df["service"].tolist()
    pencere = pd.Timedelta(seconds=pencere_sn).to_timedelta64()

    j_bas = 0
    for i in range(len(df)):
        while zamanlar[i] - zamanlar[j_bas] > pencere:
            j_bas += 1
        for j in range(j_bas, i):
            if servisler[i] == servisler[j]:
                bb.birlestir(i, j)
                continue
            d = grafik.mesafe(servisler[i], servisler[j], max_atlama=azami_atlama)
            if d is not None and d <= azami_atlama:
                bb.birlestir(i, j)

    df["_kume"] = [bb.bul(i) for i in range(len(df))]
    return [g.drop(columns="_kume") for _, g in df.groupby("_kume")]


def _kok_adaylari(alarmlar: pd.DataFrame, grafik, azami_atlama=3):
    """Kumedeki her servis icin 'kok olsaydi ne kadarini aciklardi' hesabi.

    Aciklama orani: kok kabul edilen servisin grafikte asagi akisinda kalan
    ve zamansal olarak kokten SONRA gelen uyelerin orani. Zaman kosulu onemli,
    aksi halde gec baslayan bir servis kendinden onceki alarmlari 'aciklayabilir'
    gorunur.
    """
    adaylar = []
    toplam = len(alarmlar)
    if toplam == 0:
        return []

    kume_bas = alarmlar["timestamp"].min()
    sure = max(
        (alarmlar["timestamp"].max() - kume_bas).total_seconds(), 1.0
    )
    # Oncelik ve imza daima YUKSEK SIDDETLI alarmlar uzerinden olculur.
    # Gurultu dusuk siddetle sizabildigi icin ham "ilk alarm" yaniltici olur.
    agir = alarmlar[alarmlar["severity"] >= 4]
    if agir.empty:
        agir = alarmlar

    for servis in alarmlar["service"].unique():
        kendi = alarmlar[alarmlar["service"] == servis]
        kendi_agir = agir[agir["service"] == servis]
        if kendi_agir.empty:
            continue

        kok_t = kendi_agir["timestamp"].min()
        asagi = grafik.asagi_akis(servis, max_atlama=azami_atlama)

        aciklanan = alarmlar[
            alarmlar["service"].isin(asagi.keys())
            & (alarmlar["timestamp"] >= kok_t)
        ]
        oran = len(aciklanan) / toplam

        # Oncelik: bu kok kabul edilirse kumenin ne kadari ondan SONRA geliyor.
        oncelik = float((alarmlar["timestamp"] >= kok_t).mean())

        # Imza gucu: kok adayinin en yogunlasmis alarm tipinin z skoru.
        # Nadir ve tek pencerede toplanan tipler (disk_full, ext_unreach,
        # batch_overlap, network_down) burada one cikar; yaygin semptomlar
        # (timeout, latency_high) tabanda kalir.
        imza_z = float(kendi_agir["z_tip"].max()) if "z_tip" in kendi_agir else 0.0
        imza = min(imza_z / 10.0, 1.0)
        imza_satir = kendi_agir.loc[kendi_agir["z_tip"].idxmax()] \
            if "z_tip" in kendi_agir else kendi_agir.iloc[0]

        adaylar.append({
            "tur": "servis",
            "servis": servis,
            "etiket": servis,
            "aciklama_orani": round(oran, 4),
            "oncelik": round(oncelik, 4),
            "imza": round(imza, 4),
            "skor": round(0.35 * oran + 0.40 * oncelik + 0.25 * imza, 4),
            "ilk_zaman": kok_t,
            "alarm_tipi": imza_satir["alarm_type"],
            "alarm_sayisi": len(kendi),
        })

    adaylar.extend(_lokalite_adaylari(alarmlar, grafik, agir, azami_atlama))
    return sorted(adaylar, key=lambda a: -a["skor"])


# Bir kabinin kumede beklenenden kac kat fazla temsil edilmesi gerektigi.
# Envanterde 6 kabin var, yani beklenen pay ~1/6.
LOKALITE_YOGUNLASMA_ESIGI = 2.0

# Kabin kokunun onerilebilmesi icin kabindeki host'larin en az bu oraninin
# alarm uretiyor olmasi gerekir. Veride olculen ayrim keskin: gercek kabin
# arizasinda kapsam %100, diger tum kabin/kume ciftlerinde en fazla %56.
ASGARI_HOST_KAPSAMI = 0.75


def _lokalite_adaylari(alarmlar, grafik, agir, azami_atlama=3):
    """Kabin / veri merkezi seviyesinde altyapi arizasi adaylari.

    Bazi koklerin servis karsiligi yoktur: bir kabinin agi coktugunde o
    kabindeki BIRBIRIYLE ILGISIZ servisler ayni anda alarm uretir. Servis
    grafigi bunu aciklayamaz, cunku ortak neden grafigin disindadir.

    Bu adayi ancak kabin, kumenin agir alarmlarinda beklenenden belirgin
    fazla temsil ediliyorsa oneriyoruz.
    """
    adaylar = []
    toplam = len(alarmlar)
    if toplam == 0 or agir.empty:
        return adaylar

    kabin_sayisi = max(
        alarmlar.groupby(["veri_merkezi", "kabin"]).ngroups, 1
    )
    beklenen_pay = 1.0 / kabin_sayisi

    for (dc, kabin), g in agir.groupby(["veri_merkezi", "kabin"]):
        pay = len(g) / len(agir)
        yogunlasma = pay / beklenen_pay
        if yogunlasma < LOKALITE_YOGUNLASMA_ESIGI:
            continue

        kok_t = g["timestamp"].min()
        kabin_servisleri = set(g["service"].unique())

        # Kabin kokunun asil kaniti: kabindeki host'larin buyuk cogunlugunun
        # ayni anda alarm uretmesi. Tek bir servisin bozulmasi kabindeki tum
        # host'lari vurmaz; kabin seviyesi altyapi arizasi vurur.
        toplam_host = grafik.kabin_host_sayisi.get((dc, kabin), 0)
        kapsam = g["host"].nunique() / toplam_host if toplam_host else 0.0
        if kapsam < ASGARI_HOST_KAPSAMI:
            continue
        # Kabindeki servisler + onlarin asagi akisi
        asagi = set(kabin_servisleri)
        for s in kabin_servisleri:
            asagi |= set(grafik.asagi_akis(s, max_atlama=azami_atlama).keys())

        aciklanan = alarmlar[
            (
                (alarmlar["veri_merkezi"] == dc) & (alarmlar["kabin"] == kabin)
                | alarmlar["service"].isin(asagi)
            )
            & (alarmlar["timestamp"] >= kok_t)
        ]
        oran = len(aciklanan) / toplam
        oncelik = float((alarmlar["timestamp"] >= kok_t).mean())
        imza_z = float(g["z_tip"].max()) if "z_tip" in g else 0.0
        imza = min(imza_z / 10.0, 1.0)
        imza_satir = g.loc[g["z_tip"].idxmax()] if "z_tip" in g else g.iloc[0]

        adaylar.append({
            "tur": "lokalite",
            "servis": "%s/%s" % (dc, kabin),
            "etiket": "%s/%s kabini" % (dc, kabin),
            "aciklama_orani": round(oran, 4),
            "oncelik": round(oncelik, 4),
            "imza": round(imza, 4),
            "yogunlasma": round(yogunlasma, 2),
            "etkilenen_host": int(g["host"].nunique()),
            # Lokalite adayi ancak yogunlasma gercekten yuksekse servis
            # adaylarini gecebilsin diye yogunlasma skora katiliyor.
            "skor": round(
                0.35 * oran + 0.40 * oncelik + 0.25 * imza
                + 0.05 * min(yogunlasma - LOKALITE_YOGUNLASMA_ESIGI, 2.0),
                4,
            ),
            "ilk_zaman": kok_t,
            "alarm_tipi": imza_satir["alarm_type"],
            "alarm_sayisi": len(
                alarmlar[
                    (alarmlar["veri_merkezi"] == dc)
                    & (alarmlar["kabin"] == kabin)
                ]
            ),
        })

    return adaylar


def ayristir(alarmlar: pd.DataFrame, grafik, derinlik=0,
             esik=AYRISMA_ESIGI, asgari=ASGARI_KUME) -> List[Kume]:
    """Kumeyi tek kokle aciklanabilir parcalara boler.

    En iyi kok secilir; onun asagi akisinda olmayan uyeler 'aciklanamayan'
    kabul edilir. Bu grup yeterince buyukse kendi icinde ayni islem
    tekrarlanir ve kume bolunur.
    """
    if len(alarmlar) == 0:
        return []

    adaylar = _kok_adaylari(alarmlar, grafik)
    if not adaylar:
        return [Kume(alarmlar=alarmlar)]

    en_iyi = adaylar[0]
    aciklanan_maske = _aciklanan_maske(alarmlar, en_iyi, grafik)
    aciklanan = alarmlar[aciklanan_maske]
    aciklanamayan = alarmlar[~aciklanan_maske]

    kume = Kume(
        alarmlar=aciklanan if len(aciklanan) else alarmlar,
        kok_servis=en_iyi["etiket"],
        kok_alarm_tipi=en_iyi["alarm_tipi"],
        kok_zamani=en_iyi["ilk_zaman"],
        aciklama_orani=en_iyi["aciklama_orani"],
        kok_imza=en_iyi["imza"],
        karsi_hipotez=adaylar[1] if len(adaylar) > 1 else {},
    )

    if derinlik >= 3 or len(aciklanamayan) < asgari:
        return [kume]

    # Bolunme karari yalnizca "artan uye sayisi" ile verilmez. Artan grubun
    # KENDI kokunun, birincil kokten grafikte KOPUK olmasi aranir. Ayrimin
    # dayanagi budur: iki olay ayni anda olsa ve ayni servisi vursa bile,
    # kokleri arasinda nedensel yol yoksa ayri olaylardir.
    artan_adaylar = _kok_adaylari(aciklanamayan, grafik)
    if not artan_adaylar:
        return [kume]

    ikincil = artan_adaylar[0]
    kopuk = _kokler_kopuk_mu(en_iyi, ikincil, grafik)
    oran = len(aciklanamayan) / len(alarmlar)

    # Asil olcut grafik koplugu. Bagli kalan bir artik, ancak hem cok buyukse
    # hem de kendi basina guclu bir imzasi varsa ayri olay sayilir; aksi halde
    # ayni olayin gec gelen kuyrugudur ve bolmek yanlis olur.
    bagli_ama_guclu = (
        oran > BAGLI_BOLME_ESIGI and ikincil.get("imza", 0.0) >= ASGARI_IMZA
    )

    if kopuk or bagli_ama_guclu:
        kume.ayrisma_ile_bolundu = True
        alt = ayristir(aciklanamayan, grafik, derinlik + 1, esik, asgari)
        for k in alt:
            k.ayrisma_ile_bolundu = True
        return [kume] + alt

    return [kume]


def _aciklanan_maske(alarmlar, aday, grafik, azami_atlama=3):
    """Bir kok adayinin hangi uyeleri aciklayabildigi."""
    zaman = alarmlar["timestamp"] >= aday["ilk_zaman"]

    if aday.get("tur") == "lokalite":
        dc, kabin = aday["servis"].split("/", 1)
        kabin_maske = (alarmlar["veri_merkezi"] == dc) & (
            alarmlar["kabin"] == kabin
        )
        kabin_servisleri = set(alarmlar[kabin_maske]["service"].unique())
        asagi = set(kabin_servisleri)
        for s in kabin_servisleri:
            asagi |= set(grafik.asagi_akis(s, max_atlama=azami_atlama).keys())
        return (kabin_maske | alarmlar["service"].isin(asagi)) & zaman

    asagi = grafik.asagi_akis(aday["servis"], max_atlama=azami_atlama)
    return alarmlar["service"].isin(asagi.keys()) & zaman


def _kokler_kopuk_mu(a, b, grafik, azami_atlama=AZAMI_ATLAMA):
    """Iki kok adayi arasinda nedensel yol var mi.

    Lokalite adaylari icin grafik mesafesi tanimsizdir; bu durumda kabin
    esitligine bakilir.
    """
    if a.get("tur") == "lokalite" or b.get("tur") == "lokalite":
        return a["servis"] != b["servis"]
    d = grafik.mesafe(a["servis"], b["servis"], max_atlama=azami_atlama + 1)
    return d is None or d > azami_atlama


def olaylari_cikar(sinyaller: pd.DataFrame, grafik, ayrisma_acik=True,
                   asgari=ASGARI_KUME) -> List[Kume]:
    """Uctan uca: kumele -> (istege bagli) ayristir -> kok neden ata."""
    ham = kumele(sinyaller, grafik)
    kumeler = []
    for parca in ham:
        if len(parca) < asgari:
            continue
        if ayrisma_acik:
            kumeler.extend(ayristir(parca, grafik, asgari=asgari))
        else:
            adaylar = _kok_adaylari(parca, grafik)
            en_iyi = adaylar[0] if adaylar else {}
            kumeler.append(Kume(
                alarmlar=parca,
                kok_servis=en_iyi.get("etiket", ""),
                kok_alarm_tipi=en_iyi.get("alarm_tipi", ""),
                kok_zamani=en_iyi.get("ilk_zaman"),
                aciklama_orani=en_iyi.get("aciklama_orani", 0.0),
                kok_imza=en_iyi.get("imza", 0.0),
                karsi_hipotez=adaylar[1] if len(adaylar) > 1 else {},
            ))

    kumeler = [k for k in kumeler if k.boyut >= asgari]
    return sorted(kumeler, key=lambda k: k.baslangic)
