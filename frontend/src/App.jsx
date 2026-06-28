import React, { useCallback, useContext, useMemo, useState } from "react";
import {
  AppBar, Toolbar, Typography, Tabs, Tab, Box, Button, IconButton, Container,
  Tooltip, LinearProgress, Snackbar, Alert, useScrollTrigger, ToggleButtonGroup, ToggleButton,
} from "@mui/material";
import { Routes, Route, useNavigate, useLocation, Navigate, useSearchParams, Link as RouterLink } from "react-router-dom";
import Brightness4Icon from "@mui/icons-material/Brightness4";
import Brightness7Icon from "@mui/icons-material/Brightness7";
import MenuBookIcon from "@mui/icons-material/MenuBook";
import RefreshIcon from "@mui/icons-material/Refresh";
import InsightsIcon from "@mui/icons-material/Insights";
import RocketLaunchIcon from "@mui/icons-material/RocketLaunch";
import LocalFireDepartmentIcon from "@mui/icons-material/LocalFireDepartment";
import ShowChartIcon from "@mui/icons-material/ShowChart";
import NotificationsActiveIcon from "@mui/icons-material/NotificationsActive";
import ScienceIcon from "@mui/icons-material/Science";
import TravelExploreIcon from "@mui/icons-material/TravelExplore";
import AccountBalanceWalletIcon from "@mui/icons-material/AccountBalanceWallet";

import ScreenView from "./components/ScreenView.jsx";
import ThemesView from "./components/ThemesView.jsx";
import OptionsView from "./components/OptionsView.jsx";
import PredictorView from "./components/PredictorView.jsx";
import PaperView from "./components/PaperView.jsx";
import AnalyzeView from "./components/AnalyzeView.jsx";
import PortfolioView from "./components/PortfolioView.jsx";
import GlossaryPage from "./components/GlossaryPage.jsx";
import GlossaryDrawer from "./components/GlossaryDrawer.jsx";
import SymbolSearch from "./components/SymbolSearch.jsx";
import { ColorModeContext } from "./theme.js";
import { UIContext } from "./uiContext.js";
import { MarketContext, MARKETS, getMarket, DEFAULT_MARKET } from "./markets.js";
import { api } from "./lib/api.js";

const TABS = [
  { id: "screen", label: "Multibagger Finder", icon: <RocketLaunchIcon fontSize="small" /> },
  { id: "analyze", label: "Analyze a Stock", icon: <TravelExploreIcon fontSize="small" /> },
  { id: "portfolio", label: "My Portfolio", icon: <AccountBalanceWalletIcon fontSize="small" /> },
  { id: "themes", label: "Themes", icon: <LocalFireDepartmentIcon fontSize="small" /> },
  { id: "options", label: "Options / F&O", icon: <ShowChartIcon fontSize="small" /> },
  { id: "predictor", label: "Next-Day Predictor", icon: <NotificationsActiveIcon fontSize="small" /> },
  { id: "paper", label: "Paper Trading", icon: <ScienceIcon fontSize="small" /> },
];
const REFRESHABLE = new Set(["screen", "predictor"]);

