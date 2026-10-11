import { DeleteOutlined, PlusOutlined, UndoOutlined } from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, App, Button, Card, Input, InputNumber, Popconfirm, Select, Skeleton, Switch, Table, Tag, Timeline, Typography } from "antd";
import { useEffect, useMemo, useState } from "react";

import { ApiError } from "../api/client";
import { api } from "../api/endpoints";
import type { AdminModule } from "../api/types";
import { ErrorAlert } from "../components/common/ErrorAlert";
import { PageHeader } from "../components/ui/PageHeader";
import { keys } from "../hooks/queries";
import { ago } from "../lib/format";

type Cfg = Record<string, unknown>;
interface LabelRow { key: string; description: string; uid: number }

const NUMERIC = ["review_below", "threshold", "min_confidence", "max_pairs", "max_relations", "batch_size", "concurrency",
                 "min_probability", "same_event_threshold", "max_entity_rows", "top_k"];

/** Labels may be {key: description} (classifiers) or [label] (NER). Edited as rows either way. */
function toRows(labels: unknown): LabelRow[] {
  let uid = 0;
  if (Array.isArray(labels)) return labels.map((k) => ({ key: String(k), description: "", uid: uid++ }));
  return Object.entries((labels as Record<string, string>) ?? {}).map(([k, d]) => ({ key: k, description: d ?? "", uid: uid++ }));
}

function fromRows(rows: LabelRow[], wasList: boolean): unknown {
  const clean = rows.filter((r) => r.key.trim());
  if (wasList && clean.every((r) => !r.description.trim())) return clean.map((r) => r.key.trim());
  return Object.fromEntries(clean.map((r) => [r.key.trim(), r.description.trim()]));
}

