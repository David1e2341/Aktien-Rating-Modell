import streamlit as st
import yfinance as yf
import requests
import re
import pandas as pd
import math
import plotly.graph_objects as go


# =========================================================
# SEITENEINSTELLUNGEN
# =========================================================

# =========================================================
# ROBUSTE YAHOO-ABFRAGE
# =========================================================
import time

def ticker_basisdaten_robust(ticker_symbol, versuche=3):
    """Versucht Yahoo Finance mehrfach, bevor ein Fehler gemeldet wird."""
    letzter_fehler = None
    for nr in range(versuche):
        try:
            aktie = yf.Ticker(ticker_symbol)
            info = aktie.info
            if isinstance(info, dict) and info:
                return aktie, info
        except Exception as exc:
            letzter_fehler = exc
        if nr < versuche - 1:
            time.sleep(1.5 * (nr + 1))
    if letzter_fehler:
        raise letzter_fehler
    raise ValueError("Yahoo Finance hat momentan keine Basisdaten geliefert.")

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

# Reihenfolge entspricht Kapitel 3.1–3.8 der schriftlichen BMA.
CONFIG = {
    "Operative Marge": {"max_punkte": 10},
    "KGV": {"max_punkte": 10},
    "EPS-Wachstum": {"max_punkte": 10},
    "FCF-Marge": {"max_punkte": 10},
    "FCF-Yield": {"max_punkte": 15},
    "ROIC": {"max_punkte": 15},
    "Umsatzwachstum": {"max_punkte": 15},
    "Net Debt / EBITDA": {"max_punkte": 15},
}

MINDESTABDECKUNG = 70

# Öffentliche Sektor-Benchmarks (Stand Oktober 2026).
# Fair Value Calculator: KGV, EBIT-Marge, Umsatzwachstum.
SEKTOR_BENCHMARKS = {
    "Financial Services": {
        "KGV": (8.2, 11.9, 18.9),
        "Operative Marge": (11.8, 34.3, 53.6),
        "Umsatzwachstum": (-1.3, 8.2, 24.8),
    },
    "Real Estate": {
        "KGV": (7.5, 12.4, 24.1),
        "Operative Marge": (2.1, 20.4, 51.1),
        "Umsatzwachstum": (-11.0, 1.5, 16.2),
    },
    "Energy": {
        "KGV": (9.0, 15.1, 24.9),
        "Operative Marge": (1.7, 11.2, 27.9),
        "Umsatzwachstum": (-11.9, 1.5, 20.8),
    },
    "Utilities": {
        "KGV": (10.6, 17.2, 26.6),
        "Operative Marge": (4.6, 13.6, 25.0),
        "Umsatzwachstum": (-7.5, 0.7, 14.4),
    },
    "Communication Services": {
        "KGV": (9.8, 17.3, 35.4),
        "Operative Marge": (-3.3, 6.1, 15.9),
        "Umsatzwachstum": (-7.7, 1.6, 15.7),
    },
    "Consumer Defensive": {
        "KGV": (11.2, 17.3, 28.4),
        "Operative Marge": (0.7, 5.6, 12.2),
        "Umsatzwachstum": (-4.3, 2.9, 13.7),
    },
    "Consumer Cyclical": {
        "KGV": (11.1, 18.0, 32.7),
        "Operative Marge": (0.3, 5.4, 11.6),
        "Umsatzwachstum": (-7.0, 2.7, 13.4),
    },
    "Basic Materials": {
        "KGV": (11.3, 18.4, 34.8),
        "Operative Marge": (0.9, 7.1, 14.5),
        "Umsatzwachstum": (-6.4, 3.3, 22.0),
    },
    "Industrials": {
        "KGV": (12.4, 20.6, 37.3),
        "Operative Marge": (1.3, 6.9, 14.0),
        "Umsatzwachstum": (-6.4, 4.6, 18.8),
    },
    "Healthcare": {
        "KGV": (14.4, 24.2, 42.9),
        "Operative Marge": (0.0, 8.0, 16.6),
        "Umsatzwachstum": (-4.9, 4.3, 18.1),
    },
    "Technology": {
        "KGV": (15.6, 28.3, 54.8),
        "Operative Marge": (-0.8, 5.6, 14.2),
        "Umsatzwachstum": (-4.9, 8.4, 25.3),
    },
}

# Basis Report: 5-Jahres-EPS-CAGR-Sektormediane.
EPS_5J_SEKTOR = {
    "Technology": 15.0,
    "Healthcare": 12.0,
    "Financial Services": 10.0,
    "Consumer Cyclical": 11.0,
    "Energy": 8.0,
    "Industrials": 9.0,
    "Utilities": 5.0,
    "Basic Materials": 8.0,
    "Communication Services": 10.0,
    "Real Estate": 6.0,
    "Consumer Defensive": 7.0,
}

# Basis Report: FCF-Yield TTM; Reihenfolge = P25, Median, P75.
FCF_YIELD_SEKTOR = {
    "Technology": (1.0, 3.0, 6.0),
    "Healthcare": (0.5, 2.0, 5.0),
    "Communication Services": (1.0, 4.0, 8.0),
    "Real Estate": (0.5, 2.0, 4.0),
    "Consumer Defensive": (2.0, 4.0, 7.0),
    "Consumer Cyclical": (0.5, 2.0, 5.0),
    "Utilities": (0.5, 2.0, 4.0),
    "Industrials": (1.0, 3.0, 6.0),
    "Basic Materials": (1.0, 4.0, 8.0),
    "Energy": (1.0, 7.0, 14.0),
    # Financial Services: Quelle bezeichnet FCF Yield für Financials als N/A.
}

# FCF-Marge:
# Die bisher dokumentierte CSIMarket-Quelle zeigt öffentlich FCF Margin,
# aber die P25/Median/P75-Verteilung ist lizenzpflichtig. Deshalb werden
# hier bewusst KEINE erfundenen Quartile eingetragen.
FCF_MARGIN_SEKTOR = {}



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


def linear(x, x0, y0, x1, y1):
    if x1 == x0:
        return y0
    return y0 + (x - x0) * (y1 - y0) / (x1 - x0)


def stueckweise(wert, paare, max_punkte):
    if wert is None:
        return None
    paare = sorted(paare)
    if wert <= paare[0][0]:
        return max(0.0, min(max_punkte, paare[0][1]))
    if wert >= paare[-1][0]:
        return max(0.0, min(max_punkte, paare[-1][1]))
    for (x0, y0), (x1, y1) in zip(paare, paare[1:]):
        if x0 <= wert <= x1:
            return max(0.0, min(max_punkte, linear(wert, x0, y0, x1, y1)))
    return None


def punkte_hoeher_besser(wert, p25, median, p75, p25_pts, med_pts, p75_pts, max_pts,
                         null_negativ_null=False):
    if wert is None:
        return None
    if null_negativ_null and wert <= 0:
        return 0.0
    unten = p25 - (median - p25)
    oben = p75 + (p75 - median)
    return stueckweise(wert, [(unten, 0), (p25, p25_pts), (median, med_pts),
                              (p75, p75_pts), (oben, max_pts)], max_pts)


def kgv_punkte(kgv, eps_ttm, p25, median, p75):
    if eps_ttm is None or eps_ttm <= 0:
        return 0.0
    if kgv is None:
        return None
    oben = p75 + (p75 - median)
    return stueckweise(kgv, [(p25, 10), (median, 7), (p75, 4), (oben, 0)], 10)


def net_debt_ebitda_punkte(verhaeltnis, ebitda):
    if ebitda is None:
        return None
    if ebitda <= 0:
        return 0.0
    if verhaeltnis is None:
        return None
    return stueckweise(verhaeltnis,
                       [(1, 15), (2, 12), (3, 9.75), (4, 6.75), (5, 4.5), (6, 0)], 15)


def cagr(start, ende, jahre):
    if start is None or ende is None or start <= 0 or ende <= 0 or jahre <= 0:
        return None
    return ((ende / start) ** (1 / jahre) - 1) * 100


def avg(vals):
    vals = [float(v) for v in vals if v is not None and not pd.isna(v)]
    return sum(vals) / len(vals) if vals else None


def _norm_label(text):
    """Yahoo/yfinance nutzt je nach Methode z.B. 'TotalRevenue' oder 'Total Revenue'."""
    return "".join(ch.lower() for ch in str(text) if ch.isalnum())


def row(df, names):
    """Findet Finanzzeilen unabhängig von Leerzeichen, Bindestrichen und CamelCase."""
    if df is None or df.empty:
        return None

    index_map = {_norm_label(idx): idx for idx in df.index}

    # Erst exakte normalisierte Treffer.
    for name in names:
        key = _norm_label(name)
        if key in index_map:
            return df.loc[index_map[key]]

    # Danach vorsichtige Teiltreffer für leicht abweichende Yahoo-Bezeichnungen.
    for name in names:
        key = _norm_label(name)
        for norm_idx, original_idx in index_map.items():
            if key and (key in norm_idx or norm_idx in key):
                return df.loc[original_idx]

    return None


def annual_values(df, names, n=None):
    s = row(df, names)
    if s is None:
        return []
    s = s.dropna().sort_index()
    vals = list(s.values)
    return vals[-n:] if n else vals



