import React, { useEffect, useRef, useState } from "react";
import {
  Box, Card, CardContent, Typography, Grid, Stack, Chip, LinearProgress, Avatar,
} from "@mui/material";
import { api } from "../lib/api.js";
import { yahooUrl } from "../lib/format.js";
import { SectionHeader, CardGridSkeleton } from "./common.jsx";
import { hoverCard } from "../theme.js";
import { useUI } from "../uiContext.js";
import { useMarket } from "../markets.js";

const heatColor = (h) => (h >= 66 ? "error" : h >= 58 ? "warning" : h >= 48 ? "primary" : "info");

export default function ThemesView({ active }) {
  const { setBusy } = useUI();
  const { region, market: marketCfg } = useMarket();
  const [payload, setPayload] = useState(null);
  const [asOf, setAsOf] = useState("");
  const poll = useRef(null);

  async function load() {
    try {
      const j = await api.screen();
      setBusy("themes", j.status === "running" && !j.data);
      if (j.data) { setPayload(j.data); setAsOf(j.data.as_of || ""); if (j.status !== "running") stop(); else ensure(); }
      else ensure();
    } catch (e) { ensure(); }
  }
  function ensure() { if (!poll.current) poll.current = setInterval(load, 6000); }
  function stop() { if (poll.current) { clearInterval(poll.current); poll.current = null; } }
  useEffect(() => { load(); return () => { stop(); setBusy("themes", false); }; }, []);

  // region-specific heatmap, falling back to the global one for older payloads
  const themes = payload ? ((payload.themes_by_market || {})[region] || payload.themes || []) : null;

  if (!themes) {
    return (
      <Box>
        <SectionHeader overline="Where the momentum is" title="Theme & sentiment heatmap"
          subtitle="Ranking growth themes by opportunity quality, news sentiment, momentum and breadth…" />
        <CardGridSkeleton count={6} />
      </Box>
    );
  }
  if (!themes.length) {
    return (
      <Box>
        <SectionHeader overline="Where the momentum is" title={`Theme & sentiment heatmap · ${marketCfg.flag} ${marketCfg.label}`}
          subtitle="No themes detected for this market yet — try re-screening or switch market." />
      </Box>
    );
  }

  return (
    <Box>
      <SectionHeader overline="Where the momentum is" title={`Theme & sentiment heatmap · ${marketCfg.flag} ${marketCfg.label}`}
        subtitle={`Which growth themes have the strongest tailwind in ${marketCfg.label} right now — blending opportunity quality (avg score), news sentiment, price momentum and breadth.${asOf ? ` As of ${asOf}.` : ""}`} />
      <Grid container spacing={2}>
        {themes.map((t, i) => {
          const c = heatColor(t.heat);
          return (
            <Grid item xs={12} sm={6} md={4} key={t.theme}>
              <Card sx={{ height: "100%", borderTop: 3, borderColor: `${c}.main`, ...hoverCard }}>
                <CardContent>
                  <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 0.5 }}>
                    <Stack direction="row" spacing={1} alignItems="center">
                      <Avatar sx={{ width: 24, height: 24, fontSize: 12, bgcolor: "action.hover", color: "text.secondary" }}>{i + 1}</Avatar>
                      <Typography variant="subtitle1">{t.emoji} {t.theme}</Typography>
                    </Stack>
                    <Typography variant="h5" color={`${c}.main`}>{Math.round(t.heat)}</Typography>
                  </Stack>
                  <LinearProgress variant="determinate" value={Math.min(100, t.heat)} color={c} sx={{ height: 8, my: 1 }} />
                  <Stack direction="row" spacing={2} sx={{ mb: 1 }}>
                    <Typography variant="caption" color="text.secondary">{t.count} names</Typography>
                    <Typography variant="caption" color="text.secondary">catalyst {Math.round(t.avg_catalyst)}</Typography>
                    <Typography variant="caption" color={t.avg_momentum_pct >= 0 ? "success.main" : "error.main"}>6m {t.avg_momentum_pct >= 0 ? "+" : ""}{t.avg_momentum_pct}%</Typography>
                  </Stack>
                  <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                    {t.top_stocks.map((s) => (
                      <Chip key={s.ticker} size="small" variant="outlined" clickable component="a"
                        href={yahooUrl(s.ticker)} target="_blank" rel="noopener noreferrer"
                        label={<span>{s.name} <b>{Math.round(s.score)}</b></span>}
                        title={`${s.sector} · score ${Math.round(s.score)}`} />
                    ))}
                  </Stack>
                </CardContent>
              </Card>
            </Grid>
          );
        })}
      </Grid>
    </Box>
  );
}
