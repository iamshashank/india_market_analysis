import { createContext, useContext } from "react";

// Single source of truth for selectable markets. Add Asia / EU / etc. here and
// every screen picks it up — no per-screen wiring needed.
// `markets` = backend market codes this region maps to (IN folds in BSE).
// `tiers`   = cap-tier display order for the screener (per region).
// `sample`  = a default ticker for Options/Analyze placeholders.
export const MARKETS = [
  {
    id: "IN", label: "India", flag: "🇮🇳",
    markets: ["IN", "BSE"],
    tiers: ["Large", "Mid", "Small"],
    sample: "RELIANCE.NS",
    optionMarket: "IN",
  },
  {
    id: "US", label: "US", flag: "🇺🇸",
    markets: ["US"],
    tiers: ["Mega", "Large", "Mid", "Small", "Micro"],
    sample: "AAPL",
    optionMarket: "US",
  },
  // Future, e.g.:
  // { id: "ASIA", label: "Asia", flag: "🌏", markets: ["JP", "HK", "SG"], tiers: [...], sample: "7203.T" },
  // { id: "EU", label: "Europe", flag: "🇪🇺", markets: ["DE", "FR", "UK"], tiers: [...], sample: "SAP.DE" },
];

export const DEFAULT_MARKET = "IN";

export const getMarket = (id) => MARKETS.find((m) => m.id === id) || MARKETS[0];

// region context: { region, setRegion, market(resolved cfg) }
export const MarketContext = createContext({
  region: DEFAULT_MARKET,
  setRegion: () => {},
  market: getMarket(DEFAULT_MARKET),
});

export const useMarket = () => useContext(MarketContext);
