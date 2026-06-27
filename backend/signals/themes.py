"""Theme & sentiment heatmap.

Maps every screened stock to one or more growth *themes* (AI/deep-tech,
semiconductors, renewables, EV, defense, power, fintech, pharma, premium
consumer, infrastructure) using its name, industry, sector and recent news, then
ranks which themes have the strongest tailwind right now.

A theme's "heat" blends:
  * the quality of opportunities in it (avg composite score),
  * how positive the news flow is (avg catalyst score),
  * price momentum (avg 6-month return),
  * breadth (how many names qualify).

Output feeds the Themes tab — which sectors/themes are hot, and the best-placed
stocks in each — so you can see where market + consumer sentiment is pointing.
"""

from __future__ import annotations

from typing import Dict, List

# theme -> keyword substrings (matched lowercase against name/industry/sector/news)
THEMES: Dict[str, Dict] = {
    "AI & Deep-tech": {"emoji": "🤖", "keywords": [
        "ai", "artificial intelligence", "machine learning", "genai", "llm",
        "deep tech", "automation", "analytics", "software", "data", "cloud", "saas"]},
    "Semiconductors & GPU": {"emoji": "🔩", "keywords": [
        "semiconductor", "chip", "gpu", "fab", "wafer", "foundry", "electronics",
        "semis", "photonics", "sensor"]},
    "Renewable Energy": {"emoji": "🌱", "keywords": [
        "renewable", "solar", "wind", "green energy", "clean energy", "hydrogen",
        "recycling", "biofuel", "ethanol"]},
    "EV & Mobility": {"emoji": "🔋", "keywords": [
        "ev", "electric vehicle", "battery", "lithium", "charging", "mobility",
        "auto component", "automobile", "two-wheeler"]},
    "Defense & Aerospace": {"emoji": "🛡️", "keywords": [
        "defense", "defence", "aerospace", "missile", "radar", "military", "naval",
        "shipbuild"]},
    "Power & Grid": {"emoji": "⚡", "keywords": [
        "power", "grid", "transmission", "utility", "electric", "transformer",
        "cable", "wire"]},
    "Digital & Fintech": {"emoji": "💳", "keywords": [
        "fintech", "payment", "digital", "depository", "broking", "broker",
        "wealth", "exchange", "capital market", "insurance", "nbfc", "asset management"]},
    "Healthcare & Pharma": {"emoji": "🧬", "keywords": [
        "pharma", "healthcare", "hospital", "diagnostic", "biotech", "drug",
        "medical", "lifescience", "therapeutic", "clinical"]},
    "Premium Consumer": {"emoji": "🛍️", "keywords": [
        "consumer", "fmcg", "beverage", "retail", "brand", "premium", "food",
        "apparel", "jewell", "restaurant", "cosmetic", "beauty"]},
    "Infrastructure & Capex": {"emoji": "🏗️", "keywords": [
        "infrastructure", "construction", "capex", "engineering", "capital goods",
        "cement", "building", "industrial", "machinery", "pipe"]},
}


def _clip(x, lo, hi):
    return max(lo, min(hi, x))


def _text_for(stock: dict) -> str:
    parts = [stock.get("name") or "", stock.get("sector") or "", stock.get("industry") or ""]
    news = stock.get("news") or {}
    parts += [h.get("title", "") for h in (news.get("headlines") or [])]
    parts += news.get("top_events") or []
    return " ".join(parts).lower()


def _themes_for(text: str) -> List[str]:
    hits = []
    for name, cfg in THEMES.items():
        if any(kw in text for kw in cfg["keywords"]):
            hits.append(name)
    return hits


def build_heatmap(scored: List[dict]) -> List[dict]:
    buckets: Dict[str, List[dict]] = {k: [] for k in THEMES}
    for s in scored:
        text = _text_for(s)
        for th in _themes_for(text):
            buckets[th].append(s)

    out: List[dict] = []
    for name, cfg in THEMES.items():
        names = buckets[name]
        if not names:
            continue
        n = len(names)
        avg_score = sum(x["score"] for x in names) / n
        avg_cat = sum((x.get("news") or {}).get("catalyst_score", 50) for x in names) / n
        moms = [(x.get("metrics") or {}).get("ret_6m") for x in names]
        moms = [m for m in moms if isinstance(m, (int, float))]
        avg_mom = sum(moms) / len(moms) if moms else 0.0
        mom_score = _clip(50.0 + avg_mom * 100.0, 0.0, 100.0)
        breadth = _clip(n * 18.0, 0.0, 100.0)

        heat = round(0.40 * avg_score + 0.30 * avg_cat + 0.20 * mom_score + 0.10 * breadth, 1)
        top = sorted(names, key=lambda x: x["score"], reverse=True)[:6]
        out.append({
            "theme": name,
            "emoji": cfg["emoji"],
            "heat": heat,
            "count": n,
            "avg_score": round(avg_score, 1),
            "avg_catalyst": round(avg_cat, 1),
            "avg_momentum_pct": round(avg_mom * 100, 1),
            "top_stocks": [{"ticker": x["ticker"], "name": x["name"], "market": x["market"],
                            "score": x["score"], "sector": x["sector"]} for x in top],
        })
    out.sort(key=lambda x: x["heat"], reverse=True)
    return out
