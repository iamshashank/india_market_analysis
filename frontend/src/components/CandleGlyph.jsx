import React from "react";
import { useTheme } from "@mui/material/styles";

/**
 * Draw a small candlestick diagram from a list of candles.
 * Each candle: { o, c, h, l } on a 0–100 scale (100 = top of chart).
 */
export default function CandleGlyph({ candles = [], width = 120, height = 90 }) {
  const theme = useTheme();
  const green = theme.palette.success.main;
  const red = theme.palette.error.main;
  const axis = theme.palette.text.disabled;

  const n = candles.length;
  const slot = width / (n + 1);
  const cw = Math.min(slot * 0.5, 18);
  const pad = 6;
  const y = (v) => pad + (100 - v) / 100 * (height - 2 * pad);

  return (
    <svg width={width} height={height} role="img" aria-label="candlestick pattern">
      {candles.map((c, i) => {
        const cx = slot * (i + 1);
        const up = c.c >= c.o;
        const color = up ? green : red;
        const bodyTop = y(Math.max(c.o, c.c));
        const bodyBot = y(Math.min(c.o, c.c));
        const bodyH = Math.max(2, bodyBot - bodyTop);
        return (
          <g key={i}>
            <line x1={cx} x2={cx} y1={y(c.h)} y2={y(c.l)} stroke={color} strokeWidth={1.5} />
            <rect x={cx - cw / 2} y={bodyTop} width={cw} height={bodyH} fill={color} rx={1.5} />
          </g>
        );
      })}
      <line x1={pad} x2={width - pad} y1={height - 2} y2={height - 2} stroke={axis} strokeWidth={0.75} opacity={0.4} />
    </svg>
  );
}