def jahresserie(serie):
    """Nur echte Jahresabschlüsse, chronologisch alt -> neu; TTM-Spalten werden ausgeschlossen."""
    if serie is None:
        return None
    s = serie.dropna().copy()
    if s.empty:
        return None

    # yfinance kann Timestamp-Spalten und zusätzliche TTM-Spalten liefern.
    items = []
    for k, v in s.items():
        try:
            datum = pd.to_datetime(k)
        except Exception:
            continue
        if pd.isna(datum):
            continue
        items.append((datum, float(v)))

    if not items:
        return None

    items.sort(key=lambda x: x[0])
    return pd.Series([v for _, v in items], index=[d for d, _ in items], dtype=float)


def fcf_from_cashflow(cf):
    direct = row(cf, ["Free Cash Flow", "FreeCashFlow"])
    if direct is not None:
        return direct
    ocf = row(cf, ["Operating Cash Flow", "OperatingCashFlow", "Total Cash From Operating Activities", "TotalCashFromOperatingActivities"])
    capex = row(cf, ["Capital Expenditure", "CapitalExpenditure", "Capital Expenditures", "CapitalExpenditures"])
    if ocf is None or capex is None:
        return None
    # Yahoo stellt CapEx meist negativ dar. abs() macht die Definition OCF - CapEx eindeutig.
    common = ocf.index.intersection(capex.index)
    if len(common) == 0:
        return None
    return ocf[common] - capex[common].abs()


def alternative_eps_punkte(eps_werte):
    """Fallback bei Start- oder End-EPS <= 0. Erwartet chronologisch 6 Jahreswerte."""
    if len(eps_werte) < 2:
        return None
    vals = list(eps_werte)
    punkte = 3.0 if vals[-1] > 0 else 0.0
    # Neueste Verbesserung zählt am stärksten: 2.5, 2.0, 1.5, 1.0.
    gewichte = [1.0, 1.5, 2.0, 2.5]
    veraenderungen = []
    for i in range(1, len(vals)):
        veraenderungen.append(vals[i] > vals[i - 1])
    for besser, gewicht in zip(veraenderungen[-4:], gewichte[-len(veraenderungen[-4:]):]):
        if besser:
            punkte += gewicht
    return min(10.0, punkte)


def eps_punkte(cagr_wert, sektorwert):
    if cagr_wert is None or sektorwert is None:
        return None
    # Eure festgelegte Skala: -Sektorwert=0, 0%=4.5, Sektorwert=6.5, 2x=10.
    # Funktioniert sauber für positive Sektorwerte; die hinterlegten Werte sind positiv.
    return stueckweise(cagr_wert,
                       [(-sektorwert, 0), (0, 4.5), (sektorwert, 6.5), (2*sektorwert, 10)], 10)



@st.cache_data(ttl=86400, show_spinner=False)
def sec_ticker_cik_map():
    """Offizielle SEC-Zuordnung von Börsenticker zu CIK."""
    url = "https://www.sec.gov/files/company_tickers.json"
    headers = {
        "User-Agent": "BMA Aktien Rating Modell student-project contact@example.com",
        "Accept-Encoding": "gzip, deflate",
    }
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    data = r.json()

    mapping = {}
    for item in data.values():
        ticker = str(item.get("ticker", "")).upper().strip()
        cik = item.get("cik_str")
        if ticker and cik is not None:
            mapping[ticker] = str(int(cik)).zfill(10)
    return mapping


@st.cache_data(ttl=86400, show_spinner=False)
def eps_historisch_sec(ticker_symbol):
    """
    Historische jährliche Diluted-EPS aus SEC Company Facts.

    Wichtig:
    SEC Company Facts kann für dasselbe Geschäftsjahr mehrere 10-K-Facts
    enthalten (z.B. Vergleichsspalten in späteren Geschäftsberichten).
    Deshalb wird nicht einfach der zuletzt eingereichte Fact genommen.

    Bevorzugt wird der Fact, dessen Zeitraum zum angegebenen Geschäftsjahr
    gehört und dessen 'fp' FY ist. Bei mehreren Kandidaten wird der Fact mit
    dem plausibelsten Jahreszeitraum (ca. 12 Monate) gewählt.
    """
    ticker = str(ticker_symbol).upper().strip().replace(".", "-")
    try:
        mapping = sec_ticker_cik_map()
        cik = mapping.get(ticker)
        if not cik:
            return []

        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        headers = {
            "User-Agent": "BMA Aktien Rating Modell student-project contact@example.com",
            "Accept-Encoding": "gzip, deflate",
        }
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()

        us_gaap = data.get("facts", {}).get("us-gaap", {})
        concept = None
        for tag in ("EarningsPerShareDiluted",
                    "EarningsPerShareDilutedIncludingExtraordinaryItems"):
            if tag in us_gaap:
                concept = us_gaap[tag]
                break
        if not concept:
            return []

        units = concept.get("units", {})
        facts = (
            units.get("USD/shares")
            or units.get("USD-per-shares")
            or units.get("USD / shares")
            or []
        )
        if not facts:
            for unit_name, unit_facts in units.items():
                if "share" in unit_name.lower():
                    facts = unit_facts
                    break

        candidates = {}
        for fact in facts:
            if fact.get("form") not in ("10-K", "10-K/A"):
                continue
            if fact.get("fp") not in (None, "FY"):
                continue

            fy = fact.get("fy")
            val = fact.get("val")
            start_date = fact.get("start")
            end_date = fact.get("end")
            if fy is None or val is None or not start_date or not end_date:
                continue

            try:
                year = int(fy)
                value = float(val)
                start_ts = pd.Timestamp(start_date)
                end_ts = pd.Timestamp(end_date)
                days = (end_ts - start_ts).days
            except Exception:
                continue

            # EPS-Jahresfact muss ungefähr ein Geschäftsjahr umfassen.
            if not (330 <= days <= 380):
                continue

            # Ein Geschäftsjahr endet normalerweise im FY-Kalenderjahr.
            # Kleine Sonderfälle um den Jahreswechsel werden toleriert.
            end_year_distance = abs(int(end_ts.year) - year)
            if end_year_distance > 1:
                continue

            # Priorität:
            # 1) Periodenende liegt im FY-Jahr
            # 2) Dauer möglichst nahe an 365 Tagen
            # 3) ursprüngliche/ältere Einreichung statt späterer Vergleichs-Facts
            score = (
                0 if int(end_ts.year) == year else 1,
                abs(days - 365),
                str(fact.get("filed", "9999-99-99")),
            )

            candidates.setdefault(year, []).append((score, value))

        annual = {}
        for year, items in candidates.items():
            items.sort(key=lambda x: x[0])
            annual[year] = items[0][1]

        return sorted(annual.items())

    except Exception:
        return []


