"""Streamlit arayuzu — nobetci muhendis gorunumu.

    streamlit run src/app.py

Dort sekme:
  Olay Kartlari   — indirgenmis karar listesi, aksiyon durumu degistirilebilir
  X-Factor        — ayrisma testi acik/kapali karsilastirmasi
  Gurultu Denetimi— elenen her alarmin neden elendigi
  Zaman Cizelgesi — alarm yogunlugu ve olay pencereleri
"""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# `streamlit run src/app.py` ile calistirildiginda proje koku sys.path'te
# olmadigi icin paket importu basarisiz oluyor; ekliyoruz.
KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src.pipeline import ayrisma_karsilastirmasi, calistir  # noqa: E402
from src.replay import VARSAYILAN_ADIM_SN, erken_tespit  # noqa: E402
from src.scoring import VARSAYILAN_ESIK  # noqa: E402

st.set_page_config(page_title="Alarm Firtinasi — Olay Kartlari",
                   page_icon="🚨", layout="wide")

DURUM_RENK = {"acik": "🔴", "devam_ediyor": "🟡", "kapandi": "🟢"}
GUVEN_RENK = {"yuksek": "🟢", "orta": "🟡", "dusuk": "🔴"}


@st.cache_data(show_spinner=False)
def _calistir(esik, ayrisma_acik):
    s = calistir(esik=esik, ayrisma_acik=ayrisma_acik)
    return s.kartlar, s.alarmlar, s.metrikler


@st.cache_data(show_spinner=False)
def _x_factor():
    return ayrisma_karsilastirmasi()


@st.cache_data(show_spinner=False)
def _erken_tespit(adim_sn, ayrisma_acik):
    # Replay onlarca kosu yapar (~15 sn); onbellek olmadan her etkilesimde
    # tekrarlanir ve arayuz kullanilamaz hale gelir.
    return erken_tespit(adim_sn=adim_sn, ayrisma_acik=ayrisma_acik).ozet()


def main():
    st.title("🚨 Alarm Firtinasi — Olay Kartlari")
    st.caption(
        "3000 alarm, 2 saatlik pencere. Nobetci muhendisin okuyup harekete "
        "gecebilecegi karar listesine indirgenmis hali."
    )

    with st.sidebar:
        st.header("Ayarlar")
        esik = st.slider(
            "Sinyal esigi", 0.10, 0.70, VARSAYILAN_ESIK, 0.05,
            help="Dusuk esik daha cok alarmi sinyal sayar, gurultu artar.",
        )
        ayrisma = st.checkbox(
            "Grafik ayrisma testi", value=True,
            help="Kapatirsan ayni anda olan bagimsiz olaylar tek karta birlesir.",
        )
        mobil = st.checkbox(
            "📱 Mobil / saha gorunumu", value=False,
            help="Telefonda okunacak sade liste: kok neden, konum, aksiyon.",
        )
        st.divider()
        st.caption(
            "Ayrisma testi, bir kumenin aciklanamayan artigi kendi kokune "
            "sahipse ve bu kok birincil kokle grafikte bagli degilse kumeyi "
            "boler."
        )

    kartlar, alarmlar, metrikler = _calistir(esik, ayrisma)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Toplam alarm", f"{metrikler['toplam_alarm']:,}".replace(",", "."))
    k2.metric("Olay karti", metrikler["kart_sayisi"],
              help="Kabul kriteri: en fazla 15")
    k3.metric(
        "Kart disi",
        f"%{100 * metrikler['acikca_dislanan_oran']:.0f}",
        help=(
            f"{metrikler['gurultu']} skor gurultusu + "
            f"{metrikler['korelasyon_disi_sinyal']} korelasyon disi sinyal"
        ),
    )
    k4.metric("Indirgeme", f"{metrikler['indirgeme_carpani']:.0f}x")

    if mobil:
        _mobil_gorunum(kartlar)
        return

    sekmeler = st.tabs(
        ["📋 Olay Kartlari", "⏱️ Erken Tespit", "🔬 X-Factor",
         "🔇 Gurultu Denetimi", "📈 Zaman Cizelgesi"]
    )

    with sekmeler[0]:
        _kartlar_sekmesi(kartlar)
    with sekmeler[1]:
        _erken_tespit_sekmesi(ayrisma)
    with sekmeler[2]:
        _x_factor_sekmesi()
    with sekmeler[3]:
        _gurultu_sekmesi(alarmlar)
    with sekmeler[4]:
        _zaman_sekmesi(alarmlar, kartlar)


