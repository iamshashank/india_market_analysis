import { createContext } from "react";
import { createTheme } from "@mui/material/styles";

export const ColorModeContext = createContext({ mode: "light", toggle: () => {} });

export function buildTheme(mode) {
  const light = mode === "light";
  return createTheme({
    palette: {
      mode,
      primary: { main: light ? "#2f5fed" : "#6f9bff" },
      secondary: { main: light ? "#7c3aed" : "#b794f6" },
      success: { main: light ? "#0f9d58" : "#34d399" },
      error: { main: light ? "#dc2626" : "#f87171" },
      warning: { main: light ? "#c2820b" : "#fbbf57" },
      info: { main: light ? "#0284c7" : "#56ccf2" },
      divider: light ? "rgba(15,23,42,0.10)" : "rgba(148,163,184,0.18)",
      background: light
        ? { default: "#f5f7fb", paper: "#ffffff" }
        : { default: "#0a0e1a", paper: "#141a2e" },
      text: light
        ? { primary: "#0f172a", secondary: "#5b6478" }
        : { primary: "#e8ecf6", secondary: "#9aa5bf" },
    },
    shape: { borderRadius: 14 },
    typography: {
      fontFamily: "Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
      h4: { fontWeight: 800, letterSpacing: "-0.02em" },
      h5: { fontWeight: 800, letterSpacing: "-0.01em" },
      h6: { fontWeight: 700, letterSpacing: "-0.01em" },
      subtitle1: { fontWeight: 700 },
      subtitle2: { fontWeight: 700 },
      overline: { fontWeight: 700, letterSpacing: "0.08em" },
      button: { textTransform: "none", fontWeight: 600 },
    },
    components: {
      MuiCssBaseline: {
        styleOverrides: {
          "*::-webkit-scrollbar": { width: 10, height: 10 },
          "*::-webkit-scrollbar-thumb": {
            backgroundColor: light ? "rgba(15,23,42,0.18)" : "rgba(148,163,184,0.28)",
            borderRadius: 8,
          },
        },
      },
      MuiCard: {
        defaultProps: { variant: "outlined" },
        styleOverrides: {
          root: {
            transition: "transform .18s ease, box-shadow .18s ease, border-color .18s ease",
            backgroundImage: "none",
          },
        },
      },
      MuiButton: { defaultProps: { disableElevation: true }, styleOverrides: { root: { borderRadius: 10 } } },
      MuiChip: { styleOverrides: { root: { fontWeight: 600 } } },
      MuiTooltip: {
        styleOverrides: {
          tooltip: { fontSize: 12, lineHeight: 1.5, padding: "8px 10px", maxWidth: 280 },
        },
      },
      MuiTableCell: { styleOverrides: { root: { borderColor: light ? "rgba(15,23,42,0.08)" : "rgba(148,163,184,0.14)" } } },
      MuiTab: { styleOverrides: { root: { textTransform: "none", fontWeight: 600, minHeight: 52 } } },
      MuiLinearProgress: { styleOverrides: { root: { borderRadius: 6 } } },
    },
  });
}

// reusable card-hover sx
export const hoverCard = {
  "&:hover": { transform: "translateY(-3px)", boxShadow: 6, borderColor: "primary.main" },
};
