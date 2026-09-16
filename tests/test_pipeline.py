"""Kritik mantik testleri.

Odak, cozumun dogru olmasi icin tutmasi GEREKEN ozellikler:
  - tum veri isleniyor (ornekleme yok)
  - kabul kriterleri saglaniyor
  - ayrisma testi cakisik bagimsiz olaylari ayiriyor
  - gurultu elemesi gerekce uretiyor
  - aksiyon durumu izlenebiliyor
"""

import json
import shutil
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.cards import Aksiyon, _guven_seviyesi  # noqa: E402
from src.clustering import _kokler_kopuk_mu, olaylari_cikar  # noqa: E402
from src.ingest import (  # noqa: E402
    VERI_DIZINI,
    BagimlilikGrafigi,
    VeriDogrulamaHatasi,
    veriyi_hazirla,
)
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


# --- final kalite kapisi: veri muhasebesi ve determinizm ---------------------

def test_alarm_muhasebesinde_kayip_yok(sonuc):
    m = sonuc.metrikler
    assert m["toplam_alarm"] == (
        m["kartlara_giren_alarm"] + m["acikca_dislanan_alarm"]
    )
    assert m["kayip_alarm"] == 0
    assert m["tekrar_atanan_alarm"] == 0
    assert sonuc.alarmlar["son_sinif"].notna().all()


def test_korelasyon_disi_sinyaller_acikca_gerekceli(sonuc):
    disarida = sonuc.alarmlar[
        sonuc.alarmlar["son_sinif"] == "korelasyon_disi"
    ]
    assert len(disarida) == sonuc.metrikler["korelasyon_disi_sinyal"]
    assert len(disarida) > 0  # regression: once 118 alarm sessizce kayboluyordu
    assert (disarida["eleme_gerekcesi"].str.len() > 0).all()


def test_kart_atamalari_benzersiz(sonuc):
    atanan = sonuc.alarmlar[sonuc.alarmlar["kart_id"] != ""]
    assert len(atanan) == atanan["alarm_id"].nunique()
    assert len(atanan) == sonuc.metrikler["kartlara_giren_alarm"]


def test_pipeline_semantik_ciktisi_determinist():
    a = calistir()
    b = calistir()
    a_metrik = dict(a.metrikler)
    b_metrik = dict(b.metrikler)
    a_metrik.pop("calisma_suresi_sn")
    b_metrik.pop("calisma_suresi_sn")
    assert a_metrik == b_metrik
    assert [k.sozluk() for k in a.kartlar] == [k.sozluk() for k in b.kartlar]


def test_guven_secilen_kokun_imzasini_kullaniyor(veri, sonuc):
    alarmlar, _, grafik = veri
    puanli = skorla(alarmlar)
    kumeler = olaylari_cikar(puanli[puanli["sinyal"]], grafik)
    assert len(kumeler) == len(sonuc.kartlar)
    for kume, kart in zip(kumeler, sonuc.kartlar):
        beklenen = _guven_seviyesi(
            kume.aciklama_orani, kume.boyut, kume.kok_imza
        )[1]
        assert kart.guven_skoru == beklenen


def test_mesafe_onbellegi_arama_derinligini_ayiriyor():
    bagimliliklar = pd.DataFrame([
        {"kaynak_servis": "b", "hedef_servis": "a", "kritiklik": "orta"},
        {"kaynak_servis": "c", "hedef_servis": "b", "kritiklik": "orta"},
        {"kaynak_servis": "d", "hedef_servis": "c", "kritiklik": "orta"},
    ])
    grafik = BagimlilikGrafigi(bagimliliklar)
    assert grafik.mesafe("a", "d", max_atlama=2) is None
    assert grafik.mesafe("a", "d", max_atlama=4) == 3


def test_csv_ve_json_ayni_alarm_kumesini_iceriyor():
    csv = pd.read_csv(VERI_DIZINI / "alarms.csv")
    with (VERI_DIZINI / "alarms.json").open(encoding="utf-8") as f:
        json_ids = {x["alarm_id"] for x in json.load(f)}
    assert set(csv["alarm_id"]) == json_ids


# --- negatif testler ---------------------------------------------------------

def _veri_kopyasi(tmp_path):
    dizin = tmp_path / "veri"
    dizin.mkdir()
    for ad in ["alarms.csv", "host_inventory.csv", "service_dependencies.csv"]:
        shutil.copy2(VERI_DIZINI / ad, dizin / ad)
    return dizin


def test_eksik_alarm_dosyasi_acik_hata_veriyor(tmp_path):
    dizin = _veri_kopyasi(tmp_path)
    (dizin / "alarms.csv").unlink()
    with pytest.raises(VeriDogrulamaHatasi, match="bulunamadi"):
        veriyi_hazirla(dizin)


