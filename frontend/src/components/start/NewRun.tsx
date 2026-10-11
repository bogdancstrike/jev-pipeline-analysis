import { CloudUploadOutlined } from "@ant-design/icons";
import { App, Progress, Typography, Upload } from "antd";
import { useEffect, useState } from "react";

import { api } from "../../api/endpoints";
import type { AppConfig, JobSnapshot } from "../../api/types";
import { useHealth } from "../../hooks/queries";
import { useStoredState } from "../../hooks/useUrlState";
import { ModulePicker } from "./ModulePicker";
import { SamplePicker } from "./SamplePicker";

/** Pick analyses, drop a CSV (or use the sample), and the run starts. */
export function NewRun({ config, onStarted }: { config: AppConfig; onStarted: (j: JobSnapshot) => void }) {
  const { message } = App.useApp();
  const health = useHealth();
  const [stored, setSelected] = useStoredState<string[]>("triage.modules", config.defaults);
  const [pct, setPct] = useState<number | null>(null);
  const [startingSample, setStartingSample] = useState(false);
  const known = new Set(config.modules.map((m) => m.name));
  const selected = stored.filter((n) => known.has(n));

  // A config change on the server (module disabled) must not leave a stale selection behind.
  useEffect(() => { if (selected.length !== stored.length) setSelected(selected); }); // eslint-disable-line react-hooks/exhaustive-deps

  const notReady = selected.filter((n) => !health.data?.modules[n]?.ready);
  const busy = pct !== null || startingSample;
  const blocked = !selected.length || notReady.length > 0;

  const start = async (file: File) => {
    if (file.size > config.limits.max_upload_mb * 1024 * 1024) {
      message.error(`${file.name} is larger than ${config.limits.max_upload_mb} MB`);
      return;
    }
    setPct(0);
    try {
      onStarted(await api.createJob(file, selected, setPct));
    } catch (e) {
      message.error((e as Error).message);
    } finally {
      setPct(null);
    }
  };

  const runSample = async (file: string) => {
    setStartingSample(true);
    try {
      onStarted(await api.sampleJob(file, selected));
    } catch (e) {
      message.error((e as Error).message);
    } finally {
      setStartingSample(false);
    }
  };

  const titles = Object.fromEntries(config.modules.map((m) => [m.name, m.title]));

  return (
    <section className="panel new-run" aria-labelledby="new-run-title">
      <h1 id="new-run-title" className="page-title">Analyze a batch of texts</h1>
      <p className="lede">
        Upload a CSV with <code>id</code> and <code>text</code> columns. Each row is enriched by the analyses
        you pick, on this server's GPU. No text leaves the machine.
      </p>

      <ModulePicker modules={config.modules} selected={selected} onChange={setSelected} disabled={busy} />

      <Upload.Dragger
        accept=".csv,text/csv"
        showUploadList={false}
        multiple={false}
        disabled={busy || blocked}
        customRequest={({ file }) => { void start(file as File); }}
        className="dropzone"
      >
        <div className="dropzone-icon"><CloudUploadOutlined /></div>
        <div className="dropzone-title">
          {blocked
            ? (selected.length ? "Waiting for the models to load…" : "Pick at least one analysis")
            : "Drop a CSV here, or click to choose"}
        </div>
        <Typography.Text type="secondary" className="small">
          {notReady.length > 0
            ? `Still loading: ${notReady.map((n) => titles[n] ?? n).join(", ")}`
            : `Comma, semicolon or tab separated · up to ${config.limits.max_upload_mb} MB · ${config.limits.max_rows.toLocaleString()} rows`}
        </Typography.Text>
      </Upload.Dragger>
      {pct !== null && <Progress percent={pct} size="small" className="upload-progress" />}

      <SamplePicker samples={config.samples} disabled={busy || blocked} busy={startingSample} onRun={runSample} />
    </section>
  );
}
