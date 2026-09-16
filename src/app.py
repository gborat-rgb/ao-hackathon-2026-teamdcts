"""Streamlit arayuzu — executive ve nobetci muhendis gorunumu.

    streamlit run src/app.py

Ustte yonetici ozeti (ham alarm -> dislanan -> korele -> olay -> indirgeme)
ve sekiz KPI; hepsi pipeline metriklerinden uretilir. Bes sekme:
  Olaylar         — oncelikli olay listesi, kanit/gerekce, aksiyon durumu
  Erken Tespit    — artan zaman dilimlerinde ilk kart olusma ani
  X-Factor        — ayrisma testi acik/kapali karsilastirmasi ve olculen
                    false merge kaniti
  Gurultu Denetimi— elenen her alarmin neden elendigi
  Zaman Cizelgesi — alarm yogunlugu ve olay pencereleri
"""

import sys
from html import escape
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# `streamlit run src/app.py` ile calistirildiginda proje koku sys.path'te
# olmadigi icin paket importu basarisiz oluyor; ekliyoruz.
KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src.clustering import AZAMI_ATLAMA  # noqa: E402
from src.ingest import veriyi_hazirla  # noqa: E402
from src.pipeline import ayrisma_karsilastirmasi, calistir  # noqa: E402
from src.replay import VARSAYILAN_ADIM_SN, erken_tespit  # noqa: E402
from src.scoring import VARSAYILAN_ESIK  # noqa: E402

st.set_page_config(
    page_title="Fail-i Over | Incident Command",
    page_icon="◉",
    layout="wide",
    initial_sidebar_state="expanded",
)

DURUM_RENK = {"acik": "●", "devam_ediyor": "◐", "kapandi": "✓"}
DURUM_ETIKET = {
    "acik": "AÇIK",
    "devam_ediyor": "MÜDAHALEDE",
    "kapandi": "KAPANDI",
}
GUVEN_RENK = {"yuksek": "●", "orta": "◐", "dusuk": "○"}
GUVEN_ETIKET = {"yuksek": "yüksek", "orta": "orta", "dusuk": "düşük"}