function Editor({ m }: { m: AdminModule }) {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const eff = m.effective;
  const [draft, setDraft] = useState<Cfg>(eff);
  // The task's options live under `labels` (classifiers, NER) or `languages` (language ID).
  const labelKey = "labels" in eff ? "labels" : "languages" in eff ? "languages" : null;
  const [rows, setRows] = useState<LabelRow[]>(toRows(labelKey ? eff[labelKey] : undefined));
  const [json, setJson] = useState(JSON.stringify(eff, null, 2));
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const history = useQuery({ queryKey: keys.history(m.name), queryFn: ({ signal }) => api.admin.history(m.name, signal) });

  useEffect(() => {
    setDraft(m.effective); setRows(toRows(labelKey ? m.effective[labelKey] : undefined));
    setJson(JSON.stringify(m.effective, null, 2)); setError(null);
  }, [m, labelKey]);

  const hasLabels = labelKey !== null;
  const wasList = labelKey ? Array.isArray(eff[labelKey]) : false;
  const config = useMemo<Cfg>(() => (labelKey ? { ...draft, [labelKey]: fromRows(rows, wasList) } : draft), [draft, rows, labelKey, wasList]);
  const dirty = JSON.stringify(config) !== JSON.stringify(eff);
  const set = (k: string, v: unknown) => setDraft((d) => ({ ...d, [k]: v }));

  const save = async (cfg: Cfg) => {
    setSaving(true);
    setError(null);
    try {
      await api.admin.save(m.name, cfg);
      message.success(`${m.title}: saved. New runs use it.`);
      await Promise.all([qc.invalidateQueries({ queryKey: keys.admin }), qc.invalidateQueries({ queryKey: keys.config }),
                         qc.invalidateQueries({ queryKey: keys.history(m.name) })]);
    } catch (e) {
      setError(e);
    } finally {
      setSaving(false);
    }
  };
  const reset = async () => {
    try {
      await api.admin.reset(m.name);
      message.success(`${m.title}: back to the YAML defaults.`);
      await Promise.all([qc.invalidateQueries({ queryKey: keys.admin }), qc.invalidateQueries({ queryKey: keys.config }),
                         qc.invalidateQueries({ queryKey: keys.history(m.name) })]);
    } catch (e) {
      setError(e);
    }
  };

  const numericKeys = NUMERIC.filter((k) => typeof eff[k] === "number");

  return (
    <div className="admin-editor">
      <div className="admin-head">
        <div>
          <h3 className="section-heading admin-title">{m.title} {m.override ? <Tag color="processing" variant="filled">customised</Tag> : <Tag variant="outlined">defaults</Tag>}</h3>
          <Typography.Text type="secondary">{m.description}</Typography.Text>
        </div>
        <span className="admin-actions">
          <Popconfirm title="Back to the YAML defaults?" description="Removes every override of this task." onConfirm={reset} disabled={!m.override}>
            <Button icon={<UndoOutlined />} disabled={!m.override}>Reset</Button>
          </Popconfirm>
          <Button type="primary" loading={saving} disabled={!dirty} onClick={() => save(config)}>Save</Button>
        </span>
      </div>
      {error ? <ErrorAlert error={error} title={error instanceof ApiError && error.status === 422 ? "Not saved: the configuration is invalid" : "Not saved"} /> : null}

      <Card size="small" className="module-card" title="Model & behaviour">
        <div className="form-grid">
          <label className="form-row"><span>Enabled</span>
            <Switch checked={draft.enabled !== false} onChange={(v) => set("enabled", v)} />
            <span className="muted small">Off removes the task (and refuses if another task needs it).</span>
          </label>
          <label className="form-row"><span>Selected by default</span>
            <Switch checked={draft.default_on !== false} onChange={(v) => set("default_on", v)} />
          </label>
          {m.engine_choices.length > 0 && (
            <label className="form-row"><span>Model engine</span>
              <Select value={String(draft.engine ?? "")} onChange={(v) => set("engine", v)} style={{ minWidth: 200 }}
                      options={m.engine_choices.map((e) => ({ value: e, label: e }))} />
              <span className="muted small">Engines able to run this task ({m.engine_kinds.join(" / ")}), from config/engines.yaml.</span>
            </label>
          )}
          {numericKeys.map((k) => (
            <label key={k} className="form-row"><span>{k.replace(/_/g, " ")}</span>
              <InputNumber value={draft[k] as number} onChange={(v) => set(k, v)} step={k.includes("below") || k.includes("threshold") || k.includes("confidence") || k.includes("probability") ? 0.05 : 1} />
            </label>
          ))}
        </div>
        {typeof eff.instructions === "string" && (
          <div className="form-block">
            <div className="form-label">Instructions (the question the model answers)</div>
            <Input.TextArea value={String(draft.instructions ?? "")} onChange={(e) => set("instructions", e.target.value)} autoSize={{ minRows: 3, maxRows: 8 }} />
          </div>
        )}
      </Card>

      {hasLabels && (
        <Card size="small" className="module-card" title={`Options (${rows.filter((r) => r.key.trim()).length})`}
              extra={<Button size="small" icon={<PlusOutlined />} onClick={() => setRows((r) => [...r, { key: "", description: "", uid: Math.max(0, ...r.map((x) => x.uid)) + 1 }])}>Add option</Button>}>
          <Typography.Paragraph type="secondary" className="small">
            Keys go into the output; descriptions are shown to the model, so make them concrete. Keys are snake_case
            and no key may be the start of another (the decision engines need distinct first tokens).
          </Typography.Paragraph>
          <Table<LabelRow> size="small" rowKey="uid" dataSource={rows} pagination={false} columns={[
            { title: "Key", dataIndex: "key", width: 260, render: (_, r) => (
                <Input value={r.key} status={r.key && !/^[\w ]+$/.test(r.key) ? "error" : undefined} placeholder="new_option"
                       onChange={(e) => setRows((all) => all.map((x) => x.uid === r.uid ? { ...x, key: e.target.value } : x))} />) },
            { title: "Description", dataIndex: "description", render: (_, r) => (
                <Input value={r.description} placeholder="what this option means"
                       onChange={(e) => setRows((all) => all.map((x) => x.uid === r.uid ? { ...x, description: e.target.value } : x))} />) },
            { title: "", key: "x", width: 48, render: (_, r) => (
                <Button type="text" icon={<DeleteOutlined />} aria-label={`Remove ${r.key}`}
                        onClick={() => setRows((all) => all.filter((x) => x.uid !== r.uid))} />) },
          ]} />
        </Card>
      )}

      <Card size="small" className="module-card" title="Advanced: full configuration (JSON)">
        <Input.TextArea value={json} onChange={(e) => { setJson(e.target.value); setJsonError(null); }} autoSize={{ minRows: 6, maxRows: 24 }}
                        className="mono" status={jsonError ? "error" : undefined} />
        {jsonError && <div className="text-danger small">{jsonError}</div>}
        <div style={{ marginTop: 8 }}>
          <Button onClick={() => {
            try { void save(JSON.parse(json) as Cfg); } catch (e) { setJsonError(`Invalid JSON: ${(e as Error).message}`); }
          }}>Save JSON</Button>
        </div>
      </Card>

      <Card size="small" className="module-card" title="History">
        {history.data?.length ? (
          <Timeline items={history.data.map((h) => ({
            color: h.action === "reset" ? "gray" : "blue",
            children: <div><b>{h.action === "reset" ? "Reset to defaults" : `Changed ${Object.keys(h.after ?? {}).join(", ")}`}</b>
              <div className="muted small">{h.changed_by} · {ago(h.changed_at)}</div></div>,
          }))} />
        ) : <span className="muted">No changes yet: this task runs on its YAML defaults.</span>}
      </Card>
    </div>
  );
}

/** Edit what each task does (options, prompts, thresholds, model) without a redeploy. */
export function AdminPage() {
  const q = useQuery({ queryKey: keys.admin, queryFn: ({ signal }) => api.admin.modules(signal) });
  const engines = useQuery({ queryKey: ["admin", "engines"], queryFn: ({ signal }) => api.admin.engines(signal) });
  const [sel, setSel] = useState<string | null>(null);
  if (q.error) return <ErrorAlert error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <Skeleton active />;
  const current = q.data.find((m) => m.name === sel) ?? q.data[0];
  return (
    <div className="admin">
      <PageHeader title="Admin" description="Change what each task does: its options, the question it asks, thresholds and the model that runs it. Saved settings are validated first, stored in the database and used by new runs." />
      {engines.data?.store === "memory" && (
        <Alert type="warning" showIcon title="Settings are kept in memory" style={{ marginBottom: 16 }}
               description="No database is configured, so changes are lost when the backend restarts." />
      )}
      <div className="admin-layout">
        <nav className="admin-list" aria-label="Tasks">
          {q.data.map((m) => (
            <button key={m.name} type="button" className={`admin-item${m.name === current.name ? " is-active" : ""}`} onClick={() => setSel(m.name)}>
              <span>{m.title}</span>
              <span className="admin-item-meta">
                {!m.enabled && <Tag variant="outlined">off</Tag>}
                {m.override && <span className="dot" style={{ background: "var(--accent)" }} title="customised" />}
              </span>
            </button>
          ))}
        </nav>
        <Editor key={current.name} m={current} />
      </div>
    </div>
  );
}
