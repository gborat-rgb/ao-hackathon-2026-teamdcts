"""Executive Streamlit yuzeyinin veri ve etkilesim sozlesmesi."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from src.pipeline import ayrisma_karsilastirmasi, calistir


APP = Path(__file__).resolve().parents[1] / "src" / "app.py"


def _sayi(deger):
    return f"{int(deger):,}".replace(",", ".")


def test_executive_dashboard_pipeline_verisini_eksiksiz_gosteriyor():
    beklenen = calistir().metrikler
    app = AppTest.from_file(str(APP), default_timeout=60).run(timeout=60)

    assert not app.exception
    assert [sekme.label for sekme in app.tabs] == [
        "Olaylar",
        "Erken Tespit",
        "X-Factor",
        "Gürültü Denetimi",
        "Zaman Çizelgesi",
    ]

    kpi = {metrik.label: metrik.value for metrik in app.metric[:8]}
    assert kpi == {
        "Ham alarm": _sayi(beklenen["toplam_alarm"]),
        "Aksiyonlanabilir olay": _sayi(beklenen["kart_sayisi"]),
        "Korele alarm": _sayi(beklenen["kartlara_giren_alarm"]),
        "Dışlanan / gürültü": _sayi(beklenen["acikca_dislanan_alarm"]),
        "İndirgeme": f"{beklenen['indirgeme_carpani']:.0f}×",
        "Kayıp alarm": _sayi(beklenen["kayip_alarm"]),
        "Çift atama": _sayi(beklenen["tekrar_atanan_alarm"]),
        "Çalışma süresi": kpi["Çalışma süresi"],
    }
    assert kpi["Çalışma süresi"].endswith(" sn")
    assert len(app.expander) == beklenen["kart_sayisi"]

    gurultu = next(
        tablo.value
        for tablo in app.dataframe
        if "eleme_gerekcesi" in tablo.value.columns
    )
    assert len(gurultu) == beklenen["acikca_dislanan_alarm"]
    assert gurultu["eleme_gerekcesi"].notna().all()
    assert gurultu["eleme_gerekcesi"].str.len().gt(0).all()


def test_x_factor_false_merge_kaniti_gercek_kosulardan_geliyor():
    x = ayrisma_karsilastirmasi()
    acik = calistir(ayrisma_acik=True)
    kapali_kartlar = {k.kart_id for k in calistir(ayrisma_acik=False).kartlar}
    app = AppTest.from_file(str(APP), default_timeout=60).run(timeout=60)
    assert not app.exception

    html = [m.value for m in app.markdown]
    assert any(f'fo-x-value">{x["ayrisma_kapali_kart"]}<' in h for h in html)
    assert any(f'fo-x-value">{x["ayrisma_acik_kart"]}<' in h for h in html)

    assert x["ayrisma_ile_ortaya_cikan"]
    for kok in x["ayrisma_ile_ortaya_cikan"]:
        kart = next(k for k in acik.kartlar if k.kok_neden == kok)
        panel = next(h for h in html if f"{kok} alarmlarının" in h)
        assert f"/{kart.alarm_sayisi} kadarı" in panel
        assert any(f"Ayrışma kapalı · {kid}<" in panel for kid in kapali_kartlar)
    assert any("Kopuk kökler" in h for h in html)


def test_aksiyon_durumu_arayuzden_kapatilabiliyor():
    app = AppTest.from_file(str(APP), default_timeout=60).run(timeout=60)
    assert not app.exception

    app.radio[0].set_value("kapandi").run(timeout=60)

    assert not app.exception
    assert app.session_state["aksiyon_durum"]["OLAY-01"] == "kapandi"
    assert app.session_state["aksiyon_gecmis"]["OLAY-01"]
