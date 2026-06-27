import React, { useEffect, useMemo, useState } from "react";
import { Autocomplete, TextField, Box, Typography, CircularProgress, InputAdornment } from "@mui/material";
import SearchIcon from "@mui/icons-material/Search";
import { api } from "../lib/api.js";

// debounced symbol typeahead. onPick(ticker) fires on selection.
export default function SymbolSearch({ onPick, size = "small", placeholder = "Search any company or symbol…", sx }) {
  const [input, setInput] = useState("");
  const [options, setOptions] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const q = input.trim();
    if (q.length < 2) { setOptions([]); return; }
    let cancelled = false;
    setLoading(true);
    const t = setTimeout(async () => {
      try {
        const j = await api.searchSymbols(q);
        if (!cancelled) setOptions(j.results || []);
      } catch (e) { if (!cancelled) setOptions([]); }
      if (!cancelled) setLoading(false);
    }, 220);
    return () => { cancelled = true; clearTimeout(t); };
  }, [input]);

  return (
    <Autocomplete
      sx={sx}
      size={size}
      options={options}
      filterOptions={(x) => x}
      getOptionLabel={(o) => (typeof o === "string" ? o : `${o.name} (${o.ticker})`)}
      isOptionEqualToValue={(a, b) => a.ticker === b.ticker}
      loading={loading}
      onInputChange={(_, v) => setInput(v)}
      onChange={(_, v) => { if (v && v.ticker) onPick(v.ticker); }}
      noOptionsText={input.trim().length < 2 ? "Type at least 2 characters" : "No matches"}
      renderOption={(props, o) => (
        <Box component="li" {...props} key={o.ticker}>
          <Box>
            <Typography variant="body2" fontWeight={600}>{o.name}</Typography>
            <Typography variant="caption" color="text.secondary">
              {o.ticker} · {o.market === "IN" ? "NSE" : o.market === "BSE" ? "BSE" : "US"}
            </Typography>
          </Box>
        </Box>
      )}
      renderInput={(params) => (
        <TextField {...params} placeholder={placeholder}
          InputProps={{
            ...params.InputProps,
            startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment>,
            endAdornment: <>{loading ? <CircularProgress size={16} /> : null}{params.InputProps.endAdornment}</>,
          }} />
      )}
    />
  );
}
