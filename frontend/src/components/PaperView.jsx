import React, { useEffect, useRef, useState } from "react";
import {
  Box, Card, CardContent, Typography, Grid, Stack, Chip, TextField, Button,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, Alert,
} from "@mui/material";
import { LineChart } from "@mui/x-charts/LineChart";
import { api } from "../lib/api.js";
import { fmtNum } from "../lib/format.js";
import { TickerLink, SectionHeader, KpiSkeleton } from "./common.jsx";
import { useUI } from "../uiContext.js";
import { useMarket } from "../markets.js";

const FIELDS = [
  ["budget_inr", "Total budget (₹)", 1000, 500],
  ["min_score", "Min stock score", 50, 1],
  ["min_market_bias", "Min market bias", 0, 1],
  ["max_stocks", "Max stocks/day", 1, 1],
];
const statusColor = (s) => ({ settled: "success", pending: "warning", failed: "error", skipped: "default" }[(s || "").toLowerCase()] || "default");

function Stat({ lbl, val, color }) {
  return (
    <Grid item xs={6} sm={4}>
      <Box sx={{ p: 1.2, borderRadius: 2, bgcolor: "action.hover" }}>
        <Typography variant="caption" color="text.secondary">{lbl}</Typography>
        <Typography variant="h6" color={color || "text.primary"}>{val}</Typography>
      </Box>
    </Grid>
  );
}

