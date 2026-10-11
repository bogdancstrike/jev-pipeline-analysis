import { useCallback, useEffect, useState } from "react";

/**
 * One value mirrored into the URL query string (e.g. `?job=…`), so a reload or a shared
 * link opens the same run, and Back returns to the previous one.
 */
export function useUrlParam(name: string): [string | null, (v: string | null) => void] {
  const read = () => new URLSearchParams(window.location.search).get(name);
  const [value, setValue] = useState<string | null>(read);

  useEffect(() => {
    const onPop = () => setValue(read());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const update = useCallback((v: string | null) => {
    const params = new URLSearchParams(window.location.search);
    if (v) params.set(name, v);
    else params.delete(name);
    const qs = params.toString();
    window.history.pushState(null, "", `${window.location.pathname}${qs ? `?${qs}` : ""}`);
    setValue(v);
  }, [name]);

  return [value, update];
}

/** A small per-browser preference (column choice, ...). Storage failures fall back silently. */
export function useStoredState<T>(key: string, initial: T): [T, (v: T) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key);
      return raw ? (JSON.parse(raw) as T) : initial;
    } catch {
      return initial;
    }
  });
  const update = useCallback((v: T) => {
    setValue(v);
    try { localStorage.setItem(key, JSON.stringify(v)); } catch { /* ignore */ }
  }, [key]);
  return [value, update];
}
