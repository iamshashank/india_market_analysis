import React, { useEffect, useState } from "react";
import {
  Box, Card, CardContent, Typography, Grid, Stack, Chip, LinearProgress, Button,
  Alert, List, ListItem, Divider,
} from "@mui/material";
import AssessmentIcon from "@mui/icons-material/Assessment";
import { useSearchParams } from "react-router-dom";
import { LineChart } from "@mui/x-charts/LineChart";
import { api } from "../lib/api.js";
import { fmtNum, fmtPctFrac, fmtUsd } from "../lib/format.js";
import {
  SectionHeader, ScoreRing, TickerLink, MarketChip, Jargon,
  pillarColor, convColor, candleColor, scoreColor, CardGridSkeleton,
} from "./common.jsx";
import SymbolSearch from "./SymbolSearch.jsx";
import StockDetailDialog from "./StockDetailDialog.jsx";
import PriceChart from "./PriceChart.jsx";
import { useMarket } from "../markets.js";

const PILLARS = {
  room_to_grow: "Room to grow", consistency: "Earnings consistency",
  under_covered: "Low coverage", growth: "Growth", quality: "Quality",
  valuation: "Valuation", catalyst: "News catalyst",
};
const tierColor = (t) => ({ Mega: "secondary", Large: "primary", Mid: "info", Small: "warning", Micro: "error" }[t] || "default");

