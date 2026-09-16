"""Erken tespit (replay) ve saha gorevi ozelliklerinin testleri.

Mevcut `test_pipeline.py` boru hattinin degismezlerini sabitliyor; bu dosya
yalnizca iki yeni yetenege odaklanir ve ayni yaklasimi izler: ciktinin
fotografini cekmek yerine tutmasi gereken ozellikleri sinar.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.cards import SAHA_ASGARI_HOST_PAYI, _saha_gorevi  # noqa: E402
from src.ingest import veriyi_hazirla  # noqa: E402
from src.pipeline import calistir  # noqa: E402
from src.replay import erken_tespit  # noqa: E402


@pytest.fixture(scope="module")
def sonuc():
    return calistir()


@pytest.fixture(scope="module")
def tespit():
    # Kaba adim; testin amaci sayilari degil davranisi sabitlemek.
    return erken_tespit(adim_sn=300)


# --- O1: erken tespit ---------------------------------------------------------

def test_toplu_kosudaki_her_kok_replayde_de_yakalaniyor(tespit, sonuc):
    """Canli akis, toplu kosunun buldugu hicbir olayi kacirmamali."""
    toplu_kokler = {k.kok_neden for k in sonuc.kartlar}
    replay_kokler = {k.kok_neden for k in tespit.kayitlar}
    eksik = toplu_kokler - replay_kokler
    assert not eksik, "replay su kokleri kacirdi: %s" % eksik


def test_gecikme_pozitif_ve_pencere_icinde(tespit):
    """Kart, olay baslamadan once olusamaz; pencereden de tasamaz."""
    assert tespit.kayitlar
    for k in tespit.kayitlar:
        assert k.gecikme_sn > 0, "%s icin gecikme pozitif degil" % k.kok_neden
        assert k.kart_olusma_ani > k.kok_ilk_alarm
        # Iki saatlik pencerede hicbir tespit bu kadar gecikemez.
        assert k.gecikme_sn < 2 * 3600


def test_gecikme_dilim_adimindan_kucuk_olamaz_cok_buyuk_de(tespit):
    """Olcum cozunurlugu dilim adimi kadardir; gecikme buna oranli olmali."""
    for k in tespit.kayitlar:
        assert k.gecikme_sn <= tespit.adim_sn * 12, (
            "%s gecikmesi cozunurluge gore asiri: %s"
            % (k.kok_neden, k.gecikme_metni)
        )


def test_ara_hipotezler_isaretleniyor(tespit, sonuc):
    """Toplu kosuda olmayan kokler gizlenmemeli, etiketlenmeli."""
    toplu_kokler = {k.kok_neden for k in sonuc.kartlar}
    for k in tespit.kayitlar:
        assert k.toplu_kosuda_var == (k.kok_neden in toplu_kokler)


def test_ince_adim_gecikmeyi_buyutmez():
    """Daha ince dilim, tespit anini erkene ceker ya da ayni birakir."""
    kaba = erken_tespit(adim_sn=300)
    ince = erken_tespit(adim_sn=120)
    kaba_h = {k.kok_neden: k.gecikme_sn for k in kaba.kayitlar}
    for k in ince.kayitlar:
        if k.kok_neden in kaba_h and k.toplu_kosuda_var:
            assert k.gecikme_sn <= kaba_h[k.kok_neden] + 1e-6, (
                "%s: ince adim gecikmeyi buyuttu" % k.kok_neden
            )


def test_ozet_serilestirilebilir(tespit):
    ozet = tespit.ozet()
    assert ozet["dilim_sayisi"] > 0
    assert ozet["tespit_edilen_kok"] == len(tespit.kayitlar)
    for kayit in ozet["kayitlar"]:
        assert isinstance(kayit["gecikme_sn"], float)
        assert isinstance(kayit["kok_neden"], str)


def test_gecersiz_adim_reddediliyor():
    for kotu in (0, -1, -300):
        with pytest.raises(ValueError):
            erken_tespit(adim_sn=kotu)


def test_onceden_yuklenmis_veri_ayni_sonucu_veriyor():
    """`veri` parametresi davranisi degistirmemeli, sadece yuklemeyi atlamali."""
    veri = veriyi_hazirla()
    diskten = calistir()
    onbellekten = calistir(veri=veri)
    assert [k.kok_neden for k in diskten.kartlar] == \
           [k.kok_neden for k in onbellekten.kartlar]
    assert diskten.metrikler["kartlara_giren_alarm"] == \
           onbellekten.metrikler["kartlara_giren_alarm"]


def test_bos_veri_reddediliyor():
    veri = veriyi_hazirla()
    alarmlar, envanter, grafik = veri
    with pytest.raises(ValueError):
        calistir(veri=(alarmlar.iloc[0:0], envanter, grafik))


# --- M1: saha gorevi ----------------------------------------------------------

def test_her_kartta_saha_gorevi_alani_var(sonuc):
    for k in sonuc.kartlar:
        assert isinstance(k.saha_gorevi, list)


def test_kabin_olayinda_dogru_konum_veriliyor(sonuc):
    """Kabin ag arizasinda saha gorevi o kabini isaret etmeli."""
    kart = next(k for k in sonuc.kartlar if "rack-A" in k.kok_neden)
    assert kart.saha_gorevi, "kabin olayinda saha gorevi uretilmemis"
    konumlar = [g["konum"] for g in kart.saha_gorevi]
    assert any("rack-A" in x for x in konumlar), konumlar


def test_saha_gorevi_alanlari_tutarli(sonuc):
    for k in sonuc.kartlar:
        for g in k.saha_gorevi:
            assert g["host_sayisi"] > 0
            assert 0 <= g["kritik_host"] <= g["host_sayisi"]
            assert 1 <= g["azami_siddet"] <= 5
            assert len(g["hostlar"]) <= 8
            assert g["host_kirpildi"] == (g["host_sayisi"] > 8)
            assert " / " in g["konum"]


def test_saha_gorevi_host_sayisina_gore_sirali(sonuc):
    for k in sonuc.kartlar:
        sayilar = [g["host_sayisi"] for g in k.saha_gorevi]
        assert sayilar == sorted(sayilar, reverse=True)


def test_dagilmis_olayda_tek_kabin_one_cikmaz(sonuc):
    """Konum listesi azami uc kabinle sinirli kalmali."""
    for k in sonuc.kartlar:
        assert len(k.saha_gorevi) <= 3


def test_kucuk_payli_konum_eleniyor():
    """Tek host'un tasmasi kabin gorevi uretmemeli."""
    hostlar = ["h%02d" % i for i in range(20)]
    df = pd.DataFrame({
        "host": hostlar,
        "veri_merkezi": ["dc1"] * 19 + ["dc2"],
        "kabin": ["rack-A"] * 19 + ["rack-C"],
        "severity": [4] * 20,
        "is_kritikligi": ["kritik"] * 20,
    })

    class _Kume:
        alarmlar = df

    gorevler = _saha_gorevi(_Kume())
    konumlar = [g["konum"] for g in gorevler]
    assert "dc1 / rack-A" in konumlar
    assert "dc2 / rack-C" not in konumlar, (
        "1/20 paylik konum elenmedi (esik %.2f)" % SAHA_ASGARI_HOST_PAYI
    )


def test_bos_kume_saha_gorevi_uretmez():
    class _Bos:
        alarmlar = pd.DataFrame(
            columns=["host", "veri_merkezi", "kabin", "severity", "is_kritikligi"]
        )

    assert _saha_gorevi(_Bos()) == []


def test_eksik_sutunla_cokmez():
    """Kolon yoksa saha gorevi sessizce bos donmeli, patlamamali."""
    class _Eksik:
        alarmlar = pd.DataFrame({"host": ["h1"], "severity": [4]})

    assert _saha_gorevi(_Eksik()) == []


def test_saha_gorevi_json_ciktisinda(sonuc):
    d = sonuc.kartlar[0].sozluk()
    assert "saha_gorevi" in d
    assert isinstance(d["saha_gorevi"], list)
