import React from "react";
import {
  Box, CircularProgress, Typography, Link, Chip, Card, CardContent, Stack,
  Skeleton, Grid, Tooltip,
} from "@mui/material";
import { yahooUrl } from "../lib/format.js";

// ---- links / chips ----
export function TickerLink({ ticker, children }) {
  return (
    <Link href={yahooUrl(ticker)} target="_blank" rel="noopener noreferrer" underline="hover" color="inherit" fontWeight={700}>
      {children}
    </Link>
  );
}
export function MarketChip({ m }) {
  return <Chip size="small" variant="outlined" color={m === "IN" ? "warning" : "primary"} label={m === "IN" ? "🇮🇳 IN" : "🇺🇸 US"} />;
}

export const pillarColor = (v) => (v >= 66 ? "success" : v >= 45 ? "primary" : "warning");
export const convColor = (c) => (c === "High" ? "success" : c === "Medium" ? "warning" : "default");
export const candleColor = (bias) => (bias === "bullish" ? "success" : bias === "bearish" ? "error" : "default");
export const scoreColor = (v) => (v >= 70 ? "success" : v >= 55 ? "primary" : v >= 45 ? "warning" : "error");

// ---- multi-horizon score chips (Compounder / Catalyst / Momentum) ----
const HORIZON_TIPS = {
  Compounder: "Long-term wealth lens: quality, earnings consistency, growth runway, room to grow & value — is this a great business to own for years?",
  Catalyst: "Near-term entry-timing lens: recent news/event catalysts + price momentum — is now a good moment to enter?",
  Momentum: "Price momentum: 6-month return, distance above the 200-day average, and proximity to the 52-week high.",
};
export function HorizonScores({ compounder, catalyst, momentum, dense = false }) {
  const cell = (label, v) => (
    <Tooltip key={label} title={HORIZON_TIPS[label]} arrow enterTouchDelay={0}>
      <Box sx={{ textAlign: "center", px: 1, py: dense ? 0.25 : 0.5, borderRadius: 1.5,
        bgcolor: "action.hover", cursor: "help", minWidth: dense ? 56 : 64 }}>
        <Typography sx={{ fontSize: 9, textTransform: "uppercase", letterSpacing: ".5px" }} color="text.secondary">{label}</Typography>
        <Typography variant={dense ? "body2" : "subtitle2"} fontWeight={800} color={v == null ? "text.disabled" : `${scoreColor(v)}.main`}>
          {v == null ? "\u2014" : Math.round(v)}
        </Typography>
      </Box>
    </Tooltip>
  );
  return (
    <Stack direction="row" spacing={0.75} useFlexGap flexWrap="wrap">
      {compounder != null && cell("Compounder", compounder)}
      {catalyst != null && cell("Catalyst", catalyst)}
      {momentum != null && cell("Momentum", momentum)}
    </Stack>
  );
}

// ---- forensic-health + discovery-inflection signal chips ----
export const healthColor = (label) => ({ Strong: "success", Sound: "info", Watch: "warning", Distress: "error" }[label] || "default");
export const inflColor = (label) => ({ Inflecting: "success", Stirring: "info", Quiet: "default" }[label] || "default");

// Plain-English meaning of each health / inflection label (shared by tooltips + glossary).
export const HEALTH_LABEL_TIP = {
  Strong: "Strong — good liquidity, low leverage, and earnings backed by cash.",
  Sound: "Sound — a generally healthy balance sheet with only minor watch-items.",
  Watch: "Watch — some balance-sheet stress (leverage, liquidity, or weak cash conversion).",
  Distress: "Distress — multiple red flags (high leverage / weak liquidity / losses). Higher risk.",
  Unknown: "Not enough statement data to judge financial health.",
};
export const INFLECTION_LABEL_TIP = {
  Inflecting: "Inflecting — under-covered + sound, with news/volume clearly picking up (“hidden but waking up”).",
  Stirring: "Stirring — early signs of rising attention off a low base.",
  Quiet: "Quiet — little change in attention or coverage right now.",
};

export function SignalChips({ health, inflection, emerging, size = "small" }) {
  const has = emerging || (health?.label && health.label !== "Unknown") || (inflection?.label && inflection.label !== "Quiet");
  if (!has) return null;
  return (
    <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
      {emerging && (
        <Tooltip title="Emerging compounder — a financially sound (Strong/Sound), still under-covered company whose discovery is inflecting. The multibagger sweet spot; deliberately rare." arrow>
          <Chip size={size} color="secondary" label="✨ Emerging compounder" sx={{ cursor: "help" }} />
        </Tooltip>
      )}
      {health?.label && health.label !== "Unknown" && (
        <Tooltip title={`Financial health — ${HEALTH_LABEL_TIP[health.label] || health.label}${(health.flags || []).length ? " Flags: " + health.flags.join("; ") + "." : ""}`} arrow>
          <Chip size={size} variant="outlined" color={healthColor(health.label)} label={`Health: ${health.label}`} sx={{ cursor: "help" }} />
        </Tooltip>
      )}
      {inflection?.label && inflection.label !== "Quiet" && (
        <Tooltip title={`Discovery inflection — ${INFLECTION_LABEL_TIP[inflection.label] || inflection.label}`} arrow>
          <Chip size={size} variant="outlined" color={inflColor(inflection.label)} label={inflection.label} sx={{ cursor: "help" }} />
        </Tooltip>
      )}
    </Stack>
  );
}

