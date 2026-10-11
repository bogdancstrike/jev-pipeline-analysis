import { CheckOutlined, CodeOutlined, DeleteOutlined, DownOutlined, HistoryOutlined, PlusOutlined, SaveOutlined, SearchOutlined, SettingOutlined, TagsOutlined, UndoOutlined } from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, App, Button, Empty, Input, InputNumber, Popconfirm, Select, Skeleton, Switch, Table, Tabs, Tag, Timeline } from "antd";
import { useEffect, useMemo, useState } from "react";

import { ApiError } from "../api/client";
import { api } from "../api/endpoints";
import type { AdminModule } from "../api/types";
import { ErrorAlert } from "../components/common/ErrorAlert";
import { PageHeader } from "../components/ui/PageHeader";
import { keys } from "../hooks/queries";
import { ago, humanize, plural } from "../lib/format";

type Cfg = Record<string, unknown>;
interface LabelRow { key: string; description: string; uid: number }
const NUMERIC = ["review_below", "threshold", "min_confidence", "max_pairs", "max_relations", "batch_size", "concurrency",
  "min_probability", "same_event_threshold", "max_entity_rows", "top_k"];
const TASK_GROUPS = [
  { title: "Classification & routing", names: ["language", "category", "relevance", "routing"] },
  { title: "Entities & events", names: ["ner", "entity_resolution", "relations", "fields", "event", "event_coreference"] },
  { title: "Tone & risk", names: ["sentiment", "intent", "risk", "toxicity", "propaganda"] },
];

function toRows(labels: unknown): LabelRow[] {
  if (Array.isArray(labels)) return labels.map((k, uid) => ({ key: String(k), description: "", uid }));
  return Object.entries((labels as Record<string, string>) ?? {}).map(([key, description], uid) => ({ key, description: String(description ?? ""), uid }));
}
function fromRows(rows: LabelRow[], wasList: boolean): unknown {
  const clean = rows.filter((r) => r.key.trim());
  if (wasList && clean.every((r) => !r.description.trim())) return clean.map((r) => r.key.trim());
  return Object.fromEntries(clean.map((r) => [r.key.trim(), r.description.trim()]));
}

