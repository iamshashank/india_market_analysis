import React, { useMemo, useState } from "react";
import {
  Drawer, Box, Typography, IconButton, TextField, ToggleButtonGroup, ToggleButton,
  List, ListItem, Chip, Stack, Divider, InputAdornment, Button,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import SearchIcon from "@mui/icons-material/Search";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";
import { useNavigate } from "react-router-dom";
import { GLOSSARY, GLOSSARY_CATEGORIES } from "../data/glossary.js";

export default function GlossaryDrawer({ open, onClose }) {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("All");

  const results = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return GLOSSARY.filter((g) => {
      if (cat !== "All" && g.category !== cat) return false;
      if (!needle) return true;
      return g.term.toLowerCase().includes(needle)
        || (g.abbr || "").toLowerCase().includes(needle)
        || g.def.toLowerCase().includes(needle);
    });
  }, [q, cat]);

  return (
    <Drawer anchor="right" open={open} onClose={onClose}
            PaperProps={{ sx: { width: { xs: "92vw", sm: 440 }, p: 2 } }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between">
        <Typography variant="h6">📖 Quick glossary</Typography>
        <IconButton onClick={onClose} aria-label="Close"><CloseIcon /></IconButton>
      </Stack>
      <Button size="small" endIcon={<OpenInNewIcon />} sx={{ alignSelf: "flex-start", mb: 1 }}
        onClick={() => { onClose(); navigate(q.trim() ? `/glossary?q=${encodeURIComponent(q.trim())}` : "/glossary"); }}>
        Open full glossary &amp; FAQ
      </Button>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
        Plain-English definitions for every metric, acronym and candlestick pattern.
      </Typography>
      <TextField
        fullWidth size="small" placeholder="Search e.g. EPS, hammer, PCR, ATR…"
        value={q} onChange={(e) => setQ(e.target.value)} autoFocus
        InputProps={{ startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment> }}
        sx={{ mb: 1.5 }}
      />
      <ToggleButtonGroup
        size="small" exclusive value={cat}
        onChange={(_, v) => v && setCat(v)}
        sx={{ flexWrap: "wrap", mb: 1.5, gap: 0.5 }}
      >
        {["All", ...GLOSSARY_CATEGORIES].map((c) => (
          <ToggleButton key={c} value={c} sx={{ border: 1, borderColor: "divider", borderRadius: "999px !important", px: 1.2, py: 0.3, textTransform: "none" }}>
            {c}
          </ToggleButton>
        ))}
      </ToggleButtonGroup>
      <Divider sx={{ mb: 1 }} />
      <List sx={{ overflowY: "auto" }}>
        {results.length === 0 && <Typography variant="body2" color="text.secondary">No matches.</Typography>}
        {results.map((g) => (
          <ListItem key={g.term} disableGutters sx={{ display: "block", py: 1 }}>
            <Stack direction="row" alignItems="center" spacing={1} flexWrap="wrap">
              <Typography variant="subtitle2" fontWeight={700}>{g.term}</Typography>
              {g.abbr && <Chip label={g.abbr} size="small" color="primary" variant="outlined" />}
              <Chip label={g.category} size="small" variant="outlined" sx={{ ml: "auto" }} />
            </Stack>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>{g.def}</Typography>
          </ListItem>
        ))}
      </List>
    </Drawer>
  );
}
