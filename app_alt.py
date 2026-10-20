import streamlit as st
import yfinance as yf
import pandas as pd
import math


# =========================================================
# SEITENEINSTELLUNGEN
# =========================================================

st.set_page_config(
    page_title="Aktien Rating Modell",
    page_icon="📈",
    layout="wide"
)


# =========================================================
# MODELL-KONFIGURATION
# =========================================================
# VORLÄUFIG!
# Diese Werte können später nach eurer Recherche geändert werden.

CONFIG = {
    "FCF-Yield": {
        "max_punkte": 15,
        "schlecht": 0,
        "gut": 10
    },
    "Umsatzwachstum": {
        "max_punkte": 15,
        "schlecht": 0,
        "gut": 20
    },
    "ROIC": {
        "max_punkte": 15,
        "schlecht": 0,
        "gut": 25
    },
    "Net Debt / EBITDA": {
        "max_punkte": 15,
        "gut": 0,
        "schlecht": 4
    },
    "KGV": {
        "max_punkte": 10
    },
    "EPS-Wachstum": {
        "max_punkte": 10,
        "schlecht": 0,
        "gut": 25
    },
    "Operative Marge": {
        "max_punkte": 10,
        "schlecht": 0,
        "gut": 30
    },
    "FCF-Marge": {
        "max_punkte": 10,
        "schlecht": 0,
        "gut": 25
    }
}


# =========================================================
# HILFSFUNKTIONEN
# =========================================================

def sicherer_wert(dictionary, key):

    wert = dictionary.get(key)

    if wert is None:
        return None

    try:
        if pd.isna(wert):
            return None
    except:
        pass

    return wert


def positive_punkte(wert, schlecht, gut, max_punkte):

    if wert is None:
        return None

    if wert <= schlecht:
        return 0

    if wert >= gut:
        return max_punkte

    return max_punkte * (
        (wert - schlecht) / (gut - schlecht)
    )


def negative_punkte(wert, gut, schlecht, max_punkte):

    if wert is None:
        return None

    if wert <= gut:
        return max_punkte

    if wert >= schlecht:
        return 0

    return max_punkte * (
        (schlecht - wert) / (schlecht - gut)
    )


def kgv_punkte(kgv):

    if kgv is None or kgv <= 0:
        return 0

    if kgv < 5:
        return 2

    if kgv < 10:
        return 2 + (kgv - 5) * (4 / 5)

    if kgv < 15:
        return 6 + (kgv - 10) * (4 / 5)

    if kgv <= 20:
        return 10

    if kgv < 25:
        return 10 - (kgv - 20) * (2 / 5)

    if kgv < 30:
        return 8 - (kgv - 25) * (2 / 5)

    if kgv < 40:
        return 6 - (kgv - 30) * (3 / 10)

    if kgv < 50:
        return 3 - (kgv - 40) * (3 / 10)

    return 0


def rating_bestimmen(score):

    if score >= 80:
        return "Strong Buy"

    elif score >= 65:
        return "Buy"

    elif score >= 45:
        return "Hold"

    elif score >= 30:
        return "Underperform"

    else:
        return "Sell"


# =========================================================
# RATING-TACHO
# =========================================================

