import React, { useEffect, useRef, useState } from "react";
import {
  Box, Card, CardContent, Typography, Grid, Stack, Chip, LinearProgress, Tooltip,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, List, ListItem,
  Accordion, AccordionSummary, AccordionDetails, Button, ToggleButton, ToggleButtonGroup, Alert,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import AssessmentIcon from "@mui/icons-material/Assessment";
import StockDetailDialog from "./StockDetailDialog.jsx";
import RocketLaunchIcon from "@mui/icons-material/RocketLaunch";
import EmojiEventsIcon from "@mui/icons-material/EmojiEvents";
import LocalFireDepartmentIcon from "@mui/icons-material/LocalFireDepartment";
import TravelExploreIcon from "@mui/icons-material/TravelExplore";
import { api } from "../lib/api.js";
import { fmtNum, fmtPctFrac, fmtUsd } from "../lib/format.js";
import {
  SectionHeader, KpiCard, ScoreRing, TickerLink, MarketChip, Jargon,
  pillarColor, convColor, candleColor, scoreColor, CardGridSkeleton, KpiSkeleton,
} from "./common.jsx";
import { hoverCard } from "../theme.js";
import { useUI } from "../uiContext.js";
import { useMarket } from "../markets.js";
import { useSearchParams, Link as RouterLink, useLocation } from "react-router-dom";

const PILLARS = {
  room_to_grow: "Room to grow", consistency: "Earnings consistency",
  under_covered: "Low coverage", growth: "Growth", quality: "Quality",
  valuation: "Valuation", catalyst: "News catalyst",
};

const tierColor = (t) => ({ Mega: "secondary", Large: "primary", Mid: "info", Small: "warning", Micro: "error" }[t] || "default");

function PillarBars({ pillars }) {
  return (
    <Stack spacing={0.6}>
      {Object.keys(PILLARS).map((k) => {
        const v = pillars?.[k];
        if (v == null) return null;
        return (
          <Box key={k} sx={{ display: "grid", gridTemplateColumns: "118px 1fr 26px", alignItems: "center", gap: 1 }}>
            <Typography variant="caption" color="text.secondary"><Jargon term={PILLARS[k]} /></Typography>
            <LinearProgress variant="determinate" value={Math.max(2, Math.min(100, v))} color={pillarColor(v)} sx={{ height: 7 }} />
            <Typography variant="caption" fontWeight={700} align="right">{Math.round(v)}</Typography>
          </Box>
        );
      })}
    </Stack>
  );
}

function Metric({ k, v }) {
  return (
    <Grid item xs={4}>
      <Typography variant="caption" color="text.secondary"><Jargon term={k} /> </Typography>
      <Typography variant="caption" fontWeight={700}>{v}</Typography>
    </Grid>
  );
}

function Headlines({ headlines }) {
  if (!headlines?.length) {
    return <Typography variant="body2" color="text.secondary" fontStyle="italic">No recent headlines — part of the "hidden" thesis.</Typography>;
  }
  return (
    <List dense disablePadding>
      {headlines.slice(0, 4).map((h, i) => (
        <ListItem key={i} disableGutters sx={{ alignItems: "flex-start", gap: 1, py: 0.3 }}>
          <Box sx={{ width: 8, height: 8, borderRadius: "50%", mt: 0.8, flexShrink: 0,
            bgcolor: h.tone === "positive" ? "success.main" : h.tone === "negative" ? "error.main" : "text.disabled" }} />
          <Typography variant="body2">
            {h.link ? <a href={h.link} target="_blank" rel="noopener noreferrer" style={{ color: "inherit" }}>{h.title}</a> : h.title}
            {h.events?.length ? <Chip label={h.events[0]} size="small" variant="outlined" sx={{ ml: 0.5, height: 18 }} /> : null}
            <Typography component="span" variant="caption" color="text.secondary"> {h.publisher || ""}{h.date ? " · " + h.date : ""}</Typography>
          </Typography>
        </ListItem>
      ))}
    </List>
  );
}

function PortfolioCard({ p, rank, onOpen }) {
  const m = p.metrics || {};
  const metrics = [["P/E", fmtNum(m.trailing_pe, 1)], ["Ind. P/E", p.industry_pe != null ? fmtNum(p.industry_pe, 1) : "—"],
    ["PEG", fmtNum(m.peg, 2)], ["ROE", fmtPctFrac(m.roe)],
    ["Margin", fmtPctFrac(m.profit_margin)], ["Rev gr", fmtPctFrac(m.revenue_growth)],
    ["Analysts", p.num_analysts ?? "—"]];
  return (
    <Card sx={{ height: "100%", ...hoverCard }}>
      <CardContent>
        <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1}>
          <Box sx={{ minWidth: 0 }}>
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
              <Chip label={`#${rank}`} size="small" color="primary" />
              <Typography variant="subtitle1"><TickerLink ticker={p.ticker}>{p.name || p.ticker}</TickerLink></Typography>
              <MarketChip m={p.market} />
              {p.cap_tier && <Chip label={p.cap_tier} size="small" variant="outlined" color={tierColor(p.cap_tier)} />}
            </Stack>
            <Typography variant="caption" color="text.secondary">{p.ticker} · {p.sector} · {fmtUsd(p.market_cap_usd)} cap</Typography>
          </Box>
          <ScoreRing value={p.score} size={60} />
        </Stack>

        <Stack direction="row" spacing={1} alignItems="center" sx={{ my: 1.2, p: 1, borderRadius: 2, bgcolor: "action.hover" }}>
          <Typography variant="h6" color="success.main">{fmtNum(p.weight_pct, 1)}%</Typography>
          <Typography variant="caption" color="text.secondary" sx={{ flex: 1 }}>suggested weight · {p.size_tier} position</Typography>
          <Chip size="small" label={`${p.conviction} conviction`} color={convColor(p.conviction)} variant={p.conviction === "Speculative" ? "outlined" : "filled"} />
        </Stack>

        <PillarBars pillars={p.pillars} />

        <Grid container spacing={0.5} sx={{ my: 1, py: 1, borderTop: 1, borderBottom: 1, borderColor: "divider" }}>
          {metrics.map(([k, v]) => <Metric key={k} k={k} v={v} />)}
        </Grid>

        {p.candle && (
          <Tooltip title={`Most recent candlestick pattern (${p.candle.date}) — a short-term timing signal.`} arrow>
            <Chip size="small" sx={{ mb: 1 }} color={candleColor(p.candle.bias)} variant="outlined"
              label={`${p.candle.bias === "bullish" ? "▲" : p.candle.bias === "bearish" ? "▼" : "•"} ${p.candle.pattern} · ${p.candle.date}`} />
          </Tooltip>
        )}

        <Typography variant="overline" color="success.main">Why it fits</Typography>
        <List dense disablePadding sx={{ mb: 1, listStyleType: "disc", pl: 2 }}>
          {(p.thesis || []).map((t, i) => <ListItem key={i} sx={{ display: "list-item", py: 0 }}><Typography variant="body2">{t}</Typography></ListItem>)}
        </List>
        <Typography variant="overline" color="error.main">Key risks</Typography>
        <List dense disablePadding sx={{ mb: 1, listStyleType: "disc", pl: 2 }}>
          {(p.risks || []).map((t, i) => <ListItem key={i} sx={{ display: "list-item", py: 0 }}><Typography variant="body2" color="text.secondary">{t}</Typography></ListItem>)}
        </List>

        {(p.news?.top_events || []).length > 0 && (
          <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap sx={{ mb: 1 }}>
            {p.news.top_events.map((e, i) => <Chip key={i} label={e} size="small" color="success" variant="outlined" />)}
          </Stack>
        )}
        <Typography variant="overline" color="primary">Recent news · catalyst {Math.round(p.news?.catalyst_score ?? 50)}/100</Typography>
        <Headlines headlines={p.news?.headlines} />
        <Typography variant="caption" color="text.secondary" fontStyle="italic" display="block" sx={{ mt: 1 }}>{p.entry_note}</Typography>
        <Button fullWidth size="small" variant="outlined" startIcon={<AssessmentIcon />} sx={{ mt: 1.5 }} onClick={() => onOpen(p.ticker)}>
          View full fundamentals
        </Button>
      </CardContent>
    </Card>
  );
}

