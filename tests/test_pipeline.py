"""Kritik mantik testleri.

Odak, cozumun dogru olmasi icin tutmasi GEREKEN ozellikler:
  - tum veri isleniyor (ornekleme yok)
  - kabul kriterleri saglaniyor
  - ayrisma testi cakisik bagimsiz olaylari ayiriyor
  - gurultu elemesi gerekce uretiyor
  - aksiyon durumu izlenebiliyor
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.cards import Aksiyon  # noqa: E402
from src.clustering import _kokler_kopuk_mu  # noqa: E402
from src.ingest import veriyi_hazirla  # noqa: E402
from src.pipeline import ayrisma_karsilastirmasi, calistir  # noqa: E402
from src.scoring import skorla  # noqa: E402


@pytest.fixture(scope="module")
def sonuc():
    return calistir()


@pytest.fixture(scope="module")
def veri():
    return veriyi_hazirla()


# --- zorunlu gereksinim 1: tum akis isleniyor ---------------------------------

def test_tum_alarmlar_isleniyor(sonuc):
    """Kismi veri ile calisan cozum eksik sayiliyor; ornekleme olmamali."""
    assert sonuc.metrikler["toplam_alarm"] == 3000
    assert len(sonuc.alarmlar) == 3000
    assert sonuc.alarmlar["alarm_id"].nunique() == 3000


def test_her_alarm_siniflandirilmis(sonuc):
    """Hicbir alarm sinifsiz kalmamali: ya sinyal ya gurultu."""
    assert sonuc.alarmlar["sinyal"].notna().all()
    gurultu = sonuc.alarmlar[~sonuc.alarmlar["sinyal"]]
    assert (gurultu["eleme_gerekcesi"].str.len() > 0).all(), \
        "gerekcesiz elenen alarm var"


# --- kabul kriterleri ---------------------------------------------------------

def test_en_fazla_onbes_kart(sonuc):
    assert 1 <= sonuc.metrikler["kart_sayisi"] <= 15


def test_kartlarda_zorunlu_alanlar(sonuc):
    """Her kart kok neden, servis listesi, alarm sayisi ve zaman araligi tasimali."""
    for k in sonuc.kartlar:
        assert k.kok_neden
        assert k.etkilenen_servisler
        assert k.alarm_sayisi > 0
        assert k.baslangic and k.bitis
        assert k.baslangic <= k.bitis
        assert k.kanit, "kanitsiz kart"
        assert k.gerekce
        assert k.guven in {"yuksek", "orta", "dusuk"}


def test_her_kartta_aksiyon_ve_sahip(sonuc):
    """Zorunlu gereksinim 4: aksiyon sahip ve durum bilgisi icermeli."""
    for k in sonuc.kartlar:
        assert k.aksiyon is not None
        assert k.aksiyon.sahip
        assert k.aksiyon.durum == "acik"


def test_calisma_suresi_makul(sonuc):
    assert sonuc.metrikler["calisma_suresi_sn"] < 10


# --- X-Factor: ayrisma testi --------------------------------------------------

def test_ayrisma_testi_olay_ayiriyor():
    """Ayrisma acikken en az bir ek kok ortaya cikmali."""
    x = ayrisma_karsilastirmasi()
    assert x["ayrisma_acik_kart"] > x["ayrisma_kapali_kart"]
    assert x["ayrisma_ile_ortaya_cikan"]


def test_session_service_payment_ile_birlesmiyor(sonuc):
    """Cakisik ama bagimsiz iki olay ayni karta konmamali.

    session-service OOM ile payment-provider-gw kesintisi 02:38-02:58
    arasinda es zamanli ve ikisi de mobile-bff'i etkiliyor. Ayri kalmalilar.
    """
    kokler = {k.kok_neden for k in sonuc.kartlar}
    assert "session-service" in kokler
    assert "payment-provider-gw" in kokler

    ss = next(k for k in sonuc.kartlar if k.kok_neden == "session-service")
    pp = next(k for k in sonuc.kartlar if k.kok_neden == "payment-provider-gw")
    assert ss.kart_id != pp.kart_id


def test_kopukluk_olcusu(veri):
    """Ayrimin dayanagi: iki kok arasinda nedensel yol yok."""
    _, _, grafik = veri
    a = {"tur": "servis", "servis": "payment-provider-gw"}
    b = {"tur": "servis", "servis": "session-service"}
    assert _kokler_kopuk_mu(a, b, grafik), \
        "payment-provider-gw ile session-service bagli gorunuyor"

    # Ayni zincirdeki iki servis kopuk OLMAMALI
    c = {"tur": "servis", "servis": "payment-service"}
    assert not _kokler_kopuk_mu(a, c, grafik)


# --- veri keşfinde doğrulanan olaylar ----------------------------------------

def test_bilinen_kokler_yakalaniyor(sonuc):
    """Veri keşfinde (docs/plan.md 2.3) doğrulanan beş olayın kökleri."""
    kokler = {k.kok_neden for k in sonuc.kartlar}
    beklenen = {
        "billing-db",            # disk dolmasi
        "payment-provider-gw",   # dis servis kesintisi
        "session-service",       # bellek tukenmesi
        "subscriber-db",         # baglanti havuzu
    }
    eksik = beklenen - kokler
    assert not eksik, "yakalanamayan kok: %s" % eksik

    # Kabin arizasi servis degil lokalite koku olarak cikmali
    assert any("rack-A" in k for k in kokler), "kabin seviyesi kok yakalanamadi"


def test_kabin_koku_host_kapsamina_dayaniyor(sonuc):
    """Kabin koku iddiasinin arkasinda olculmus host kapsami olmali."""
    kart = next(k for k in sonuc.kartlar if "rack-A" in k.kok_neden)
    assert any("host" in c and "%" in c for c in kart.kanit)


# --- gurultu elemesi ----------------------------------------------------------

def test_gurultu_orani_anlamli(sonuc):
    oran = sonuc.metrikler["gurultu_orani"]
    assert 0.35 < oran < 0.85, "gurultu orani beklenen araligin disinda: %s" % oran


def test_esik_yukseltince_gurultu_artiyor():
    dusuk = calistir(esik=0.25)
    yuksek = calistir(esik=0.50)
    assert yuksek.metrikler["gurultu"] > dusuk.metrikler["gurultu"]


def test_yayvan_tipler_agirlikli_eleniyor(sonuc):
    """cert_expiry / ntp_drift gibi zamana yayilan tipler cogunlukla gurultu."""
    a = sonuc.alarmlar
    for tip in ["cert_expiry", "ntp_drift", "log_rotate"]:
        g = a[a["alarm_type"] == tip]
        assert (~g["sinyal"]).mean() > 0.80, \
            "%s yeterince elenmemis: %.2f" % (tip, (~g["sinyal"]).mean())


def test_yogunlasan_tipler_sinyal_kaliyor(sonuc):
    """Tek pencerede toplanan nadir tipler sinyal olarak kalmali."""
    a = sonuc.alarmlar
    for tip in ["pkt_loss", "disk_full", "ext_unreach", "oom_risk"]:
        g = a[a["alarm_type"] == tip]
        assert g["sinyal"].mean() > 0.80, \
            "%s sinyal olarak tutulmamis: %.2f" % (tip, g["sinyal"].mean())


# --- aksiyon izlenebilirligi --------------------------------------------------

def test_aksiyon_durum_gecisi():
    a = Aksiyon(aksiyon_id="AKS-01", kart_id="OLAY-01", sahip="Ag ekibi",
                aciklama="test")
    assert a.durum == "acik"
    a.durum_degistir("devam_ediyor", "mudahale basladi")
    a.durum_degistir("kapandi", "cozuldu")
    assert a.durum == "kapandi"
    assert len(a.gecmis) == 2
    assert a.gecmis[0]["onceki"] == "acik"
    assert a.gecmis[-1]["yeni"] == "kapandi"


def test_gecersiz_durum_reddediliyor():
    a = Aksiyon(aksiyon_id="AKS-01", kart_id="OLAY-01", sahip="x", aciklama="y")
    with pytest.raises(ValueError):
        a.durum_degistir("bilinmeyen")


# --- bagimlilik grafigi -------------------------------------------------------

def test_etki_yonu_dogru(veri):
    """hedef bozulursa kaynak etkilenir: billing-db -> billing-service."""
    _, _, grafik = veri
    asagi = grafik.asagi_akis("billing-db")
    assert "billing-service" in asagi
    assert "invoice-batch" in asagi
    # Ters yon olmamali
    assert "billing-db" not in grafik.asagi_akis("billing-service")


def test_skorlama_determinist(veri):
    alarmlar, _, _ = veri
    a = skorla(alarmlar)
    b = skorla(alarmlar)
    assert a["sinyal_skoru"].equals(b["sinyal_skoru"])
