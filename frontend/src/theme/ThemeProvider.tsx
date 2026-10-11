import { App as AntApp, ConfigProvider } from "antd";
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { buildTheme, cssVariables } from "./antd";
import type { Mode } from "./tokens";

export type Appearance = Mode | "system";

const STORAGE_KEY = "triage.appearance";
const DARK_QUERY = "(prefers-color-scheme: dark)";

interface ThemeState {
  appearance: Appearance;
  mode: Mode;
  setAppearance: (a: Appearance) => void;
}

const ThemeContext = createContext<ThemeState | null>(null);

function stored(): Appearance {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    return v === "light" || v === "dark" || v === "system" ? v : "system";
  } catch {
    return "system"; // private mode / storage disabled: the default is a working app
  }
}

const systemMode = (): Mode => (window.matchMedia?.(DARK_QUERY).matches ? "dark" : "light");

/** Light / dark / follow the OS, applied to antd and to the stylesheet at once. */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [appearance, setAppearanceState] = useState<Appearance>(stored);
  const [system, setSystem] = useState<Mode>(systemMode);

  useEffect(() => {
    const q = window.matchMedia?.(DARK_QUERY);
    if (!q) return;
    const on = (e: MediaQueryListEvent) => setSystem(e.matches ? "dark" : "light");
    q.addEventListener("change", on);
    return () => q.removeEventListener("change", on);
  }, []);

  const mode = appearance === "system" ? system : appearance;

  useEffect(() => {
    const root = document.documentElement;
    for (const [k, v] of Object.entries(cssVariables(mode))) root.style.setProperty(k, v);
    root.dataset.theme = mode;
    root.style.colorScheme = mode;
  }, [mode]);

  const value = useMemo<ThemeState>(() => ({
    appearance,
    mode,
    setAppearance: (a) => {
      setAppearanceState(a);
      try { localStorage.setItem(STORAGE_KEY, a); } catch { /* not worth failing over */ }
    },
  }), [appearance, mode]);

  const theme = useMemo(() => buildTheme(mode), [mode]);

  return (
    <ThemeContext.Provider value={value}>
      <ConfigProvider theme={theme}>
        <AntApp>{children}</AntApp>
      </ConfigProvider>
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeState {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme outside ThemeProvider");
  return ctx;
}
