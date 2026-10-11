/**
 * Design tokens: the one source for the antd theme AND the CSS custom properties, so a
 * table cell and the bar chart beside it can never drift apart.
 *
 * Rules:
 * - Colour carries meaning. One accent for actions; amber only means "worth a human look";
 *   red only means failure or harm. Everything else is neutral.
 * - Categorical hues (labels, entity types) are mid-saturation so they read on both grounds.
 */

export type Mode = "light" | "dark";

export const NEUTRAL = {
  0: "#ffffff",
  50: "#f8f9fb",
  100: "#f1f3f6",
  200: "#e4e7ec",
  300: "#cfd4dc",
  400: "#98a1b0",
  500: "#5f6b7d",
  600: "#4a5466",
  700: "#353d4b",
  800: "#1f2530",
  900: "#121722",
} as const;

/** Near-achromatic dark ramp: a slate inverted reads navy, which nobody asked for. */
export const INK = {
  950: "#0a0b0e",
  900: "#0e1014",
  850: "#13151a",
  800: "#181b21",
  750: "#1e2129",
  700: "#262a33",
  600: "#343944",
  500: "#4b5260",
  400: "#808898",
  300: "#a1a9b8",
  200: "#c8cdd6",
  100: "#e9ecf1",
} as const;

export const ACCENT = {
  50: "#eef2ff",
  100: "#dfe6ff",
  300: "#9db1ff",
  400: "#7b93ff",
  500: "#4361ee",
  600: "#3450d4",
  700: "#2a40ad",
} as const;

export const SEMANTIC = {
  success: "#16a34a",
  warning: "#d97706",
  danger: "#dc2626",
  info: "#0891b2",
} as const;

/** Same meanings at a lightness that passes 4.5:1 as small text. */
export const SEMANTIC_TEXT: Record<Mode, Record<keyof typeof SEMANTIC, string>> = {
  light: { success: "#15803d", warning: "#b45309", danger: "#b91c1c", info: "#0e7490" },
  dark: { success: "#4ade80", warning: "#fbbf24", danger: "#f87171", info: "#22d3ee" },
};

/** 16 distinguishable hues for labels and entity types, assigned by config order. */
export const CATEGORICAL = [
  "#4361ee", "#0f9d8a", "#9b51e0", "#e8590c", "#0284c7", "#c2410c", "#d6336c", "#5c940d",
  "#7048e8", "#1098ad", "#b7791f", "#2b8a3e", "#c92a2a", "#6741d9", "#0c8599", "#a61e4d",
] as const;

export const FONT = {
  family: "'IBM Plex Sans', system-ui, -apple-system, 'Segoe UI', sans-serif",
  mono: "ui-monospace, 'SFMono-Regular', 'JetBrains Mono', Menlo, Consolas, monospace",
} as const;

export const RADIUS = { control: 8, card: 12, pill: 999 } as const;

export const LAYOUT = { maxWidth: 1360, headerHeight: 56, gutter: 24, gutterMobile: 16 } as const;
