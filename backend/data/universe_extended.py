"""Extended universe for the nightly broad-market scan.

Merged with the curated ``universe.UNIVERSE`` by ``scan.py``. This is a much
wider net of small/mid-caps across India + US. It is still a (large) curated
list rather than every listed ticker — scanning literally all ~7,000 names per
run is impractical via yfinance (rate limits, runtime). Add tickers freely.
"""

from __future__ import annotations

from typing import Dict

_INDIA_EXT = {
    "KPITTECH.NS": "KPIT Technologies", "CYIENT.NS": "Cyient", "BSOFT.NS": "Birlasoft",
    "SONATSOFTW.NS": "Sonata Software", "ZENSARTECH.NS": "Zensar", "FSL.NS": "Firstsource",
    "MASTEK.NS": "Mastek", "BIRLASOFT.NS": "Birlasoft", "TANLA.NS": "Tanla",
    "AFFLE.NS": "Affle India", "RATEGAIN.NS": "RateGain", "ZAGGLE.NS": "Zaggle",
    "POLYCAB.NS": "Polycab", "FINOLEXIND.NS": "Finolex Industries", "SUPREMEIND.NS": "Supreme Industries",
    "ASTRAL.NS": "Astral", "APLAPOLLO.NS": "APL Apollo Tubes", "JINDALSAW.NS": "Jindal Saw",
    "BLUESTARCO.NS": "Blue Star", "VOLTAS.NS": "Voltas", "AMBER.NS": "Amber Enterprises",
    "DIXON.NS": "Dixon Technologies", "KAYNES.NS": "Kaynes Technology", "SYRMA.NS": "Syrma SGS",
    "CESC.NS": "CESC", "KALYANKJIL.NS": "Kalyan Jewellers", "SAREGAMA.NS": "Saregama",
    "PVRINOX.NS": "PVR INOX", "DEVYANI.NS": "Devyani International", "WESTLIFE.NS": "Westlife Foodworld",
    "SAPPHIRE.NS": "Sapphire Foods", "MEDANTA.NS": "Global Health (Medanta)", "FORTIS.NS": "Fortis Healthcare",
    "METROPOLIS.NS": "Metropolis Healthcare", "LALPATHLAB.NS": "Dr Lal PathLabs", "VIJAYA.NS": "Vijaya Diagnostic",
    "GLAND.NS": "Gland Pharma", "LAURUSLABS.NS": "Laurus Labs", "AJANTPHARM.NS": "Ajanta Pharma",
    "NATCOPHARM.NS": "Natco Pharma", "SUVENPHAR.NS": "Suven Pharma", "GRANULES.NS": "Granules India",
    "SUMICHEM.NS": "Sumitomo Chemical", "PIIND.NS": "PI Industries", "SRF.NS": "SRF",
    "ATUL.NS": "Atul", "VINATIORGA.NS": "Vinati Organics", "TATACHEM.NS": "Tata Chemicals",
    "CAMS.NS": "CAMS", "BSE.NS": "BSE Ltd", "MCX.NS": "Multi Commodity Exchange",
    "CDSL.NS": "CDSL", "IEX.NS": "Indian Energy Exchange", "360ONE.NS": "360 ONE WAM",
    "JSWINFRA.NS": "JSW Infrastructure", "GRINFRA.NS": "G R Infraprojects", "KNRCON.NS": "KNR Constructions",
    "PNCINFRA.NS": "PNC Infratech", "IRCON.NS": "Ircon International", "RVNL.NS": "Rail Vikas Nigam",
    "RAILTEL.NS": "RailTel", "MAZDOCK.NS": "Mazagon Dock", "BDL.NS": "Bharat Dynamics",
    "COCHINSHIP.NS": "Cochin Shipyard", "ASTRAMICRO.NS": "Astra Microwave", "PARAS.NS": "Paras Defence",
}

_US_EXT = {
    "AEHR": "Aehr Test Systems", "ACLS": "Axcelis Technologies", "KLIC": "Kulicke & Soffa",
    "UCTT": "Ultra Clean Holdings", "COHU": "Cohu", "AMKR": "Amkor Technology",
    "VECO": "Veeco Instruments", "NVMI": "Nova Ltd", "CAMT": "Camtek",
    "ASPN": "Aspen Aerogels", "ENVX": "Enovix", "FLNC": "Fluence Energy",
    "NXT": "Nextracker", "RUN": "Sunrun", "NOVA": "Sunnova", "STEM": "Stem Inc",
    "PLUG": "Plug Power", "BE": "Bloom Energy", "CHPT": "ChargePoint",
    "FCEL": "FuelCell Energy", "ARRY": "Array Technologies",
    "DDOG": "Datadog", "NET": "Cloudflare", "ESTC": "Elastic", "GTLB": "GitLab",
    "S": "SentinelOne", "FROG": "JFrog", "AI": "C3.ai", "PATH": "UiPath",
    "BAND": "Bandwidth", "FSLY": "Fastly", "APPN": "Appian", "ASAN": "Asana",
    "SMAR": "Smartsheet", "WK": "Workiva", "ALRM": "Alarm.com",
    "AXNX": "Axonics", "TMDX": "TransMedics", "SHC": "Sotera Health",
    "PRCT": "Procept BioRobotics", "NARI": "Inari Medical", "PGNY": "Progyny",
    "DOCS": "Doximity", "PHR": "Phreesia", "HIMS": "Hims & Hers Health",
    "RXST": "RxSight", "KROS": "Keros Therapeutics", "RVMD": "Revolution Medicines",
    "OABI": "OmniAb", "VKTX": "Viking Therapeutics", "CRNX": "Crinetics",
    "SKWD": "Skyward Specialty", "HCI": "HCI Group", "PLMR": "Palomar Holdings",
}


def _build() -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    for tk, name in _INDIA_EXT.items():
        out[tk] = {"name": name, "market": "IN", "currency": "INR"}
    for tk, name in _US_EXT.items():
        out[tk] = {"name": name, "market": "US", "currency": "USD"}
    return out


EXTENDED: Dict[str, dict] = _build()
