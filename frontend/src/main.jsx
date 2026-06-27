import React, { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import CssBaseline from "@mui/material/CssBaseline";
import { ThemeProvider } from "@mui/material/styles";
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import App from "./App.jsx";
import { ColorModeContext, buildTheme } from "./theme.js";
import { BrowserRouter } from "react-router-dom";

function Root() {
  const [mode, setMode] = useState(() => localStorage.getItem("mi-color-mode") || "light");
  const colorMode = useMemo(() => ({
    mode,
    toggle: () => setMode((m) => {
      const next = m === "light" ? "dark" : "light";
      localStorage.setItem("mi-color-mode", next);
      return next;
    }),
  }), [mode]);
  const theme = useMemo(() => buildTheme(mode), [mode]);

  return (
    <ColorModeContext.Provider value={colorMode}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </ThemeProvider>
    </ColorModeContext.Provider>
  );
}

createRoot(document.getElementById("root")).render(<Root />);
