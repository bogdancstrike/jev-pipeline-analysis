import { CloudUploadOutlined, PlayCircleOutlined } from "@ant-design/icons";
import { App, Button, Input, Progress, Tabs, Typography, Upload } from "antd";
import { useEffect, useState } from "react";

import { api } from "../../api/endpoints";
import type { AppConfig, JobSnapshot } from "../../api/types";
import { useHealth } from "../../hooks/queries";
import { useStoredState } from "../../hooks/useUrlState";
import { ModulePicker, Presets } from "./ModulePicker";
import { RunSummary } from "./RunSummary";
import { PageHeader } from "../ui/PageHeader";
import { Section } from "../ui/Section";
import { SamplePicker } from "./SamplePicker";

const SEPARATOR = /^\s*---+\s*$/m;

/** "a\n---\nb" -> two articles; no separator -> one article. */
export function splitArticles(text: string): string[] {
  return text.split(SEPARATOR).map((t) => t.trim()).filter(Boolean);
}

/** Pick analyses, then feed it: a built-in sample, a CSV, or pasted text. */
export function NewRun({ config, onStarted }: { config: AppConfig; onStarted: (j: JobSnapshot) => void }) {
  const { message } = App.useApp();
  const health = useHealth();
  const [stored, setSelected] = useStoredState<string[]>("triage.modules", config.defaults);
  const [tab, setTab] = useStoredState<string>("triage.input", "samples");
  const [pct, setPct] = useState<number | null>(null);
  const [starting, setStarting] = useState(false);
  const [text, setText] = useState("");
  const known = new Set(config.modules.map((m) => m.name));
  const selected = stored.filter((n) => known.has(n));

  // A config change on the server (module disabled) must not leave a stale selection behind.
  useEffect(() => { if (selected.length !== stored.length) setSelected(selected); }); // eslint-disable-line react-hooks/exhaustive-deps

  const notReady = selected.filter((n) => !health.data?.modules[n]?.ready);
  const busy = pct !== null || starting;
  const blocked = !selected.length || notReady.length > 0;
  const titles = Object.fromEntries(config.modules.map((m) => [m.name, m.title]));
  const blockedWhy = !selected.length ? "Pick at least one analysis (or a preset)"
    : notReady.length ? `Still loading: ${notReady.map((n) => titles[n] ?? n).join(", ")}` : "";

  const launch = async (start: () => Promise<JobSnapshot>) => {
    setStarting(true);
    try {
      onStarted(await start());
    } catch (e) {
      message.error((e as Error).message);
    } finally {
      setStarting(false);
    }
  };

  const upload = async (file: File) => {
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

  const articles = splitArticles(text);

  return (
    <div className="newrun">
      <PageHeader title="New analysis"
        description="Pick the analyses, then give it text: a built-in sample, a CSV, or articles pasted in. Everything runs on this server's GPU; no text leaves the machine." />
      <div className="newrun-grid">
        <div className="newrun-main">
          <Section step={1} title="Choose analyses" description={`${selected.length} of ${config.modules.length} selected. Hover ⓘ for what each one outputs and costs.`}
                   extra={<Presets modules={config.modules} selected={selected} onChange={setSelected} disabled={busy} />}>
            <ModulePicker config={config} selected={selected} onChange={setSelected} disabled={busy} />
            {blockedWhy && <div className="blocked-why">{blockedWhy}</div>}
          </Section>
          <Section step={2} title="Add text">
      <Tabs activeKey={tab} onChange={setTab} className="input-tabs" items={[
        {
          key: "samples", label: "Sample datasets",
          children: <SamplePicker samples={config.samples} disabled={busy || blocked} busy={starting}
                                  onRun={(f) => launch(() => api.sampleJob(f, selected))} />,
        },
        {
          key: "upload", label: "Upload CSV",
          children: (
            <>
              <Upload.Dragger accept=".csv,text/csv" showUploadList={false} multiple={false} disabled={busy || blocked}
                              customRequest={({ file }) => { void upload(file as File); }} className="dropzone">
                <div className="dropzone-icon"><CloudUploadOutlined /></div>
                <div className="dropzone-title">Drop a CSV here, or click to choose</div>
                <Typography.Text type="secondary" className="small">
                  Columns <code>id</code> and <code>text</code> (others are kept) · comma, semicolon or tab ·
                  up to {config.limits.max_upload_mb} MB · {config.limits.max_rows.toLocaleString()} rows
                </Typography.Text>
              </Upload.Dragger>
              {pct !== null && <Progress percent={pct} size="small" className="upload-progress" />}
            </>
          ),
        },
        {
          key: "paste", label: "Paste text",
          children: (
            <div className="paste">
              <Input.TextArea value={text} onChange={(e) => setText(e.target.value)} disabled={busy}
                              autoSize={{ minRows: 8, maxRows: 24 }} aria-label="Text to analyze"
                              placeholder={"Paste an article here.\n\nSeveral articles? Put a line with only --- between them."} />
              <div className="paste-foot">
                <Typography.Text type="secondary" className="small">
                  {articles.length === 0 ? "Nothing to analyze yet"
                    : `${articles.length} article${articles.length > 1 ? "s" : ""} · ${articles.reduce((a, t) => a + t.split(/\s+/).length, 0).toLocaleString()} words`}
                </Typography.Text>
                <Button type="primary" icon={<PlayCircleOutlined />} disabled={busy || blocked || !articles.length} loading={starting}
                        onClick={() => launch(() => api.textJob(articles, selected))}>
                  Analyze {articles.length > 1 ? `${articles.length} articles` : "text"}
                </Button>
              </div>
            </div>
          ),
        },
      ]} />
          </Section>
        </div>
        <RunSummary config={config} selected={selected} />
      </div>
    </div>
  );
}
