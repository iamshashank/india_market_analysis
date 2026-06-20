"""Candidate universe of liquid Indian (NSE) stocks.

Tickers use Yahoo Finance's NSE suffix (``.NS``). The universe is intentionally
broad and deliberately carries >= 6 liquid names in each major sector so that
the "top 6 stocks per sector" view always has enough candidates. Edit freely.

The grouping below is only for readability; the *actual* sector used in scoring
and reporting is pulled live from Yahoo Finance (GICS-style ``sector`` field).
"""

UNIVERSE = {
    # ---- Financial Services (banks / NBFC / insurance) ----
    "HDFCBANK.NS": "HDFC Bank",
    "ICICIBANK.NS": "ICICI Bank",
    "SBIN.NS": "State Bank of India",
    "AXISBANK.NS": "Axis Bank",
    "KOTAKBANK.NS": "Kotak Mahindra Bank",
    "BAJFINANCE.NS": "Bajaj Finance",
    "BAJAJFINSV.NS": "Bajaj Finserv",
    "SBILIFE.NS": "SBI Life Insurance",
    "HDFCLIFE.NS": "HDFC Life Insurance",
    "BANKBARODA.NS": "Bank of Baroda",
    "CHOLAFIN.NS": "Cholamandalam Invest",
    "ICICIGI.NS": "ICICI Lombard",

    # ---- Technology / IT services ----
    "TCS.NS": "Tata Consultancy Services",
    "INFY.NS": "Infosys",
    "HCLTECH.NS": "HCL Technologies",
    "TECHM.NS": "Tech Mahindra",
    "WIPRO.NS": "Wipro",
    "PERSISTENT.NS": "Persistent Systems",
    "COFORGE.NS": "Coforge",
    "MPHASIS.NS": "Mphasis",
    "TATAELXSI.NS": "Tata Elxsi",
    "OFSS.NS": "Oracle Financial Services",

    # ---- Consumer Defensive (staples) ----
    "HINDUNILVR.NS": "Hindustan Unilever",
    "ITC.NS": "ITC",
    "NESTLEIND.NS": "Nestle India",
    "VBL.NS": "Varun Beverages",
    "DMART.NS": "Avenue Supermarts (DMart)",
    "BRITANNIA.NS": "Britannia Industries",
    "TATACONSUM.NS": "Tata Consumer Products",
    "MARICO.NS": "Marico",
    "DABUR.NS": "Dabur India",
    "GODREJCP.NS": "Godrej Consumer",
    "COLPAL.NS": "Colgate-Palmolive India",

    # ---- Consumer Cyclical (discretionary + autos) ----
    "TITAN.NS": "Titan Company",
    "TRENT.NS": "Trent",
    "MARUTI.NS": "Maruti Suzuki",
    "M&M.NS": "Mahindra & Mahindra",
    "BAJAJ-AUTO.NS": "Bajaj Auto",
    "EICHERMOT.NS": "Eicher Motors",
    "HEROMOTOCO.NS": "Hero MotoCorp",
    "TVSMOTOR.NS": "TVS Motor",
    "ASIANPAINT.NS": "Asian Paints",
    "JUBLFOOD.NS": "Jubilant FoodWorks",

    # ---- Industrials / Capex / Defence ----
    "LT.NS": "Larsen & Toubro",
    "SIEMENS.NS": "Siemens India",
    "BEL.NS": "Bharat Electronics",
    "HAL.NS": "Hindustan Aeronautics",
    "ABB.NS": "ABB India",
    "CUMMINSIND.NS": "Cummins India",
    "BHEL.NS": "Bharat Heavy Electricals",
    "THERMAX.NS": "Thermax",

    # ---- Energy / Oil & Gas ----
    "RELIANCE.NS": "Reliance Industries",
    "COALINDIA.NS": "Coal India",
    "ONGC.NS": "Oil & Natural Gas Corp",
    "IOC.NS": "Indian Oil Corp",
    "BPCL.NS": "Bharat Petroleum",
    "GAIL.NS": "GAIL India",

    # ---- Utilities / Power ----
    "NTPC.NS": "NTPC",
    "POWERGRID.NS": "Power Grid Corp",
    "TATAPOWER.NS": "Tata Power",
    "ADANIPOWER.NS": "Adani Power",
    "JSWENERGY.NS": "JSW Energy",
    "NHPC.NS": "NHPC",

    # ---- Healthcare / Pharma ----
    "SUNPHARMA.NS": "Sun Pharma",
    "DRREDDY.NS": "Dr Reddy's Labs",
    "CIPLA.NS": "Cipla",
    "DIVISLAB.NS": "Divi's Laboratories",
    "LUPIN.NS": "Lupin",
    "APOLLOHOSP.NS": "Apollo Hospitals",
    "MAXHEALTH.NS": "Max Healthcare",

    # ---- Basic Materials / Cement / Metals ----
    "ULTRACEMCO.NS": "UltraTech Cement",
    "GRASIM.NS": "Grasim Industries",
    "TATASTEEL.NS": "Tata Steel",
    "JSWSTEEL.NS": "JSW Steel",
    "HINDALCO.NS": "Hindalco Industries",
    "VEDL.NS": "Vedanta",
    "JINDALSTEL.NS": "Jindal Steel & Power",

    # ---- Communication Services ----
    "BHARTIARTL.NS": "Bharti Airtel",
}


def all_tickers():
    return list(UNIVERSE.keys())


def display_name(ticker: str) -> str:
    return UNIVERSE.get(ticker, ticker)