def rating_tacho(score):

    # Winkel:
    # Score 0   = 180 Grad
    # Score 100 = 0 Grad

    winkel = 180 - (score / 100 * 180)

    rad = math.radians(winkel)

    # Mittelpunkt
    cx = 200
    cy = 180

    # Zeigerlänge
    laenge = 115

    x = cx + laenge * math.cos(rad)
    y = cy - laenge * math.sin(rad)

    rating = rating_bestimmen(score)

    html = f"""
    <div style="
        text-align:center;
        max-width:500px;
        margin:auto;
    ">

    <svg
        viewBox="0 0 400 245"
        width="100%"
        xmlns="http://www.w3.org/2000/svg"
    >

        <!-- Hintergrundbogen -->

        <path
            d="M 50 180
               A 150 150 0 0 1 350 180"
            fill="none"
            stroke="#e5e7eb"
            stroke-width="20"
            stroke-linecap="round"
        />

        <!-- Sell -->

        <path
            d="M 50 180
               A 150 150 0 0 1 79 90"
            fill="none"
            stroke="#dc2626"
            stroke-width="20"
            stroke-linecap="round"
        />

        <!-- Underperform -->

        <path
            d="M 79 90
               A 150 150 0 0 1 154 37"
            fill="none"
            stroke="#f97316"
            stroke-width="20"
        />

        <!-- Hold -->

        <path
            d="M 154 37
               A 150 150 0 0 1 246 37"
            fill="none"
            stroke="#eab308"
            stroke-width="20"
        />

        <!-- Buy -->

        <path
            d="M 246 37
               A 150 150 0 0 1 321 90"
            fill="none"
            stroke="#22c55e"
            stroke-width="20"
        />

        <!-- Strong Buy -->

        <path
            d="M 321 90
               A 150 150 0 0 1 350 180"
            fill="none"
            stroke="#15803d"
            stroke-width="20"
            stroke-linecap="round"
        />


        <!-- Zeiger -->

        <line
            x1="{cx}"
            y1="{cy}"
            x2="{x}"
            y2="{y}"
            stroke="#374151"
            stroke-width="5"
        />

        <!-- Mittelpunkt -->

        <circle
            cx="{cx}"
            cy="{cy}"
            r="9"
            fill="#374151"
        />


        <!-- Beschriftungen -->

        <text
            x="35"
            y="215"
            font-size="15"
            text-anchor="middle"
            fill="#6b7280"
        >
            Sell
        </text>

        <text
            x="100"
            y="50"
            font-size="13"
            text-anchor="middle"
            fill="#6b7280"
        >
            Underperform
        </text>

        <text
            x="200"
            y="18"
            font-size="15"
            text-anchor="middle"
            fill="#6b7280"
        >
            Hold
        </text>

        <text
            x="300"
            y="50"
            font-size="15"
            text-anchor="middle"
            fill="#6b7280"
        >
            Buy
        </text>

        <text
            x="365"
            y="215"
            font-size="13"
            text-anchor="middle"
            fill="#6b7280"
        >
            Strong Buy
        </text>

    </svg>


    <div style="
        font-size:30px;
        font-weight:700;
        margin-top:-20px;
    ">
        {rating}
    </div>


    <div style="
        font-size:20px;
        color:#6b7280;
        margin-top:5px;
    ">
        {score:.1f} / 100 Punkte
    </div>

    </div>
    """

    st.html(html)


# =========================================================
# QUARTALSDATEN SUCHEN
# =========================================================

def zeile_suchen(tabelle, moegliche_namen):

    if tabelle is None or tabelle.empty:
        return None

    for name in moegliche_namen:

        if name in tabelle.index:
            return tabelle.loc[name]

    return None


def quartalsdaten_vorbereiten(serie):

    if serie is None:
        return None

    serie = serie.dropna()

    if serie.empty:
        return None

    # Yahoo liefert neueste Quartale zuerst.
    # Für den Chart drehen wir die Reihenfolge um.
    serie = serie.iloc[:8]
    serie = serie.sort_index()

    daten = pd.DataFrame({
        "Wert": serie.values
    })

    daten.index = [
        datum.strftime("%b %Y")
        if hasattr(datum, "strftime")
        else str(datum)
        for datum in serie.index
    ]

    return daten


# =========================================================
# AKTIE ANALYSIEREN
# =========================================================