export default function AnalyzeView() {
  const { region, market: marketCfg } = useMarket();
  const [params, setParams] = useSearchParams();
  const ticker = params.get("ticker") || "";
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showDialog, setShowDialog] = useState(false);

  function pick(tk) { setParams((p) => { p.set("ticker", tk); return p; }, { replace: true }); }

  useEffect(() => {
    if (!ticker) { setData(null); return; }
    let cancelled = false;
    setLoading(true); setData(null);
    api.analyze(ticker)
      .then((j) => { if (!cancelled) { setData(j); setLoading(false); } })
      .catch(() => { if (!cancelled) { setData({ available: false, reason: "Request failed" }); setLoading(false); } });
    return () => { cancelled = true; };
  }, [ticker]);

  const wsum = data?.weights ? Object.values(data.weights).reduce((a, b) => a + b, 0) : 1;

  return (
    <Box>
      <SectionHeader overline="Analyze any company" title="Search & score any stock"
        subtitle="Type a company name or symbol (NSE / BSE / US). It runs the full multibagger algorithm on that one stock — composite score, every pillar, conviction, candlestick, news catalysts and full fundamentals." />

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <SymbolSearch onPick={pick} size="medium" sx={{ maxWidth: 520 }}
            placeholder={`e.g. ${marketCfg.id === "IN" ? "Reliance, RELIANCE.NS, Tata Elxsi" : "Apple, AAPL, AAON"}…`} />
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1 }}>
            Search any market — you're viewing <b>{marketCfg.flag} {marketCfg.label}</b> by default, but you can analyze any NSE / BSE / US stock here.
          </Typography>
        </CardContent>
      </Card>

      {loading && <CardGridSkeleton count={3} />}

      {!loading && data && !data.available && (
        <Alert severity="info">Couldn't analyze {ticker}{data.reason ? `: ${data.reason}` : "."}</Alert>
      )}

      {!loading && data?.available && (
        <Stack spacing={2}>
          {(data.warnings || []).length > 0 && (
            <Alert severity="warning" variant="outlined">
              <Stack component="ul" sx={{ m: 0, pl: 2 }}>
                {data.warnings.map((w, i) => <li key={i}><Typography variant="body2">{w}</Typography></li>)}
              </Stack>
            </Alert>
          )}
          <Card>
            <CardContent>
              <Grid container spacing={2} alignItems="center">
                <Grid item xs={12} sm="auto"><ScoreRing value={data.score} size={84} /></Grid>
                <Grid item xs={12} sm>
                  <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                    <Typography variant="h5"><TickerLink ticker={data.ticker}>{data.name || data.ticker}</TickerLink></Typography>
                    <MarketChip m={data.market} />
                    {data.cap_tier && <Chip size="small" variant="outlined" color={tierColor(data.cap_tier)} label={`${data.cap_tier}-cap`} />}
                    <Chip size="small" color={convColor(data.conviction)} variant={data.conviction === "Speculative" ? "outlined" : "filled"} label={`${data.conviction} conviction`} />
                  </Stack>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                    {data.ticker} · {data.sector}{data.industry ? ` · ${data.industry}` : ""} · {fmtUsd(data.market_cap_usd)} cap
                    {data.rank ? ` · ranks #${data.rank} of ${data.scored_total} vs peers` : ""}
                  </Typography>
                  {data.candle && (
                    <Chip size="small" sx={{ mt: 1 }} color={candleColor(data.candle.bias)} variant="outlined"
                      label={`${data.candle.bias === "bullish" ? "▲" : data.candle.bias === "bearish" ? "▼" : "•"} ${data.candle.pattern} · ${data.candle.date}`} />
                  )}
                </Grid>
                <Grid item xs={12} sm="auto">
                  <Button variant="contained" startIcon={<AssessmentIcon />} onClick={() => setShowDialog(true)}>Full fundamentals</Button>
                </Grid>
              </Grid>
            </CardContent>
          </Card>

          <PriceChart ticker={data.ticker} currency={data.currency} />
          <ScoreHistoryCard ticker={data.ticker} currentScore={data.score} />

          <Grid container spacing={2}>
            <Grid item xs={12} md={7}>
              <Card sx={{ height: "100%" }}>
                <CardContent>
                  <Typography variant="overline" color="primary">Score breakdown (weighted pillars)</Typography>
                  <Stack spacing={1} sx={{ mt: 1 }}>
                    {Object.keys(PILLARS).map((k) => {
                      const v = data.pillars?.[k];
                      if (v == null) return null;
                      const w = data.weights?.[k] ? Math.round((data.weights[k] / wsum) * 100) : null;
                      return (
                        <Box key={k} sx={{ display: "grid", gridTemplateColumns: "150px 1fr 40px", alignItems: "center", gap: 1 }}>
                          <Typography variant="body2" color="text.secondary">
                            <Jargon term={PILLARS[k]} />{w != null ? <Typography component="span" variant="caption" color="text.disabled"> · {w}%</Typography> : null}
                          </Typography>
                          <LinearProgress variant="determinate" value={Math.max(2, Math.min(100, v))} color={pillarColor(v)} sx={{ height: 9 }} />
                          <Typography variant="body2" fontWeight={700} align="right">{Math.round(v)}</Typography>
                        </Box>
                      );
                    })}
                  </Stack>
                  <Divider sx={{ my: 1.5 }} />
                  <Grid container spacing={1}>
                    {[["P/E", fmtNum(data.metrics?.trailing_pe, 1)], ["PEG", fmtNum(data.metrics?.peg, 2)],
                      ["ROE", fmtPctFrac(data.metrics?.roe)], ["Margin", fmtPctFrac(data.metrics?.profit_margin)],
                      ["Rev gr", fmtPctFrac(data.metrics?.revenue_growth)], ["Analysts", data.num_analysts ?? "—"]].map(([k, v]) => (
                      <Grid item xs={4} key={k}>
                        <Typography variant="caption" color="text.secondary"><Jargon term={k}>{k}</Jargon> </Typography>
                        <Typography variant="caption" fontWeight={700}>{v}</Typography>
                      </Grid>
                    ))}
                  </Grid>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} md={5}>
              <Card sx={{ height: "100%" }}>
                <CardContent>
                  <Typography variant="overline" color="success.main">Why it fits</Typography>
                  <List dense disablePadding sx={{ listStyleType: "disc", pl: 2, mb: 1 }}>
                    {(data.thesis || []).map((t, i) => <ListItem key={i} sx={{ display: "list-item", py: 0 }}><Typography variant="body2">{t}</Typography></ListItem>)}
                  </List>
                  <Typography variant="overline" color="error.main">Key risks</Typography>
                  <List dense disablePadding sx={{ listStyleType: "disc", pl: 2 }}>
                    {(data.risks || []).map((t, i) => <ListItem key={i} sx={{ display: "list-item", py: 0 }}><Typography variant="body2" color="text.secondary">{t}</Typography></ListItem>)}
                  </List>
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          {(data.news?.headlines || []).length > 0 && (
            <Card>
              <CardContent>
                <Typography variant="overline" color="primary">Recent news · catalyst {Math.round(data.news?.catalyst_score ?? 50)}/100</Typography>
                <List dense disablePadding sx={{ mt: 0.5 }}>
                  {data.news.headlines.slice(0, 6).map((h, i) => (
                    <ListItem key={i} disableGutters sx={{ alignItems: "flex-start", gap: 1 }}>
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
              </CardContent>
            </Card>
          )}
        </Stack>
      )}

      {!ticker && !loading && (
        <Typography color="text.secondary">Search for a company above to see its full score breakdown.</Typography>
      )}

      <StockDetailDialog ticker={showDialog ? data?.ticker : null} open={showDialog} onClose={() => setShowDialog(false)} />
    </Box>
  );
}

function ScoreHistoryCard({ ticker, currentScore }) {
  const [series, setSeries] = useState(null);
  useEffect(() => {
    if (!ticker) return;
    let cancelled = false;
    api.scoreHistory(ticker).then((j) => { if (!cancelled) setSeries(j.series || []); }).catch(() => { if (!cancelled) setSeries([]); });
    return () => { cancelled = true; };
  }, [ticker]);

  if (series === null) return null;
  return (
    <Card>
      <CardContent>
        <Typography variant="overline" color="primary">Composite score over time</Typography>
        {series.length < 2 ? (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            Score history builds as the screen runs over time — today's score is <b>{Math.round(currentScore)}</b>.
            Check back after a few daily runs to see the trend.
          </Typography>
        ) : (
          <LineChart height={200}
            xAxis={[{ scaleType: "point", data: series.map((d) => d.date),
              tickInterval: (v, i) => i % Math.ceil(series.length / 6) === 0 }]}
            yAxis={[{ min: 0, max: 100 }]}
            series={[{ data: series.map((d) => d.score), label: "Composite score", showMark: true, area: true }]}
            margin={{ left: 40, right: 12, top: 16, bottom: 28 }} />
        )}
      </CardContent>
    </Card>
  );
}
