export const fmtNum = (x, nd = 1) => (x === null || x === undefined ? "n/a" : Number(x).toFixed(nd));
export const fmtPct = (v) => (v === null || v === undefined ? "n/a" : (v >= 0 ? "+" : "") + Number(v).toFixed(2) + "%");
export const fmtPctFrac = (v) => (v === null || v === undefined ? "n/a" : (v * 100).toFixed(0) + "%");
export const signClass = (x) => (x === null || x === undefined ? "" : x >= 0 ? "pos" : "neg");

export function fmtUsd(v) {
  if (v === null || v === undefined) return "n/a";
  const n = Number(v);
  if (n >= 1e9) return "$" + (n / 1e9).toFixed(2) + "B";
  if (n >= 1e6) return "$" + (n / 1e6).toFixed(0) + "M";
  return "$" + n.toFixed(0);
}

export const yahooUrl = (ticker) =>
  ticker ? `https://finance.yahoo.com/quote/${encodeURIComponent(ticker)}` : "#";

const SYM = { INR: "₹", USD: "$" };

// Large currency amount, humanized by market convention (INR → Cr, USD → B/M).
export function humanizeMoney(v, currency = "USD") {
  if (v === null || v === undefined || isNaN(v)) return "—";
  const sym = SYM[currency] || "";
  const n = Number(v);
  const abs = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  if (currency === "INR") {
    if (abs >= 1e7) return `${sign}${sym}${(abs / 1e7).toFixed(2)} Cr`;
    if (abs >= 1e5) return `${sign}${sym}${(abs / 1e5).toFixed(2)} L`;
    return `${sign}${sym}${abs.toFixed(0)}`;
  }
  if (abs >= 1e9) return `${sign}${sym}${(abs / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${sign}${sym}${(abs / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${sign}${sym}${(abs / 1e3).toFixed(1)}K`;
  return `${sign}${sym}${abs.toFixed(0)}`;
}

export const moneyPrice = (v, currency = "USD") =>
  v == null || isNaN(v) ? "—" : `${SYM[currency] || ""}${Number(v).toFixed(2)}`;

// Format a fundamentals ratio value by its declared kind.
export function fmtKind(value, kind, currency) {
  if (value === null || value === undefined || isNaN(value)) return "—";
  if (kind === "money") return humanizeMoney(value, currency);
  if (kind === "price") return moneyPrice(value, currency);
  if (kind === "pct") return (value * 100).toFixed(2) + "%";
  return Number(value).toFixed(2);
}