def aktie_analysieren(ticker_symbol):

    aktie = yf.Ticker(ticker_symbol)

    info = aktie.info

    if not info:
        raise ValueError(
            "Für diesen Ticker wurden keine Daten gefunden."
        )

    # -----------------------------------------------------
    # GRUNDDATEN
    # -----------------------------------------------------

    name = info.get(
        "longName",
        ticker_symbol.upper()
    )

    kurs = sicherer_wert(
        info,
        "currentPrice"
    )

    if kurs is None:

        kurs = sicherer_wert(
            info,
            "regularMarketPrice"
        )

    waehrung = info.get(
        "currency",
        ""
    )

    market_cap = sicherer_wert(
        info,
        "marketCap"
    )


    # -----------------------------------------------------
    # FINANZDATEN
    # -----------------------------------------------------

    trailing_pe = sicherer_wert(
        info,
        "trailingPE"
    )

    operating_margin = sicherer_wert(
        info,
        "operatingMargins"
    )

    free_cashflow = sicherer_wert(
        info,
        "freeCashflow"
    )

    revenue = sicherer_wert(
        info,
        "totalRevenue"
    )

    ebitda = sicherer_wert(
        info,
        "ebitda"
    )

    total_debt = sicherer_wert(
        info,
        "totalDebt"
    )

    cash = sicherer_wert(
        info,
        "totalCash"
    )

    return_on_assets = sicherer_wert(
        info,
        "returnOnAssets"
    )

    revenue_growth = sicherer_wert(
        info,
        "revenueGrowth"
    )

    earnings_growth = sicherer_wert(
        info,
        "earningsGrowth"
    )


    # -----------------------------------------------------
    # EIGENE BERECHNUNGEN
    # -----------------------------------------------------

    # FCF-Yield

    if (
        free_cashflow is not None
        and market_cap not in (None, 0)
    ):

        fcf_yield = (
            free_cashflow
            / market_cap
            * 100
        )

    else:

        fcf_yield = None


    # FCF-Marge

    if (
        free_cashflow is not None
        and revenue not in (None, 0)
    ):

        fcf_margin = (
            free_cashflow
            / revenue
            * 100
        )

    else:

        fcf_margin = None


    # Operative Marge

    if operating_margin is not None:

        operating_margin_pct = (
            operating_margin * 100
        )

    else:

        operating_margin_pct = None


    # Umsatzwachstum

    if revenue_growth is not None:

        revenue_growth_pct = (
            revenue_growth * 100
        )

    else:

        revenue_growth_pct = None


    # EPS-Wachstum

    if earnings_growth is not None:

        eps_growth_pct = (
            earnings_growth * 100
        )

    else:

        eps_growth_pct = None


    # Nettoverschuldung

    if (
        total_debt is not None
        and cash is not None
    ):

        net_debt = (
            total_debt - cash
        )

    else:

        net_debt = None


    # Net Debt / EBITDA

    if (
        net_debt is not None
        and ebitda is not None
        and ebitda > 0
    ):

        net_debt_ebitda = (
            net_debt / ebitda
        )

    else:

        net_debt_ebitda = None


    # ROIC - MOMENTAN NUR NÄHERUNG

    if return_on_assets is not None:

        roic = (
            return_on_assets * 100
        )

    else:

        roic = None


    # -----------------------------------------------------
    # PUNKTE
    # -----------------------------------------------------

    punkte = {}


    punkte["FCF-Yield"] = positive_punkte(
        fcf_yield,
        CONFIG["FCF-Yield"]["schlecht"],
        CONFIG["FCF-Yield"]["gut"],
        CONFIG["FCF-Yield"]["max_punkte"]
    )


    punkte["Umsatzwachstum"] = positive_punkte(
        revenue_growth_pct,
        CONFIG["Umsatzwachstum"]["schlecht"],
        CONFIG["Umsatzwachstum"]["gut"],
        CONFIG["Umsatzwachstum"]["max_punkte"]
    )


    punkte["ROIC"] = positive_punkte(
        roic,
        CONFIG["ROIC"]["schlecht"],
        CONFIG["ROIC"]["gut"],
        CONFIG["ROIC"]["max_punkte"]
    )


    punkte["Net Debt / EBITDA"] = negative_punkte(
        net_debt_ebitda,
        CONFIG["Net Debt / EBITDA"]["gut"],
        CONFIG["Net Debt / EBITDA"]["schlecht"],
        CONFIG["Net Debt / EBITDA"]["max_punkte"]
    )


    punkte["KGV"] = kgv_punkte(
        trailing_pe
    )


    punkte["EPS-Wachstum"] = positive_punkte(
        eps_growth_pct,
        CONFIG["EPS-Wachstum"]["schlecht"],
        CONFIG["EPS-Wachstum"]["gut"],
        CONFIG["EPS-Wachstum"]["max_punkte"]
    )


    punkte["Operative Marge"] = positive_punkte(
        operating_margin_pct,
        CONFIG["Operative Marge"]["schlecht"],
        CONFIG["Operative Marge"]["gut"],
        CONFIG["Operative Marge"]["max_punkte"]
    )


    punkte["FCF-Marge"] = positive_punkte(
        fcf_margin,
        CONFIG["FCF-Marge"]["schlecht"],
        CONFIG["FCF-Marge"]["gut"],
        CONFIG["FCF-Marge"]["max_punkte"]
    )


    kennzahlen = {

        "FCF-Yield":
            fcf_yield,

        "Umsatzwachstum":
            revenue_growth_pct,

        "ROIC":
            roic,

        "Net Debt / EBITDA":
            net_debt_ebitda,

        "KGV":
            trailing_pe,

        "EPS-Wachstum":
            eps_growth_pct,

        "Operative Marge":
            operating_margin_pct,

        "FCF-Marge":
            fcf_margin
    }


    # -----------------------------------------------------
    # SCORE
    # -----------------------------------------------------

    vorhandene_punkte = [
        p
        for p in punkte.values()
        if p is not None
    ]


    max_verfuegbar = sum(

        CONFIG[k]["max_punkte"]

        for k, p in punkte.items()

        if p is not None
    )


    rohe_punkte = sum(
        vorhandene_punkte
    )


    if max_verfuegbar > 0:

        score = (
            rohe_punkte
            / max_verfuegbar
            * 100
        )

    else:

        score = 0


    # -----------------------------------------------------
    # QUARTALS-FINANZDATEN
    # -----------------------------------------------------

    try:

        quartals_finanzen = (
            aktie.quarterly_financials
        )

    except:

        quartals_finanzen = (
            pd.DataFrame()
        )


    try:

        quartals_cashflow = (
            aktie.quarterly_cashflow
        )

    except:

        quartals_cashflow = (
            pd.DataFrame()
        )


    return {

        "ticker":
            ticker_symbol,

        "aktie":
            aktie,

        "name":
            name,

        "kurs":
            kurs,

        "waehrung":
            waehrung,

        "kennzahlen":
            kennzahlen,

        "punkte":
            punkte,

        "score":
            score,

        "rating":
            rating_bestimmen(score),

        "max_verfuegbar":
            max_verfuegbar,

        "quartals_finanzen":
            quartals_finanzen,

        "quartals_cashflow":
            quartals_cashflow
    }