export default function ScreenView({ active, setStatusLine }) {
  const { setBusy } = useUI();
  const { region: market, market: marketCfg } = useMarket();
  const [data, setData] = useState(null);
  const [sel, setSel] = useState(null);
  const [params] = useSearchParams();
  const location = useLocation();
  const tier = params.get("tier") || "All";
  const tierHref = (t) => {
    const sp = new URLSearchParams(params);
    if (t && t !== "All") sp.set("tier", t); else sp.delete("tier");
    const qs = sp.toString();
    return `${location.pathname}${qs ? "?" + qs : ""}`;
  };
  const poll = useRef(null);

  async function load() {
    try {
      const j = await api.screen();
      setBusy("screen", j.status === "running");
      if (j.data) {
        setData(j.data);
        if (active) setStatusLine(j.data.as_of ? `as of ${j.data.as_of}` : "");
        if (j.status !== "running") stop(); else ensure();
      } else ensure();
    } catch (e) { ensure(); }
  }
  function ensure() { if (!poll.current) poll.current = setInterval(load, 5000); }
  function stop() { if (poll.current) { clearInterval(poll.current); poll.current = null; } }
  useEffect(() => { load(); return () => { stop(); setBusy("screen", false); }; }, []);

  if (!data) {
    return (
      <Box>
        <SectionHeader overline="Wealth-creation screen" title="Multibagger compounders across cap tiers"
          subtitle="Scanning India + US across every market-cap tier, earnings history & news… (~1–2 min the first time)." />
        <KpiSkeleton count={4} />
        <CardGridSkeleton count={6} />
      </Box>
    );
  }

  const marketsAvail = marketCfg.markets;
  const inMarket = (x) => marketsAvail.includes(x.market);
  const tierList = marketCfg.tiers;
  const tierCounts = data.tier_counts || {};

  // tier portfolios for the selected market (+ BSE folded into India)
  const tierPfs = (data.tier_portfolios || []).filter((g) => marketsAvail.includes(g.market));
  const flatPf = (data.portfolio || []).filter(inMarket);
  const avgScore = flatPf.length ? Math.round(flatPf.reduce((s, p) => s + p.score, 0) / flatPf.length) : 0;
  const topTheme = (data.themes || [])[0];
  const totalScored = Object.values(tierCounts).reduce((a, m) => a + Object.values(m).reduce((x, y) => x + y, 0), 0);

  // shortlist filtered by market + tier
  let sl = (data.shortlist || []).filter(inMarket);
  if (tier !== "All") sl = sl.filter((s) => s.cap_tier === tier);

  // which tier sections to show
  const showTiers = tier === "All" ? tierList : [tier];

  return (
    <Stack spacing={3}>
      <SectionHeader
        overline="Wealth-creation screen"
        title={data.strategy?.title || "Multibagger compounders across cap tiers"}
        subtitle="Room to grow (size-neutral, ranked within each cap tier) · consistent earnings · limited coverage · news catalysts → concentrated, high-conviction ideas per size class. Not investment advice." />

      {/* cap-tier filter (market is chosen globally in the top bar) */}
      <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap alignItems="center">
        <Typography variant="body2" color="text.secondary">{marketCfg.flag} {marketCfg.label} · filter by size:</Typography>
        <ToggleButtonGroup exclusive size="small" value={tier}>
          <ToggleButton value="All" component={RouterLink} to={tierHref("All")}>All caps</ToggleButton>
          {tierList.map((t) => {
            const cnt = marketsAvail.reduce((a, m) => a + ((tierCounts[m] || {})[t] || 0), 0);
            return <ToggleButton key={t} value={t} component={RouterLink} to={tierHref(t)}>{t}{cnt ? ` (${cnt})` : ""}</ToggleButton>;
          })}
        </ToggleButtonGroup>
      </Stack>

      {/* headline KPI strip */}
      <Grid container spacing={2}>
        <Grid item xs={6} md={3}><KpiCard icon={<RocketLaunchIcon />} label="Portfolio ideas" value={flatPf.length} caption={`${market} · all tiers`} /></Grid>
        <Grid item xs={6} md={3}><KpiCard icon={<EmojiEventsIcon />} label="Avg portfolio score" value={avgScore} color={`${scoreColor(avgScore)}.main`} caption="0–100 composite" /></Grid>
        <Grid item xs={6} md={3}><KpiCard icon={<LocalFireDepartmentIcon />} label="Hottest theme" value={topTheme ? topTheme.theme.replace(/ &.*/, "") : "—"} caption={topTheme ? `heat ${Math.round(topTheme.heat)}` : ""} /></Grid>
        <Grid item xs={6} md={3}><KpiCard icon={<TravelExploreIcon />} label="Universe scanned" value={data.universe_size} caption={`${totalScored || data.scored_count} passed · ${data.build_seconds || "—"}s`} /></Grid>
      </Grid>

      <BacktestPanel contemporaneous={data.score_validation} />

      {/* per-tier portfolios */}
      {showTiers.map((t) => {
        const grp = tierPfs.find((g) => g.cap_tier === t);
        const pfRows = grp?.portfolio || [];
        const cnt = marketsAvail.reduce((a, m) => a + ((tierCounts[m] || {})[t] || 0), 0);
        return (
          <Box key={t}>
            <SectionHeader
              title={<Stack direction="row" spacing={1} alignItems="center"><span>{t}-cap portfolio</span><Chip size="small" variant="outlined" color={tierColor(t)} label={`${cnt} screened`} /></Stack>}
              subtitle={pfRows.length ? `Best ${t.toLowerCase()}-cap compounders in ${market}, ranked within this size class.` : undefined} />
            {pfRows.length === 0 ? (
              <Card><CardContent><Typography color="text.secondary">No {t}-cap names clear the conviction threshold yet{cnt ? ` (of ${cnt} screened)` : ""}.</Typography></CardContent></Card>
            ) : (
              <Grid container spacing={2}>
                {pfRows.map((p, i) => <Grid item xs={12} md={6} lg={4} key={p.ticker}><PortfolioCard p={p} rank={i + 1} onOpen={setSel} /></Grid>)}
              </Grid>
            )}
          </Box>
        );
      })}

      {/* shortlist behind progressive disclosure */}
      <Accordion variant="outlined" disableGutters sx={{ borderRadius: 2, "&:before": { display: "none" } }}>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="subtitle1">Full ranked shortlist</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ ml: 1.5, alignSelf: "center" }}>{sl.length} names · {market}{tier !== "All" ? ` · ${tier}-cap` : " · all tiers"}</Typography>
        </AccordionSummary>
        <AccordionDetails sx={{ p: 0 }}>
          <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: 560 }}>
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  {["#", "Stock", "Mkt", "Tier", "Sector", "Score", "Cap", "P/E", "Ind. P/E", "Room", "Consistency", "Low cov.", "Growth", "Quality", "Catalyst", "Candle"].map((h, i) => (
                    <TableCell key={h} align={i < 2 || i === 4 || i === 15 ? "left" : "right"}>{h}</TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {sl.map((r, i) => {
                  const pl = r.pillars || {}; const cat = pl.catalyst ?? 50;
                  return (
                    <TableRow key={r.ticker} hover sx={{ cursor: "pointer" }} onClick={() => setSel(r.ticker)}>
                      <TableCell>{i + 1}</TableCell>
                      <TableCell><Typography variant="body2" fontWeight={700} color="primary">{r.name || r.ticker}</Typography></TableCell>
                      <TableCell align="right">{r.market}</TableCell>
                      <TableCell><Chip size="small" variant="outlined" color={tierColor(r.cap_tier)} label={r.cap_tier} /></TableCell>
                      <TableCell>{r.sector}</TableCell>
                      <TableCell align="right"><Chip size="small" label={Math.round(r.score)} color={scoreColor(r.score)} variant="outlined" /></TableCell>
                      <TableCell align="right">{fmtUsd(r.market_cap_usd)}</TableCell>
                      <TableCell align="right">{fmtNum(r.metrics?.trailing_pe, 1)}</TableCell>
                      <TableCell align="right">{r.industry_pe != null ? fmtNum(r.industry_pe, 1) : "—"}</TableCell>
                      <TableCell align="right">{Math.round(pl.room_to_grow ?? 0)}</TableCell>
                      <TableCell align="right">{Math.round(pl.consistency ?? 0)}</TableCell>
                      <TableCell align="right">{Math.round(pl.under_covered ?? 0)}</TableCell>
                      <TableCell align="right">{Math.round(pl.growth ?? 0)}</TableCell>
                      <TableCell align="right">{Math.round(pl.quality ?? 0)}</TableCell>
                      <TableCell align="right" sx={{ color: cat >= 55 ? "success.main" : cat <= 45 ? "error.main" : "text.primary" }}>{Math.round(cat)}</TableCell>
                      <TableCell>{r.candle ? <Chip size="small" variant="outlined" color={candleColor(r.candle.bias)} label={r.candle.pattern} /> : "—"}</TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
        </AccordionDetails>
      </Accordion>

      <StockDetailDialog ticker={sel} open={!!sel} onClose={() => setSel(null)} />
    </Stack>
  );
}

function BacktestPanel({ contemporaneous }) {
  const [bt, setBt] = useState(null);
  useEffect(() => {
    let cancelled = false;
    api.backtest().then((j) => { if (!cancelled) setBt(j); }).catch(() => { if (!cancelled) setBt({ available: false }); });
    return () => { cancelled = true; };
  }, []);

  // Real forward backtest available → show it.
  if (bt?.available && (bt.buckets || []).length) {
    return (
      <Card>
        <CardContent>
          <Typography variant="overline" color="success.main">Forward-return backtest (real)</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            Stocks scored on <b>{bt.baseline_date}</b> (~{bt.horizon_days}d ago), bucketed by score; forward return
            measured to the latest price. {bt.snapshots} snapshots accumulated.
          </Typography>
          <Grid container spacing={1.5}>
            {bt.buckets.map((b) => (
              <Grid item xs={6} sm={3} key={b.bucket}>
                <Box sx={{ p: 1.25, borderRadius: 2, bgcolor: "action.hover" }}>
                  <Typography variant="caption" color="text.secondary">Score {b.bucket} · {b.count} names</Typography>
                  <Typography variant="h6" color={b.avg_fwd_return_pct >= 0 ? "success.main" : "error.main"}>
                    {b.avg_fwd_return_pct >= 0 ? "+" : ""}{b.avg_fwd_return_pct}%
                  </Typography>
                  <Typography variant="caption" color="text.secondary">{b.hit_rate_pct}% positive</Typography>
                </Box>
              </Grid>
            ))}
          </Grid>
          {bt.caveat && <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>⚠ {bt.caveat}</Typography>}
        </CardContent>
      </Card>
    );
  }

  // Otherwise: contemporaneous association + a note that the real one is accruing.
  if (!(contemporaneous || []).length) return null;
  return (
    <Card>
      <CardContent>
        <Typography variant="overline" color="primary">Does the score track returns?</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          Average <b>trailing</b> 1-year return by score bucket (association check across the current universe).
          {bt && !bt.available && bt.reason ? ` Real forward backtest: ${bt.reason}` : " A real forward-return backtest is accumulating as the screen runs daily."}
        </Typography>
        <Grid container spacing={1.5}>
          {contemporaneous.map((b) => (
            <Grid item xs={6} sm={3} key={b.bucket}>
              <Box sx={{ p: 1.25, borderRadius: 2, bgcolor: "action.hover" }}>
                <Typography variant="caption" color="text.secondary">Score {b.bucket} · {b.count} names</Typography>
                <Typography variant="h6" color={b.avg_ret_1y_pct == null ? "text.primary" : b.avg_ret_1y_pct >= 0 ? "success.main" : "error.main"}>
                  {b.avg_ret_1y_pct == null ? "n/a" : `${b.avg_ret_1y_pct >= 0 ? "+" : ""}${b.avg_ret_1y_pct}%`}
                </Typography>
              </Box>
            </Grid>
          ))}
        </Grid>
      </CardContent>
    </Card>
  );
}
