import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Box, Card, CardContent, Stack, Typography, ToggleButtonGroup, ToggleButton,
  CircularProgress, Skeleton,
} from "@mui/material";
import { LineChart } from "@mui/x-charts/LineChart";
import { useTheme } from "@mui/material/styles";
import { api } from "../lib/api.js";
import { fmtNum } from "../lib/format.js";

const RANGES = ["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"];
const RANGE_LABEL = { "1mo": "1M", "3mo": "3M", "6mo": "6M", "1y": "1Y", "2y": "2Y", "5y": "5Y", max: "Max" };

// Lightweight candlestick renderer (x-charts has no native candles).
function Candles({ candles, height = 280 }) {
  const theme = useTheme();
  const wrapRef = useRef(null);
  const [w, setW] = useState(640);
  useEffect(() => {
    const el = wrapRef.current; if (!el) return;
    const ro = new ResizeObserver((es) => setW(es[0].contentRect.width));
    ro.observe(el); return () => ro.disconnect();
  }, []);
  const green = theme.palette.success.main, red = theme.palette.error.main;
  const pad = 8;
  const lo = Math.min(...candles.map((c) => c.low));
  const hi = Math.max(...candles.map((c) => c.high));
  const y = (v) => pad + (hi - v) / (hi - lo || 1) * (height - 2 * pad);
  const n = candles.length;
  const slot = (w - 2 * pad) / Math.max(1, n);
  const cw = Math.max(1, Math.min(slot * 0.7, 9));
  return (
    <Box ref={wrapRef} sx={{ width: "100%" }}>
      <svg width={w} height={height}>
        {candles.map((c, i) => {
          const cx = pad + slot * (i + 0.5);
          const up = c.close >= c.open;
          const col = up ? green : red;
          const bt = y(Math.max(c.open, c.close)), bb = y(Math.min(c.open, c.close));
          return (
            <g key={i}>
              <line x1={cx} x2={cx} y1={y(c.high)} y2={y(c.low)} stroke={col} strokeWidth={1} />
              <rect x={cx - cw / 2} y={bt} width={cw} height={Math.max(1, bb - bt)} fill={col} />
            </g>
          );
        })}
      </svg>
    </Box>
  );
}

export default function PriceChart({ ticker, currency = "USD" }) {
  const theme = useTheme();
  const [range, setRange] = useState("1y");
  const [mode, setMode] = useState("line");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const sym = currency === "INR" ? "₹" : "$";

  useEffect(() => {
    if (!ticker) return;
    let cancelled = false;
    setLoading(true);
    api.history(ticker, range)
      .then((j) => { if (!cancelled) { setData(j); setLoading(false); } })
      .catch(() => { if (!cancelled) { setData({ available: false }); setLoading(false); } });
    return () => { cancelled = true; };
  }, [ticker, range]);

  const candles = data?.available ? data.candles : [];
  const xLabels = useMemo(() => candles.map((c) => c.date), [candles]);
  const series = useMemo(() => {
    const s = [{ data: candles.map((c) => c.close), label: "Close", color: theme.palette.primary.main, showMark: false, area: true }];
    if (candles.some((c) => c.sma50 != null)) s.push({ data: candles.map((c) => c.sma50), label: "SMA 50", color: theme.palette.warning.main, showMark: false });
    if (candles.some((c) => c.sma200 != null)) s.push({ data: candles.map((c) => c.sma200), label: "SMA 200", color: theme.palette.secondary.main, showMark: false });
    return s;
  }, [candles, theme]);

  return (
    <Card>
      <CardContent>
        <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" sx={{ mb: 1, gap: 1 }}>
          <Stack direction="row" spacing={1.5} alignItems="baseline">
            <Typography variant="subtitle1">Price</Typography>
            {data?.available && (
              <>
                <Typography variant="h6">{sym}{fmtNum(data.last, 2)}</Typography>
                <Typography variant="body2" color={data.change_pct >= 0 ? "success.main" : "error.main"}>
                  {data.change_pct >= 0 ? "+" : ""}{fmtNum(data.change_pct, 2)}% · {RANGE_LABEL[range]}
                </Typography>
              </>
            )}
          </Stack>
          <Stack direction="row" spacing={1}>
            <ToggleButtonGroup size="small" exclusive value={mode} onChange={(_, v) => v && setMode(v)}>
              <ToggleButton value="line">Line</ToggleButton>
              <ToggleButton value="candle">Candles</ToggleButton>
            </ToggleButtonGroup>
            <ToggleButtonGroup size="small" exclusive value={range} onChange={(_, v) => v && setRange(v)}>
              {RANGES.map((r) => <ToggleButton key={r} value={r} sx={{ px: 1 }}>{RANGE_LABEL[r]}</ToggleButton>)}
            </ToggleButtonGroup>
          </Stack>
        </Stack>

        {loading && <Skeleton variant="rounded" height={280} />}
        {!loading && data && !data.available && <Typography color="text.secondary" sx={{ py: 4 }}>No price history available for {ticker}.</Typography>}
        {!loading && data?.available && (
          mode === "candle"
            ? <Candles candles={candles} />
            : <LineChart height={300} xAxis={[{ scaleType: "point", data: xLabels, tickInterval: (v, i) => i % Math.ceil(xLabels.length / 8) === 0 }]}
                series={series} grid={{ horizontal: true }}
                slotProps={{ legend: { labelStyle: { fontSize: 12 } } }} margin={{ left: 56, right: 12, top: 16, bottom: 28 }} />
        )}
      </CardContent>
    </Card>
  );
}