def _kartlar_sekmesi(kartlar):
    if "aksiyon_durum" not in st.session_state:
        st.session_state.aksiyon_durum = {}
    if "aksiyon_gecmis" not in st.session_state:
        st.session_state.aksiyon_gecmis = {}

    for k in kartlar:
        durum = st.session_state.aksiyon_durum.get(k.kart_id, "acik")
        bayrak = " · ⚡ ayrisma testi ile ayrildi" if k.ayrisma_ile_bolundu else ""
        baslik = "%s %s — %s  (%d alarm)%s" % (
            DURUM_RENK[durum], k.kart_id, k.baslik, k.alarm_sayisi, bayrak,
        )

        with st.expander(baslik, expanded=(k is kartlar[0])):
            s1, s2 = st.columns([3, 2])

            with s1:
                st.markdown("#### Kok neden hipotezi")
                st.markdown(
                    f"**{k.kok_neden}** — `{k.kok_alarm_tipi}`  "
                    f"{GUVEN_RENK[k.guven]} guven: **{k.guven}** ({k.guven_skoru})"
                )

                st.markdown("**Kanit** (veriden olculdu)")
                for c in k.kanit:
                    st.markdown(f"- {c}")

                st.markdown("**Gerekce** (cikarim)")
                st.info(k.gerekce)

                st.markdown("**Karsi hipotez**")
                st.warning(k.karsi_hipotez)

                if k.sinirlar:
                    st.markdown("**Sinirlar**")
                    for x in k.sinirlar:
                        st.markdown(f"- {x}")

            with s2:
                st.markdown("#### Kapsam")
                st.markdown(
                    f"- Zaman: `{k.baslangic[11:]}` → `{k.bitis[11:]}`\n"
                    f"- Alarm: **{k.alarm_sayisi}**\n"
                    f"- Host: **{k.etkilenen_host_sayisi}**\n"
                    f"- Azami siddet: **{k.azami_siddet}**"
                )
                st.markdown("**Etkilenen servisler**")
                st.markdown(" ".join(f"`{s}`" for s in k.etkilenen_servisler))

                if k.saha_gorevi:
                    st.divider()
                    st.markdown("#### 📍 Saha gorevi")
                    for g in k.saha_gorevi:
                        st.markdown(
                            f"**{g['konum']}** — {g['host_sayisi']} host "
                            f"({g['kritik_host']} kritik)"
                        )
                        hostlar = " ".join(f"`{h}`" for h in g["hostlar"])
                        if g["host_kirpildi"]:
                            hostlar += " …"
                        st.markdown(hostlar)

                st.divider()
                st.markdown("#### Aksiyon")
                st.markdown(
                    f"**{k.aksiyon.aksiyon_id}** · sahip: **{k.aksiyon.sahip}**"
                )
                st.markdown(k.aksiyon.aciklama)

                yeni = st.radio(
                    "Durum", ["acik", "devam_ediyor", "kapandi"],
                    index=["acik", "devam_ediyor", "kapandi"].index(durum),
                    key=f"durum_{k.kart_id}", horizontal=True,
                )
                if yeni != durum:
                    st.session_state.aksiyon_durum[k.kart_id] = yeni
                    st.session_state.aksiyon_gecmis.setdefault(
                        k.kart_id, []
                    ).append(
                        "%s: %s → %s"
                        % (pd.Timestamp.now().strftime("%H:%M:%S"), durum, yeni)
                    )
                    st.rerun()

                gecmis = st.session_state.aksiyon_gecmis.get(k.kart_id, [])
                if gecmis:
                    st.caption("Durum gecmisi")
                    for g in gecmis:
                        st.caption(f"· {g}")


def _mobil_gorunum(kartlar):
    """Telefonda okunacak sade liste — sahaya cikan muhendis icin.

    Genis ekran duzeni telefonda okunamiyor; burada her kart tek kolonda,
    yalnizca harekete gecmek icin gereken alanlarla veriliyor: kok neden,
    fiziksel konum, sahip ve durum.
    """
    st.info("📱 Saha gorunumu — sade liste. Tam analiz icin kapatin.")

    if "aksiyon_durum" not in st.session_state:
        st.session_state.aksiyon_durum = {}

    for k in kartlar:
        durum = st.session_state.aksiyon_durum.get(k.kart_id, "acik")
        st.markdown(f"### {DURUM_RENK[durum]} {k.kart_id}")
        st.markdown(f"**{k.kok_neden}** · `{k.kok_alarm_tipi}`")
        st.caption(
            f"{k.baslangic[11:16]}–{k.bitis[11:16]} · {k.alarm_sayisi} alarm · "
            f"siddet {k.azami_siddet} · guven {k.guven}"
        )

        if k.saha_gorevi:
            for g in k.saha_gorevi:
                st.markdown(
                    f"📍 **{g['konum']}** — {g['host_sayisi']} host "
                    f"({g['kritik_host']} kritik)"
                )
        else:
            st.markdown("📍 Fiziksel saha gorevi yok — uzaktan mudahale")

        st.markdown(f"🧰 **{k.aksiyon.sahip}** · {k.aksiyon.aciklama}")

        yeni = st.radio(
            "Durum", ["acik", "devam_ediyor", "kapandi"],
            index=["acik", "devam_ediyor", "kapandi"].index(durum),
            key=f"mobil_durum_{k.kart_id}", horizontal=True,
            label_visibility="collapsed",
        )
        if yeni != durum:
            st.session_state.aksiyon_durum[k.kart_id] = yeni
            st.rerun()

        st.divider()


