import React, { useState } from "react";
import {
  Box, Card, CardContent, Typography, Grid, Stack, Chip, TextField, Button,
  ToggleButtonGroup, ToggleButton, Alert, CircularProgress,
} from "@mui/material";
import { api } from "../lib/api.js";
import { fmtNum } from "../lib/format.js";
import { SectionHeader } from "./common.jsx";
import { useSearchParams } from "react-router-dom";
import { useMarket } from "../markets.js";

function Stat({ lbl, val, color }) {
  return (
    <Grid item xs={6} sm={4} md={2}>
      <Box sx={{ p: 1.2, borderRadius: 2, bgcolor: "action.hover" }}>
        <Typography variant="caption" color="text.secondary">{lbl}</Typography>
        <Typography variant="h6" color={color || "text.primary"}>{val}</Typography>
      </Box>
    </Grid>
  );
}

export default function OptionsView() {
  const { market: regionCfg } = useMarket();
  const [params, setParams] = useSearchParams();
  const market = params.get("market") || (regionCfg.optionMarket || "US");
  const [ticker, setTicker] = useState(params.get("ticker") || regionCfg.sample || "AAPL");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);

  async function run(e) {
    e?.preventDefault();
    const tk = ticker.trim();
    setParams((p) => { p.set("market", market); if (tk) p.set("ticker", tk); return p; }, { replace: true });
    setLoading(true); setErr(null); setData(null);
    try {
      const j = await api.options(tk, market);
      if (!j.available) setErr(j.reason || "Options data unavailable for this symbol.");
      else setData(j);
    } catch (e2) { setErr("Request failed."); }
    setLoading(false);
  }
  function setMkt(m) {
    if (!m) return;
    const t = m === "IN" ? "RELIANCE.NS" : "AAPL";
    setTicker(t);
    setParams((p) => { p.set("market", m); p.set("ticker", t); return p; }, { replace: true });
    setData(null); setErr(null);
  }

  return (
    <Box>
      <SectionHeader overline="Positioning & flow" title="Options / F&O analytics"
        subtitle="Put/call ratio, max-pain, ATM implied volatility and the biggest open-interest strikes (support/resistance) for the nearest expiry. US works via Yahoo; Indian F&O is best-effort from NSE (a broker API gives reliable data)." />

      <Stack direction="row" spacing={1} alignItems="center" component="form" onSubmit={run} sx={{ mb: 2, flexWrap: "wrap" }}>
        <ToggleButtonGroup exclusive size="small" value={market} onChange={(_, v) => setMkt(v)}>
          <ToggleButton value="US">🇺🇸 US</ToggleButton>
          <ToggleButton value="IN">🇮🇳 India</ToggleButton>
        </ToggleButtonGroup>
        <TextField size="small" value={ticker} onChange={(e) => setTicker(e.target.value)}
          placeholder={market === "IN" ? "e.g. RELIANCE.NS" : "e.g. AAPL"} />
        <Button type="submit" variant="contained" disabled={loading}
          startIcon={loading ? <CircularProgress size={16} color="inherit" /> : null}>
          {loading ? "Loading…" : "Analyze"}
        </Button>
      </Stack>

      {market === "IN" && (
        <Alert severity="warning" variant="outlined" sx={{ mb: 2 }}>
          Indian F&amp;O is fetched best-effort from NSE, which often blocks automated requests from servers — it may
          return "unavailable". US options (via Yahoo) are reliable. For dependable Indian option chains, a broker API
          (e.g. Zerodha Kite) is needed.
        </Alert>
      )}

      {err && <Alert severity="info" sx={{ mb: 2 }}>{err}</Alert>}

      {data && (
        <Card>
          <CardContent>
            <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" sx={{ mb: 1.5 }}>
              <Typography variant="h6">{data.ticker}</Typography>
              <Typography variant="body2" color="text.secondary">spot {data.spot ?? "n/a"} · expiry {data.expiry}</Typography>
              <Chip label={data.sentiment} color="warning" variant="outlined" size="small" />
            </Stack>
            <Grid container spacing={1.5} sx={{ mb: 2 }}>
              <Stat lbl="Put/Call (OI)" val={data.pcr_oi ?? "n/a"} color={data.pcr_oi > 1 ? "error.main" : "success.main"} />
              <Stat lbl="Put/Call (Vol)" val={data.pcr_volume ?? "n/a"} />
              <Stat lbl="Max pain" val={data.max_pain ?? "n/a"} />
              <Stat lbl="ATM IV" val={data.atm_iv_pct != null ? data.atm_iv_pct + "%" : "n/a"} />
              <Stat lbl="Total call OI" val={fmtNum(data.total_call_oi, 0)} color="success.main" />
              <Stat lbl="Total put OI" val={fmtNum(data.total_put_oi, 0)} color="error.main" />
            </Grid>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6}>
                <Typography variant="subtitle2" color="success.main" gutterBottom>Resistance (biggest call OI)</Typography>
                {(data.resistance_strikes || []).map((s, i) => (
                  <Typography variant="body2" key={i}>Strike <b>{s.strike}</b> — call OI {fmtNum(s.call_oi, 0)}</Typography>
                ))}
              </Grid>
              <Grid item xs={12} sm={6}>
                <Typography variant="subtitle2" color="error.main" gutterBottom>Support (biggest put OI)</Typography>
                {(data.support_strikes || []).map((s, i) => (
                  <Typography variant="body2" key={i}>Strike <b>{s.strike}</b> — put OI {fmtNum(s.put_oi, 0)}</Typography>
                ))}
              </Grid>
            </Grid>
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1.5 }}>
              High put OI often marks support; high call OI resistance. PCR is a positioning gauge — extremes can be contrarian. Not advice.
            </Typography>
          </CardContent>
        </Card>
      )}
    </Box>
  );
}
