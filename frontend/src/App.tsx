import { Result, Skeleton } from "antd";
import { lazy, Suspense } from "react";

import { ErrorAlert } from "./components/common/ErrorAlert";
import { JobPage } from "./components/job/JobPage";
import { AppShell } from "./components/layout/AppShell";
import { NewRun } from "./components/start/NewRun";
import { useAppConfig } from "./hooks/queries";
import { useRoute } from "./hooks/useRoute";
import { AdminPage } from "./pages/AdminPage";
import { DashboardPage } from "./pages/DashboardPage";
import { RunsPage } from "./pages/RunsPage";
const DocsPage = lazy(() => import("./pages/DocsPage"));

/** Pages behind a sidebar: New analysis, Runs (and one run: ?job=...), Dashboard, Admin. */
export default function App() {
  const config = useAppConfig();
  const [route, go] = useRoute();
  const openJob = (id: string) => go("runs", id);

  let body;
  if (route.page === "docs") {
    body = <Suspense fallback={<Skeleton active />}><DocsPage modules={config.data?.modules ?? []} /></Suspense>;
  } else if (config.error) {
    body = <Result status="warning" title="The backend is not answering"
                   subTitle={<ErrorAlert error={config.error} onRetry={() => config.refetch()} />} />;
  } else if (!config.data) {
    body = <Skeleton active paragraph={{ rows: 8 }} />;
  } else if (route.jobId) {
    body = <JobPage jobId={route.jobId} config={config.data} onBack={() => go("runs")} />;
  } else if (route.page === "runs") {
    body = <RunsPage onOpen={openJob} />;
  } else if (route.page === "dashboard") {
    body = <DashboardPage />;
  } else if (route.page === "admin") {
    body = <AdminPage />;
  } else {
    body = <NewRun config={config.data} onStarted={(j) => openJob(j.id)} />;
  }

  return (
    <>
      <a className="skip-link" href="#main">Skip to content</a>
      <AppShell page={route.jobId ? "runs" : route.page} title={route.jobId ? "Run" : undefined}
                onNavigate={(p) => go(p)} onOpenJob={openJob}>
        {body}
      </AppShell>
    </>
  );
}
