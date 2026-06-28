import React, { useEffect, useRef, useState } from "react";
import {
  Box, Card, CardContent, Typography, Grid, Stack, Chip, TextField, Button,
  ToggleButton, ToggleButtonGroup, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, Paper, IconButton, Divider, Alert, Accordion, AccordionSummary,
  AccordionDetails, Tooltip, TableSortLabel,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import UploadFileIcon from "@mui/icons-material/UploadFile";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import AccountBalanceWalletIcon from "@mui/icons-material/AccountBalanceWallet";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import EmojiEventsIcon from "@mui/icons-material/EmojiEvents";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";
import { api } from "../lib/api.js";
import { fmtNum } from "../lib/format.js";
import {
  SectionHeader, KpiCard, TickerLink, MarketChip, SignalChips,
  scoreColor, healthColor, HEALTH_LABEL_TIP, CardGridSkeleton, KpiSkeleton,
} from "./common.jsx";
import { useUI } from "../uiContext.js";
import { useMarket } from "../markets.js";

const money = (v, ccy) =>
  v == null ? "—" : (ccy === "USD" ? "$" : "₹") + Number(v).toLocaleString(ccy === "USD" ? "en-US" : "en-IN", { maximumFractionDigits: 2, minimumFractionDigits: 2 });

const HCOLS = [
  { label: "Stock", key: "stock", align: "left" },
  { label: "Mkt", key: "market", align: "left" },
  { label: "Qty", key: "qty", align: "right" },
  { label: "Price", key: "price", align: "right" },
  { label: "Value", key: "value", align: "right" },
  { label: "P&L", key: "pnl", align: "right" },
  { label: "Score", key: "score", align: "right", tip: "Composite multibagger score (0–100)." },
  { label: "Health", key: "health", align: "left", tip: "Financial-health from the statements — Strong / Sound / Watch / Distress." },
  { label: "Signals", key: null, align: "left", tip: "Discovery-inflection + ✨ Emerging-compounder flags." },
  { label: "", key: null, align: "left" },
];
const SORT_ACC = {
  stock: (h) => (h.name || h.ticker || "").toLowerCase(),
  market: (h) => h.market || "",
  qty: (h) => h.quantity,
  price: (h) => h.price,
  value: (h) => (h.value_usd != null ? h.value_usd : h.value),
  pnl: (h) => h.pnl_pct,
  score: (h) => h.score,
  health: (h) => (h.health ? h.health.score : null),
};

export default function PortfolioView() {
  const { toast, setBusy } = useUI();
  const { region } = useMarket();
  const [data, setData] = useState(null);
  const [status, setStatus] = useState("idle");
  const [broker, setBroker] = useState("");
  const [market, setMarket] = useState(region === "US" ? "US" : "IN");
  const [sym, setSym] = useState("");
  const [qty, setQty] = useState("");
  const [avg, setAvg] = useState("");
  const [casPwd, setCasPwd] = useState("");
  const [casInfo, setCasInfo] = useState(null);
  const fileRef = useRef(null);
  const casRef = useRef(null);
  const poll = useRef(null);
  const [orderBy, setOrderBy] = useState("score");
  const [order, setOrder] = useState("desc");
  function handleSort(key) {
    if (orderBy === key) setOrder(order === "asc" ? "desc" : "asc");
    else { setOrderBy(key); setOrder(key === "stock" || key === "market" ? "asc" : "desc"); }
  }
  function sortRows(rows) {
    const acc = SORT_ACC[orderBy];
    if (!acc) return rows;
    const dir = order === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
      const va = acc(a), vb = acc(b);
      const na = va == null || va === "", nb = vb == null || vb === "";
      if (na && nb) return 0;
      if (na) return 1;
      if (nb) return -1;
      if (typeof va === "string" || typeof vb === "string") return String(va).localeCompare(String(vb)) * dir;
      return (va - vb) * dir;
    });
  }

  async function load() {
    try {
      const j = await api.portfolio();
      setStatus(j.status);
      setBusy("portfolio", j.status === "running");
      if (j.data) setData(j.data);
      if (j.status === "running") ensure(); else stop();
    } catch (e) { stop(); }
  }
  function ensure() { if (!poll.current) poll.current = setInterval(load, 4000); }
  function stop() { if (poll.current) { clearInterval(poll.current); poll.current = null; } }
  useEffect(() => { load(); return () => { stop(); setBusy("portfolio", false); }; }, []);

  async function addHolding() {
    if (!sym.trim()) { toast("Enter a symbol", "warning"); return; }
    try {
      await api.portfolioAdd({ broker: broker || "Manual", symbol: sym, market, quantity: qty || null, avg_price: avg || null });
      toast(`Added ${sym.toUpperCase()} — analysing…`);
      setSym(""); setQty(""); setAvg("");
      setStatus("running"); setBusy("portfolio", true); setTimeout(load, 500); ensure();
    } catch (e) { toast("Could not add holding", "error"); }
  }
  async function onFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const r = await api.portfolioUpload(text, broker || "CSV", market);
      toast(r.added ? `Imported ${r.added} holdings — analysing…` : "No rows recognised in that CSV", r.added ? "success" : "warning");
      if (r.added) { setStatus("running"); setBusy("portfolio", true); setTimeout(load, 500); ensure(); }
    } catch (e2) { toast("Could not read that file", "error"); }
    if (fileRef.current) fileRef.current.value = "";
  }
  async function onCas(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const r = await api.portfolioCas(file, casPwd);
      if (r.ok) {
        toast(r.added ? `Imported ${r.added} equity holdings from your CAS — analysing…` : (r.note || "No NSE equities found in that CAS"), r.added ? "success" : "warning");
        setCasInfo({ note: r.note, sample: r.sample || [] });
        if (r.added) { setStatus("running"); setBusy("portfolio", true); setTimeout(load, 500); ensure(); }
      } else {
        toast(r.reason || "Could not read the CAS", "error");
        setCasInfo(null);
      }
    } catch (e2) { toast("Could not upload the CAS — " + (e2?.message || "the request failed (file too large or timed out)"), "error"); }
    if (casRef.current) casRef.current.value = "";
    setCasPwd("");
  }
  async function removeHolding(id) {
    try { await api.portfolioRemove(id); setStatus("running"); setTimeout(load, 400); ensure(); }
    catch (e) { toast("Could not remove", "error"); }
  }
  async function clearAll() {
    if (!window.confirm("Remove all manually-added / uploaded holdings?")) return;
    try { await api.portfolioClear(); toast("Portfolio cleared"); setData(null); setTimeout(load, 400); ensure(); }
    catch (e) { toast("Could not clear", "error"); }
  }

  const connectCard = (
    <Card>
      <CardContent>
        <Typography variant="overline" color="primary">Add a holding</Typography>
        <Grid container spacing={1.5} alignItems="center" sx={{ mt: 0.25 }}>
          <Grid item xs={6} sm={3} md={2}>
            <ToggleButtonGroup exclusive size="small" value={market} onChange={(e, v) => v && setMarket(v)} fullWidth>
              <ToggleButton value="IN">🇮🇳 IN</ToggleButton>
              <ToggleButton value="US">🇺🇸 US</ToggleButton>
            </ToggleButtonGroup>
          </Grid>
          <Grid item xs={6} sm={3} md={2}><TextField size="small" label="Symbol" value={sym} onChange={(e) => setSym(e.target.value)} placeholder={market === "US" ? "AAPL" : "RELIANCE"} fullWidth /></Grid>
          <Grid item xs={6} sm={3} md={2}><TextField size="small" label="Broker" value={broker} onChange={(e) => setBroker(e.target.value)} placeholder="Groww / Zerodha…" fullWidth /></Grid>
          <Grid item xs={6} sm={2} md={2}><TextField size="small" label="Qty" value={qty} onChange={(e) => setQty(e.target.value)} type="number" fullWidth /></Grid>
          <Grid item xs={6} sm={2} md={2}><TextField size="small" label="Avg price" value={avg} onChange={(e) => setAvg(e.target.value)} type="number" fullWidth /></Grid>
          <Grid item xs={6} sm={3} md={2}><Button variant="contained" startIcon={<AddIcon />} onClick={addHolding} fullWidth>Add</Button></Grid>
        </Grid>

        <Divider sx={{ my: 2 }}><Typography variant="caption" color="text.secondary">or import a statement</Typography></Divider>

        <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" useFlexGap>
          <Button variant="outlined" startIcon={<UploadFileIcon />} component="label">
            Upload holdings CSV
            <input hidden type="file" accept=".csv,text/csv" ref={fileRef} onChange={onFile} />
          </Button>
          <Typography variant="caption" color="text.secondary">
            Export a holdings CSV from Groww / Zerodha / IndMoney. Uses the <b>{market === "US" ? "🇺🇸 US" : "🇮🇳 IN"}</b> market + <b>{broker || "CSV"}</b> label above. Columns like Symbol, Quantity, Avg Price are auto-detected.
          </Typography>
        </Stack>

        <Divider sx={{ my: 2 }}><Typography variant="caption" color="text.secondary">or import your NSDL/CDSL e-CAS — all demat holdings, grouped by broker</Typography></Divider>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ sm: "center" }} flexWrap="wrap" useFlexGap sx={{ mb: 1 }}>
          <TextField size="small" type="password" label="CAS PDF password" value={casPwd} onChange={(e) => setCasPwd(e.target.value)} sx={{ maxWidth: 200 }} />
          <Button variant="outlined" startIcon={<UploadFileIcon />} component="label">
            Upload e-CAS PDF
            <input hidden type="file" accept="application/pdf,.pdf" ref={casRef} onChange={onCas} />
          </Button>
          <Typography variant="caption" color="text.secondary">
            Equities only (mutual funds skipped). Split by broker automatically. The password unlocks the PDF <b>on your machine</b> and is never stored or sent anywhere.
          </Typography>
        </Stack>

        {casInfo && (
          <Alert severity="info" variant="outlined" sx={{ mb: 1 }}>
            <Typography variant="body2">{casInfo.note}</Typography>
            {(casInfo.sample || []).length > 0 && (
              <Box sx={{ mt: 1 }}>
                <Typography variant="caption" color="text.secondary">How a few rows were read from your statement (paste a line or two here to perfect quantity parsing — redact the name if you like):</Typography>
                <Box component="pre" sx={{ m: 0, mt: 0.5, p: 1, borderRadius: 1, bgcolor: "action.hover", fontSize: 11, overflowX: "auto", whiteSpace: "pre-wrap" }}>{casInfo.sample.join("\n")}</Box>
              </Box>
            )}
          </Alert>
        )}

        <Accordion variant="outlined" disableGutters sx={{ mt: 2, borderRadius: 2, "&:before": { display: "none" } }}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="body2">Connect a broker for live holdings (Groww / Zerodha) — optional</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              For automatic, always-current holdings, add your own broker API token to a git-ignored <code>.env</code> (never paste it in chat) and restart the app:
            </Typography>
            <Box component="pre" sx={{ m: 0, p: 1.5, borderRadius: 1, bgcolor: "action.hover", fontSize: 12, overflowX: "auto" }}>{`# Zerodha Kite (kite.trade app → daily login token)
KITE_API_KEY=your_key
KITE_ACCESS_TOKEN=today's_token      # pip install kiteconnect

# Groww (token from Groww API settings)
GROWW_ACCESS_TOKEN=your_token        # pip install growwapi`}</Box>
            <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: "block" }}>
              Connected sources: {(data?.sources_configured || []).length ? data.sources_configured.join(", ") : "none yet (manual / CSV active)"}.
              The OTP/login happens in the broker's own page — never through this app.
            </Typography>
          </AccordionDetails>
        </Accordion>
      </CardContent>
    </Card>
  );

  const stats = data?.stats || {};
  const totals = stats.total_by_ccy || {};
  const totalStr = Object.keys(totals).length
    ? Object.entries(totals).map(([c, v]) => money(v, c)).join(" · ") : "—";

  return (
    <Stack spacing={3}>
      <SectionHeader overline="My Portfolio" title="Your holdings, run through the engine"
        subtitle="Add holdings manually, import a broker CSV, or connect Groww/Zerodha. Each stock is scored on the same multibagger engine (composite · health · inflection · emerging) and grouped by broker. Nothing leaves your machine."
        action={data?.holdings?.length ? <Button color="inherit" size="small" onClick={clearAll}>Clear all</Button> : null} />

      {connectCard}

      {!data && <><KpiSkeleton count={4} /><CardGridSkeleton count={3} /></>}

      {data && status === "running" && !data.holdings?.length && (
        <Alert severity="info">Analysing your holdings… this takes a little while the first time (it fetches fresh fundamentals).</Alert>
      )}

      {data && !data.holdings?.length && status !== "running" && (
        <Alert severity="info">No holdings yet — add one above or upload a CSV to see it scored and grouped by broker.</Alert>
      )}

      {data?.holdings?.length > 0 && (
        <>
          <Grid container spacing={2}>
            <Grid item xs={6} md={3}><KpiCard icon={<AccountBalanceWalletIcon />} label="Portfolio value" value={totalStr} caption={stats.valued_count != null && stats.valued_count < stats.count ? `${stats.valued_count} of ${stats.count} valued · add qty` : `${stats.count} holdings`} /></Grid>
            <Grid item xs={6} md={3}><KpiCard icon={<EmojiEventsIcon />} label="Weighted avg score" value={stats.weighted_avg_score ?? "—"} color={`${scoreColor(stats.weighted_avg_score || 0)}.main`} caption="value-weighted, 0–100" /></Grid>
            <Grid item xs={6} md={3}><KpiCard icon={<WarningAmberIcon />} label="Flagged holdings" value={(stats.flagged || []).length} color={(stats.flagged || []).length ? "warning.main" : "text.primary"} caption="forensic red flags" /></Grid>
            <Grid item xs={6} md={3}><KpiCard icon={<EmojiEventsIcon />} label="Emerging compounders" value={(stats.emerging || []).length} color={(stats.emerging || []).length ? "secondary.main" : "text.primary"} caption="sweet-spot holdings" /></Grid>
          </Grid>

          {((stats.flagged || []).length > 0 || (stats.weakest || []).length > 0) && (
            <Accordion variant="outlined" disableGutters sx={{ borderRadius: 2, "&:before": { display: "none" } }}>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Typography variant="subtitle1">Watch-outs &amp; weakest holdings</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ ml: 1.5, alignSelf: "center" }}>
                  {(stats.flagged || []).length} flagged · {(stats.weakest || []).length} lowest-scoring
                </Typography>
              </AccordionSummary>
              <AccordionDetails>
                <Grid container spacing={2}>
                  <Grid item xs={12} md={6}>
                    <Typography variant="overline" color="error.main">Watch-outs (forensic flags)</Typography>
                    {(stats.flagged || []).length ? (
                      <Stack spacing={0.5} sx={{ mt: 0.5 }}>
                        {stats.flagged.map((f) => (
                          <Typography key={f.ticker} variant="body2"><b>{f.name || f.ticker}</b> — {f.flags.join("; ")}</Typography>
                        ))}
                      </Stack>
                    ) : <Typography variant="body2" color="text.secondary">No red flags across your holdings.</Typography>}
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <Typography variant="overline" color="primary">Lowest-scoring holdings</Typography>
                    <Stack spacing={0.5} sx={{ mt: 0.5 }}>
                      {(stats.weakest || []).map((w) => (
                        <Typography key={w.ticker} variant="body2"><b>{w.name || w.ticker}</b> — score {Math.round(w.score)}</Typography>
                      ))}
                    </Stack>
                  </Grid>
                </Grid>
              </AccordionDetails>
            </Accordion>
          )}

          {(data.by_broker || []).map((g) => (
            <Box key={g.broker}>
              <SectionHeader title={<Stack direction="row" spacing={1} alignItems="center"><span>{g.broker}</span><Chip size="small" variant="outlined" label={`${g.count} holdings`} /></Stack>} />
              <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      {HCOLS.map((c, i) => {
                        const inner = c.key ? (
                          <TableSortLabel active={orderBy === c.key} direction={orderBy === c.key ? order : "desc"} onClick={() => handleSort(c.key)}>{c.label}</TableSortLabel>
                        ) : c.label;
                        return (
                          <TableCell key={c.label + i} align={c.align} sortDirection={orderBy === c.key ? order : false}>
                            {c.tip ? <Tooltip title={c.tip} arrow><Box component="span" sx={{ display: "inline-flex", cursor: "help" }}>{inner}</Box></Tooltip> : inner}
                          </TableCell>
                        );
                      })}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {sortRows(g.holdings).map((h) => (
                      <TableRow key={h.id} hover>
                        <TableCell>
                          <Typography variant="body2" fontWeight={700}><TickerLink ticker={h.ticker}>{h.name || h.symbol}</TickerLink></Typography>
                          <Typography variant="caption" color="text.secondary">{h.ticker}{h.sector ? ` · ${h.sector}` : ""}</Typography>
                        </TableCell>
                        <TableCell><MarketChip m={h.market === "US" ? "US" : "IN"} /></TableCell>
                        <TableCell align="right">{h.quantity ?? "—"}</TableCell>
                        <TableCell align="right">{h.price != null ? money(h.price, h.ccy) : "—"}</TableCell>
                        <TableCell align="right">{h.value != null ? money(h.value, h.ccy) : "—"}</TableCell>
                        <TableCell align="right" sx={{ color: h.pnl_pct == null ? "text.secondary" : h.pnl_pct >= 0 ? "success.main" : "error.main" }}>
                          {h.pnl_pct == null ? "—" : `${h.pnl_pct >= 0 ? "+" : ""}${h.pnl_pct}%`}
                        </TableCell>
                        <TableCell align="right">
                          {h.score != null ? <Chip size="small" label={Math.round(h.score)} color={scoreColor(h.score)} variant="outlined" /> : (h.unanalysed ? "—" : "…")}
                        </TableCell>
                        <TableCell>
                          {h.health?.label && h.health.label !== "Unknown"
                            ? <Tooltip title={`${HEALTH_LABEL_TIP[h.health.label] || h.health.label}${(h.health.flags || []).length ? " Flags: " + h.health.flags.join("; ") + "." : ""}`} arrow><Chip size="small" variant="outlined" color={healthColor(h.health.label)} label={h.health.label} sx={{ cursor: "help" }} /></Tooltip>
                            : "—"}
                        </TableCell>
                        <TableCell><SignalChips inflection={h.inflection} emerging={h.emerging_compounder} /></TableCell>
                        <TableCell>
                          {!h.live && (
                            <Tooltip title="Remove holding" arrow>
                              <IconButton size="small" onClick={() => removeHolding(h.id)} aria-label="Remove"><DeleteOutlineIcon fontSize="small" /></IconButton>
                            </Tooltip>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Box>
          ))}
        </>
      )}
    </Stack>
  );
}
