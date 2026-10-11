import { Result, Skeleton } from "antd";

import { AppHeader } from "./components/layout/AppHeader";
import { ErrorAlert } from "./components/common/ErrorAlert";
import { JobPage } from "./components/job/JobPage";
import { NewRun } from "./components/start/NewRun";
import { RecentRuns } from "./components/start/RecentRuns";
import { useAppConfig } from "./hooks/queries";
import { useUrlParam } from "./hooks/useUrlState";

/** Two screens: start a run, or look at one. The run id lives in the URL (?job=…). */
export default function App() {
  const config = useAppConfig();
  const [jobId, setJobId] = useUrlParam("job");

  let body;
  if (config.error) {
    body = <Result status="warning" title="The backend is not answering"
                   subTitle={<ErrorAlert error={config.error} onRetry={() => config.refetch()} />} />;
  } else if (!config.data) {
    body = <Skeleton active paragraph={{ rows: 8 }} />;
  } else if (jobId) {
    body = <JobPage jobId={jobId} config={config.data} onBack={() => setJobId(null)} />;
  } else {
    body = (
      <div className="start-page">
        <NewRun config={config.data} onStarted={(j) => setJobId(j.id)} />
        <RecentRuns onOpen={setJobId} />
      </div>
    );
  }

  return (
    <div className="app">
      <a className="skip-link" href="#main">Skip to content</a>
      <AppHeader onHome={() => setJobId(null)} />
      <main id="main" className="app-main">{body}</main>
    </div>
  );
}