# =========================================================
# SESSION STATE
# =========================================================

if "analyse" not in st.session_state:

    st.session_state.analyse = None


# =========================================================
# TITEL
# =========================================================

st.title(
    "📈 Aktien Rating Modell"
)

st.caption(
    "Berufsmaturitätsarbeit – Prototyp Version 2"
)


st.info(
    "Das Rating-Modell befindet sich noch in der "
    "Entwicklungsphase. Kennzahlen, Gewichtungen "
    "und Grenzwerte können später angepasst werden."
)


# =========================================================
# TICKER-EINGABE
# =========================================================

ticker = st.text_input(
    "Aktien-Ticker eingeben:",
    value="AAPL"
).strip().upper()


if st.button(
    "Aktie analysieren",
    type="primary"
):

    if ticker == "":

        st.error(
            "Bitte einen Aktien-Ticker eingeben."
        )

    else:

        try:

            with st.spinner(
                "Aktie wird analysiert..."
            ):

                st.session_state.analyse = (
                    aktie_analysieren(ticker)
                )

        except Exception as fehler:

            st.session_state.analyse = None

            st.error(
                "Die Aktie konnte nicht analysiert werden."
            )

            st.code(
                str(fehler)
            )


# =========================================================
# ERGEBNISSE
# =========================================================