// ---- section header (title + subtitle + optional action) ----
export function SectionHeader({ title, subtitle, action, overline }) {
  return (
    <Stack direction="row" alignItems="flex-end" justifyContent="space-between" sx={{ mb: 2, gap: 2, flexWrap: "wrap" }}>
      <Box>
        {overline && <Typography variant="overline" color="primary">{overline}</Typography>}
        <Typography variant="h5">{title}</Typography>
        {subtitle && <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, maxWidth: 720 }}>{subtitle}</Typography>}
      </Box>
      {action}
    </Stack>
  );
}

// ---- circular score gauge ----
export function ScoreRing({ value, size = 56, label = "score" }) {
  const v = Math.max(0, Math.min(100, Number(value) || 0));
  const color = scoreColor(v);
  return (
    <Box sx={{ position: "relative", display: "inline-flex" }}>
      <CircularProgress variant="determinate" value={100} size={size} thickness={4}
        sx={{ color: (t) => t.palette.action.hover }} />
      <CircularProgress variant="determinate" value={v} size={size} thickness={4} color={color}
        sx={{ position: "absolute", left: 0, [`& .MuiCircularProgress-circle`]: { strokeLinecap: "round" } }} />
      <Box sx={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
        <Typography variant="subtitle1" fontWeight={800} lineHeight={1}>{Math.round(v)}</Typography>
        <Typography sx={{ fontSize: 8, textTransform: "uppercase", letterSpacing: ".5px" }} color="text.secondary">{label}</Typography>
      </Box>
    </Box>
  );
}

// ---- KPI tile ----
export function KpiCard({ icon, label, value, caption, color = "text.primary" }) {
  return (
    <Card sx={{ height: "100%" }}>
      <CardContent sx={{ py: 1.75, "&:last-child": { pb: 1.75 } }}>
        <Stack direction="row" spacing={1.25} alignItems="center">
          {icon && <Box sx={{ color: "primary.main", display: "flex" }}>{icon}</Box>}
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="caption" color="text.secondary" noWrap>{label}</Typography>
            <Typography variant="h6" color={color} noWrap>{value}</Typography>
            {caption && <Typography variant="caption" color="text.secondary" noWrap display="block">{caption}</Typography>}
          </Box>
        </Stack>
      </CardContent>
    </Card>
  );
}

// ---- jargon tooltip (dotted underline) ----
const TIPS = {
  "P/E": "Price ÷ earnings per share — what you pay for ₹1/$1 of annual profit.",
  PEG: "P/E ÷ growth rate. ~1 is fair; below 1 can be cheap for the growth.",
  ROE: "Return on equity — profit ÷ shareholders' equity. Higher = more efficient.",
  Margin: "Net profit as a % of revenue.",
  "Rev gr": "Year-on-year revenue growth.",
  Analysts: "Number of brokerages covering it. Fewer = more under-the-radar.",
  "Small base": "Smaller companies can compound faster off a small base.",
  "Earnings consistency": "Steady/rising quarterly earnings, not lumpy swings.",
  "Low coverage": "Few analysts + little news = overlooked, often mispriced.",
  Growth: "Revenue & earnings growth runway.",
  Quality: "ROE, margins, free cash flow, low debt.",
  Valuation: "Whether the price is sane for the growth (PEG, P/B).",
  "News catalyst": "Recent events (orders, approvals, expansion) that can re-rate it.",
};
export function Jargon({ term, children }) {
  const tip = TIPS[term];
  if (!tip) return <>{children ?? term}</>;
  return (
    <Tooltip title={tip} arrow enterTouchDelay={0}>
      <Box component="span" sx={{ borderBottom: "1px dotted", borderColor: "text.disabled", cursor: "help" }}>
        {children ?? term}
      </Box>
    </Tooltip>
  );
}

// ---- loading skeletons ----
export function Loading({ text }) {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2, py: 9 }}>
      <CircularProgress />
      <Typography color="text.secondary" align="center">{text}</Typography>
    </Box>
  );
}

export function CardGridSkeleton({ count = 6 }) {
  return (
    <Grid container spacing={2}>
      {Array.from({ length: count }).map((_, i) => (
        <Grid item xs={12} md={6} lg={4} key={i}>
          <Card><CardContent>
            <Stack direction="row" justifyContent="space-between" sx={{ mb: 1 }}>
              <Box sx={{ flex: 1 }}>
                <Skeleton width="70%" height={26} />
                <Skeleton width="50%" />
              </Box>
              <Skeleton variant="circular" width={56} height={56} />
            </Stack>
            <Skeleton variant="rounded" height={36} sx={{ mb: 1 }} />
            {Array.from({ length: 5 }).map((__, j) => <Skeleton key={j} height={14} />)}
            <Skeleton variant="rounded" height={60} sx={{ mt: 1 }} />
          </CardContent></Card>
        </Grid>
      ))}
    </Grid>
  );
}

export function KpiSkeleton({ count = 4 }) {
  return (
    <Grid container spacing={2} sx={{ mb: 3 }}>
      {Array.from({ length: count }).map((_, i) => (
        <Grid item xs={6} sm={3} key={i}><Card><CardContent><Skeleton width="60%" /><Skeleton width="40%" height={30} /></CardContent></Card></Grid>
      ))}
    </Grid>
  );
}