def _erken_tespit_sekmesi(ayrisma_acik):
    st.subheader("Gece yeniden oynatiliyor")
    st.markdown(
        "Boru hatti, gecenin tamami yerine **artan zaman dilimleri** uzerinde "
        "tekrar calistiriliyor. Olculen sey: arac o gece canli calisiyor "
        "olsaydi her kok nedeni **kacinci dakikada** soylerdi."
    )

    adim = st.select_slider(
        "Dilim adimi (saniye)", options=[60, 120, 300],
        value=VARSAYILAN_ADIM_SN,
        help="Ince adim gecikmeyi keskinlestirir, sureyi uzatir.",
    )

    with st.spinner("Gece yeniden oynatiliyor…"):
        s = _erken_tespit(adim, ayrisma_acik)

    if not s["kayitlar"]:
        st.warning("Bu ayarlarla hicbir kart olusmadi.")
        return

    a, b, c = st.columns(3)
    a.metric("Calistirilan kosu", s["dilim_sayisi"])
    b.metric("Tespit edilen kok", s["tespit_edilen_kok"])
    ort = s["ortalama_gecikme_sn"]
    c.metric("Ortalama gecikme", f"{ort / 60:.1f} dk" if ort else "—")

    en_hizli = min(s["kayitlar"], key=lambda k: k["gecikme_sn"])
    st.success(
        f"En hizli tespit: **{en_hizli['kok_neden']}** — olay basladiktan "
        f"**{en_hizli['gecikme_metni']}** sonra kart olarak acildi."
    )

    df = pd.DataFrame(s["kayitlar"])
    st.dataframe(
        df[["kart_olusma_ani", "kok_neden", "kok_alarm_tipi", "kok_ilk_alarm",
            "gecikme_metni", "kart_alarm_sayisi", "toplu_kosuda_var"]]
        .rename(columns={
            "kart_olusma_ani": "kart olustu",
            "kok_neden": "kok neden",
            "kok_alarm_tipi": "imza",
            "kok_ilk_alarm": "olay basi",
            "gecikme_metni": "gecikme",
            "kart_alarm_sayisi": "alarm",
            "toplu_kosuda_var": "toplu kosuda var",
        }),
        width="stretch", hide_index=True,
    )

    ara = df[~df["toplu_kosuda_var"]]
    if not ara.empty:
        st.warning(
            "**Ara hipotez:** " + ", ".join(ara["kok_neden"]) +
            " — canli akista bir sure kok olarak gorundu, gecenin tamami "
            "okundugunda baska bir koke evrildi. Gizlenmiyor, isaretleniyor."
        )

    fig = px.bar(
        df.sort_values("gecikme_sn"), x="gecikme_sn", y="kok_neden",
        orientation="h", color="toplu_kosuda_var",
        color_discrete_map={True: "#2a9d8f", False: "#e9c46a"},
        labels={"gecikme_sn": "tespit gecikmesi (sn)", "kok_neden": "",
                "toplu_kosuda_var": "toplu kosuda var"},
    )
    fig.update_layout(height=320)
    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "Gecikme, olayin ilk alarmi ile o olayin ilk kez kart olarak "
        "belirdigi an arasindaki fark; dilim adimi kadar yukari yuvarlanir."
    )


