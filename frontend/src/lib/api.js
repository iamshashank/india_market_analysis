// Thin fetch wrappers for the Flask API.
async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} -> ${r.status}`);
  return r.json();
}
async function postJSON(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  return r.json();
}

export const api = {
  screen: () => getJSON("/api/screen"),
  refreshScreen: () => postJSON("/api/screen/refresh"),
  premarket: () => getJSON("/api/premarket"),
  refreshPremarket: () => postJSON("/api/refresh"),
  paperDashboard: () => getJSON("/api/paper/dashboard"),
  paperSettings: (s) => postJSON("/api/paper/settings", s),
  paperRun: (force) => postJSON("/api/paper/run", { force }),
  paperSettle: () => postJSON("/api/paper/settle"),
  options: (ticker, market) => getJSON(`/api/options?ticker=${encodeURIComponent(ticker)}&market=${market}`),
  fundamentals: (ticker) => getJSON(`/api/fundamentals?ticker=${encodeURIComponent(ticker)}`),
  searchSymbols: (q) => getJSON(`/api/symbols/search?q=${encodeURIComponent(q)}`),
  analyze: (ticker) => getJSON(`/api/analyze?ticker=${encodeURIComponent(ticker)}`),
  history: (ticker, range) => getJSON(`/api/history?ticker=${encodeURIComponent(ticker)}&range=${range}`),
  scoreHistory: (ticker) => getJSON(`/api/score-history?ticker=${encodeURIComponent(ticker)}`),
  backtest: () => getJSON("/api/backtest"),
};