def _sayfa_stili():
    """Kurumsal, yogun ve projektorde okunabilir tek bir gorsel sistem."""
    st.markdown(
        """
        <style>
        :root {
            --fo-ink: #e8eef7;
            --fo-muted: #8fa3ba;
            --fo-line: rgba(143, 163, 186, .18);
            --fo-panel: rgba(14, 29, 47, .76);
            --fo-accent: #2dd4bf;
            --fo-warn: #fbbf24;
            --fo-danger: #fb7185;
        }
        [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at 78% -18%, rgba(45,212,191,.10), transparent 34rem),
                #07111f;
        }
        [data-testid="stHeader"] { background: transparent; }
        [data-testid="stSidebar"] {
            background: #091522;
            border-right: 1px solid var(--fo-line);
        }
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
            color: var(--fo-muted);
        }
        .block-container { max-width: 1480px; padding-top: 1.6rem; }
        h1, h2, h3, h4 { letter-spacing: -.025em; }
        .fo-kicker {
            color: var(--fo-accent); font-size: .72rem; font-weight: 750;
            letter-spacing: .18em; text-transform: uppercase; margin-bottom: .35rem;
        }
        .fo-title {
            color: var(--fo-ink); font-size: clamp(2rem, 3vw, 3.35rem);
            font-weight: 760; letter-spacing: -.055em; line-height: .98;
            margin: 0;
        }
        .fo-subtitle {
            color: var(--fo-muted); font-size: .98rem; margin-top: .75rem;
            max-width: 820px;
        }
        .fo-health {
            color: #a7f3d0; border: 1px solid rgba(45,212,191,.3);
            border-radius: 999px; display: inline-block; font-size: .72rem;
            font-weight: 700; letter-spacing: .08em; padding: .35rem .65rem;
            text-transform: uppercase;
        }
        .fo-health.bad { border-color: rgba(251,113,133,.45); color: var(--fo-danger); }
        .fo-flow {
            align-items: stretch; background: rgba(14,29,47,.52);
            border-bottom: 1px solid var(--fo-line); border-top: 1px solid var(--fo-line);
            display: grid; gap: 0; grid-template-columns: repeat(5, 1fr);
            margin: 1.4rem 0 1.1rem; padding: .9rem 0;
        }
        .fo-flow.compact { grid-template-columns: repeat(3, 1fr); margin: .9rem 0; }
        .fo-flow.compact .fo-flow-step { border-bottom: 0; padding: 0 .7rem; }
        .fo-flow-step { padding: 0 1rem; position: relative; }
        .fo-flow-step + .fo-flow-step { border-left: 1px solid var(--fo-line); }
        .fo-flow-value { color: var(--fo-ink); font-size: 1.25rem; font-weight: 730; }
        .fo-flow-label {
            color: var(--fo-muted); font-size: .66rem; letter-spacing: .09em;
            margin-top: .15rem; text-transform: uppercase;
        }
        [data-testid="stMetric"] {
            border-left: 2px solid rgba(45,212,191,.48); padding: .15rem 0 .2rem .8rem;
        }
        [data-testid="stMetricLabel"] { color: var(--fo-muted); }
        [data-testid="stMetricValue"] { letter-spacing: -.04em; }
        [data-testid="stExpander"] {
            background: rgba(14,29,47,.55); border: 1px solid var(--fo-line);
            border-radius: .45rem;
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--fo-panel); border-color: var(--fo-line) !important;
            border-radius: .55rem;
        }
        .fo-incident-id {
            color: var(--fo-accent); font-size: .72rem; font-weight: 800;
            letter-spacing: .13em; text-transform: uppercase;
        }
        .fo-root { color: var(--fo-ink); font-size: 1.14rem; font-weight: 720; }
        .fo-meta { color: var(--fo-muted); font-size: .78rem; margin-top: .25rem; }
        .fo-action {
            border-top: 1px solid var(--fo-line); color: #c8d5e5;
            font-size: .84rem; margin-top: .35rem; padding-top: .6rem;
        }
        .fo-state {
            color: #a7f3d0; font-size: .68rem; font-weight: 800;
            letter-spacing: .08em; text-transform: uppercase;
        }
        .fo-x-card {
            background: rgba(14,29,47,.68); border-top: 2px solid var(--fo-line);
            margin-bottom: .8rem; min-height: 145px; padding: 1rem 1.1rem;
        }
        .fo-x-card.active { border-top-color: var(--fo-accent); }
        .fo-x-label {
            color: var(--fo-muted); font-size: .68rem; font-weight: 760;
            letter-spacing: .12em; text-transform: uppercase;
        }
        .fo-x-value { color: var(--fo-ink); font-size: 2.7rem; font-weight: 750; line-height: 1.1; }
        .fo-x-value.sm { font-size: 1.35rem; margin-top: .35rem; }
        .fo-x-note { color: var(--fo-muted); font-size: .82rem; margin-top: .55rem; }
        .stTabs [data-baseweb="tab-list"] {
            border-bottom: 1px solid var(--fo-line); gap: 1.1rem;
        }
        .stTabs [data-baseweb="tab"] { padding-left: 0; padding-right: 0; }
        div[data-testid="stDataFrame"] { border: 1px solid var(--fo-line); }
        @media (max-width: 900px) {
            .fo-flow { grid-template-columns: 1fr 1fr; }
            .fo-flow-step { border-bottom: 1px solid var(--fo-line); padding: .7rem; }
            .fo-title { font-size: 2rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _sayi(deger):
    return f"{int(deger):,}".replace(",", ".")


def _yonetici_ozeti(metrikler, kompakt=False):
    """Ilk bakista karar akisini ve veri muhasebesini anlatir."""
    baslik, durum = st.columns([5, 1])
    with baslik:
        st.markdown('<div class="fo-kicker">Fail-i Over · Incident Command</div>',
                    unsafe_allow_html=True)
        st.markdown('<div class="fo-title">Alarm Fırtınası Kontrol Merkezi</div>',
                    unsafe_allow_html=True)
        st.markdown(
            '<div class="fo-subtitle">İki saatlik alarm akışını, kanıtı ve '
            'sahibi olan müdahale kararlarına dönüştüren yönetici görünümü.</div>',
            unsafe_allow_html=True,
        )
    with durum:
        if metrikler["kayip_alarm"] == 0 and metrikler["tekrar_atanan_alarm"] == 0:
            rozet = '<div class="fo-health">● Veri bütünlüğü sağlam</div>'
        else:
            rozet = '<div class="fo-health bad">▲ Veri bütünlüğü ihlali</div>'
        st.markdown(rozet, unsafe_allow_html=True)

    if kompakt:
        # Telefonda st.columns alt alta yigilir; tek satirlik HTML seridi
        # uc sayiyi ekranin ustunde tutar.
        adimlar = "".join(
            f'<div class="fo-flow-step"><div class="fo-flow-value">{deger}</div>'
            f'<div class="fo-flow-label">{etiket}</div></div>'
            for etiket, deger in (
                ("Ham alarm", _sayi(metrikler["toplam_alarm"])),
                ("Olay", _sayi(metrikler["kart_sayisi"])),
                ("Kayıp", _sayi(metrikler["kayip_alarm"])),
            )
        )
        st.markdown(f'<div class="fo-flow compact">{adimlar}</div>',
                    unsafe_allow_html=True)
        return

    st.markdown(
        """
        <div class="fo-flow">
          <div class="fo-flow-step"><div class="fo-flow-value">{toplam}</div><div class="fo-flow-label">Ham alarm</div></div>
          <div class="fo-flow-step"><div class="fo-flow-value">−{dislanan}</div><div class="fo-flow-label">Açıkça dışlanan</div></div>
          <div class="fo-flow-step"><div class="fo-flow-value">{korele}</div><div class="fo-flow-label">Korele alarm</div></div>
          <div class="fo-flow-step"><div class="fo-flow-value">{olay}</div><div class="fo-flow-label">Aksiyonlanabilir olay</div></div>
          <div class="fo-flow-step"><div class="fo-flow-value">{indirgeme}×</div><div class="fo-flow-label">Karar indirgemesi</div></div>
        </div>
        """.format(
            toplam=_sayi(metrikler["toplam_alarm"]),
            dislanan=_sayi(metrikler["acikca_dislanan_alarm"]),
            korele=_sayi(metrikler["kartlara_giren_alarm"]),
            olay=_sayi(metrikler["kart_sayisi"]),
            indirgeme=f"{metrikler['indirgeme_carpani']:.0f}",
        ),
        unsafe_allow_html=True,
    )

    ust = st.columns(4)
    ust[0].metric("Ham alarm", _sayi(metrikler["toplam_alarm"]))
    ust[1].metric("Aksiyonlanabilir olay", _sayi(metrikler["kart_sayisi"]))
    ust[2].metric("Korele alarm", _sayi(metrikler["kartlara_giren_alarm"]))
    ust[3].metric("Dışlanan / gürültü", _sayi(metrikler["acikca_dislanan_alarm"]))

    alt = st.columns(4)
    alt[0].metric("İndirgeme", f"{metrikler['indirgeme_carpani']:.0f}×")
    alt[1].metric("Kayıp alarm", _sayi(metrikler["kayip_alarm"]))
    alt[2].metric("Çift atama", _sayi(metrikler["tekrar_atanan_alarm"]))
    alt[3].metric("Çalışma süresi", f"{metrikler['calisma_suresi_sn']:.2f} sn")


@st.cache_data(show_spinner=False)
def _calistir(esik, ayrisma_acik):
    s = calistir(esik=esik, ayrisma_acik=ayrisma_acik)
    return s.kartlar, s.alarmlar, s.metrikler


@st.cache_data(show_spinner=False)
def _x_factor(esik):
    return ayrisma_karsilastirmasi(esik=esik)


@st.cache_resource(show_spinner=False)
def _grafik():
    return veriyi_hazirla()[2]


@st.cache_data(show_spinner=False)
def _erken_tespit(adim_sn, ayrisma_acik):
    # Replay onlarca kosu yapar (~15 sn); onbellek olmadan her etkilesimde
    # tekrarlanir ve arayuz kullanilamaz hale gelir.
    return erken_tespit(adim_sn=adim_sn, ayrisma_acik=ayrisma_acik).ozet()


def main():
    _sayfa_stili()

    with st.sidebar:
        st.markdown("### Demo kontrolleri")
        st.caption("Pipeline davranışını canlı ve geri alınabilir biçimde sınayın.")
        esik = st.slider(
            "Sinyal eşiği", 0.10, 0.70, VARSAYILAN_ESIK, 0.05,
            help="Düşük eşik daha çok alarmı sinyal sayar; gürültü artar.",
        )
        ayrisma = st.checkbox(
            "Grafik ayrışma testi", value=True,
            help="Kapatılırsa eşzamanlı bağımsız olaylar tek karta birleşebilir.",
        )
        mobil = st.checkbox(
            "Mobil / saha görünümü", value=False,
            help="Telefonda okunacak sade liste: kök neden, konum ve aksiyon.",
        )
        st.divider()
        st.markdown("**Aktif analiz**")
        st.caption("2 saat · 27 servis · 56 host · çevrimdışı ve deterministik")
        st.caption(
            "Ayrışma testi, açıklanamayan artığın kendi kökü varsa ve bu kök "
            "birincil kökle grafikte bağlı değilse kümeyi böler."
        )

    kartlar, alarmlar, metrikler = _calistir(esik, ayrisma)
    _yonetici_ozeti(metrikler, kompakt=mobil)

    if mobil:
        _mobil_gorunum(kartlar)
        return

    sekmeler = st.tabs(
        ["Olaylar", "Erken Tespit", "X-Factor",
         "Gürültü Denetimi", "Zaman Çizelgesi"]
    )

    with sekmeler[0]:
        _kartlar_sekmesi(kartlar)
    with sekmeler[1]:
        _erken_tespit_sekmesi(ayrisma)
    with sekmeler[2]:
        _x_factor_sekmesi(esik)
    with sekmeler[3]:
        _gurultu_sekmesi(alarmlar)
    with sekmeler[4]:
        _zaman_sekmesi(alarmlar, kartlar)


def _kartlar_sekmesi(kartlar):
    if "aksiyon_durum" not in st.session_state:
        st.session_state.aksiyon_durum = {}
    if "aksiyon_gecmis" not in st.session_state:
        st.session_state.aksiyon_gecmis = {}

    st.subheader("Aksiyonlanabilir olaylar")
    st.caption(
        "Önceliklendirilmiş olay listesi. Her satır kökü, etkiyi, güveni ve "
        "ilk müdahaleyi gösterir; ayrıntı bölümü karar kanıtını açar."
    )

    for sira, k in enumerate(kartlar):
        durum = st.session_state.aksiyon_durum.get(k.kart_id, "acik")
        with st.container(border=True):
            kok, risk, kapsam, sahip = st.columns([2.5, 1.1, 1.35, 1.55])
            servis_ozeti = ", ".join(k.etkilenen_servisler[:3])
            if len(k.etkilenen_servisler) > 3:
                servis_ozeti += f" +{len(k.etkilenen_servisler) - 3}"

            with kok:
                ayrisma = " · GRAPH-SPLIT" if k.ayrisma_ile_bolundu else ""
                st.markdown(
                    f'<div class="fo-incident-id">{escape(k.kart_id)}{ayrisma}</div>'
                    f'<div class="fo-root">{escape(k.kok_neden)}</div>'
                    f'<div class="fo-meta">{escape(k.kok_alarm_tipi)} · '
                    f'{escape(k.baslangic[11:16])}–{escape(k.bitis[11:16])}<br>'
                    f'{escape(servis_ozeti)}</div>',
                    unsafe_allow_html=True,
                )
            with risk:
                st.markdown("**Risk / güven**")
                st.markdown(
                    f"S{k.azami_siddet} · {GUVEN_RENK[k.guven]} "
                    f"**%{100 * k.guven_skoru:.0f}**"
                )
                st.caption(GUVEN_ETIKET[k.guven].upper())
            with kapsam:
                st.markdown("**Etki kapsamı**")
                st.markdown(
                    f"**{_sayi(k.alarm_sayisi)}** alarm  \n"
                    f"**{k.etkilenen_host_sayisi}** host · "
                    f"**{len(k.etkilenen_servisler)}** servis"
                )
            with sahip:
                st.markdown(
                    f'<div class="fo-state">{DURUM_RENK[durum]} '
                    f'{DURUM_ETIKET[durum]}</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(f"**{k.aksiyon.sahip}**")
                st.caption(k.aksiyon.aksiyon_id)

            st.markdown(
                f'<div class="fo-action"><strong>İlk aksiyon</strong> · '
                f'{escape(k.aksiyon.aciklama)}</div>',
                unsafe_allow_html=True,
            )

            with st.expander(
                "Kanıt, gerekçe ve müdahale ayrıntıları",
                expanded=(sira == 0),
            ):
                analiz, operasyon = st.columns([3, 2])

                with analiz:
                    st.markdown("#### Kök neden kararı")
                    st.markdown(
                        f"**{k.kok_neden}** · `{k.kok_alarm_tipi}` · "
                        f"güven **{GUVEN_ETIKET[k.guven]} ({k.guven_skoru})**"
                    )
                    st.markdown("**Kanıt — veriden ölçüldü**")
                    for c in k.kanit:
                        st.markdown(f"- {c}")

                    st.markdown("**Gerekçe — çıkarım**")
                    st.info(k.gerekce)

                    st.markdown("**Karşı hipotez**")
                    st.warning(k.karsi_hipotez)

                    if k.sinirlar:
                        st.markdown("**Sınırlar**")
                        for x in k.sinirlar:
                            st.markdown(f"- {x}")

                with operasyon:
                    st.markdown("#### Olay zaman çizgisi")
                    st.markdown(
                        f"`{k.baslangic[11:]}` **ilk sinyal**  \n"
                        f"`{k.bitis[11:]}` **son gözlem**  \n"
                        f"**{k.alarm_sayisi}** alarm · "
                        f"**S{k.azami_siddet}** azami şiddet"
                    )

                    st.markdown("**Etkilenen servisler**")
                    st.markdown(" ".join(f"`{s}`" for s in k.etkilenen_servisler))

                    if k.saha_gorevi:
                        st.divider()
                        st.markdown("#### Saha yönlendirmesi")
                        for g in k.saha_gorevi:
                            st.markdown(
                                f"**{g['konum']}** · {g['host_sayisi']} host "
                                f"({g['kritik_host']} kritik)"
                            )
                            hostlar = " ".join(f"`{h}`" for h in g["hostlar"])
                            if g["host_kirpildi"]:
                                hostlar += " …"
                            st.markdown(hostlar)

                    st.divider()
                    st.markdown("#### Aksiyon takibi")
                    st.markdown(
                        f"**{k.aksiyon.aksiyon_id}** · **{k.aksiyon.sahip}**"
                    )
                    st.markdown(k.aksiyon.aciklama)

                    yeni = st.radio(
                        "Durum", ["acik", "devam_ediyor", "kapandi"],
                        index=["acik", "devam_ediyor", "kapandi"].index(durum),
                        key=f"durum_{k.kart_id}", horizontal=True,
                        format_func=lambda x: DURUM_ETIKET[x],
                    )
                    if yeni != durum:
                        st.session_state.aksiyon_durum[k.kart_id] = yeni
                        st.session_state.aksiyon_gecmis.setdefault(
                            k.kart_id, []
                        ).append(
                            "%s: %s → %s"
                            % (
                                pd.Timestamp.now().strftime("%H:%M:%S"),
                                DURUM_ETIKET[durum],
                                DURUM_ETIKET[yeni],
                            )
                        )
                        st.rerun()

                    gecmis = st.session_state.aksiyon_gecmis.get(k.kart_id, [])
                    if gecmis:
                        st.caption("Durum geçmişi")
                        for g in gecmis:
                            st.caption(f"· {g}")


def _mobil_gorunum(kartlar):
    """Telefonda okunacak sade liste — sahaya cikan muhendis icin.

    Genis ekran duzeni telefonda okunamiyor; burada her kart tek kolonda,
    yalnizca harekete gecmek icin gereken alanlarla veriliyor: kok neden,
    fiziksel konum, sahip ve durum.
    """
    st.info("Saha görünümü · hızlı müdahale listesi. Tam analiz için kapatın.")

    if "aksiyon_durum" not in st.session_state:
        st.session_state.aksiyon_durum = {}

    for k in kartlar:
        durum = st.session_state.aksiyon_durum.get(k.kart_id, "acik")
        st.markdown(f"### {DURUM_RENK[durum]} {k.kart_id}")
        st.markdown(f"**{k.kok_neden}** · `{k.kok_alarm_tipi}`")
        st.caption(
            f"{k.baslangic[11:16]}–{k.bitis[11:16]} · {k.alarm_sayisi} alarm · "
            f"şiddet {k.azami_siddet} · güven {GUVEN_ETIKET[k.guven]}"
        )

        if k.saha_gorevi:
            for g in k.saha_gorevi:
                st.markdown(
                    f"📍 **{g['konum']}** — {g['host_sayisi']} host "
                    f"({g['kritik_host']} kritik)"
                )
        else:
            st.markdown("Fiziksel saha görevi yok · uzaktan müdahale")

        st.markdown(f"🧰 **{k.aksiyon.sahip}** · {k.aksiyon.aciklama}")

        yeni = st.radio(
            "Durum", ["acik", "devam_ediyor", "kapandi"],
            index=["acik", "devam_ediyor", "kapandi"].index(durum),
            key=f"mobil_durum_{k.kart_id}", horizontal=True,
            label_visibility="collapsed",
            format_func=lambda x: DURUM_ETIKET[x],
        )
        if yeni != durum:
            st.session_state.aksiyon_durum[k.kart_id] = yeni
            st.rerun()

        st.divider()


def _erken_tespit_sekmesi(ayrisma_acik):
    st.subheader("Gece yeniden oynatılıyor")
    st.markdown(
        "Boru hattı, gecenin tamamı yerine **artan zaman dilimleri** üzerinde "
        "tekrar çalıştırılıyor. Ölçülen şey: araç o gece canlı çalışıyor "
        "olsaydı her kök nedeni **kaçıncı dakikada** söylerdi."
    )

    adim = st.select_slider(
        "Dilim adımı (saniye)", options=[60, 120, 300],
        value=VARSAYILAN_ADIM_SN,
        help="İnce adım gecikmeyi keskinleştirir, süreyi uzatır.",
    )

    with st.spinner("Gece yeniden oynatılıyor…"):
        s = _erken_tespit(adim, ayrisma_acik)

    if not s["kayitlar"]:
        st.warning("Bu ayarlarla hiçbir kart oluşmadı.")
        return

    a, b, c = st.columns(3)
    a.metric("Çalıştırılan koşu", s["dilim_sayisi"])
    b.metric("Tespit edilen kök", s["tespit_edilen_kok"])
    ort = s["ortalama_gecikme_sn"]
    c.metric("Ortalama gecikme", f"{ort / 60:.1f} dk" if ort else "—")

    en_hizli = min(s["kayitlar"], key=lambda k: k["gecikme_sn"])
    st.success(
        f"En hızlı tespit: **{en_hizli['kok_neden']}** — olay başladıktan "
        f"**{en_hizli['gecikme_metni']}** sonra kart olarak açıldı."
    )

    df = pd.DataFrame(s["kayitlar"])
    st.dataframe(
        df[["kart_olusma_ani", "kok_neden", "kok_alarm_tipi", "kok_ilk_alarm",
            "gecikme_metni", "kart_alarm_sayisi", "toplu_kosuda_var"]]
        .rename(columns={
            "kart_olusma_ani": "kart oluştu",
            "kok_neden": "kök neden",
            "kok_alarm_tipi": "imza",
            "kok_ilk_alarm": "olay başı",
            "gecikme_metni": "gecikme",
            "kart_alarm_sayisi": "alarm",
            "toplu_kosuda_var": "toplu koşuda var",
        }),
        width="stretch", hide_index=True,
    )

    ara = df[~df["toplu_kosuda_var"]]
    if not ara.empty:
        st.warning(
            "**Ara hipotez:** " + ", ".join(ara["kok_neden"]) +
            " — canlı akışta bir süre kök olarak göründü, gecenin tamamı "
            "okunduğunda başka bir köke evrildi. Gizlenmiyor, işaretleniyor."
        )

    fig = px.bar(
        df.sort_values("gecikme_sn"), x="gecikme_sn", y="kok_neden",
        orientation="h", color="toplu_kosuda_var",
        color_discrete_map={True: "#2a9d8f", False: "#e9c46a"},
        labels={"gecikme_sn": "tespit gecikmesi (sn)", "kok_neden": "",
                "toplu_kosuda_var": "toplu koşuda var"},
    )
    fig.update_layout(height=320)
    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "Gecikme, olayın ilk alarmı ile o olayın ilk kez kart olarak "
        "belirdiği an arasındaki fark; dilim adımı kadar yukarı yuvarlanır."
    )


def _false_merge_kanitlari(x, acik, kapali, grafik):
    """Ayrisma ile korunan her kokun, test kapaliyken hangi karta gomuldugu.

    Anlatim sabit yazilmaz: alarm atamalari, zaman pencereleri ve grafik
    mesafesi ayni esikteki iki gercek kosudan okunur.
    """
    acik_kartlar, acik_alarmlar, _ = acik
    kapali_kartlar, kapali_alarmlar, _ = kapali
    kapali_kok = {k.kart_id: k.kok_neden for k in kapali_kartlar}
    acik_kok = {k.kok_neden: k for k in acik_kartlar}
    kapali_atama = kapali_alarmlar.set_index("alarm_id")["kart_id"]

    kanitlar = []
    for k in acik_kartlar:
        if k.kok_neden not in x["ayrisma_ile_ortaya_cikan"]:
            continue
        uyeler = acik_alarmlar.loc[acik_alarmlar["kart_id"] == k.kart_id, "alarm_id"]
        hedef = kapali_atama.reindex(uyeler)
        hedef = hedef[hedef.ne("")].value_counts()
        if hedef.empty:
            continue
        ev_sahibi = acik_kok.get(kapali_kok[hedef.index[0]])
        if ev_sahibi is None:
            continue

        cakisma = (
            min(pd.Timestamp(k.bitis), pd.Timestamp(ev_sahibi.bitis))
            - max(pd.Timestamp(k.baslangic), pd.Timestamp(ev_sahibi.baslangic))
        ).total_seconds()
        mesafe = None
        if {k.kok_neden, ev_sahibi.kok_neden} <= grafik.servisler:
            mesafe = grafik.mesafe(
                k.kok_neden, ev_sahibi.kok_neden,
                max_atlama=len(grafik.servisler),
            )
        kanitlar.append({
            "kart": k,
            "ev_sahibi": ev_sahibi,
            "kapali_kart": hedef.index[0],
            "gomulen_alarm": int(hedef.iloc[0]),
            "alarm": len(uyeler),
            "cakisma_dk": max(cakisma, 0) / 60,
            "mesafe": mesafe,
        })
    return kanitlar


def _false_merge_paneli(m):
    k, ev = m["kart"], m["ev_sahibi"]
    if m["mesafe"] is None:
        grafik_notu = "iki kök arasında bağımlılık yolu yok"
        kopuk = True
    else:
        grafik_notu = f"grafik mesafesi {m['mesafe']} · eşik {AZAMI_ATLAMA}"
        kopuk = m["mesafe"] > AZAMI_ATLAMA

    kapali, test, acik = st.columns([1.15, 1, 1.15])
    with kapali:
        st.markdown(
            f'<div class="fo-x-card"><div class="fo-x-label">Ayrışma kapalı · '
            f'{escape(m["kapali_kart"])}</div>'
            f'<div class="fo-x-value sm">{escape(ev.kok_neden)} + '
            f'{escape(k.kok_neden)}</div>'
            f'<div class="fo-x-note">{escape(k.kok_neden)} alarmlarının '
            f'{m["gomulen_alarm"]}/{m["alarm"]} kadarı tek karta gömülüyordu'
            f'</div></div>',
            unsafe_allow_html=True,
        )
    with test:
        st.markdown(
            f'<div class="fo-x-card"><div class="fo-x-label">Grafik testi</div>'
            f'<div class="fo-x-value sm">{"Kopuk kökler" if kopuk else "Bağlı kökler"}'
            f'</div><div class="fo-x-note">{m["cakisma_dk"]:.0f} dk zaman '
            f'çakışması · {escape(grafik_notu)}</div></div>',
            unsafe_allow_html=True,
        )
    with acik:
        st.markdown(
            f'<div class="fo-x-card active"><div class="fo-x-label">Ayrışma açık'
            f'</div><div class="fo-x-value sm">{escape(ev.kart_id)} · '
            f'{escape(k.kart_id)}</div>'
            f'<div class="fo-x-note">{escape(ev.kok_neden)} → '
            f'{escape(ev.aksiyon.sahip)}<br>{escape(k.kok_neden)} → '
            f'{escape(k.aksiyon.sahip)}</div></div>',
            unsafe_allow_html=True,
        )


def _x_factor_sekmesi(esik):
    x = _x_factor(esik)
    st.subheader("Grafik ayrışma testi")
    st.markdown(
        "İki olay aynı anda olup aynı servisi etkileyebilir. Sadece zaman ve "
        "servis benzerliğine bakan kümeleme bunları **tek olay** sayar. "
        "Grafik ayrışması, aday kökler arasındaki nedensel yolu sınar."
    )

    a, b = st.columns(2)
    with a:
        st.markdown(
            f'<div class="fo-x-card"><div class="fo-x-label">Grafik ayrışması olmadan</div>'
            f'<div class="fo-x-value">{x["ayrisma_kapali_kart"]}</div>'
            f'<div class="fo-x-note">olay · eşzamanlı kökler tek karta '
            f'birleşebilir</div></div>',
            unsafe_allow_html=True,
        )
    with b:
        st.markdown(
            f'<div class="fo-x-card active"><div class="fo-x-label">Grafik ayrışması ile</div>'
            f'<div class="fo-x-value">{x["ayrisma_acik_kart"]}</div>'
            f'<div class="fo-x-note">olay · kopuk kökler bağımsız müdahale '
            f'olarak korunur</div></div>',
            unsafe_allow_html=True,
        )

    if x["ayrisma_ile_ortaya_cikan"]:
        st.success(
            "Ayrışma açılınca korunan bağımsız kök: **%s**. Kapalı durumda bu "
            "olay başka bir olayla aynı karta giriyordu — ölçülmüş false merge."
            % ", ".join(x["ayrisma_ile_ortaya_cikan"])
        )

    st.markdown("#### False merge nasıl engellendi?")
    st.caption(
        "Zaman benzerliği eşzamanlı alarmları birleştirir; ayrışma testi "
        "artığın kendi kökünü birincil kökle bağımlılık grafiğinde sınar. "
        "Aşağıdaki değerler iki koşunun alarm atamalarından ölçülür."
    )
    kanitlar = _false_merge_kanitlari(
        x, _calistir(esik, True), _calistir(esik, False), _grafik()
    )
    if not kanitlar:
        st.caption("Bu eşikte ayrışma testi ek bir bağımsız kök ortaya çıkarmadı.")
    for m in kanitlar:
        _false_merge_paneli(m)

    s1, s2 = st.columns(2)
    with s1:
        st.markdown("**Ayrışma olmadan bulunan kökler**")
        for s in x["kapali_kokler"]:
            st.markdown(f"- {s}")
    with s2:
        st.markdown("**Grafikle korunan kökler**")
        for s in x["acik_kokler"]:
            isaret = " · **bağımsız olay**" if s not in x["kapali_kokler"] else ""
            st.markdown(f"- {s}{isaret}")


def _gurultu_sekmesi(alarmlar):
    st.subheader("Gürültü ve dışlama denetimi")
    st.markdown(
        "Her dışlama kararı skor ve gerekçe taşır. Filtrelerle daraltın; "
        "tablo örnek değil, dışlanan kayıtların tamamıdır."
    )

    gurultu = alarmlar[alarmlar["son_sinif"] != "olay_karti"]
    skor_gurultusu = int((gurultu["son_sinif"] == "puanlama_gurultusu").sum())
    korelasyon_disi = int((gurultu["son_sinif"] == "korelasyon_disi").sum())
    m1, m2, m3 = st.columns(3)
    m1.metric("Skorlama gürültüsü", _sayi(skor_gurultusu))
    m2.metric("Korelasyon dışı", _sayi(korelasyon_disi))
    m3.metric("Toplam dışlanan", _sayi(len(gurultu)))

    f1, f2, f3 = st.columns(3)
    siniflar = ["(tümü)"] + sorted(gurultu["son_sinif"].unique())
    tipler = ["(tümü)"] + sorted(gurultu["alarm_type"].unique())
    servisler = ["(tümü)"] + sorted(gurultu["service"].unique())
    sinif = f1.selectbox("Son sınıf", siniflar)
    tip = f2.selectbox("Alarm tipi", tipler)
    servis = f3.selectbox("Servis", servisler)

    g = gurultu
    if sinif != "(tümü)":
        g = g[g["son_sinif"] == sinif]
    if tip != "(tümü)":
        g = g[g["alarm_type"] == tip]
    if servis != "(tümü)":
        g = g[g["service"] == servis]

    st.caption(f"{_sayi(len(g))} kayıt gösteriliyor · her satır kendi dışlama gerekçesini taşır")

    st.dataframe(
        g[["alarm_id", "timestamp", "alarm_type", "service", "host", "son_sinif",
           "severity", "sinyal_skoru", "eleme_gerekcesi"]]
        .sort_values("sinyal_skoru", ascending=False),
        width="stretch", hide_index=True,
    )

    st.markdown("**Skor dağılımı — sinyal ve gürültü ayrımı**")
    fig = px.histogram(
        alarmlar, x="sinyal_skoru", color="sinyal", nbins=60,
        labels={"sinyal_skoru": "sinyal skoru", "sinyal": "sinyal mi"},
        color_discrete_map={True: "#d62728", False: "#9fb3c8"},
    )
    fig.update_layout(height=320, bargap=0.02)
    st.plotly_chart(fig, use_container_width=True)


def _zaman_sekmesi(alarmlar, kartlar):
    st.subheader("Alarm yoğunluğu ve olay pencereleri")

    df = alarmlar.copy()
    df["kova"] = df["timestamp"].dt.floor("2min")
    ozet = (
        df.groupby(["kova", "sinyal"]).size().reset_index(name="adet")
    )
    ozet["tur"] = ozet["sinyal"].map({True: "sinyal", False: "gürültü"})

    fig = px.bar(
        ozet, x="kova", y="adet", color="tur",
        color_discrete_map={"sinyal": "#d62728", "gürültü": "#9fb3c8"},
        labels={"kova": "zaman", "adet": "alarm sayısı", "tur": ""},
    )
    # Cakisan pencerelerin etiketleri ust uste binmesin diye asagi kaydirilir.
    acik_pencereler = []
    for k in kartlar:
        bas, bit = pd.Timestamp(k.baslangic), pd.Timestamp(k.bitis)
        kat = sum(1 for onceki_bitis in acik_pencereler if bas < onceki_bitis)
        fig.add_vrect(
            x0=bas, x1=bit,
            fillcolor="#ffa600", opacity=0.12, line_width=0,
            annotation_text=k.kart_id, annotation_position="top left",
            annotation_yshift=-16 * kat,
        )
        acik_pencereler.append(bit)
    fig.update_layout(height=420, bargap=0.05)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Kart özeti**")
    st.dataframe(
        pd.DataFrame([{
            "kart": k.kart_id,
            "kök neden": k.kok_neden,
            "alarm tipi": k.kok_alarm_tipi,
            "başlangıç": k.baslangic[11:],
            "bitiş": k.bitis[11:],
            "alarm": k.alarm_sayisi,
            "güven": GUVEN_ETIKET[k.guven],
            "ayrışma ile": k.ayrisma_ile_bolundu,
        } for k in kartlar]),
        width="stretch", hide_index=True,
    )


main()
