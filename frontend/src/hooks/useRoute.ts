import { useCallback, useEffect, useState } from "react";

export type Page = "new" | "runs" | "dashboard" | "admin" | "docs";

const PATHS: Record<Page, string> = { new: "/", runs: "/runs", dashboard: "/dashboard", admin: "/admin", docs: "/docs" };

export interface Route { page: Page; jobId: string | null }

function read(): Route {
  const path = window.location.pathname.replace(/\/+$/, "") || "/";
  const page = (Object.entries(PATHS).find(([, p]) => p === path)?.[0] ?? "new") as Page;
  return { page, jobId: new URLSearchParams(window.location.search).get("job") };
}

/**
 * Path-based pages (/runs, /dashboard, /admin) plus `?job=<id>` for one run, so every view is
 * a link. nginx serves index.html for any path; Back/Forward work through popstate.
 */
export function useRoute(): [Route, (page: Page, jobId?: string | null) => void] {
  const [route, setRoute] = useState<Route>(read);
  useEffect(() => {
    const on = () => setRoute(read());
    window.addEventListener("popstate", on);
    return () => window.removeEventListener("popstate", on);
  }, []);
  const go = useCallback((page: Page, jobId: string | null = null) => {
    const url = `${PATHS[page]}${jobId ? `?job=${encodeURIComponent(jobId)}` : ""}`;
    if (url !== `${window.location.pathname}${window.location.search}`) window.history.pushState(null, "", url);
    setRoute({ page, jobId });
    window.scrollTo({ top: 0 });
  }, []);
  return [route, go];
}