export default function PaperView({ active }) {
  const { toast } = useUI();
  const { region, market: marketCfg } = useMarket();
  const [dash, setDash] = useState(null);
  const [form, setForm] = useState({ budget_inr: 10000, min_score: 54, min_market_bias: 50, max_stocks: 3 });
  const [busy, setBusyLocal] = useState(false);
  const wired = useRef(false);

  async function load() {
    try {
      const j = await api.paperDashboard();
      setDash(j);
      if (j.settings && !wired.current) { setForm((f) => ({ ...f, ...j.settings })); wired.current = true; }
    } catch (e) { /* ignore */ }
  }
  useEffect(() => { load(); }, [active]);

  async function save() { setBusyLocal(true); const j = await api.paperSettings(form); setForm((f) => ({ ...f, ...j.settings })); toast("Settings saved."); setBusyLocal(false); }
  async function run() {
    setBusyLocal(true);
    const j = await api.paperRun(false);
    if (!j.ok) toast(j.error || "Run failed.", "error");
    else if (j.skipped) toast(j.message || j.reason || "Session skipped.", "info");
    else toast(`Logged ${(j.trades || []).length} trade(s) for ${j.trade_date}.`);
    await load(); setBusyLocal(false);
  }
  async function settle() { setBusyLocal(true); const j = await api.paperSettle(); toast(`Settled ${j.settled || 0} trade(s).`); await load(); setBusyLocal(false); }

  if (!dash) {
    return (
      <Box>
        <SectionHeader overline="Track the signals" title="Paper trading lab"
          subtitle="Loading your simulated track record…" />
        <KpiSkeleton count={6} />
      </Box>
    );
  }

  const stats = dash?.stats || {};
  const trades = dash?.trades || []; const skips = dash?.skips || [];
  const cum = stats.cumulative || [];

  return (
    <Stack spacing={2}>
      <SectionHeader overline="Track the signals" title="Paper trading lab"
        subtitle="A simulated track record of the next-day signals — no real orders. Configure a budget & filters; trades auto-log when predictions refresh and settle against Yahoo OHLC."
        action={<Chip label="Simulated · no real orders" color="primary" variant="outlined" size="small" />} />

      {region !== "IN" && (
        <Alert severity="info" variant="outlined">
          Paper trading tracks the <b>India (NSE)</b> next-day predictor (₹ budgets, NSE OHLC settlement). You have
          <b> {marketCfg.flag} {marketCfg.label}</b> selected — the simulated book below is for India. A {marketCfg.label}
          paper book isn't available yet.
        </Alert>
      )}

      <Grid container spacing={2}>
        <Grid item xs={12} md={5}>
          <Card sx={{ height: "100%" }}>
            <CardContent>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>Configure budget &amp; filters. Trades auto-log when predictions refresh.</Typography>
              <Stack spacing={1.5}>
                {FIELDS.map(([key, label, min, step]) => (
                  <TextField key={key} type="number" label={label} size="small" value={form[key]}
                    inputProps={{ min, step }} onChange={(e) => setForm({ ...form, [key]: Number(e.target.value) })} />
                ))}
                <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                  <Button variant="contained" onClick={save} disabled={busy}>Save settings</Button>
                  <Button variant="outlined" onClick={run} disabled={busy}>Run today</Button>
                  <Button variant="outlined" onClick={settle} disabled={busy}>Settle past</Button>
                </Stack>
              </Stack>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={7}>
          <Card sx={{ height: "100%" }}>
            <CardContent>
              <Typography variant="subtitle1" gutterBottom>Performance</Typography>
              <Grid container spacing={1.5} sx={{ mb: 1 }}>
                <Stat lbl="Total P&L" val={`${stats.total_pnl_inr >= 0 ? "+" : ""}₹${fmtNum(stats.total_pnl_inr, 0)}`} color={stats.total_pnl_inr >= 0 ? "success.main" : "error.main"} />
                <Stat lbl="Win rate" val={stats.win_rate != null ? `${fmtNum(stats.win_rate, 1)}%` : "n/a"} />
                <Stat lbl="Settled" val={stats.settled || 0} />
                <Stat lbl="Pending" val={stats.pending || 0} />
                <Stat lbl="W / L" val={`${stats.wins || 0} / ${stats.losses || 0}`} />
                <Stat lbl="Avg / trade" val={stats.avg_pnl_inr != null ? `₹${fmtNum(stats.avg_pnl_inr, 0)}` : "n/a"} />
              </Grid>
              {cum.length ? (
                <LineChart
                  height={240}
                  xAxis={[{ scaleType: "point", data: cum.map((d) => d.date) }]}
                  series={[
                    { data: cum.map((d) => d.cumulative_pnl), label: "Cumulative P&L (₹)", area: true, showMark: true },
                    { data: cum.map((d) => d.daily_pnl), label: "Daily P&L (₹)" },
                  ]}
                />
              ) : (
                <Typography color="text.secondary" align="center" sx={{ py: 5 }}>No settled trades yet — cumulative P&amp;L will appear here.</Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Card>
        <CardContent>
          <Typography variant="subtitle1" gutterBottom>Trade log</Typography>
          {trades.length === 0 && skips.length === 0 ? (
            <Typography color="text.secondary">No paper trades logged yet. Save settings and click <b>Run today</b>, or wait for the next prediction refresh.</Typography>
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead><TableRow>
                  {["Date", "Stock", "Score", "Qty", "Entry", "Exit", "P&L", "Reason", "Status"].map((h, i) => (
                    <TableCell key={h} align={i === 0 || i === 1 ? "left" : "right"}>{h}</TableCell>
                  ))}
                </TableRow></TableHead>
                <TableBody>
                  {trades.map((t) => {
                    const pnl = t.pnl_inr; const entry = t.entry_price ?? t.signal_entry_price;
                    return (
                      <TableRow key={t.id} hover>
                        <TableCell>{t.trade_date}</TableCell>
                        <TableCell><TickerLink ticker={t.ticker}>{t.name || t.ticker}</TickerLink></TableCell>
                        <TableCell align="right">{fmtNum(t.stock_score, 0)}</TableCell>
                        <TableCell align="right">{t.qty}</TableCell>
                        <TableCell align="right">{entry != null ? "₹" + fmtNum(entry, 2) : "—"}</TableCell>
                        <TableCell align="right">{t.exit_price != null ? "₹" + fmtNum(t.exit_price, 2) : "—"}</TableCell>
                        <TableCell align="right" sx={{ color: pnl == null ? "text.primary" : pnl >= 0 ? "success.main" : "error.main" }}>
                          {pnl != null ? (pnl >= 0 ? "+" : "") + "₹" + fmtNum(pnl, 0) : "—"}
                        </TableCell>
                        <TableCell align="right">{t.exit_reason || "—"}</TableCell>
                        <TableCell align="right"><Chip size="small" label={t.status} color={statusColor(t.status)} variant="outlined" /></TableCell>
                      </TableRow>
                    );
                  })}
                  {skips.map((s, i) => (
                    <TableRow key={`sk${i}`}>
                      <TableCell>{String(s.trade_date).slice(0, 10)}</TableCell>
                      <TableCell colSpan={6}><Typography variant="body2" color="text.secondary">{s.reason}</Typography></TableCell>
                      <TableCell align="right">—</TableCell>
                      <TableCell align="right"><Chip size="small" label="skipped" variant="outlined" /></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>
    </Stack>
  );
}