function Editor({ m, onDirtyChange }: { m: AdminModule; onDirtyChange: (dirty: boolean) => void }) {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const [baseline, setBaseline] = useState(m.effective);
  const [draft, setDraft] = useState<Cfg>(m.effective);
  const labelKey = "labels" in baseline ? "labels" : "languages" in baseline ? "languages" : null;
  const [rows, setRows] = useState<LabelRow[]>(toRows(labelKey ? m.effective[labelKey] : undefined));
  const [json, setJson] = useState(JSON.stringify(m.effective, null, 2));
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [tab, setTab] = useState("settings");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const history = useQuery({ queryKey: keys.history(m.name), queryFn: ({ signal }) => api.admin.history(m.name, signal) });
  const wasList = labelKey ? Array.isArray(draft[labelKey]) : false;
  const config = useMemo<Cfg>(() => labelKey ? { ...draft, [labelKey]: fromRows(rows, wasList) } : draft, [draft, rows, labelKey, wasList]);
  const dirty = JSON.stringify(config) !== JSON.stringify(baseline) || jsonError !== null;
  const set = (key: string, value: unknown) => setDraft((old) => ({ ...old, [key]: value }));

  useEffect(() => { onDirtyChange(dirty); }, [dirty, onDirtyChange]);
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  // Background refetches must not overwrite a draft. Successful saves set the baseline directly.
  useEffect(() => {
    if (dirty) return;
    setBaseline(m.effective); setDraft(m.effective);
    setRows(toRows(labelKey ? m.effective[labelKey] : undefined));
    setJson(JSON.stringify(m.effective, null, 2));
  }, [m.effective]); // eslint-disable-line react-hooks/exhaustive-deps

  const apply = (effective: Cfg) => {
    setBaseline(effective); setDraft(effective); setRows(toRows(labelKey ? effective[labelKey] : undefined));
    setJson(JSON.stringify(effective, null, 2)); setJsonError(null);
  };
  const refresh = () => Promise.all([
    qc.invalidateQueries({ queryKey: keys.admin }), qc.invalidateQueries({ queryKey: keys.config }),
    qc.invalidateQueries({ queryKey: keys.history(m.name) }),
  ]);
  const save = async () => {
    setSaving(true); setError(null);
    try {
      const saved = await api.admin.save(m.name, config);
      apply(saved.effective);
      message.success(`${m.title}: saved. New runs use these settings.`);
      await refresh();
    } catch (e) { setError(e); } finally { setSaving(false); }
  };
  const reset = async () => {
    setSaving(true); setError(null);
    try {
      const saved = await api.admin.reset(m.name);
      apply(saved.effective);
      message.success(`${m.title}: restored defaults.`);
      await refresh();
    } catch (e) { setError(e); } finally { setSaving(false); }
  };
  const numericKeys = NUMERIC.filter((key) => typeof baseline[key] === "number");
  const optionCount = rows.filter((r) => r.key.trim()).length;

  const settings = <div className="admin-settings">
    <div className="admin-section-label"><h4>Availability & model</h4><p>Control how this task is offered and which engine processes it.</p></div>
    <div className="admin-toggle-grid">
      <div className="admin-toggle"><div><label htmlFor="task-enabled">Task enabled</label><p>Available for new analyses</p></div><Switch id="task-enabled" checked={draft.enabled !== false} onChange={(v) => set("enabled", v)} /></div>
      <div className="admin-toggle"><div><label htmlFor="task-default">Selected by default</label><p>Included when starting an analysis</p></div><Switch id="task-default" checked={draft.default_on !== false} onChange={(v) => set("default_on", v)} /></div>
    </div>
    {m.engine_choices.length > 0 && <div className="admin-field admin-engine-field"><label htmlFor="task-engine">Model engine</label>
      <Select id="task-engine" value={String(draft.engine ?? "")} onChange={(v) => set("engine", v)} options={m.engine_choices.map((e) => ({ value: e, label: e }))} />
      <span className="muted small">Compatible with {m.engine_kinds.join(" / ")}</span></div>}
    {m.requires.length > 0 && <div className="admin-dependencies"><span className="muted small">Requires</span>{m.requires.map((name) => <Tag key={name}>{humanize(name)}</Tag>)}</div>}
    {numericKeys.length > 0 && <><div className="admin-section-label"><h4>Processing controls</h4><p>Adjust confidence thresholds and processing limits.</p></div>
      <div className="admin-field-grid">{numericKeys.map((key) => <div key={key} className="admin-field"><label htmlFor={`setting-${key}`}>{humanize(key)}</label>
        <InputNumber id={`setting-${key}`} style={{ width: "100%" }} value={draft[key] as number} onChange={(v) => set(key, v)} step={/below|threshold|confidence|probability/.test(key) ? 0.05 : 1} />
      </div>)}</div></>}
    {typeof baseline.instructions === "string" && <div className="admin-field admin-instructions"><label htmlFor="task-instructions">Model instructions</label><span className="muted small">The question this task asks the model. Be specific about the expected result.</span>
      <Input.TextArea id="task-instructions" value={String(draft.instructions ?? "")} onChange={(e) => set("instructions", e.target.value)} autoSize={{ minRows: 3, maxRows: 8 }} /></div>}
  </div>;
  const options = <div className="admin-options">
    <div className="admin-options-head"><p className="muted small">Keys appear in the output. Use clear descriptions to help the model distinguish each option.</p>
      <Button icon={<PlusOutlined />} onClick={() => setRows((old) => [...old, { key: "", description: "", uid: Math.max(0, ...old.map((r) => r.uid)) + 1 }])}>Add option</Button></div>
    <Table<LabelRow> size="small" rowKey="uid" dataSource={rows} pagination={false} scroll={{ x: 550 }} columns={[
      { title: "Output key", dataIndex: "key", width: "32%", render: (_, row) => <Input aria-label={`Option key ${row.uid + 1}`} value={row.key} placeholder="new_option" onChange={(e) => setRows((all) => all.map((r) => r.uid === row.uid ? { ...r, key: e.target.value } : r))} /> },
      { title: "Description for the model", dataIndex: "description", render: (_, row) => <Input aria-label={`Description for option ${row.uid + 1}`} value={row.description} placeholder="What this option means" onChange={(e) => setRows((all) => all.map((r) => r.uid === row.uid ? { ...r, description: e.target.value } : r))} /> },
      { title: "", key: "remove", width: 48, render: (_, row) => <Button type="text" danger icon={<DeleteOutlined />} aria-label={`Remove ${row.key || "option"}`} onClick={() => setRows((all) => all.filter((r) => r.uid !== row.uid))} /> },
    ]} />
  </div>;
  const advanced = <div className="admin-json"><p className="muted small">Edit the full task configuration. Valid JSON updates the same draft as the Settings and Options tabs; use Save changes to apply it.</p>
    <Input.TextArea aria-label="Full task configuration JSON" value={json} onChange={(event) => {
      const value = event.target.value; setJson(value);
      try {
        const parsed = JSON.parse(value) as Cfg;
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("Configuration must be a JSON object.");
        if (labelKey && parsed[labelKey] != null && typeof parsed[labelKey] !== "object") throw new Error(`${labelKey} must be an object or a list.`);
        setDraft(parsed); setRows(toRows(labelKey ? parsed[labelKey] : undefined)); setJsonError(null);
      } catch (e) { setJsonError((e as Error).message); }
    }} autoSize={{ minRows: 12, maxRows: 28 }} className="mono" status={jsonError ? "error" : undefined} />
    {jsonError && <Alert type="error" showIcon title="Fix the JSON before saving" description={jsonError} />}
  </div>;
  const changes = history.error ? <ErrorAlert error={history.error} onRetry={() => history.refetch()} /> : history.isLoading ? <Skeleton active /> : history.data?.length ? <Timeline items={history.data.map((h) => ({
    color: h.action === "reset" ? "gray" : "blue",
    children: <div><strong>{h.action === "reset" ? "Restored defaults" : `Updated ${Object.keys(h.after ?? {}).map(humanize).join(", ")}`}</strong><div className="muted small">{h.changed_by} · {ago(h.changed_at)}</div></div>,
  }))} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No changes yet. This task uses its default settings." />;

  return <div className="admin-editor">
    <div className="admin-head">
      <div className="admin-task-heading"><div className="admin-title-row"><h3>{m.title}</h3><Tag color={m.override ? "processing" : "default"}>{m.override ? "Customised" : "Default settings"}</Tag></div><p>{m.description}</p>
        <div className="admin-task-meta"><span>{humanize(m.kind)}</span><span>{m.name}</span></div></div>
      <div className="admin-actions">
        <Popconfirm title="Restore default settings?" description="Removes saved overrides and discards your draft." onConfirm={reset} disabled={(!m.override && !dirty) || saving}>
          <Button icon={<UndoOutlined />} disabled={(!m.override && !dirty) || saving}>Reset</Button>
        </Popconfirm>
        <Button type="primary" icon={<SaveOutlined />} loading={saving} disabled={!dirty || !!jsonError} onClick={save}>Save changes</Button>
      </div>
    </div>
    {error ? <ErrorAlert error={error} title={error instanceof ApiError && error.status === 422 ? "Configuration needs attention" : "Could not save settings"} /> : null}
    <div className="admin-draft-status" aria-live="polite"><span className={`dot ${dirty ? "draft-pending" : "activity-idle"}`} />{jsonError ? "Invalid JSON · fix it in Advanced before saving" : dirty ? "Unsaved changes" : "All changes saved"}<span className="muted small">Settings apply to new runs</span></div>
    <fieldset className="admin-edit-fields" disabled={saving}>
      <Tabs activeKey={tab} onChange={(next) => { if (next === "advanced" && !jsonError) setJson(JSON.stringify(config, null, 2)); setTab(next); }} items={[
        { key: "settings", label: "Settings", icon: <SettingOutlined />, children: settings },
        ...(labelKey ? [{ key: "options", label: `Options (${optionCount})`, icon: <TagsOutlined />, children: options }] : []),
        { key: "advanced", label: "Advanced", icon: <CodeOutlined />, children: advanced },
        { key: "history", label: "History", icon: <HistoryOutlined />, children: changes },
      ]} />
    </fieldset>
  </div>;
}

