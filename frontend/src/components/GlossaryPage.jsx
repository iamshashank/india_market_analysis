import React, { useMemo } from "react";
import {
  Box, Typography, Grid, Card, CardContent, Chip, Stack, TextField, InputAdornment,
  ToggleButtonGroup, ToggleButton, Divider,
} from "@mui/material";
import SearchIcon from "@mui/icons-material/Search";
import { useSearchParams } from "react-router-dom";
import { GLOSSARY, GLOSSARY_CATEGORIES, CANDLE_PATTERNS } from "../data/glossary.js";
import { SectionHeader } from "./common.jsx";
import CandleGlyph from "./CandleGlyph.jsx";

const biasColor = (b) => (b === "bullish" ? "success" : b === "bearish" ? "error" : "default");

export default function GlossaryPage() {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") || "";
  const cat = params.get("cat") || "All";
  const setQ = (v) => setParams((p) => { if (v) p.set("q", v); else p.delete("q"); return p; }, { replace: true });
  const setCat = (v) => setParams((p) => { if (v && v !== "All") p.set("cat", v); else p.delete("cat"); return p; }, { replace: true });

  const needle = q.trim().toLowerCase();
  const match = (text) => !needle || text.toLowerCase().includes(needle);

  const terms = useMemo(() => GLOSSARY.filter((g) => {
    if (cat !== "All" && g.category !== cat) return false;
    return match(`${g.term} ${g.abbr || ""} ${g.def}`);
  }), [needle, cat]);

  const showCandles = (cat === "All" || cat === "Candlestick");
  const candles = useMemo(() => CANDLE_PATTERNS.filter((c) =>
    match(`${c.name} ${c.means} ${c.why} ${c.how} ${c.bias}`)), [needle]);

  // Non-candlestick terms grouped by category for the cards section.
  const grouped = useMemo(() => {
    const g = {};
    terms.filter((t) => t.category !== "Candlestick").forEach((t) => {
      (g[t.category] = g[t.category] || []).push(t);
    });
    return g;
  }, [terms]);
  const orderedCats = GLOSSARY_CATEGORIES.filter((c) => grouped[c]?.length);

  return (
    <Box>
      <SectionHeader overline="Reference" title="Glossary & FAQ"
        subtitle="Plain-English explanations for every metric, ratio, acronym and candlestick pattern used across the app — what it means, why it matters, and how to read it." />

      <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} sx={{ mb: 2 }} alignItems={{ sm: "center" }}>
        <TextField size="small" fullWidth placeholder="Search e.g. EPS, hammer, PCR, Altman Z, free cash flow…"
          value={q} onChange={(e) => setQ(e.target.value)}
          InputProps={{ startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment> }} />
      </Stack>
      <ToggleButtonGroup size="small" exclusive value={cat} onChange={(_, v) => v && setCat(v)} sx={{ flexWrap: "wrap", gap: 0.5, mb: 3 }}>
        <ToggleButton value="All" sx={{ borderRadius: "999px !important", border: 1, borderColor: "divider", textTransform: "none" }}>All</ToggleButton>
        {GLOSSARY_CATEGORIES.map((c) => (
          <ToggleButton key={c} value={c} sx={{ borderRadius: "999px !important", border: 1, borderColor: "divider", textTransform: "none" }}>{c}</ToggleButton>
        ))}
      </ToggleButtonGroup>

      {orderedCats.map((c) => (
        <Box key={c} sx={{ mb: 3 }}>
          <Typography variant="overline" color="primary">{c}</Typography>
          <Grid container spacing={2} sx={{ mt: 0 }}>
            {grouped[c].map((t) => (
              <Grid item xs={12} sm={6} md={4} key={t.term}>
                <Card sx={{ height: "100%" }}>
                  <CardContent>
                    <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" sx={{ mb: 0.5 }}>
                      <Typography variant="subtitle2" fontWeight={700}>{t.term}</Typography>
                      {t.abbr && <Chip size="small" variant="outlined" color="primary" label={t.abbr} />}
                    </Stack>
                    <Typography variant="body2" color="text.secondary">{t.def}</Typography>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Box>
      ))}

      {showCandles && candles.length > 0 && (
        <Box sx={{ mb: 3 }}>
          <Divider sx={{ mb: 2 }} />
          <Typography variant="overline" color="primary">Candlestick patterns</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            Each diagram shows the candle shape; green = up day (close above open), red = down day. These are short-term
            timing signals — best used with the longer-term thesis, not on their own.
          </Typography>
          <Grid container spacing={2}>
            {candles.map((c) => (
              <Grid item xs={12} sm={6} md={4} key={c.name}>
                <Card sx={{ height: "100%" }}>
                  <CardContent>
                    <Stack direction="row" spacing={1.5} alignItems="center">
                      <Box sx={{ p: 0.5, borderRadius: 1.5, bgcolor: "action.hover" }}>
                        <CandleGlyph candles={c.candles} />
                      </Box>
                      <Box>
                        <Typography variant="subtitle2" fontWeight={700}>{c.name}</Typography>
                        <Chip size="small" variant="outlined" color={biasColor(c.bias)}
                          label={c.bias === "bullish" ? "▲ Bullish" : c.bias === "bearish" ? "▼ Bearish" : "• Neutral"} />
                      </Box>
                    </Stack>
                    <Typography variant="body2" sx={{ mt: 1 }}><b>What:</b> {c.means}</Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}><b>Why it matters:</b> {c.why}</Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}><b>How to read it:</b> {c.how}</Typography>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Box>
      )}

      {terms.length === 0 && candles.length === 0 && (
        <Typography color="text.secondary">No matches for “{q}”.</Typography>
      )}
    </Box>
  );
}