def eps_serie_mit_fallback(ticker_symbol, yahoo_eps):
    """
    Yahoo Finance bleibt Hauptquelle.
    Wenn weniger als sechs Jahreswerte vorhanden sind, ergänzt SEC EDGAR
    fehlende historische Diluted-EPS für SEC-Filer.
    """
    werte = {}
    if yahoo_eps is not None:
        s = jahresserie(yahoo_eps)
        if s is not None:
            for datum, wert in s.items():
                werte[int(pd.Timestamp(datum).year)] = float(wert)

    quelle = "Yahoo Finance"

    # Das letzte abgeschlossene Geschäftsjahr wird aus Yahoo bestimmt.
    # Dadurch können SEC-Werte aus einem späteren/noch nicht abgeschlossenen
    # Geschäftsjahr nicht versehentlich in den 5-Jahres-CAGR gelangen.
    letztes_abgeschlossenes_jahr = max(werte.keys()) if werte else None

    if len(werte) < 6:
        sec_werte = eps_historisch_sec(ticker_symbol)
        if sec_werte:
            for jahr, wert in sec_werte:
                jahr = int(jahr)

                # SEC nur bis zum letzten von Yahoo bestätigten abgeschlossenen Jahr.
                if letztes_abgeschlossenes_jahr is not None and jahr > letztes_abgeschlossenes_jahr:
                    continue

                # Sobald der SEC-Fallback nötig ist, ist SEC für die historischen
                # Jahres-EPS massgebend. So vermeiden wir falsch zugeordnete
                # Yahoo-Jahreslabels bei überlappenden Jahren.
                werte[jahr] = float(wert)

            quelle = "Yahoo Finance + SEC EDGAR (SEC für historische Jahres-EPS)"

    # Zusätzlich defensiv alle späteren Jahre entfernen.
    if letztes_abgeschlossenes_jahr is not None:
        werte = {
            jahr: wert for jahr, wert in werte.items()
            if jahr <= letztes_abgeschlossenes_jahr
        }

    return sorted(werte.items()), quelle


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
    """Interaktives Rating-Diagramm mit farbigen Bereichen und Score-Markierung."""
    score = max(0, min(100, float(score)))
    rating = rating_bestimmen(score)
    farben = ["#dc2626", "#f97316", "#eab308", "#22c55e", "#15803d"]
    grenzen = [(0, 30), (30, 45), (45, 65), (65, 80), (80, 100)]
    namen = ["Sell", "Underperform", "Hold", "Buy", "Strong Buy"]

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number={"suffix": " / 100 Punkte", "valueformat": ".1f", "font": {"size": 23}},
        title={"text": f"<b>{rating}</b>", "font": {"size": 25}},
        gauge={
            "axis": {"range": [0, 100], "tickvals": [0, 30, 45, 65, 80, 100]},
            "bar": {"color": "#334155", "thickness": 0.12},
            "bgcolor": "rgba(0,0,0,0)",
            "steps": [{"range": list(grenze), "color": farbe}
                      for grenze, farbe in zip(grenzen, farben)],
            "threshold": {"line": {"color": "#111827", "width": 5},
                          "thickness": 0.85, "value": score},
        },
        domain={"x": [0.06, 0.94], "y": [0.08, 0.94]},
    ))
    fig.update_layout(
        height=340,
        margin=dict(l=35, r=35, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#334155"),
    )
    links, mitte, rechts = st.columns([1, 2, 1])
    with mitte:
        st.plotly_chart(fig, use_container_width=True,
                        config={"displayModeBar": False})
    st.caption("  ·  ".join(
        f"{name}: {start}–{ende} Punkte"
        for name, (start, ende) in zip(namen, grenzen)
    ))


def diagramm_anzeigen(daten, art="linie", einheit=None):
    """Diagramm mit klarer Achsenbeschriftung und Einheiten im Tooltip."""
    if daten is None or daten.empty:
        return
    einheit = einheit or str(daten.columns[0])
    fig = go.Figure()
    for spalte in daten.columns:
        if art == "balken":
            fig.add_trace(go.Bar(
                x=daten.index, y=daten[spalte], name=str(spalte),
                hovertemplate=f"%{{x}}<br>%{{y:,.2f}} {einheit}<extra></extra>",
            ))
        else:
            fig.add_trace(go.Scatter(
                x=daten.index, y=daten[spalte], mode="lines",
                name=str(spalte), line=dict(width=2),
                hovertemplate=f"%{{x}}<br>%{{y:,.2f}} {einheit}<extra></extra>",
            ))
    fig.update_layout(
        height=430,
        margin=dict(l=35, r=25, t=35, b=65),
        dragmode="zoom",
        hovermode="x unified" if art == "linie" else "closest",
        xaxis=dict(title="Datum" if art == "linie" else "Quartal", automargin=True),
        yaxis=dict(title=einheit, automargin=True, fixedrange=False,
                   tickformat=",.2f"),
        showlegend=False,
    )
    st.plotly_chart(
        fig, use_container_width=True,
        config={
            "scrollZoom": False,
            "doubleClick": "reset",
            "displaylogo": False,
            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
        },
    )


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
# FCF-MARGE – ÖFFENTLICHE SEKTOR-QUARTILE
# ValueScreener Open Research, Messung 12.10.2026
# =========================================================
FCF_MARGIN_SEKTOR_2026 = {
    "Technology": (-14.12, 7.53, 19.37),
    "Healthcare": (-278.78, -15.27, 8.49),
    "Industrials": (-9.17, 3.72, 11.05),
    "Consumer Cyclical": (-1.79, 3.91, 8.84),
    "Consumer Defensive": (-3.35, 3.69, 10.68),
    "Basic Materials": (-3.62, 3.49, 10.29),
    "Communication Services": (-1.38, 5.86, 14.49),
    "Energy": (-2.29, 5.17, 12.80),
    "Real Estate": (-3.00, 10.30, 32.50),
    "Financial Services": (-5.80, 13.42, 29.75),
    "Utilities": (-20.27, -8.07, 1.71),
}

def fcf_margin_punkte(wert, p25, median, p75):
    if wert is None:
        return None
    x=float(wert); p25=float(p25); median=float(median); p75=float(p75)
    lower=p25-(median-p25)
    upper=p75+(p75-median)
    if x <= lower: return 0.0
    if x <= p25: return (x-lower)/(p25-lower)*3.0
    if x <= median: return 3.0+(x-p25)/(median-p25)*3.5
    if x <= p75: return 6.5+(x-median)/(p75-median)*1.5
    if x <= upper: return 8.0+(x-p75)/(upper-p75)*2.0
    return 10.0

# =========================================================
# DAMODARAN ROIC-BRANCHENVERGLEICH
# =========================================================

@st.cache_data(ttl=86400, show_spinner=False)
def damodaran_roic_tabelle():
    """
    Lädt Damodarans öffentliche US-Branchenwerte 'Margin / ROIC by Sector'.
    Verwendet wird die Spalte 'Return on Capital', passend zu unserem
    NOPAT / Invested-Capital-Ansatz.
    """
    url = "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/mgnroc.html"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        tables = pd.read_html(r.text)
        for df in tables:
            cols = [str(c).strip() for c in df.columns]
            if any("Industry" in c for c in cols) and any("Return on Capital" in c for c in cols):
                df.columns = cols
                industry_col = next(c for c in cols if "Industry" in c)
                roc_col = next(c for c in cols if "Return on Capital" in c)
                result = {}
                for _, row_ in df.iterrows():
                    name = str(row_[industry_col]).strip()
                    raw = row_[roc_col]
                    if not name or name.lower() == "nan":
                        continue
                    txt = str(raw).replace("%", "").replace(",", "").strip()
                    try:
                        result[name] = float(txt)
                    except Exception:
                        continue
                return result
    except Exception:
        pass
    return {}


# Explizite Zuordnung häufiger Yahoo-Finance-Industrien.
# Wenn keine eindeutige Zuordnung existiert, wird ROIC bewusst nicht bewertet.
YAHOO_DAMODARAN_MAP = {
    "Semiconductors": "Semiconductor",
    "Semiconductor Equipment & Materials": "Semiconductor Equip",
    "Software - Infrastructure": "Software (System & Application)",
    "Software - Application": "Software (System & Application)",
    "Electronic Components": "Electronics (General)",
    "Consumer Electronics": "Electronics (Consumer & Office)",
    "Computer Hardware": "Computers/Peripherals",
    "Information Technology Services": "Computer Services",
    "Internet Content & Information": "Information Services",
    "Communication Equipment": "Telecom. Equipment",
    "Telecom Services": "Telecom. Services",
    "Auto Manufacturers": "Auto & Truck",
    "Auto Parts": "Auto Parts",
    "Aerospace & Defense": "Aerospace/Defense",
    "Farm & Heavy Construction Machinery": "Machinery",
    "Specialty Industrial Machinery": "Machinery",
    "Engineering & Construction": "Engineering/Construction",
    "Building Materials": "Building Materials",
    "Specialty Chemicals": "Chemical (Specialty)",
    "Chemicals": "Chemical (Diversified)",
    "Steel": "Steel",
    "Gold": "Precious Metals",
    "Other Precious Metals & Mining": "Precious Metals",
    "Other Industrial Metals & Mining": "Metals & Mining",
    "Oil & Gas Integrated": "Oil/Gas (Integrated)",
    "Oil & Gas E&P": "Oil/Gas (Production and Exploration)",
    "Oil & Gas Midstream": "Oil/Gas Distribution",
    "Oil & Gas Equipment & Services": "Oilfield Svcs/Equip.",
    "Utilities - Regulated Electric": "Power",
    "Utilities - Diversified": "Utility (General)",
    "Utilities - Regulated Water": "Utility (Water)",
    "Biotechnology": "Drugs (Biotechnology)",
    "Drug Manufacturers - General": "Drugs (Pharmaceutical)",
    "Drug Manufacturers - Specialty & Generic": "Drugs (Pharmaceutical)",
    "Medical Devices": "Healthcare Products",
    "Medical Instruments & Supplies": "Healthcare Products",
    "Healthcare Plans": "Healthcare Support Services",
    "Health Information Services": "Heathcare Information and Technology",
    "Medical Care Facilities": "Hospitals/Healthcare Facilities",
    "Banks - Diversified": "Bank (Money Center)",
    "Banks - Regional": "Banks (Regional)",
    "Asset Management": "Investments & Asset Management",
    "Capital Markets": "Brokerage & Investment Banking",
    "Insurance - Diversified": "Insurance (General)",
    "Insurance - Life": "Insurance (Life)",
    "Insurance - Property & Casualty": "Insurance (Prop/Cas.)",
    "REIT - Diversified": "R.E.I.T.",
    "Real Estate Services": "Real Estate (Operations & Services)",
    "Real Estate - Development": "Real Estate (Development)",
    "Restaurants": "Restaurant/Dining",
    "Lodging": "Hotel/Gaming",
    "Resorts & Casinos": "Hotel/Gaming",
    "Discount Stores": "Retail (General)",
    "Department Stores": "Retail (General)",
    "Specialty Retail": "Retail (Special Lines)",
    "Home Improvement Retail": "Retail (Building Supply)",
    "Auto & Truck Dealerships": "Retail (Automotive)",
    "Grocery Stores": "Retail (Grocery and Food)",
    "Food Distribution": "Food Wholesalers",
    "Packaged Foods": "Food Processing",
    "Beverages - Non-Alcoholic": "Beverage (Soft)",
    "Beverages - Brewers": "Beverage (Alcoholic)",
    "Tobacco": "Tobacco",
    "Household & Personal Products": "Household Products",
    "Apparel Manufacturing": "Apparel",
    "Footwear & Accessories": "Shoe",
    "Entertainment": "Entertainment",
    "Broadcasting": "Broadcasting",
    "Publishing": "Publishing & Newspapers",
    "Advertising Agencies": "Advertising",
    "Education & Training Services": "Education",
    "Waste Management": "Environmental & Waste Services",
    "Railroads": "Transportation (Railroads)",
    "Trucking": "Trucking",
    "Airlines": "Air Transport",
    "Marine Shipping": "Shipbuilding & Marine",    "Uranium": "Metals & Mining",
    "Internet Content & Information": "Information Services",
    "Software - Infrastructure": "Software (System & Application)",
    "Software - Application": "Software (System & Application)",
    "Semiconductors": "Semiconductor",
    "Semiconductor Equipment & Materials": "Semiconductor Equip",
}


def roic_punkte(roic_wert, benchmark):
    """Eigene festgelegte ROIC-Punktevergabe, Maximum 15."""
    if roic_wert is None or benchmark is None:
        return None

    r = float(roic_wert)
    b = float(benchmark)

    # Positiver Branchenvergleich:
    # <=0 -> 0; B -> 9.75; 2B -> 15; dazwischen linear.
    if b > 0:
        if r <= 0:
            return 0.0
        if r <= b:
            return 9.75 * (r / b)
        if r <= 2 * b:
            return 9.75 + (r - b) / b * (15.0 - 9.75)
        return 15.0

    # Negativer Branchenvergleich:
    # 2B oder schlechter -> 0; B -> 9.75; 0 -> 12; 5%+ -> 15.
    if b < 0:
        if r <= 2 * b:
            return 0.0
        if r <= b:
            return (r - 2 * b) / (b - 2 * b) * 9.75
        if r <= 0:
            return 9.75 + (r - b) / (0 - b) * (12.0 - 9.75)
        if r <= 5:
            return 12.0 + (r / 5.0) * 3.0
        return 15.0

    # Sonderfall B = 0: konservative, transparente Skala.
    if r <= 0:
        return 0.0
    if r <= 5:
        return 12.0 + (r / 5.0) * 3.0
    return 15.0


# =========================================================
# AKTIE ANALYSIEREN
# =========================================================

def aktie_analysieren(ticker_symbol):
    aktie, info = ticker_basisdaten_robust(ticker_symbol)
    if not info:
        raise ValueError("Für diesen Ticker wurden momentan keine Daten gefunden.")

    # Dieses Modell bewertet einzelne Aktien, nicht Fonds/ETFs/Indizes/Kryptowährungen.
    quote_type = str(info.get("quoteType", "") or "").upper()
    if quote_type in {"ETF", "MUTUALFUND", "INDEX", "CRYPTOCURRENCY"}:
        typ_name = {
            "ETF": "ETF",
            "MUTUALFUND": "Fonds",
            "INDEX": "Index",
            "CRYPTOCURRENCY": "Kryptowährung",
        }.get(quote_type, quote_type)
        raise ValueError(
            f"{ticker_symbol.upper()} ist ein {typ_name} und keine einzelne Aktie. "
            "Dieses Aktien-Rating-Modell bewertet nur einzelne Unternehmen."
        )

    name = info.get("longName", ticker_symbol.upper())
    kurs = sicherer_wert(info, "currentPrice") or sicherer_wert(info, "regularMarketPrice")
    waehrung = info.get("currency", "")
    sektor = info.get("sector", "Unbekannt")
    yahoo_industry = info.get("industry", "Unbekannt")

    # Tabellen laden
    # Explizit yearly/quarterly laden. Das vermeidet Verwechslungen mit TTM-Daten.
    fin = aktie.get_income_stmt(freq="yearly")
    bs = aktie.get_balance_sheet(freq="yearly")
    cf = aktie.get_cashflow(freq="yearly")
    qfin = aktie.get_income_stmt(freq="quarterly")
    qcf = aktie.get_cashflow(freq="quarterly")

    gruende = {}

    # ---------- FCF Yield: TTM ----------
    market_cap = sicherer_wert(info, "marketCap")
    q_fcf = fcf_from_cashflow(qcf)
    fcf_ttm = None
    if q_fcf is not None:
        q_fcf = q_fcf.dropna().sort_index()
        if len(q_fcf) >= 4:
            fcf_ttm = float(q_fcf.iloc[-4:].sum())
    if fcf_ttm is None:
        fcf_ttm = sicherer_wert(info, "freeCashflow")
    fcf_yield = (fcf_ttm / market_cap * 100) if fcf_ttm is not None and market_cap not in (None, 0) else None

    # ---------- Jahreswerte ----------
    rev_s = jahresserie(row(fin, ["Total Revenue", "TotalRevenue", "Operating Revenue", "OperatingRevenue"]))
    opinc_s = jahresserie(row(fin, ["Operating Income", "OperatingIncome", "EBIT"]))
    eps_s = jahresserie(row(fin, ["Diluted EPS", "DilutedEPS", "Basic EPS", "BasicEPS", "Diluted EPS Continuous Operations", "DilutedEPSContinuousOperations"]))
    pretax_s = jahresserie(row(fin, ["Pretax Income", "PretaxIncome", "Income Before Tax"]))
    tax_s = jahresserie(row(fin, ["Tax Provision", "TaxProvision", "Income Tax Expense"]))
    annual_fcf = jahresserie(fcf_from_cashflow(cf))

    # Operative Marge: jedes Jahr separat, danach arithmetischer 3-Jahres-Durchschnitt.
    op_margins = []
    if rev_s is not None and opinc_s is not None:
        common = rev_s.index.intersection(opinc_s.index)
        for d in list(common)[-3:]:
            r = float(rev_s.loc[d])
            o = float(opinc_s.loc[d])
            if r > 0:
                op_margins.append(o / r * 100)
    operating_margin_pct = avg(op_margins) if len(op_margins) == 3 else None

    # Umsatzwachstum: 3-Jahres-CAGR benötigt vier Jahresendpunkte.
    revenue_growth_pct = None
    if rev_s is not None and len(rev_s) >= 4:
        revenue_growth_pct = cagr(float(rev_s.iloc[-4]), float(rev_s.iloc[-1]), 3)

    # EPS-Wachstum: Yahoo als Hauptquelle, SEC EDGAR nur als historischer Fallback.
    eps_growth_pct = None
    eps_alt_punkte = None
    eps_methode = None
    eps_quelle = None

    eps_history, eps_quelle = eps_serie_mit_fallback(ticker_symbol, eps_s)

    if len(eps_history) >= 6:
        six = eps_history[-6:]
        six_values = [float(v) for _, v in six]

        if six_values[0] > 0 and six_values[-1] > 0:
            eps_growth_pct = cagr(six_values[0], six_values[-1], 5)
            eps_methode = f"5-Jahres-CAGR ({six[0][0]}–{six[-1][0]})"
        else:
            eps_alt_punkte = alternative_eps_punkte(six_values)
            eps_methode = f"Alternative EPS-Methode ({six[0][0]}–{six[-1][0]})"
    elif len(eps_history) >= 2:
        # Sonderfall junge Unternehmen: Die vorhandenen Jahresvergleiche werden
        # nach derselben alternativen Logik bewertet. Nicht vorhandene ältere
        # Vergleiche geben keine Zusatzpunkte.
        vals = [float(v) for _, v in eps_history[-6:]]
        current_positive = 3.0 if vals[-1] > 0 else 0.0
        weights = [2.5, 2.0, 1.5, 1.0]
        improvements = 0.0
        for i in range(1, min(len(vals), 5)):
            if vals[-i] > vals[-i-1]:
                improvements += weights[i-1]
        eps_alt_punkte = current_positive + improvements
        eps_methode = f"Alternative EPS-Methode mit verfügbarer Historie ({len(vals)} Jahreswerte)"
    else:
        eps_methode = f"Nicht genügend Jahreswerte ({len(eps_history)}/2)"

    # FCF-Marge: jedes Jahr separat, danach arithmetischer 3-Jahres-Durchschnitt.
    fcf_margin = None
    fcf_margins = []
    if annual_fcf is not None and rev_s is not None:
        common = annual_fcf.index.intersection(rev_s.index)
        for d in list(common)[-3:]:
            f = float(annual_fcf.loc[d])
            r = float(rev_s.loc[d])
            if r > 0:
                fcf_margins.append(f / r * 100)
    fcf_margin = avg(fcf_margins) if len(fcf_margins) == 3 else None

    # Net Debt / EBITDA: aktuelle Werte; EBITDA <= 0 wird später mit 0 Punkten bewertet.
    total_debt = sicherer_wert(info, "totalDebt")
    cash = sicherer_wert(info, "totalCash")
    ebitda = sicherer_wert(info, "ebitda")
    net_debt = total_debt - cash if total_debt is not None and cash is not None else None
    net_debt_ebitda = net_debt / ebitda if net_debt is not None and ebitda is not None and ebitda > 0 else None

    # KGV TTM
    trailing_pe = sicherer_wert(info, "trailingPE")
    eps_ttm = sicherer_wert(info, "trailingEps")

    # ROIC: Durchschnitt der letzten 3 Geschäftsjahre.
    # Invested Capital = Eigenkapital + verzinsliche Schulden - liquide Mittel.
    # Effektiver Steuersatz = Durchschnitt gültiger profitabler Jahre.
    tax_rates = []
    if pretax_s is not None and tax_s is not None:
        common = pretax_s.index.intersection(tax_s.index)
        for d in list(common)[-3:]:
            pre = float(pretax_s.loc[d])
            tax = float(tax_s.loc[d])
            if pre > 0:
                rate = tax / pre
                if 0 <= rate <= 1:
                    tax_rates.append(rate)
    # Wenn kein profitables Jahr vorhanden ist, gibt es für die ROIC-Berechnung
    # keinen positiven Steuerabzug auf NOPAT. Deshalb 0 % statt "nicht berechenbar".
    avg_tax = avg(tax_rates)
    if avg_tax is None and opinc_s is not None:
        recent_op = [float(x) for x in opinc_s.iloc[-3:].tolist()]
        if recent_op and all(x <= 0 for x in recent_op):
            avg_tax = 0.0

    equity_s = jahresserie(row(bs, ["Stockholders Equity", "StockholdersEquity", "Total Stockholder Equity", "Common Stock Equity", "CommonStockEquity"]))
    debt_s = jahresserie(row(bs, ["Total Debt", "TotalDebt"]))
    cash_s = jahresserie(row(bs, ["Cash Cash Equivalents And Short Term Investments", "CashCashEquivalentsAndShortTermInvestments",
                                   "Cash And Cash Equivalents", "CashAndCashEquivalents", "Cash"]))
    roics = []
    if avg_tax is not None and opinc_s is not None and equity_s is not None and debt_s is not None and cash_s is not None:
        common = opinc_s.index.intersection(equity_s.index).intersection(debt_s.index).intersection(cash_s.index)
        for d in list(common)[-3:]:
            ebit = float(opinc_s.loc[d])
            invested = float(equity_s.loc[d] + debt_s.loc[d] - cash_s.loc[d])
            if invested > 0:
                nopat = ebit * (1 - avg_tax)
                roics.append(nopat / invested * 100)
    roic = avg(roics) if len(roics) == 3 else None

    # ---------- Punkte ----------
    punkte = {k: None for k in CONFIG}

    bench = SEKTOR_BENCHMARKS.get(sektor)
    if bench:
        p25, med, p75 = bench["KGV"]
        punkte["KGV"] = kgv_punkte(trailing_pe, eps_ttm, p25, med, p75)

        p25, med, p75 = bench["Operative Marge"]
        punkte["Operative Marge"] = punkte_hoeher_besser(
            operating_margin_pct, p25, med, p75, 3, 5, 8, 10, null_negativ_null=True
        )

        p25, med, p75 = bench["Umsatzwachstum"]
        punkte["Umsatzwachstum"] = punkte_hoeher_besser(
            revenue_growth_pct, p25, med, p75, 4.5, 9.75, 12, 15
        )
    else:
        gruende["KGV"] = "Für den Sektor wurde kein Vergleichswert gefunden."
        gruende["Operative Marge"] = "Für den Sektor wurde kein Vergleichswert gefunden."
        gruende["Umsatzwachstum"] = "Für den Sektor wurde kein Vergleichswert gefunden."

    fy_bench = FCF_YIELD_SEKTOR.get(sektor)
    if fy_bench:
        p25, med, p75 = fy_bench
        punkte["FCF-Yield"] = punkte_hoeher_besser(
            fcf_yield, p25, med, p75, 6.75, 9.75, 12, 15, null_negativ_null=True
        )
    else:
        gruende["FCF-Yield"] = ("FCF Yield ist für diesen Sektor nicht sinnvoll bzw. "
                                "es ist kein öffentlicher Vergleichswert hinterlegt.")

    sektor_eps = EPS_5J_SEKTOR.get(sektor)
    if eps_alt_punkte is not None:
        punkte["EPS-Wachstum"] = eps_alt_punkte
    elif eps_growth_pct is not None and sektor_eps is not None:
        punkte["EPS-Wachstum"] = eps_punkte(eps_growth_pct, sektor_eps)
    else:
        gruende["EPS-Wachstum"] = "Es sind nicht genügend historische Jahres-EPS für eine Bewertung verfügbar."

    punkte["Net Debt / EBITDA"] = net_debt_ebitda_punkte(net_debt_ebitda, ebitda)

    # ROIC: Yahoo-Industry -> eindeutige Damodaran-Branche -> aktueller Branchenwert.
    damodaran_industry = YAHOO_DAMODARAN_MAP.get(yahoo_industry)

    # Letzter Mapping-Fallback: keine Kennzahl erfinden, sondern einen klar
    # dokumentierten breiten Vergleich verwenden, wenn Yahoo eine neue/seltene
    # Branchenbezeichnung liefert.
    if damodaran_industry is None:
        if sektor == "Financial Services":
            damodaran_industry = "Financial Svcs. (Non-bank & Insurance)"
        else:
            damodaran_industry = "Total Market (without financials)"

    damodaran_benchmarks = damodaran_roic_tabelle()

    # Dokumentierter Fallback für den getesteten Halbleiter-Fall.
    # Quelle: Damodaran, "Margins / Return on Capital by Industry",
    # US-Daten, Januar 2026: Semiconductor = 41.83 % Return on Capital.
    DAMODARAN_ROIC_FALLBACK_2026 = {
        # Damodaran, Margin/ROIC by Sector (US), Januar 2026
        "Information Services": 25.65,
        "Software (System & Application)": 50.17,
        "Semiconductor": 41.83,
        "Semiconductor Equip": 44.88,
        "Metals & Mining": 27.22,
        "Precious Metals": 25.71,
        "Coal & Related Energy": -4.81,
        "Computer Services": 36.37,
        "Computers/Peripherals": 78.17,
        "Electronics (General)": 23.27,
        "Electronics (Consumer & Office)": -34.87,
        "Business & Consumer Services": 31.06,
        "Healthcare Products": 22.27,
        "Healthcare Support Services": 31.86,
        "Heathcare Information and Technology": 17.26,
        "Hospitals/Healthcare Facilities": 22.23,
        "Machinery": 27.27,
        "Oil/Gas (Integrated)": 8.51,
        "Oil/Gas (Production and Exploration)": 13.79,
        "Oil/Gas Distribution": 12.35,
        "Oilfield Svcs/Equip.": 12.26,
        "Power": 6.93,
        "Utility (General)": 5.99,
        "Utility (Water)": 7.25,
        "R.E.I.T.": 3.20,
        "Real Estate (Development)": 7.04,
        "Real Estate (General/Diversified)": 5.19,
        "Real Estate (Operations & Services)": 6.56,
        "Restaurant/Dining": 18.94,
        "Retail (General)": 20.60,
        "Retail (Special Lines)": 21.70,
        "Retail (Grocery and Food)": 6.98,
        "Auto & Truck": 2.62,
        "Auto Parts": 12.17,
        "Aerospace/Defense": 21.29,
        "Advertising": 37.32,
        "Entertainment": 14.27,
        "Telecom. Equipment": 52.73,
        "Telecom. Services": 12.13,
        "Food Processing": 16.44,
        "Household Products": 38.95,
        "Beverage (Soft)": 29.68,
        "Drugs (Biotechnology)": 7.26,
        "Drugs (Pharmaceutical)": 29.30,
        "Bank (Money Center)": 0.01,
        "Banks (Regional)": -0.03,
        "Brokerage & Investment Banking": -0.02,
        "Insurance (General)": 45.11,
        "Insurance (Life)": 10.77,
        "Insurance (Prop/Cas.)": 18.49,
        "Investments & Asset Management": 14.36,
        "Financial Svcs. (Non-bank & Insurance)": 1.17,
        "Total Market (without financials)": 17.69,
    }

    roic_benchmark = None
    if damodaran_industry:
        roic_benchmark = damodaran_benchmarks.get(damodaran_industry)
        if roic_benchmark is None:
            roic_benchmark = DAMODARAN_ROIC_FALLBACK_2026.get(damodaran_industry)

    if roic is not None and roic_benchmark is not None:
        punkte["ROIC"] = roic_punkte(roic, roic_benchmark)
    elif roic is None and opinc_s is not None and len(opinc_s) > 0 and float(opinc_s.iloc[-1]) <= 0:
        # Wirtschaftlicher Sonderfall: negatives aktuelles EBIT bedeutet negatives NOPAT.
        # Nach der Modellregel ROIC <= 0 erhält die Kennzahl 0 Punkte.
        punkte["ROIC"] = 0.0
        # Kein künstlicher Rohwert: 0 Punkte stammen hier aus der Verlust-Sonderregel.
    elif roic is None:
        gruende["ROIC"] = "ROIC konnte aus den benötigten Jahresdaten nicht vollständig berechnet werden."
    elif damodaran_industry is None:
        gruende["ROIC"] = (
            f"Für die Yahoo-Branche '{yahoo_industry}' ist noch keine eindeutige "
            "Damodaran-Branchenzuordnung hinterlegt."
        )
    else:
        gruende["ROIC"] = (
            f"Die Damodaran-Branche '{damodaran_industry}' wurde zugeordnet, "
            "aber der ROIC-Vergleichswert konnte weder live geladen noch aus dem "
            "dokumentierten 2026-Fallback entnommen werden."
        )

    # FCF-Marge: öffentliche ValueScreener-Sektorquartile.
    fcf_margin_benchmark = FCF_MARGIN_SEKTOR_2026.get(sektor)
    if fcf_margin is not None and fcf_margin_benchmark is not None:
        p25_fcf, median_fcf, p75_fcf = fcf_margin_benchmark
        punkte["FCF-Marge"] = fcf_margin_punkte(
            fcf_margin, p25_fcf, median_fcf, p75_fcf
        )
    elif fcf_margin is None:
        gruende["FCF-Marge"] = "FCF-Marge konnte aus den benötigten drei Geschäftsjahren nicht vollständig berechnet werden."
    else:
        gruende["FCF-Marge"] = (
            f"Für den Yahoo-Sektor '{sektor}' sind keine dokumentierten "
            "ValueScreener-FCF-Margen-Quartile hinterlegt."
        )

    # Datenfehler-Gründe ergänzen
    raw = {
        "FCF-Yield": fcf_yield,
        "Umsatzwachstum": revenue_growth_pct,
        "ROIC": roic,
        "Net Debt / EBITDA": net_debt_ebitda,
        "KGV": trailing_pe,
        "EPS-Wachstum": eps_growth_pct if eps_growth_pct is not None else (0.0 if eps_alt_punkte is not None else None),
        "Operative Marge": operating_margin_pct,
        "FCF-Marge": fcf_margin,
    }
    for k, v in raw.items():
        if v is None and k not in gruende:
            gruende[k] = "Benötigte Finanzdaten sind bei Yahoo Finance nicht vollständig verfügbar."

    max_verfuegbar = sum(CONFIG[k]["max_punkte"] for k, p in punkte.items() if p is not None)
    rohe_punkte = sum(p for p in punkte.values() if p is not None)

    if max_verfuegbar >= MINDESTABDECKUNG:
        score = rohe_punkte / max_verfuegbar * 100
        rating = rating_bestimmen(score)
    else:
        score = None
        rating = "Nicht genügend Daten"

    try:
        quartals_finanzen = aktie.quarterly_financials
    except Exception:
        quartals_finanzen = pd.DataFrame()
    try:
        quartals_cashflow = aktie.quarterly_cashflow
    except Exception:
        quartals_cashflow = pd.DataFrame()

    # Diagnose: Rohdaten der Jahresabschlüsse, damit falsche Periodenzuordnungen
    # eindeutig sichtbar werden. Nur für die Entwicklungsphase der BMA.
    diagnose = {}

    def diagnose_serie(name, serie):
        if serie is None:
            diagnose[name] = []
            return
        s = jahresserie(serie)
        if s is None:
            diagnose[name] = []
            return
        diagnose[name] = [
            {"Jahr": str(idx.date()), "Wert": float(val)}
            for idx, val in s.items()
        ]

    diagnose_serie("Revenue", row(fin, ["Total Revenue", "TotalRevenue", "Operating Revenue", "OperatingRevenue"]))
    diagnose_serie("Operating Income", row(fin, ["Operating Income", "OperatingIncome", "EBIT"]))
    diagnose_serie("Diluted EPS", row(fin, ["Diluted EPS", "DilutedEPS", "Basic EPS", "BasicEPS"]))
    diagnose["EPS Historie für Rating (nur abgeschlossene Jahre)"] = [
        {"Jahr": str(jahr), "Wert": float(wert)} for jahr, wert in eps_history
    ]
    diagnose_serie("Pretax Income", row(fin, ["Pretax Income", "PretaxIncome", "Income Before Tax"]))
    diagnose_serie("Tax Provision", row(fin, ["Tax Provision", "TaxProvision", "Income Tax Expense"]))
    diagnose_serie("Annual FCF", fcf_from_cashflow(cf))
    diagnose_serie("Equity", row(bs, ["Stockholders Equity", "StockholdersEquity", "Common Stock Equity", "CommonStockEquity"]))
    diagnose_serie("Total Debt", row(bs, ["Total Debt", "TotalDebt"]))
    diagnose_serie("Cash", row(bs, ["Cash Cash Equivalents And Short Term Investments",
                                    "CashCashEquivalentsAndShortTermInvestments",
                                    "Cash And Cash Equivalents", "CashAndCashEquivalents", "Cash"]))

    # ROIC-Diagnose: macht extreme Werte (z.B. bei sehr kleinem Invested Capital)
    # transparent, ohne den Rohwert künstlich zu deckeln.
    diagnose["ROIC Invested Capital"] = []
    if opinc_s is not None and equity_s is not None and debt_s is not None and cash_s is not None:
        common_roic = opinc_s.index.intersection(equity_s.index).intersection(debt_s.index).intersection(cash_s.index)
        for d in list(common_roic)[-3:]:
            ebit_d = float(opinc_s.loc[d])
            equity_d = float(equity_s.loc[d])
            debt_d = float(debt_s.loc[d])
            cash_d = float(cash_s.loc[d])
            invested_d = equity_d + debt_d - cash_d
            diagnose["ROIC Invested Capital"].append({
                "Jahr": str(d.date()),
                "Wert": float(invested_d),
            })

    return {
        "ticker": ticker_symbol, "aktie": aktie, "name": name, "kurs": kurs, "yahoo_industry": yahoo_industry, "damodaran_industry": damodaran_industry, "roic_benchmark": roic_benchmark, "fcf_margin_benchmark": fcf_margin_benchmark,
        "waehrung": waehrung, "sektor": sektor,
        "hinweis_finanzunternehmen": sektor == "Financial Services",
        "hinweis_reit": ("REIT" in str(yahoo_industry).upper() or "REIT" in str(name).upper()),
        "kennzahlen": raw, "punkte": punkte,
        "score": score, "rating": rating, "max_verfuegbar": max_verfuegbar,
        "rohe_punkte": rohe_punkte, "gruende": gruende, "eps_methode": eps_methode, "eps_quelle": eps_quelle, "eps_history": eps_history,
        "diagnose": diagnose,
        "quartals_finanzen": quartals_finanzen, "quartals_cashflow": quartals_cashflow,
    }




# =========================================================
# ANALYSTENPROGNOSEN (UNABHÄNGIG VOM EIGENEN RATING)
# =========================================================
@st.cache_data(ttl=3600, show_spinner=False)
def analysten_daten_laden(ticker_symbol):
    """Lädt verfügbare Analystenschätzungen von Yahoo Finance via yfinance."""
    aktie = yf.Ticker(ticker_symbol)
    daten = {}
    try:
        info = aktie.info or {}
        for feld in ("targetLowPrice", "targetMeanPrice", "targetMedianPrice",
                     "targetHighPrice", "numberOfAnalystOpinions", "recommendationMean",
                     "recommendationKey"):
            daten[feld] = info.get(feld)
    except Exception:
        pass
    try:
        trends = aktie.recommendations_summary
        if isinstance(trends, pd.DataFrame) and not trends.empty:
            daten["trends"] = trends.copy()
    except Exception:
        pass
    return daten


def vergleich_tacho(kategorie, titel, score=None, erklaerung=None):
    """Halbkreis für den direkten Vergleich. Eigenes Modell nutzt den echten Score,
    Analysten werden als Kategorie dargestellt und deshalb in der Kategorienmitte markiert."""
    positionen = {"Sell": 15, "Underperform": 37.5, "Hold": 55, "Buy": 72.5, "Strong Buy": 90}
    if kategorie not in positionen:
        st.info(f"{titel}: Keine Daten")
        return
    wert = float(score) if score is not None else positionen[kategorie]
    wert = max(0, min(100, wert))
    if score is not None:
        untertitel = f"{kategorie} · {wert:.1f} / 100"
    else:
        untertitel = kategorie
    st.markdown(f"### {titel}")
    if erklaerung:
        st.caption(erklaerung)
    fig = go.Figure(go.Indicator(
        mode="gauge",
        value=wert,
        title={"text": f"<b>{untertitel}</b>", "font": {"size": 20}},
        gauge={
            "axis": {"range": [0, 100], "tickvals": [0, 30, 45, 65, 80, 100]},
            "bar": {"color": "#334155", "thickness": 0.12},
            "bgcolor": "rgba(0,0,0,0)",
            "steps": [
                {"range": [0, 30], "color": "#dc2626"},
                {"range": [30, 45], "color": "#f97316"},
                {"range": [45, 65], "color": "#eab308"},
                {"range": [65, 80], "color": "#22c55e"},
                {"range": [80, 100], "color": "#15803d"},
            ],
            "threshold": {"line": {"color": "#111827", "width": 5}, "thickness": 0.85, "value": wert},
        },
        domain={"x": [0.05, 0.95], "y": [0.05, 0.95]},
    ))
    fig.update_layout(height=270, margin=dict(l=20, r=20, t=35, b=5),
                      paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#334155"))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def analystenprognosen_anzeigen(ticker_symbol, kurs, waehrung, eigener_score=None, eigenes_rating=None):
    st.divider()
    st.subheader("🔮 Vergleich mit Analysten")
    st.caption("Der Analystenvergleich ist nicht Bestandteil der 100 Punkte des eigenen Rating-Modells.")
    try:
        daten = analysten_daten_laden(ticker_symbol)
    except Exception:
        daten = {}

    def zahl(feld):
        wert = daten.get(feld)
        try:
            wert = float(wert)
            return wert if math.isfinite(wert) else None
        except (TypeError, ValueError):
            return None

    # Analystenkategorie transparent aus der MEHRHEIT der aktuell verfügbaren
    # Yahoo-Analystenempfehlungen bestimmen. Keine künstliche 0-100-Punktzahl.
    trends = daten.get("trends")
    analysten_rating = None
    aktuelle_stimmen = None
    if isinstance(trends, pd.DataFrame) and not trends.empty:
        aktuelle_zeile = trends.iloc[0]
        mapping = {
            "strongBuy": "Strong Buy",
            "buy": "Buy",
            "hold": "Hold",
            "sell": "Underperform",
            "strongSell": "Sell",
        }
        stimmen = {}
        for spalte, kategorie in mapping.items():
            if spalte in trends.columns:
                try:
                    stimmen[kategorie] = int(aktuelle_zeile[spalte])
                except (TypeError, ValueError):
                    pass
        if stimmen:
            max_stimmen = max(stimmen.values())
            gewinner = [k for k, v in stimmen.items() if v == max_stimmen]
            if len(gewinner) == 1:
                analysten_rating = gewinner[0]
            aktuelle_stimmen = stimmen

    # Nur falls die Verteilung nicht verfügbar ist, Yahoo-Konsens als Fallback.
    if analysten_rating is None:
        empfehlung = daten.get("recommendationKey")
        if isinstance(empfehlung, str) and empfehlung.strip() and empfehlung.lower() != "none":
            bezeichnungen = {
                "strong_buy": "Strong Buy", "buy": "Buy", "hold": "Hold",
                "underperform": "Underperform", "sell": "Sell",
            }
            analysten_rating = bezeichnungen.get(empfehlung.lower())

    st.write("**Direkter Rating-Vergleich**")
    links, rechts = st.columns(2)
    with links:
        if eigenes_rating and eigenes_rating != "Nicht genügend Daten" and eigener_score is not None:
            vergleich_tacho(
                eigenes_rating,
                "Eigene Webanwendung",
                score=eigener_score,
                erklaerung="Position = tatsächlich berechneter Gesamtscore aus den acht Kennzahlen."
            )
        else:
            st.info("Eigene Webanwendung: Nicht genügend Daten")
    with rechts:
        if analysten_rating:
            vergleich_tacho(
                analysten_rating,
                "Analystenrating",
                score=None,
                erklaerung="Kategorie = Mehrheit der aktuell verfügbaren Analystenempfehlungen bei Yahoo Finance."
            )
        else:
            st.info("Analystenrating: Keine Daten")

    if eigenes_rating and analysten_rating:
        if eigenes_rating == analysten_rating:
            st.success(f"Übereinstimmung: Beide Ratings ergeben {eigenes_rating}.")
        else:
            st.info(f"Abweichung: Webanwendung = {eigenes_rating} · Analysten = {analysten_rating}")

    # Für den Vergleich werden bewusst nur Analystenempfehlungen verwendet.
    # Kursziele sind für die Forschungsfrage nicht nötig.

    if isinstance(trends, pd.DataFrame) and not trends.empty:
        spalten = [k for k in ("period", "strongBuy", "buy", "hold", "sell", "strongSell") if k in trends.columns]
        if spalten:
            ausgabe = trends[spalten].copy()
            ausgabe = ausgabe.rename(columns={
                "period": "Zeitraum", "strongBuy": "Strong Buy", "buy": "Buy",
                "hold": "Hold", "sell": "Underperform", "strongSell": "Sell",
            })
            ausgabe["Zeitraum"] = ausgabe["Zeitraum"].replace({
                "0m": "Aktuell", "-1m": "Vor 1 Monat",
                "-2m": "Vor 2 Monaten", "-3m": "Vor 3 Monaten",
            })
            st.write("**Verteilung der Analystenempfehlungen:**")
            st.dataframe(ausgabe, hide_index=True, use_container_width=True)

    st.caption("Quelle der Analystendaten: Yahoo Finance via yfinance.")


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
    "Berufsmaturitätsarbeit – Rating-Modell"
)



# =========================================================
# TICKER-EINGABE
# =========================================================

# Firmennamen und Ticker können gesucht werden. Häufige Unternehmen sind
# auch bei einer vorübergehenden Störung der Yahoo-Suche verfügbar.
NAMEN_ZU_TICKER = {
    "microsoft": "MSFT", "apple": "AAPL", "nvidia": "NVDA",
    "micron": "MU", "micron technology": "MU", "google": "GOOGL",
    "alphabet": "GOOGL", "amazon": "AMZN", "meta": "META",
    "meta platforms": "META", "facebook": "META", "tesla": "TSLA",
    "amd": "AMD", "intel": "INTC", "intuit": "INTU", "broadcom": "AVGO",
    "netflix": "NFLX", "jpmorgan": "JPM", "jpmorgan chase": "JPM",
    "coca-cola": "KO", "coca cola": "KO", "walmart": "WMT",
    "exxon": "XOM", "exxon mobil": "XOM", "johnson & johnson": "JNJ",
    "eli lilly": "LLY", "visa": "V", "mastercard": "MA",
    "nike": "NKE", "nike inc": "NKE", "adidas": "ADS.DE",
    "nestle": "NESN.SW", "nestlé": "NESN.SW", "novartis": "NOVN.SW",
    "roche": "ROG.SW", "ubs": "UBSG.SW", "abb": "ABBN.SW",
    "berkshire hathaway": "BRK-B", "disney": "DIS", "the walt disney company": "DIS",
}

# Anzeigenamen für Offline-/Fallback-Suchvorschläge.
BEKANNTE_UNTERNEHMEN = {
    "MSFT": "Microsoft", "AAPL": "Apple", "NVDA": "Nvidia",
    "MU": "Micron Technology", "GOOGL": "Alphabet (Google)",
    "AMZN": "Amazon", "META": "Meta Platforms", "TSLA": "Tesla",
    "AMD": "AMD", "INTC": "Intel", "INTU": "Intuit", "AVGO": "Broadcom",
    "NFLX": "Netflix", "JPM": "JPMorgan Chase", "KO": "Coca-Cola",
    "WMT": "Walmart", "XOM": "Exxon Mobil", "JNJ": "Johnson & Johnson",
    "LLY": "Eli Lilly", "V": "Visa", "MA": "Mastercard",
    "NKE": "Nike", "ADS.DE": "Adidas", "NESN.SW": "Nestlé",
    "NOVN.SW": "Novartis", "ROG.SW": "Roche", "UBSG.SW": "UBS",
    "ABBN.SW": "ABB", "BRK-B": "Berkshire Hathaway", "DIS": "Disney",
}


def _suchtreffer_lokal(suchtext):
    text = suchtext.casefold().strip()
    treffer = []
    for symbol, name in BEKANNTE_UNTERNEHMEN.items():
        if text in name.casefold() or text in symbol.casefold():
            treffer.append((symbol, name))
    for name, symbol in NAMEN_ZU_TICKER.items():
        if text in name.casefold() and symbol not in {t[0] for t in treffer}:
            treffer.append((symbol, BEKANNTE_UNTERNEHMEN.get(symbol, name.title())))
    return treffer


@st.cache_data(ttl=3600, show_spinner=False)
def unternehmen_suchen(suchtext):
    """Yahoo-Suche nach Namen oder Symbol; lokale Treffer bleiben verfügbar."""
    text = suchtext.strip()
    if not text:
        return []
    lokal = _suchtreffer_lokal(text)
    remote = []
    try:
        # yfinance.Search ist in neueren yfinance-Versionen verfügbar.
        suche = yf.Search(text, max_results=12, news_count=0)
        for eintrag in suche.quotes:
            if not isinstance(eintrag, dict):
                continue
            typ = str(eintrag.get("quoteType", "")).upper()
            if typ and typ != "EQUITY":
                continue
            symbol = str(eintrag.get("symbol", "")).strip().upper()
            name = str(eintrag.get("shortname") or eintrag.get("longname") or symbol).strip()
            if symbol and name:
                remote.append((symbol, name))
    except Exception:
        # Ein Fehler in der Suchschnittstelle verhindert nicht die Ticker-Eingabe.
        pass
    kombiniert = []
    gesehen = set()
    for symbol, name in lokal + remote:
        if symbol not in gesehen:
            kombiniert.append((symbol, name))
            gesehen.add(symbol)
    return kombiniert[:12]


# Echte Autocomplete-Suche: leer = keine Vorschläge; Vorschläge erscheinen erst beim Tippen.
# Dafür wird streamlit-searchbox verwendet. Das vermeidet auch die alten Browser-Sucheingaben.
try:
    from streamlit_searchbox import st_searchbox
except ImportError:
    st.error(
        "Für die neue Aktiensuche fehlt einmalig das Paket 'streamlit-searchbox'. "
        "Installiere es mit: python -m pip install streamlit-searchbox"
    )
    st.stop()

@st.cache_data(ttl=3600, show_spinner=False)
def suchvorschlaege_autocomplete(suchtext):
    text = str(suchtext or "").strip()
    if len(text) < 2:
        return []

    treffer = unternehmen_suchen(text)
    # Wenige, relevante Treffer halten die Suche übersichtlich.
    return [f"{name} ({symbol})" for symbol, name in treffer[:6]]


def aktien_suchfunktion(suchtext):
    return suchvorschlaege_autocomplete(suchtext)


suchauswahl = st_searchbox(
    aktien_suchfunktion,
    key="aktien_autocomplete_v30",
    placeholder="Unternehmen oder Ticker suchen …",
    label="Aktie suchen:",
    clear_on_submit=False,
    edit_after_submit="option",
    style_overrides={
        "clear": {"width": 17, "height": 17},
        "dropdown": {"width": 17, "height": 17},
        "searchbox": {
            # Kompakter wie die früheren Versionen: weniger Höhe und kleinere Schrift.
            "control": {
                "minHeight": "40px",
                "height": "40px",
                "fontSize": "15px",
            },
            "input": {
                "fontSize": "15px",
                "margin": "0px",
                "paddingTop": "0px",
                "paddingBottom": "0px",
            },
            "placeholder": {
                "fontSize": "15px",
            },
            "singleValue": {
                "fontSize": "15px",
            },
            "option": {
                "fontSize": "15px",
                "paddingTop": "8px",
                "paddingBottom": "8px",
            },
            "menuList": {
                "paddingTop": "2px",
                "paddingBottom": "2px",
                "maxHeight": "220px",
            },
        },
    },
)

ticker = ""
if suchauswahl:
    eingabe = str(suchauswahl).strip()
    match = re.search(r"\(([^()]+)\)\s*$", eingabe)
    if match:
        ticker = match.group(1).upper()
    else:
        # Sicherheits-Fallback, falls die Komponente einmal nur Text zurückgibt.
        treffer = unternehmen_suchen(eingabe)
        if treffer:
            ticker = treffer[0][0]
        elif re.fullmatch(r"[A-Za-z0-9^][A-Za-z0-9.\-^=]{0,19}", eingabe):
            ticker = eingabe.upper()

analyse_geklickt = st.button(
    "Aktie analysieren",
    type="primary"
)

if analyse_geklickt:

    if ticker == "":

        st.error(
            "Bitte einen Aktien-Ticker eingeben."
        )

    else:

        try:

            with st.spinner(
                "Aktie wird analysiert..."
            ):
                letzte_analyse = None
                letzter_fehler = None

                # Ganze Analyse bis zu 3-mal wiederholen. Das hilft, wenn
                # Yahoo Finance einzelne Tabellen kurzzeitig leer liefert.
                for versuch in range(3):
                    try:
                        kandidat = aktie_analysieren(ticker)
                        if kandidat and kandidat.get("max_verfuegbar", 0) > 0:
                            letzte_analyse = kandidat
                            break
                    except Exception as exc:
                        letzter_fehler = exc

                    if versuch < 2:
                        time.sleep(1.5 * (versuch + 1))

                if letzte_analyse is None:
                    if letzter_fehler:
                        raise letzter_fehler
                    raise ValueError(
                        f"Für {ticker} wurden nicht genügend auswertbare Finanzdaten geliefert. "
                        "Die Yahoo-Finance-Datenquelle ist möglicherweise vorübergehend "
                        "nicht erreichbar oder liefert unvollständige Daten."
                    )

                st.session_state.analyse = letzte_analyse

        except Exception as fehler:

            st.session_state.analyse = None

            st.error(
                "Die Analyse konnte nicht abgeschlossen werden. Bitte prüfe das "
                "ausgewählte Unternehmen. Bei einer vorübergehenden Datenstörung "
                "versucht die Anwendung die Daten automatisch mehrfach neu zu laden."
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
    st.caption(f"Sektor: {analyse['sektor']}")


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
        f"{analyse['score']:.1f} / 100" if analyse["score"] is not None else "Nicht berechenbar"
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

    if analyse.get("hinweis_finanzunternehmen"):
        st.warning(
            "Hinweis: Finanzunternehmen und Banken haben eine besondere Bilanzstruktur. "
            "Kennzahlen wie FCF-Yield, ROIC und Net Debt / EBITDA sind deshalb mit diesem "
            "allgemeinen Aktienmodell nur eingeschränkt vergleichbar."
        )

    if analyse.get("hinweis_reit"):
        st.warning(
            "Hinweis: Dieses Unternehmen ist ein REIT. Bei REITs sind zusätzliche "
            "Kennzahlen wie FFO/AFFO üblich. Das Rating hier verwendet trotzdem nur "
            "die acht festgelegten Kennzahlen des BMA-Modells und sollte entsprechend "
            "vorsichtig interpretiert werden."
        )

    if analyse["score"] is not None:
        rating_tacho(analyse["score"])
    else:
        st.info("Kein Rating: weniger als 70 von 100 möglichen Punkten sind bewertbar.")


    # =====================================================
    # KENNZAHLEN
    # =====================================================

    st.divider()

    st.subheader(
        "📊 Bewertung der Kennzahlen"
    )
    with st.expander("ℹ️ Berechnungshinweise"):
        st.write(f"EPS-Methode: {analyse.get('eps_methode') or 'Nicht berechenbar'}")
        roic_wert = analyse.get("kennzahlen", {}).get("ROIC")
        if roic_wert is not None and abs(roic_wert) > 100:
            st.warning(
                "Der berechnete ROIC liegt über 100 %. Das kann entstehen, wenn das "
                "Invested Capital sehr klein ist. Der Rohwert wird bewusst nicht gedeckelt; "
                "dieser Rohwert wird bewusst nicht künstlich begrenzt."
            )
        st.write(f"EPS-Datenquelle: {analyse.get('eps_quelle') or 'Nicht verfügbar'}")
        if analyse.get("damodaran_industry") and analyse.get("roic_benchmark") is not None:
            st.write(
                f"ROIC-Branche: {analyse.get('yahoo_industry')} → "
                f"{analyse.get('damodaran_industry')} (Damodaran)"
            )
            st.write(f"ROIC-Branchenvergleich: {analyse.get('roic_benchmark'):.2f} %")

        st.write("Operative Marge und FCF-Marge: Durchschnitt aus drei einzelnen abgeschlossenen Geschäftsjahren.")
        st.write("Umsatzwachstum: 3-Jahres-CAGR aus vier Jahresendpunkten.")
        st.write("Die Finanzzeilen werden tolerant erkannt (z.B. TotalRevenue und Total Revenue).")

    zeilen = []


    prozent_kennzahlen = {

        "FCF-Yield",

        "Umsatzwachstum",

        "ROIC",

        "EPS-Wachstum",

        "Operative Marge",

        "FCF-Marge"
    }


    reihenfolge_kennzahlen = [
        "Operative Marge", "KGV", "EPS-Wachstum", "FCF-Marge",
        "FCF-Yield", "ROIC", "Umsatzwachstum", "Net Debt / EBITDA"
    ]

    for kennzahl in reihenfolge_kennzahlen:
        wert = analyse["kennzahlen"].get(kennzahl)


        if wert is None:

            if kennzahl == "KGV" and analyse["punkte"].get("KGV") == 0:
                wert_anzeige = "Nicht sinnvoll (EPS ≤ 0)"
            elif kennzahl == "Net Debt / EBITDA" and analyse["punkte"].get("Net Debt / EBITDA") == 0:
                wert_anzeige = "Nicht sinnvoll (EBITDA ≤ 0)"
            elif kennzahl == "ROIC" and analyse["punkte"].get("ROIC") == 0:
                wert_anzeige = "Negatives EBIT → 0 Punkte"
            else:
                wert_anzeige = (
                    "Keine Daten"
                )


        elif kennzahl == "EPS-Wachstum" and str(analyse.get("eps_methode", "")).startswith("Alternative EPS-Methode"):
            wert_anzeige = "Alternative EPS-Methode"

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


    if analyse.get("max_verfuegbar", 0) == 0:
        st.warning(
            "Für diese Aktie wurden momentan keine verwertbaren Finanzdaten geladen. "
            "Das ist ein Datenabrufproblem und keine Bewertung von 0 Punkten."
        )

    st.caption(
        f"Datenabdeckung: {analyse['max_verfuegbar']} von 100 möglichen Punkten. "
        + (f"Erreicht: {analyse['rohe_punkte']:.2f} / {analyse['max_verfuegbar']} verfügbare Punkte."
           if analyse["max_verfuegbar"] > 0 else "")
    )

    fehlend = [k for k, p in analyse["punkte"].items() if p is None]
    if fehlend:
        with st.expander("Warum sind Kennzahlen nicht berechenbar?"):
            for k in fehlend:
                st.write(f"**{k}:** {analyse['gruende'].get(k, 'Nicht berechenbar.')}")


    # =====================================================
    # METHODISCHER HINWEIS
    # =====================================================

    st.info(
        "Das Rating wird nur ausgegeben, wenn mindestens 70 von 100 möglichen "
        "Punkten bewertbar sind. Fehlende Kennzahlen werden nicht als 0 Punkte "
        "gewertet, sondern transparent als nicht berechenbar ausgewiesen."
    )



    # Direkter Vergleich mit externen Analysten nach dem eigenen Rating.
    analystenprognosen_anzeigen(
        analyse["ticker"], analyse.get("kurs"), analyse.get("waehrung", ""),
        analyse.get("score"), analyse.get("rating")
    )

    # =====================================================
    # AKTIENKURS
    # =====================================================

    st.divider()

    st.subheader(
        "📈 Kursentwicklung"
    )
    st.caption("Mausrad: Seite scrollen · Im Diagramm ziehen: zoomen · Doppelklick: Ansicht zurücksetzen")


    zeitraum = st.radio(
        "Zeitraum",
        ["1 Monat", "6 Monate", "1 Jahr", "5 Jahre"],
        index=2,
        horizontal=True,
        format_func=lambda wert: {
            "1 Monat": "1M", "6 Monate": "6M",
            "1 Jahr": "1J", "5 Jahre": "5J"
        }[wert],
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


            diagramm_anzeigen(chart_daten, art="linie", einheit=f"Aktienkurs ({analyse['waehrung']})")

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
    st.caption("Mausrad: Seite scrollen · Im Diagramm ziehen: zoomen · Doppelklick: Ansicht zurücksetzen")

    st.write(
        "Hier siehst du wichtige Finanzdaten "
        "des Unternehmens nach Quartalen."
    )


    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "💰 Umsatz",
            "📊 Gewinn",
            "💵 Free Cashflow",
            "🧮 EPS"
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


            diagramm_anzeigen(umsatz_daten, art="balken", einheit=f"Umsatz (Mrd. {analyse['waehrung']})")


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


            diagramm_anzeigen(gewinn_daten, art="balken", einheit=f"Gewinn (Mrd. {analyse['waehrung']})")


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


            diagramm_anzeigen(fcf_daten, art="balken", einheit=f"Free Cashflow (Mrd. {analyse['waehrung']})")


        else:

            st.info(
                "Für diese Aktie sind keine "
                "Quartals-Free-Cashflow-Daten verfügbar."
            )


    # -----------------------------------------------------
    # GEWINN JE AKTIE (EPS)
    # -----------------------------------------------------

    with tab4:
        eps = zeile_suchen(
            analyse["quartals_finanzen"],
            ["Diluted EPS", "DilutedEPS", "Basic EPS", "BasicEPS", "Diluted EPS Continuous Operations", "DilutedEPSContinuousOperations"]
        )
        eps_daten = quartalsdaten_vorbereiten(eps)
        if eps_daten is not None:
            eps_daten = eps_daten.rename(
                columns={"Wert": f"EPS ({analyse['waehrung']})"}
            )
            diagramm_anzeigen(eps_daten, art="balken", einheit=f"EPS ({analyse['waehrung']} je Aktie)")
        else:
            st.info("Für diese Aktie sind keine Quartals-EPS-Daten verfügbar.")



