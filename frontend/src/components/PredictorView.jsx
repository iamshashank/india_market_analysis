import React, { useEffect, useRef, useState } from "react";
import {
  Box, Card, CardContent, Typography, Grid, Stack, Chip, Alert,
} from "@mui/material";
import { api } from "../lib/api.js";
import { fmtNum, fmtPct } from "../lib/format.js";
import { SectionHeader, TickerLink, ScoreRing, CardGridSkeleton, KpiSkeleton } from "./common.jsx";
import { hoverCard } from "../theme.js";
import { useUI } from "../uiContext.js";
import { useMarket } from "../markets.js";

const sign = (x) => (x == null ? "text.primary" : x >= 0 ? "success.main" : "error.main");
const confColor = (c) => { const l = (c || "").toLowerCase(); return l === "high" ? "success" : l === "medium" ? "warning" : "default"; };

function StockCard({ it, rank }) {
  const levels = [["Entry", `₹${fmtNum(it.price, 2)}`, "text.primary"],
    ["Stop", `₹${fmtNum(it.stop_price, 2)} (−${fmtNum(it.stop_pct, 1)}%)`, "error.main"],
    ["Target", `₹${fmtNum(it.target_price, 2)} (+${fmtNum(it.target_pct, 1)}%)`, "success.main"],
    ["R:R", `1 : ${fmtNum(it.rr, 1)}`, "text.primary"]];
  return (
    <Card sx={{ mb: 1.5, ...hoverCard }}>
      <CardContent sx={{ py: 1.5, "&:last-child": { pb: 1.5 } }}>
        <Stack direction="row" alignItems="center" spacing={1}>
          <Chip label={`#${rank}`} size="small" color="primary" />
          <Typography variant="subtitle2" sx={{ flex: 1 }}>
            <TickerLink ticker={it.ticker}>{it.name || it.ticker}</TickerLink>
            {it.earnings_warn && <Chip label="⚠ earnings soon" size="small" color="warning" variant="outlined" sx={{ ml: 1 }} />}
          </Typography>
          <ScoreRing value={it.score} size={46} label="bias" />
        </Stack>
        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" sx={{ my: 0.75 }}>
          <Typography variant="caption" color="text.secondary">{it.verdict}</Typography>
          <Chip label={`${it.confidence} conf`} size="small" color={confColor(it.confidence)} variant="outlined" />
          <Typography variant="caption" color="text.secondary">{it.sector}{it.adv_cr != null ? ` · ₹${fmtNum(it.adv_cr, 0)} cr/day` : ""}{it.atr_pct != null ? ` · ${fmtNum(it.atr_pct, 1)}% ATR` : ""}</Typography>
        </Stack>
        <Grid container spacing={1}>
          {levels.map(([k, v, c]) => (
            <Grid item xs={6} sm={3} key={k}>
              <Box sx={{ p: 1, borderRadius: 2, bgcolor: "action.hover" }}>
                <Typography variant="caption" color="text.secondary">{k}</Typography>
                <Typography variant="body2" fontWeight={700} color={c}>{v}</Typography>
              </Box>
            </Grid>
          ))}
        </Grid>
        {(it.reasons || []).length > 0 && (
          <Box component="ul" sx={{ m: "8px 0 0", pl: 2 }}>
            {it.reasons.map((r, i) => <Typography component="li" variant="caption" color="text.secondary" key={i}>{r}</Typography>)}
          </Box>
        )}
      </CardContent>
    </Card>
  );
}

