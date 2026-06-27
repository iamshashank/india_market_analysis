"""Candidate universe for the multibagger screen — India (NSE) + US.

The strategy targets *small base* companies, so this list leans toward small-
and mid-caps that tend to get limited analyst/media coverage. It is broad on
purpose; the screener scores each name on market cap, earnings consistency,
coverage, growth, quality, valuation and news catalysts, then concentrates into
a high-conviction shortlist. Sector is pulled live from Yahoo Finance.

Edit freely. India tickers use Yahoo's ``.NS`` suffix; US tickers are plain.
"""

from __future__ import annotations

from typing import Dict

# ticker -> (display name, market)
_INDIA = {
    "CDSL.NS": "Central Depository Services",
    "CAMS.NS": "Computer Age Management Services",
    "ANGELONE.NS": "Angel One",
    "TANLA.NS": "Tanla Platforms",
    "ROUTE.NS": "Route Mobile",
    "INTELLECT.NS": "Intellect Design Arena",
    "NEWGEN.NS": "Newgen Software",
    "MAPMYINDIA.NS": "C.E. Info Systems (MapMyIndia)",
    "LATENTVIEW.NS": "LatentView Analytics",
    "HAPPSTMNDS.NS": "Happiest Minds Technologies",
    "SONACOMS.NS": "Sona BLW Precision",
    "CRAFTSMAN.NS": "Craftsman Automation",
    "JBCHEPHARM.NS": "JB Chemicals & Pharmaceuticals",
    "ERIS.NS": "Eris Lifesciences",
    "CAPLIPOINT.NS": "Caplin Point Laboratories",
    "NH.NS": "Narayana Hrudayalaya",
    "RAINBOW.NS": "Rainbow Children's Medicare",
    "KIMS.NS": "Krishna Institute of Medical Sciences",
    "APARINDS.NS": "Apar Industries",
    "TRITURBINE.NS": "Triveni Turbine",
    "ELGIEQUIP.NS": "Elgi Equipments",
    "GRINDWELL.NS": "Grindwell Norton",
    "TIMKEN.NS": "Timken India",
    "FINEORG.NS": "Fine Organic Industries",
    "GALAXYSURF.NS": "Galaxy Surfactants",
    "NAVINFLUOR.NS": "Navin Fluorine International",
    "CLEAN.NS": "Clean Science & Technology",
    "CCL.NS": "CCL Products India",
    "VSTIND.NS": "VST Industries",
    "GARFIBRES.NS": "Garware Technical Fibres",
    "KEI.NS": "KEI Industries",
    "POLYMED.NS": "Poly Medicure",
    "RATNAMANI.NS": "Ratnamani Metals & Tubes",
    "CARBORUNIV.NS": "Carborundum Universal",
    "AIAENG.NS": "AIA Engineering",
    "CERA.NS": "Cera Sanitaryware",
    "PRINCEPIPE.NS": "Prince Pipes & Fittings",
    "TATAINVEST.NS": "Tata Investment Corp",
    "RHIM.NS": "RHI Magnesita India",
    "ANANDRATHI.NS": "Anand Rathi Wealth",
    "KFINTECH.NS": "KFin Technologies",
    "AETHER.NS": "Aether Industries",
    "DATAPATTNS.NS": "Data Patterns India",
    "MARKSANS.NS": "Marksans Pharma",
}

_US = {
    "CELH": "Celsius Holdings",
    "ELF": "e.l.f. Beauty",
    "WING": "Wingstop",
    "SHAK": "Shake Shack",
    "CROX": "Crocs",
    "PLAB": "Photronics",
    "POWL": "Powell Industries",
    "AAON": "AAON Inc",
    "FORM": "FormFactor",
    "ONTO": "Onto Innovation",
    "RMBS": "Rambus",
    "SITM": "SiTime",
    "CSWI": "CSW Industrials",
    "ATKR": "Atkore",
    "GRBK": "Green Brick Partners",
    "IBP": "Installed Building Products",
    "STRL": "Sterling Infrastructure",
    "MGNI": "Magnite",
    "TGTX": "TG Therapeutics",
    "MEDP": "Medpace Holdings",
    "LNTH": "Lantheus Holdings",
    "CPRX": "Catalyst Pharmaceuticals",
    "BCC": "Boise Cascade",
    "UFPI": "UFP Industries",
    "PLXS": "Plexus Corp",
    "BMI": "Badger Meter",
    "NSSC": "Napco Security Technologies",
    "ROAD": "Construction Partners",
    "CVLT": "Commvault Systems",
    "DOCN": "DigitalOcean Holdings",
    "SPSC": "SPS Commerce",
    "PCTY": "Paylocity Holding",
    "BRZE": "Braze",
    "AMRC": "Ameresco",
    "SHLS": "Shoals Technologies",
    "PRG": "PROG Holdings",
    "FOUR": "Shift4 Payments",
    "MGPI": "MGP Ingredients",
    "UTMD": "Utah Medical Products",
    "EVER": "EverQuote",
    "DAKT": "Daktronics",
    "PRDO": "Perdoceo Education",
    "AMR": "Alpha Metallurgical Resources",
    "GRC": "Gorman-Rupp",
    "KAI": "Kadant Inc",
}


def _build() -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    for tk, name in _INDIA.items():
        out[tk] = {"name": name, "market": "IN", "currency": "INR"}
    for tk, name in _US.items():
        out[tk] = {"name": name, "market": "US", "currency": "USD"}
    return out


UNIVERSE: Dict[str, dict] = _build()


def all_tickers():
    return list(UNIVERSE.keys())


def market_of(ticker: str) -> str:
    return (UNIVERSE.get(ticker) or {}).get("market", "US")


def display_name(ticker: str) -> str:
    info = UNIVERSE.get(ticker)
    return info["name"] if info else ticker