if st.session_state.analyse is not None:

    analyse = st.session_state.analyse

    aktie = analyse["aktie"]

    st.divider()


    # =====================================================
    # UNTERNEHMEN
    # =====================================================

    st.header(
        f"{analyse['name']} ({analyse['ticker']})"
    )


    col1, col2, col3 = st.columns(3)


    if analyse["kurs"] is not None:

        col1.metric(
            "Aktienkurs",
            f"{analyse['kurs']:,.2f} "
            f"{analyse['waehrung']}"
        )

    else:

        col1.metric(
            "Aktienkurs",
            "Keine Daten"
        )


    col2.metric(
        "Gesamtscore",
        f"{analyse['score']:.1f} / 100"
    )


    col3.metric(
        "Rating",
        analyse["rating"]
    )


    # =====================================================
    # RATING-TACHO
    # =====================================================

    st.divider()

    st.subheader(
        "🎯 Ergebnis des Rating-Modells"
    )

    rating_tacho(
        analyse["score"]
    )


    # =====================================================
    # AKTIENKURS
    # =====================================================

    st.divider()

    st.subheader(
        "📈 Kursentwicklung"
    )


    zeitraum = st.selectbox(

        "Zeitraum auswählen:",

        [
            "1 Monat",
            "6 Monate",
            "1 Jahr",
            "5 Jahre"
        ],

        index=2,

        key="kurs_zeitraum"
    )


    perioden = {

        "1 Monat": "1mo",

        "6 Monate": "6mo",

        "1 Jahr": "1y",

        "5 Jahre": "5y"
    }


    try:

        kursdaten = aktie.history(
            period=perioden[zeitraum]
        )


        if not kursdaten.empty:

            chart_daten = (
                kursdaten[["Close"]]
                .rename(
                    columns={
                        "Close":
                            f"Kurs ({analyse['waehrung']})"
                    }
                )
            )


            st.line_chart(
                chart_daten,
                use_container_width=True
            )

        else:

            st.warning(
                "Keine Kursdaten verfügbar."
            )


    except Exception as fehler:

        st.warning(
            "Der Aktienchart konnte nicht geladen werden."
        )


    # =====================================================
    # FINANZENTWICKLUNG
    # =====================================================

    st.divider()

    st.subheader(
        "💼 Finanzentwicklung"
    )

    st.write(
        "Hier siehst du wichtige Finanzdaten "
        "des Unternehmens nach Quartalen."
    )


    tab1, tab2, tab3 = st.tabs(
        [
            "💰 Umsatz",
            "📊 Gewinn",
            "💵 Free Cashflow"
        ]
    )


    # -----------------------------------------------------
    # UMSATZ
    # -----------------------------------------------------

    with tab1:

        umsatz = zeile_suchen(

            analyse["quartals_finanzen"],

            [
                "Total Revenue",
                "Operating Revenue"
            ]
        )


        umsatz_daten = (
            quartalsdaten_vorbereiten(
                umsatz
            )
        )


        if umsatz_daten is not None:

            # Milliarden
            umsatz_daten["Wert"] = (
                umsatz_daten["Wert"]
                / 1_000_000_000
            )


            umsatz_daten = (
                umsatz_daten.rename(
                    columns={
                        "Wert":
                            f"Umsatz in Mrd. {analyse['waehrung']}"
                    }
                )
            )


            st.bar_chart(
                umsatz_daten,
                use_container_width=True
            )


        else:

            st.info(
                "Für diese Aktie sind keine "
                "Quartals-Umsatzdaten verfügbar."
            )


    # -----------------------------------------------------
    # GEWINN
    # -----------------------------------------------------

    with tab2:

        gewinn = zeile_suchen(

            analyse["quartals_finanzen"],

            [
                "Net Income",
                "Net Income Common Stockholders"
            ]
        )


        gewinn_daten = (
            quartalsdaten_vorbereiten(
                gewinn
            )
        )


        if gewinn_daten is not None:

            gewinn_daten["Wert"] = (
                gewinn_daten["Wert"]
                / 1_000_000_000
            )


            gewinn_daten = (
                gewinn_daten.rename(
                    columns={
                        "Wert":
                            f"Gewinn in Mrd. {analyse['waehrung']}"
                    }
                )
            )


            st.bar_chart(
                gewinn_daten,
                use_container_width=True
            )


        else:

            st.info(
                "Für diese Aktie sind keine "
                "Quartals-Gewinndaten verfügbar."
            )


    # -----------------------------------------------------
    # FREE CASHFLOW
    # -----------------------------------------------------

    with tab3:

        fcf = zeile_suchen(

            analyse["quartals_cashflow"],

            [
                "Free Cash Flow"
            ]
        )


        # Falls Yahoo FCF nicht direkt liefert,
        # versuchen wir FCF selbst zu berechnen.

        if fcf is None:

            operating_cf = zeile_suchen(

                analyse["quartals_cashflow"],

                [
                    "Operating Cash Flow",
                    "Total Cash From Operating Activities"
                ]
            )


            capex = zeile_suchen(

                analyse["quartals_cashflow"],

                [
                    "Capital Expenditure",
                    "Capital Expenditures"
                ]
            )


            if (
                operating_cf is not None
                and capex is not None
            ):

                # CapEx ist bei Yahoo häufig negativ.
                fcf = (
                    operating_cf + capex
                )


        fcf_daten = (
            quartalsdaten_vorbereiten(
                fcf
            )
        )


        if fcf_daten is not None:

            fcf_daten["Wert"] = (
                fcf_daten["Wert"]
                / 1_000_000_000
            )


            fcf_daten = (
                fcf_daten.rename(
                    columns={
                        "Wert":
                            f"Free Cashflow in Mrd. {analyse['waehrung']}"
                    }
                )
            )


            st.bar_chart(
                fcf_daten,
                use_container_width=True
            )


        else:

            st.info(
                "Für diese Aktie sind keine "
                "Quartals-Free-Cashflow-Daten verfügbar."
            )


    # =====================================================
    # KENNZAHLEN
    # =====================================================

    st.divider()

    st.subheader(
        "📊 Bewertung der Kennzahlen"
    )


    zeilen = []


    prozent_kennzahlen = {

        "FCF-Yield",

        "Umsatzwachstum",

        "ROIC",

        "EPS-Wachstum",

        "Operative Marge",

        "FCF-Marge"
    }


    for (
        kennzahl,
        wert
    ) in analyse["kennzahlen"].items():


        if wert is None:

            wert_anzeige = (
                "Keine Daten"
            )


        elif kennzahl in prozent_kennzahlen:

            wert_anzeige = (
                f"{wert:.2f} %"
            )


        else:

            wert_anzeige = (
                f"{wert:.2f}"
            )


        punktzahl = (
            analyse["punkte"][
                kennzahl
            ]
        )


        if punktzahl is None:

            punkte_anzeige = (
                "Keine Daten"
            )


        else:

            punkte_anzeige = (

                f"{punktzahl:.2f} / "

                f"{CONFIG[kennzahl]['max_punkte']}"
            )


        zeilen.append({

            "Kennzahl":
                kennzahl,

            "Wert":
                wert_anzeige,

            "Punkte":
                punkte_anzeige
        })


    tabelle = pd.DataFrame(
        zeilen
    )


    st.dataframe(

        tabelle,

        use_container_width=True,

        hide_index=True
    )


    st.caption(

        f"Verfügbare Daten decken aktuell "

        f"{analyse['max_verfuegbar']} "

        f"von 100 möglichen Punkten ab."
    )


    # =====================================================
    # METHODISCHER HINWEIS
    # =====================================================

    st.warning(
        "Prototyp: Die Bewertungslogik ist noch nicht "
        "endgültig. Insbesondere ROIC und die "
        "Wachstumskennzahlen werden momentan vereinfacht "
        "berechnet. Die endgültigen Formeln, Grenzwerte "
        "und Gewichtungen werden anhand der Recherche "
        "für die BMA festgelegt."
    )