export default function PredictorView({ active, setStatusLine }) {
  const { setBusy } = useUI();
  const { region, market: marketCfg } = useMarket();
  const [pm, setPm] = useState(null);
  const poll = useRef(null);

  async function load() {
    try {
      const j = await api.premarket();
      setBusy("predictor", j.status === "running" && !j.data);
      if (j.data) {
        setPm(j.data);
        if (active) setStatusLine(j.data.predict_for_label ? `Prediction for ${j.data.predict_for_label}` : (j.data.as_of ? `as of ${j.data.as_of}` : ""));
        if (j.status !== "running") stop(); else ensure();
      } else if (j.status === "running") ensure(); else stop();
    } catch (e) { ensure(); }
  }
  function ensure() { if (!poll.current) poll.current = setInterval(load, 4000); }
  function stop() { if (poll.current) { clearInterval(poll.current); poll.current = null; } }
  useEffect(() => { load(); return () => { stop(); setBusy("predictor", false); }; }, []);

  if (!pm) {
    return (
      <Box>
        <SectionHeader overline="Tomorrow's open" title="Next-day market-open predictor"
          subtitle="Reading global markets, futures & commodities… (~30–60s)." />
        <KpiSkeleton count={4} />
        <CardGridSkeleton count={4} />
      </Box>
    );
  }

  const b = pm.market_bias || {};
  const high = pm.high_confidence || []; const watch = pm.watchlist || [];
  const g = pm.gold_etf; const v = pm.validation;

  return (
    <Stack spacing={3}>
      <SectionHeader overline="Tomorrow's open" title="Next-day market-open predictor"
        subtitle="Which liquid NSE names are most likely to open higher tomorrow, from overnight global cues. Educational — not a guarantee." />

      {region !== "IN" && (
        <Alert severity="info" variant="outlined">
          The next-day predictor currently covers <b>India (NSE)</b> only — it's built on India-specific overnight cues
          (GIFT Nifty proxy, India VIX, ADRs). You have <b>{marketCfg.flag} {marketCfg.label}</b> selected; the India
          prediction is shown below. US/other-market open prediction isn't available yet.
        </Alert>
      )}

      <Card>
        <CardContent>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} md={3}>
              <Stack direction="row" spacing={2} alignItems="center">
                <ScoreRing value={b.score} size={72} label="bias" />
                <Box>
                  <Typography variant="caption" color="text.secondary">Market open bias</Typography>
                  <Typography variant="subtitle1">{b.label}</Typography>
                </Box>
              </Stack>
            </Grid>
            <Grid item xs={12} md={9}>
              <Grid container spacing={1}>
                {(pm.cue_strip || []).map((cu, i) => (
                  <Grid item xs={6} sm={3} key={i}>
                    <Box sx={{ p: 1, borderRadius: 2, bgcolor: "action.hover" }}>
                      <Typography variant="caption" color="text.secondary" display="block" noWrap>{cu.label}</Typography>
                      <Typography variant="subtitle2" color={sign(cu.change_pct)}>{fmtPct(cu.change_pct)}</Typography>
                    </Box>
                  </Grid>
                ))}
              </Grid>
            </Grid>
          </Grid>
          <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: "block" }}>{pm.gift_nifty_note}</Typography>
        </CardContent>
      </Card>

      <Box>
        <Typography variant="h6" gutterBottom>Stocks likely to open higher tomorrow</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          Liquid NSE names ranked by overnight cues, sector sensitivity &amp; beta. Each idea has an ATR-based stop &amp; target — not a guarantee.
        </Typography>
        {high.length === 0 && watch.length === 0 ? (
          <Alert severity="info">Overnight cues are weak or mixed — no clear up-bias names. Staying out is often the disciplined move.</Alert>
        ) : (
          <>
            {high.length > 0 && <><Typography variant="subtitle1" color="success.main" gutterBottom>Higher-confidence</Typography>{high.map((it, i) => <StockCard key={it.ticker} it={it} rank={i + 1} />)}</>}
            {watch.length > 0 && <><Typography variant="subtitle1" gutterBottom sx={{ mt: 1 }}>Watchlist (lower confidence)</Typography>{watch.map((it, i) => <StockCard key={it.ticker} it={it} rank={i + 1} />)}</>}
          </>
        )}
      </Box>

      {g && (
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>Gold ETF prediction (next day)</Typography>
            <Typography variant="subtitle1" color={sign(g.implied_move_pct)}>{g.direction}</Typography>
            <Box component="ul" sx={{ pl: 2, mt: 1 }}>
              {(g.drivers || []).map((d, i) => <Typography component="li" variant="body2" key={i}><b>{d.label}</b> {fmtPct(d.change_pct)} — {d.effect}</Typography>)}
            </Box>
            <Typography variant="caption" color="text.secondary">{g.method}</Typography>
          </CardContent>
        </Card>
      )}

      {v && (
        <Box>
          <Typography variant="h6" gutterBottom>Model accuracy (backtested)</Typography>
          <Grid container spacing={1.5}>
            {[["Baseline: any day opens up", v.gap?.overall_gap_up_pct != null ? { hit_rate: v.gap.overall_gap_up_pct, n: v.gap.sample_days } : null],
              ["Opens up · overnight UP", v.gap?.gap_up_when_overnight_up],
              ["Opens up · overnight DOWN", v.gap?.gap_up_when_overnight_down],
              ["Gap holds 1st hour", v.first_hour?.first_hour_up_when_gap_up]].map(([label, r], i) => (
              <Grid item xs={6} md={3} key={i}>
                <Card sx={hoverCard}><CardContent>
                  <Typography variant="caption" color="text.secondary">{label}</Typography>
                  <Typography variant="h5" color={r ? sign(r.hit_rate - 50) : "text.primary"}>{r ? fmtNum(r.hit_rate, 1) + "%" : "n/a"}</Typography>
                  {r && <Typography variant="caption" color="text.secondary">{r.n} samples</Typography>}
                </CardContent></Card>
              </Grid>
            ))}
          </Grid>
          {v.caveat && <Alert severity="warning" sx={{ mt: 1.5 }}>{v.caveat}</Alert>}
        </Box>
      )}
    </Stack>
  );
}
