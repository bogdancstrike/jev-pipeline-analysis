import { theme as antdTheme, type ThemeConfig } from "antd";

import { ACCENT, FONT, INK, NEUTRAL, RADIUS, SEMANTIC, SEMANTIC_TEXT, type Mode } from "./tokens";

/** The antd theme, derived from tokens only: re-theming is one edit in tokens.ts. */
export function buildTheme(mode: Mode): ThemeConfig {
  const dark = mode === "dark";
  return {
    algorithm: dark ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
    token: {
      colorPrimary: dark ? ACCENT[400] : ACCENT[500],
      colorLink: dark ? ACCENT[300] : ACCENT[600],
      colorInfo: SEMANTIC.info,
      colorSuccess: SEMANTIC.success,
      colorWarning: SEMANTIC.warning,
      colorError: SEMANTIC.danger,
      colorSuccessText: SEMANTIC_TEXT[mode].success,
      colorWarningText: SEMANTIC_TEXT[mode].warning,
      colorErrorText: SEMANTIC_TEXT[mode].danger,
      colorBgLayout: dark ? INK[900] : NEUTRAL[50],
      colorBgContainer: dark ? INK[800] : NEUTRAL[0],
      colorBgElevated: dark ? INK[750] : NEUTRAL[0],
      colorBorder: dark ? INK[600] : NEUTRAL[200],
      colorBorderSecondary: dark ? INK[700] : NEUTRAL[100],
      colorText: dark ? INK[100] : NEUTRAL[900],
      colorTextSecondary: dark ? INK[300] : NEUTRAL[600],
      colorTextTertiary: dark ? INK[400] : NEUTRAL[500],
      colorTextDescription: dark ? INK[300] : NEUTRAL[600],
      colorTextPlaceholder: dark ? INK[400] : NEUTRAL[500],
      fontFamily: FONT.family,
      fontFamilyCode: FONT.mono,
      fontSize: 14,
      borderRadius: RADIUS.control,
      borderRadiusLG: RADIUS.card,
      wireframe: false,
    },
    components: {
      Layout: { headerBg: dark ? INK[850] : NEUTRAL[0], headerHeight: 56, headerPadding: "0 24px",
                bodyBg: dark ? INK[900] : NEUTRAL[50] },
      Table: { headerBg: dark ? INK[750] : NEUTRAL[50], headerSplitColor: "transparent",
               rowHoverBg: dark ? INK[750] : ACCENT[50], cellPaddingBlockSM: 10 },
      Card: { paddingLG: 20 },
      Tabs: { horizontalMargin: "0 0 16px 0" },
      Tooltip: { colorBgSpotlight: dark ? INK[700] : NEUTRAL[800] },
      Drawer: { paddingLG: 24 },
    },
  };
}

/** Tokens the stylesheet needs, for anything styled outside an antd component. */
export function cssVariables(mode: Mode): Record<string, string> {
  const dark = mode === "dark";
  return {
    "--bg": dark ? INK[900] : NEUTRAL[50],
    "--surface": dark ? INK[800] : NEUTRAL[0],
    "--surface-2": dark ? INK[750] : NEUTRAL[100],
    "--border": dark ? INK[600] : NEUTRAL[200],
    "--border-soft": dark ? INK[700] : NEUTRAL[100],
    "--text": dark ? INK[100] : NEUTRAL[900],
    "--text-2": dark ? INK[300] : NEUTRAL[600],
    "--text-3": dark ? INK[400] : NEUTRAL[500],
    "--accent": dark ? ACCENT[400] : ACCENT[500],
    "--accent-soft": dark ? "rgba(123,147,255,0.14)" : ACCENT[50],
    "--warning": SEMANTIC_TEXT[mode].warning,
    "--danger": SEMANTIC_TEXT[mode].danger,
    "--success": SEMANTIC_TEXT[mode].success,
    "--font": FONT.family,
    "--mono": FONT.mono,
    "--radius": `${RADIUS.control}px`,
    "--radius-lg": `${RADIUS.card}px`,
  };
}