def test_bozuk_csv_acik_hata_veriyor(tmp_path):
    dizin = _veri_kopyasi(tmp_path)
    (dizin / "alarms.csv").write_text(
        'alarm_id,timestamp\n"kapanmayan', encoding="utf-8"
    )
    with pytest.raises(VeriDogrulamaHatasi):
        veriyi_hazirla(dizin)


@pytest.mark.parametrize("alan,deger", [
    ("timestamp", "gecersiz-zaman"),
    ("severity", 9),
    ("severity", None),
    ("host", "bilinmeyen-host"),
])
def test_gecersiz_alarm_alani_reddediliyor(tmp_path, alan, deger):
    dizin = _veri_kopyasi(tmp_path)
    alarms = pd.read_csv(dizin / "alarms.csv")
    alarms.loc[0, alan] = deger
    alarms.to_csv(dizin / "alarms.csv", index=False)
    with pytest.raises(VeriDogrulamaHatasi):
        veriyi_hazirla(dizin)


def test_tekrar_eden_alarm_id_reddediliyor(tmp_path):
    dizin = _veri_kopyasi(tmp_path)
    alarms = pd.read_csv(dizin / "alarms.csv")
    alarms.loc[1, "alarm_id"] = alarms.loc[0, "alarm_id"]
    alarms.to_csv(dizin / "alarms.csv", index=False)
    with pytest.raises(VeriDogrulamaHatasi, match="tekrar eden alarm_id"):
        veriyi_hazirla(dizin)


def test_eksik_zorunlu_sutun_reddediliyor(tmp_path):
    dizin = _veri_kopyasi(tmp_path)
    alarms = pd.read_csv(dizin / "alarms.csv").drop(columns="service")
    alarms.to_csv(dizin / "alarms.csv", index=False)
    with pytest.raises(VeriDogrulamaHatasi, match="zorunlu sutunlari eksik"):
        veriyi_hazirla(dizin)


def test_bozuk_bagimlilik_semasi_reddediliyor(tmp_path):
    dizin = _veri_kopyasi(tmp_path)
    deps = pd.read_csv(dizin / "service_dependencies.csv").drop(
        columns="hedef_servis"
    )
    deps.to_csv(dizin / "service_dependencies.csv", index=False)
    with pytest.raises(VeriDogrulamaHatasi, match="zorunlu sutunlari eksik"):
        veriyi_hazirla(dizin)


def test_tek_alarm_kaybolmadan_acikca_dislanir(tmp_path):
    dizin = _veri_kopyasi(tmp_path)
    alarms = pd.read_csv(dizin / "alarms.csv").head(1)
    alarms.to_csv(dizin / "alarms.csv", index=False)
    sonuc = calistir(dizin=dizin)
    assert sonuc.metrikler["kart_sayisi"] == 0
    assert sonuc.metrikler["acikca_dislanan_alarm"] == 1
    assert sonuc.metrikler["kayip_alarm"] == 0


def test_bilinmeyen_alarm_tipi_guvenli_islenir(tmp_path):
    dizin = _veri_kopyasi(tmp_path)
    alarms = pd.read_csv(dizin / "alarms.csv").head(1)
    alarms.loc[alarms.index[0], "alarm_type"] = "yeni_alarm_tipi"
    alarms.to_csv(dizin / "alarms.csv", index=False)
    sonuc = calistir(dizin=dizin)
    assert sonuc.metrikler["toplam_alarm"] == 1
    assert sonuc.metrikler["kayip_alarm"] == 0


def test_bagimlilik_dongusu_sonsuz_dongu_yaratmaz(tmp_path):
    dizin = _veri_kopyasi(tmp_path)
    deps = pd.read_csv(dizin / "service_dependencies.csv")
    ilk = deps.iloc[0].copy()
    ilk["kaynak_servis"], ilk["hedef_servis"] = (
        ilk["hedef_servis"], ilk["kaynak_servis"]
    )
    deps = pd.concat([deps, ilk.to_frame().T], ignore_index=True)
    deps.to_csv(dizin / "service_dependencies.csv", index=False)
    _, _, grafik = veriyi_hazirla(dizin)
    assert len(grafik.asagi_akis(str(ilk["kaynak_servis"]))) <= len(grafik.servisler)


def test_satir_sirasi_sonucu_degistirmiyor(tmp_path):
    dizin = _veri_kopyasi(tmp_path)
    alarms = pd.read_csv(dizin / "alarms.csv")
    alarms.sample(frac=1.0, random_state=2026).to_csv(
        dizin / "alarms.csv", index=False
    )
    normal = calistir()
    karisik = calistir(dizin=dizin)
    assert [k.sozluk() for k in normal.kartlar] == [
        k.sozluk() for k in karisik.kartlar
    ]