def _x_factor_sekmesi():
    x = _x_factor()
    st.subheader("Grafik ayrisma testi")
    st.markdown(
        "Iki olay ayni anda olup ayni servisi etkileyebilir. Sadece zaman ve "
        "servis benzerligine bakan bir kumeleme bunlari **tek olay** sayar. "
        "Ayrisma testi, artik alarmlarin kendi kokune sahip olup olmadigina ve "
        "bu kokun birincil kokle grafikte **bagli olup olmadigina** bakar."
    )

    a, b = st.columns(2)
    a.metric("Ayrisma testi KAPALI", f"{x['ayrisma_kapali_kart']} kart")
    b.metric("Ayrisma testi ACIK", f"{x['ayrisma_acik_kart']} kart",
             delta=f"+{x['ayrisma_acik_kart'] - x['ayrisma_kapali_kart']}")

    if x["ayrisma_ile_ortaya_cikan"]:
        st.success(
            "Test acilinca ortaya cikan kok neden: **%s**. Test kapaliyken bu "
            "olay baska bir olayla ayni karta konuyordu — yanlis birlestirme."
            % ", ".join(x["ayrisma_ile_ortaya_cikan"])
        )

    s1, s2 = st.columns(2)
    with s1:
        st.markdown("**Kapaliyken bulunan kokler**")
        for s in x["kapali_kokler"]:
            st.markdown(f"- {s}")
    with s2:
        st.markdown("**Acikken bulunan kokler**")
        for s in x["acik_kokler"]:
            isaret = " ⬅️ **yeni**" if s not in x["kapali_kokler"] else ""
            st.markdown(f"- {s}{isaret}")


def _gurultu_sekmesi(alarmlar):
    st.subheader("Neden elendi?")
    st.markdown(
        "Eleme ikili bir karar degil, skorlu. Her alarmin skoru ve eleme "
        "gerekcesi burada denetlenebilir."
    )

    gurultu = alarmlar[alarmlar["son_sinif"] != "olay_karti"]
    st.caption(
        f"{len(gurultu)} alarm acikca kart disinda birakildi: "
        f"{(gurultu['son_sinif'] == 'puanlama_gurultusu').sum()} skor gurultusu, "
        f"{(gurultu['son_sinif'] == 'korelasyon_disi').sum()} korelasyon disi sinyal."
    )

    tipler = ["(hepsi)"] + sorted(gurultu["alarm_type"].unique())
    secim = st.selectbox("Alarm tipi", tipler)
    g = gurultu if secim == "(hepsi)" else gurultu[gurultu["alarm_type"] == secim]

    st.dataframe(
        g[["alarm_id", "timestamp", "alarm_type", "service", "host", "son_sinif",
           "severity", "sinyal_skoru", "eleme_gerekcesi"]]
        .sort_values("sinyal_skoru", ascending=False)
        .head(300),
        width="stretch", hide_index=True,
    )

    st.markdown("**Skor dagilimi — sinyal ve gurultu ayrimi**")
    fig = px.histogram(
        alarmlar, x="sinyal_skoru", color="sinyal", nbins=60,
        labels={"sinyal_skoru": "sinyal skoru", "sinyal": "sinyal mi"},
        color_discrete_map={True: "#d62728", False: "#9fb3c8"},
    )
    fig.update_layout(height=320, bargap=0.02)
    st.plotly_chart(fig, use_container_width=True)


def _zaman_sekmesi(alarmlar, kartlar):
    st.subheader("Alarm yogunlugu ve olay pencereleri")

    df = alarmlar.copy()
    df["kova"] = df["timestamp"].dt.floor("2min")
    ozet = (
        df.groupby(["kova", "sinyal"]).size().reset_index(name="adet")
    )
    ozet["tur"] = ozet["sinyal"].map({True: "sinyal", False: "gurultu"})

    fig = px.bar(
        ozet, x="kova", y="adet", color="tur",
        color_discrete_map={"sinyal": "#d62728", "gurultu": "#9fb3c8"},
        labels={"kova": "zaman", "adet": "alarm sayisi", "tur": ""},
    )
    for k in kartlar:
        fig.add_vrect(
            x0=pd.Timestamp(k.baslangic), x1=pd.Timestamp(k.bitis),
            fillcolor="#ffa600", opacity=0.12, line_width=0,
            annotation_text=k.kart_id, annotation_position="top left",
        )
    fig.update_layout(height=420, bargap=0.05)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Kart ozeti**")
    st.dataframe(
        pd.DataFrame([{
            "kart": k.kart_id,
            "kok_neden": k.kok_neden,
            "alarm_tipi": k.kok_alarm_tipi,
            "baslangic": k.baslangic[11:],
            "bitis": k.bitis[11:],
            "alarm": k.alarm_sayisi,
            "guven": k.guven,
            "ayrisma_ile": k.ayrisma_ile_bolundu,
        } for k in kartlar]),
        width="stretch", hide_index=True,
    )


main()