export default function App() {
  const colorMode = useContext(ColorModeContext);
  const navigate = useNavigate();
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const [statusLine, setStatusLine] = useState("");
  const [glossaryOpen, setGlossaryOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [busyKeys, setBusyKeys] = useState({});
  const [snack, setSnack] = useState({ open: false, msg: "", severity: "info" });
  const elevate = useScrollTrigger({ disableHysteresis: true, threshold: 8 });

  // Global market region (shared by every screen), persisted + URL-synced.
  const region = params.get("mkt") || localStorage.getItem("mi-market") || DEFAULT_MARKET;
  const setRegion = useCallback((r) => {
    localStorage.setItem("mi-market", r);
    setParams((p) => { p.set("mkt", r); p.delete("tier"); return p; }, { replace: true });
  }, [setParams]);
  const market = useMemo(() => getMarket(region), [region]);
  const marketCtx = useMemo(() => ({ region, setRegion, market }), [region, setRegion, market]);

  // Build an href for switching market region, preserving path + other params.
  const marketHref = (r) => {
    const sp = new URLSearchParams(params);
    sp.set("mkt", r); sp.delete("tier");
    return `${location.pathname}?${sp.toString()}`;
  };

  const seg = location.pathname.replace(/^\/+/, "").split("/")[0] || "screen";
  const tab = TABS.some((t) => t.id === seg) ? seg : seg === "glossary" ? false : "screen";

  const toast = useCallback((msg, severity = "success") => setSnack({ open: true, msg, severity }), []);
  const setBusy = useCallback((key, val) => setBusyKeys((s) => (s[key] === val ? s : { ...s, [key]: val })), []);
  const ui = useMemo(() => ({ toast, setBusy }), [toast, setBusy]);
  const anyBusy = refreshing || Object.values(busyKeys).some(Boolean);

  async function refresh() {
    if (!REFRESHABLE.has(tab)) return;
    setRefreshing(true);
    toast(tab === "screen" ? "Re-screening India + US universe…" : "Refreshing overnight cues…", "info");
    try {
      if (tab === "screen") await api.refreshScreen();
      else await api.refreshPremarket();
    } catch (e) { toast("Could not reach the server.", "error"); }
    setTimeout(() => setRefreshing(false), 3000);
  }

  return (
    <UIContext.Provider value={ui}>
    <MarketContext.Provider value={marketCtx}>
      <Box sx={{ minHeight: "100vh", bgcolor: "background.default" }}>
        <AppBar position="sticky" color="default" elevation={elevate ? 3 : 0}
          sx={{ borderBottom: 1, borderColor: "divider", backdropFilter: "blur(8px)",
            bgcolor: (t) => (t.palette.mode === "light" ? "rgba(255,255,255,0.86)" : "rgba(20,26,46,0.86)") }}>
          <Toolbar sx={{ gap: 1, flexWrap: "wrap" }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1, cursor: "pointer", mr: "auto" }} onClick={() => navigate("/screen")}>
              <InsightsIcon color="primary" />
              <Box>
                <Typography variant="h6" sx={{ lineHeight: 1.1 }}>Market Intelligence</Typography>
                <Typography variant="caption" color="text.secondary">
                  Multibagger compounders across cap tiers (India + US) · themes · options · next-day predictor
                </Typography>
              </Box>
            </Box>
            {statusLine && <Typography variant="caption" color="text.secondary" sx={{ mr: 1, display: { xs: "none", sm: "block" } }}>{statusLine}</Typography>}
            <ToggleButtonGroup exclusive size="small" value={region} aria-label="Market region">
              {MARKETS.map((m) => (
                <ToggleButton key={m.id} value={m.id} sx={{ px: 1.2, py: 0.4 }}
                  component={RouterLink} to={marketHref(m.id)}
                  onClick={() => localStorage.setItem("mi-market", m.id)}>
                  {m.flag} {m.label}
                </ToggleButton>
              ))}
            </ToggleButtonGroup>
            <SymbolSearch onPick={(tk) => navigate(`/analyze?ticker=${encodeURIComponent(tk)}`)}
              sx={{ width: { xs: 0, md: 230 }, display: { xs: "none", md: "block" } }}
              placeholder="Analyze any stock…" />
            <Button startIcon={<MenuBookIcon />} onClick={() => navigate("/glossary")} color="inherit">Glossary</Button>
            <Tooltip title="Quick lookup">
              <IconButton onClick={() => setGlossaryOpen(true)} color="inherit" aria-label="Quick glossary"><MenuBookIcon /></IconButton>
            </Tooltip>
            <Tooltip title={colorMode.mode === "light" ? "Switch to dark" : "Switch to light"}>
              <IconButton onClick={colorMode.toggle} color="inherit" aria-label="Toggle color mode">
                {colorMode.mode === "light" ? <Brightness4Icon /> : <Brightness7Icon />}
              </IconButton>
            </Tooltip>
            {REFRESHABLE.has(tab) && (
              <Button variant="contained" startIcon={<RefreshIcon />} onClick={refresh} disabled={refreshing}>
                {refreshing ? "Running…" : tab === "screen" ? "Re-screen" : "Refresh"}
              </Button>
            )}
          </Toolbar>
          <Tabs value={tab} variant="scrollable" scrollButtons="auto"
            allowScrollButtonsMobile sx={{ px: 1, borderTop: 1, borderColor: "divider" }}>
            {TABS.map((t) => (
              <Tab key={t.id} value={t.id} label={t.label} icon={t.icon} iconPosition="start"
                component={RouterLink} to={`/${t.id}${location.search}`} />
            ))}
          </Tabs>
          <Box sx={{ height: 3 }}>{anyBusy && <LinearProgress />}</Box>
        </AppBar>

        <Container maxWidth="xl" sx={{ py: 3 }}>
          <Routes>
            <Route path="/" element={<Navigate to="/screen" replace />} />
            <Route path="/screen" element={<ScreenView active={tab === "screen"} setStatusLine={setStatusLine} />} />
            <Route path="/analyze" element={<AnalyzeView />} />
            <Route path="/portfolio" element={<PortfolioView active={tab === "portfolio"} />} />
            <Route path="/themes" element={<ThemesView active={tab === "themes"} />} />
            <Route path="/options" element={<OptionsView />} />
            <Route path="/predictor" element={<PredictorView active={tab === "predictor"} setStatusLine={setStatusLine} />} />
            <Route path="/paper" element={<PaperView active={tab === "paper"} />} />
            <Route path="/glossary" element={<GlossaryPage />} />
            <Route path="*" element={<Navigate to="/screen" replace />} />
          </Routes>
        </Container>

        <Box component="footer" sx={{ borderTop: 1, borderColor: "divider", py: 3, px: 2, mt: 4 }}>
          <Container maxWidth="xl">
            <Typography variant="caption" color="text.secondary">
              Educational tool — not investment advice. Data via Yahoo Finance. Small-cap &amp; low-coverage stocks are illiquid and risky.
            </Typography>
          </Container>
        </Box>

        <GlossaryDrawer open={glossaryOpen} onClose={() => setGlossaryOpen(false)} />
        <Snackbar open={snack.open} autoHideDuration={3500} onClose={() => setSnack((s) => ({ ...s, open: false }))}
          anchorOrigin={{ vertical: "bottom", horizontal: "center" }}>
          <Alert severity={snack.severity} variant="filled" onClose={() => setSnack((s) => ({ ...s, open: false }))} sx={{ width: "100%" }}>
            {snack.msg}
          </Alert>
        </Snackbar>
      </Box>
    </MarketContext.Provider>
    </UIContext.Provider>
  );
}