export function AdminPage() {
  const q = useQuery({ queryKey: keys.admin, queryFn: ({ signal }) => api.admin.modules(signal) });
  const engines = useQuery({ queryKey: ["admin", "engines"], queryFn: ({ signal }) => api.admin.engines(signal) });
  const { modal } = App.useApp();
  const [selected, setSelected] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [dirty, setDirty] = useState(false);
  const [expanded, setExpanded] = useState<string[]>([TASK_GROUPS[0].title]);
  if (q.error) return <ErrorAlert error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <Skeleton active />;
  const current = q.data.find((m) => m.name === selected) ?? q.data[0];
  const filtered = q.data.filter((m) => `${m.title} ${m.name}`.toLowerCase().includes(search.toLowerCase().trim()));
  const known = new Set(TASK_GROUPS.flatMap((group) => group.names));
  const groups = [...TASK_GROUPS.map((group) => ({ title: group.title, items: filtered.filter((m) => group.names.includes(m.name)) })),
    { title: "Other tasks", items: filtered.filter((m) => !known.has(m.name)) }].filter((group) => group.items.length);
  const select = (name: string) => {
    if (name === current?.name) return;
    const change = () => {
      setDirty(false); setSelected(name);
      const group = groups.find((group) => group.items.some((m) => m.name === name));
      if (group) setExpanded((old) => old.includes(group.title) ? old : [...old, group.title]);
    };
    if (dirty) modal.confirm({ title: "Discard unsaved changes?", content: "Your edits to this task have not been saved.", okText: "Discard changes", okButtonProps: { danger: true }, cancelText: "Keep editing", onOk: change });
    else change();
  };
  return <div className="admin">
    <PageHeader title="Task configuration" description="Fine-tune models, instructions and output options for your analyses."
      meta={<><span className="meta-chip">{q.data.filter((m) => m.enabled).length} enabled</span><span className="meta-chip">{q.data.filter((m) => m.override).length} customised</span></>} />
    {engines.data?.store === "memory" && <Alert type="warning" showIcon title="Settings are kept in memory" className="admin-store-alert" description="Changes are lost when the backend restarts. Configure a database to retain them." />}
    <div className="admin-layout">
      <nav className="admin-list" aria-label="Tasks">
        <div className="admin-list-head"><div><strong>Analysis tasks</strong><span className="muted small">{q.data.length}</span></div>
          <Input prefix={<SearchOutlined />} placeholder="Find a task…" aria-label="Search tasks" value={search} onChange={(e) => setSearch(e.target.value)} allowClear /></div>
        <div className="admin-list-items">{filtered.length ? groups.map((group, index) => {
          const open = !!search.trim() || expanded.includes(group.title);
          return <div key={group.title} className={`admin-task-group${open ? " is-open" : ""}`}>
            <button type="button" className="admin-group-toggle" aria-expanded={open} aria-controls={`task-group-${index}`} onClick={() => setExpanded((old) => old.includes(group.title) ? old.filter((title) => title !== group.title) : [...old, group.title])}>
              <span>{group.title}</span><span className="admin-group-count">{group.items.length}</span><DownOutlined className="admin-group-arrow" aria-hidden />
            </button>
            {open && <div id={`task-group-${index}`} className="admin-group-items">{group.items.map((m) => <button key={m.name} type="button" aria-current={m.name === current?.name ? "true" : undefined} className={`admin-item${m.name === current?.name ? " is-active" : ""}`} onClick={() => select(m.name)}>
          <span className="admin-item-main"><strong>{m.title}</strong><span className="admin-engine-label">{m.effective.engine ? String(m.effective.engine) : "Local"}</span></span>
          <span className="admin-item-meta">{!m.enabled ? <span className="admin-off">Off</span> : m.override ? <span className="dot draft-pending" title="Customised" /> : m.name === current?.name ? <CheckOutlined /> : null}</span>
        </button>)}</div>}</div>;
        }) : <p className="admin-no-match muted small">No tasks match “{search}”.</p>}</div>
        <div className="admin-list-foot">{plural(filtered.length, "task")} · select one to configure</div>
      </nav>
      {current ? <Editor key={current.name} m={current} onDirtyChange={setDirty} /> : <Empty description="No tasks configured" />}
    </div>
  </div>;
}
