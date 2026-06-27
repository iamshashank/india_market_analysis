import React, { useEffect, useState } from "react";
import {
  Dialog, DialogTitle, DialogContent, IconButton, Typography, Grid, Box, Stack,
  Chip, Divider, Tabs, Tab, ToggleButtonGroup, ToggleButton, Table, TableBody,
  TableCell, TableContainer, TableHead, TableRow, Paper, Link, Skeleton, Alert,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";
import { api } from "../lib/api.js";
import { fmtKind, humanizeMoney, moneyPrice, yahooUrl } from "../lib/format.js";
import { MarketChip } from "./common.jsx";
import PriceChart from "./PriceChart.jsx";

function HealthPanel({ health }) {
  if (!health) return null;
  const { piotroski, altman_z, graham, magic_formula, beneish_m } = health;
  const items = [];
  if (piotroski) {
    const c = piotroski.score >= 7 ? "success" : piotroski.score >= 4 ? "warning" : "error";
    items.push({ label: "Piotroski F-Score", value: `${piotroski.score} / ${piotroski.max}`, sub: piotroski.label, color: c });
  }
  if (altman_z) {
    const c = altman_z.zone === "Safe" ? "success" : altman_z.zone === "Grey" ? "warning" : "error";
    items.push({ label: "Altman Z-Score", value: altman_z.value, sub: `${altman_z.zone} zone`, color: c });
  }
  if (graham) {
    const c = graham.upside_pct == null ? "default" : graham.upside_pct >= 0 ? "success" : "error";
    items.push({ label: "Graham Number", value: graham.number, sub: graham.upside_pct != null ? `${graham.upside_pct >= 0 ? "+" : ""}${graham.upside_pct}% vs price` : "", color: c });
  }
  if (magic_formula?.earnings_yield_pct != null) {
    items.push({ label: "Earnings Yield (MF)", value: `${magic_formula.earnings_yield_pct}%`, sub: magic_formula.roc_pct != null ? `ROC ${magic_formula.roc_pct}%` : "", color: "default" });
  }
  if (beneish_m) {
    const c = beneish_m.value > -1.78 ? "error" : "success";
    items.push({ label: "Beneish M-Score", value: beneish_m.value, sub: beneish_m.flag, color: c });
  }
  if (!items.length) return null;
  return (
    <Box sx={{ mb: 2 }}>
      <Typography variant="overline" color="primary">Financial health (proven quant scores)</Typography>
      <Grid container spacing={1.5} sx={{ mt: 0 }}>
        {items.map((it) => (
          <Grid item xs={6} sm={4} md={2.4} key={it.label}>
            <Box sx={{ p: 1.25, borderRadius: 2, border: 1, borderColor: it.color === "default" ? "divider" : `${it.color}.main`, height: "100%" }}>
              <Typography variant="caption" color="text.secondary" display="block" noWrap>{it.label}</Typography>
              <Typography variant="subtitle1" fontWeight={800} color={it.color === "default" ? "text.primary" : `${it.color}.main`}>{it.value}</Typography>
              {it.sub && <Typography variant="caption" color="text.secondary" noWrap display="block">{it.sub}</Typography>}
            </Box>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}

const STMT_TABS = [
  { id: "income", label: "Income statement" },
  { id: "balance", label: "Balance sheet" },
  { id: "cashflow", label: "Cash flow" },
];

function StatementTable({ stmt, currency }) {
  if (!stmt || !stmt.rows?.length) return <Typography color="text.secondary" sx={{ p: 2 }}>No data reported.</Typography>;
  return (
    <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: 460 }}>
      <Table size="small" stickyHeader>
        <TableHead>
          <TableRow>
            <TableCell sx={{ fontWeight: 700 }}>Line item</TableCell>
            {stmt.periods.map((p) => <TableCell key={p} align="right" sx={{ fontWeight: 700 }}>{p}</TableCell>)}
          </TableRow>
        </TableHead>
        <TableBody>
          {stmt.rows.map((r) => (
            <TableRow key={r.label} hover>
              <TableCell>{r.label}</TableCell>
              {r.values.map((v, i) => (
                <TableCell key={i} align="right" sx={{ color: v < 0 ? "error.main" : "text.primary" }}>
                  {v == null ? "—" : humanizeMoney(v, currency)}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

export default function StockDetailDialog({ ticker, open, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState("income");
  const [period, setPeriod] = useState("annual");

  useEffect(() => {
    if (!open || !ticker) return;
    let cancelled = false;
    setLoading(true); setData(null); setTab("income"); setPeriod("annual");
    api.fundamentals(ticker).then((j) => { if (!cancelled) { setData(j); setLoading(false); } })
      .catch(() => { if (!cancelled) { setData({ available: false, reason: "Request failed" }); setLoading(false); } });
    return () => { cancelled = true; };
  }, [open, ticker]);

  const cur = data?.currency || "USD";
  const stmt = data?.statements?.[`${tab}_${period}`];

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="lg" scroll="paper">
      <DialogTitle sx={{ pr: 6 }}>
        {data?.available ? (
          <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap">
            <Typography variant="h6">{data.name}</Typography>
            <MarketChip m={data.market} />
            <Typography variant="body2" color="text.secondary">{data.ticker}{data.sector ? ` · ${data.sector}` : ""}</Typography>
            {data.price != null && <Chip size="small" label={moneyPrice(data.price, cur)} />}
            <Link href={yahooUrl(ticker)} target="_blank" rel="noopener noreferrer" sx={{ display: "inline-flex", alignItems: "center", gap: 0.5 }}>
              Yahoo <OpenInNewIcon fontSize="inherit" />
            </Link>
          </Stack>
        ) : <Typography variant="h6">{ticker}</Typography>}
        <IconButton onClick={onClose} sx={{ position: "absolute", right: 8, top: 8 }} aria-label="Close"><CloseIcon /></IconButton>
      </DialogTitle>

      <DialogContent dividers>
        {loading && (
          <Box>
            <Grid container spacing={1.5}>
              {Array.from({ length: 12 }).map((_, i) => (
                <Grid item xs={6} sm={4} md={3} key={i}><Skeleton variant="rounded" height={48} /></Grid>
              ))}
            </Grid>
            <Skeleton variant="rounded" height={300} sx={{ mt: 2 }} />
          </Box>
        )}

        {!loading && data && !data.available && (
          <Alert severity="info">Couldn't load fundamentals{data.reason ? `: ${data.reason}` : "."}</Alert>
        )}

        {!loading && data?.available && (
          <Box>
            {data.summary && <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>{data.summary}</Typography>}

            <Box sx={{ mb: 2 }}><PriceChart ticker={data.ticker} currency={cur} /></Box>

            <HealthPanel health={data.health} />

            <Typography variant="overline" color="primary">Fundamentals &amp; ratios</Typography>
            <Grid container spacing={1.5} sx={{ mt: 0, mb: 2 }}>
              {data.ratios.map((r) => (
                <Grid item xs={6} sm={4} md={3} key={r.label}>
                  <Box sx={{ p: 1.25, borderRadius: 2, bgcolor: "action.hover", height: "100%" }}>
                    <Typography variant="caption" color="text.secondary" display="block" noWrap>{r.label}</Typography>
                    <Typography variant="subtitle2" fontWeight={700}>{fmtKind(r.value, r.kind, cur)}</Typography>
                  </Box>
                </Grid>
              ))}
            </Grid>

            <Divider sx={{ mb: 1.5 }} />
            <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" sx={{ mb: 1.5, gap: 1 }}>
              <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="scrollable" scrollButtons="auto">
                {STMT_TABS.map((t) => <Tab key={t.id} value={t.id} label={t.label} />)}
              </Tabs>
              <ToggleButtonGroup exclusive size="small" value={period} onChange={(_, v) => v && setPeriod(v)}>
                <ToggleButton value="annual">Annual</ToggleButton>
                <ToggleButton value="quarterly">Quarterly</ToggleButton>
              </ToggleButtonGroup>
            </Stack>
            <StatementTable stmt={stmt} currency={cur} />
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1.5 }}>
              Amounts in {cur === "INR" ? "₹ (Cr/L where large)" : "$ (M/B where large)"} · source: {data.source}. Educational — not investment advice.
            </Typography>
          </Box>
        )}
      </DialogContent>
    </Dialog>
  );
}
