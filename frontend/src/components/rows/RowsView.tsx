import { SearchOutlined, SettingOutlined, WarningFilled } from "@ant-design/icons";
import { Button, Checkbox, Input, Popover, Segmented, Table, Tag, Tooltip } from "antd";
import type { ColumnsType } from "antd/es/table";

import type { JobSnapshot, ModuleInfo, RowItem, RowPage } from "../../api/types";
import { humanize } from "../../lib/format";
import { EmptyState } from "../common/EmptyState";
import { ErrorAlert } from "../common/ErrorAlert";
import type { Filter } from "../job/Overview";
import { rendererFor } from "../results/registry";

export type RowMode = "all" | "review" | "errors";

const DEFAULT_COLUMNS = ["language", "category", "sentiment", "toxicity", "entity_resolution", "event_coreference"];
const WIDTH: Record<string, number> = { label: 170, entities: 260, resolved: 260, relations: 260, cluster: 110 };

interface Props {
  job: JobSnapshot;
  modules: ModuleInfo[];
  page: RowPage | undefined;
  loading: boolean;
  error: unknown;
  onRetry: () => void;
  pageNo: number;
  pageSize: number;
  onPage: (p: number) => void;
  search: string;
  onSearch: (q: string) => void;
  mode: RowMode;
  onMode: (m: RowMode) => void;
  filters: Filter[];
  onRemoveFilter: (f: Filter) => void;
  onClearAll: () => void;
  columns: string[];
  onColumns: (c: string[]) => void;
  onOpen: (idx: number) => void;
}

export const defaultColumns = (job: JobSnapshot) => {
  const base = DEFAULT_COLUMNS.filter((c) => job.modules.includes(c));
  if (!base.includes("entity_resolution") && job.modules.includes("ner")) base.push("ner");
  return base;
};

export function RowsView(p: Props) {
  const { job, modules } = p;
  const inJob = modules.filter((m) => job.modules.includes(m.name));
  const visible = inJob.filter((m) => p.columns.includes(m.name));
  const title = (n: string) => modules.find((m) => m.name === n)?.title ?? n;

  const columns: ColumnsType<RowItem> = [
    {
      title: "ID", dataIndex: "id", width: 84, fixed: "left",
      render: (id: string, r) => (
        <span className="row-id">
          {r.review.length > 0 && (
            <Tooltip title={`Needs review: ${r.review.map(title).join(", ")}`}>
              <WarningFilled className="review-mark" aria-label="needs review" />
            </Tooltip>
          )}
          <span className="mono">{id}</span>
        </span>
      ),
    },
    {
      title: "Text", dataIndex: "preview", width: 360,
      render: (t: string, r) => (
        <div className="cell-text">
          {t || <span className="muted">(empty)</span>}
          {r.errors.length > 0 && <div className="text-danger small">Failed: {r.errors.map(title).join(", ")}</div>}
        </div>
      ),
    },
    ...visible.map((m) => ({
      title: m.title, key: m.name, width: WIDTH[m.kind] ?? 180,
      render: (_: unknown, r: RowItem) => rendererFor(m.kind).cell(r.results[m.name], { module: m, modules }),
    })),
  ];

  const columnPicker = (
    <Checkbox.Group value={p.columns} onChange={(v) => p.onColumns(v as string[])} className="column-picker">
      {inJob.map((m) => <Checkbox key={m.name} value={m.name}>{m.title}</Checkbox>)}
    </Checkbox.Group>
  );

  const filtered = p.filters.length > 0 || p.mode !== "all" || p.search.trim() !== "";

  return (
    <div className="rows-view">
      <div className="toolbar">
        <Input allowClear prefix={<SearchOutlined />} placeholder="Search id or text" value={p.search}
               onChange={(e) => p.onSearch(e.target.value)} className="toolbar-search" aria-label="Search rows" />
        <Segmented<RowMode> value={p.mode} onChange={p.onMode} options={[
          { value: "all", label: "All" }, { value: "review", label: "Needs review" }, { value: "errors", label: "Errors" },
        ]} />
        <span className="toolbar-spacer" />
        <Popover content={columnPicker} title="Columns" trigger="click" placement="bottomRight">
          <Button icon={<SettingOutlined />}>Columns</Button>
        </Popover>
      </div>
      {p.filters.length > 0 && (
        <div className="active-filters">
          {p.filters.map((f) => (
            <Tag key={f.join(":")} closable onClose={() => p.onRemoveFilter(f)} color="processing" variant="filled">
              {title(f[0])}: {f[0] === "entity_resolution" || f[0] === "event_coreference" ? f[1] : humanize(f[1])}
            </Tag>
          ))}
          <Button type="link" size="small" onClick={p.onClearAll}>Clear all</Button>
        </div>
      )}
      {p.error ? <ErrorAlert error={p.error} onRetry={p.onRetry} /> : (
        <Table<RowItem>
          rowKey="idx"
          size="small"
          columns={columns}
          dataSource={p.page?.items ?? []}
          loading={p.loading && !p.page}
          scroll={{ x: "max-content" }}
          onRow={(r) => ({ onClick: () => p.onOpen(r.idx), className: "row-click", tabIndex: 0,
                           onKeyDown: (e) => { if (e.key === "Enter") p.onOpen(r.idx); } })}
          pagination={{ current: p.pageNo, pageSize: p.pageSize, total: p.page?.total ?? 0, showSizeChanger: false,
                        onChange: p.onPage, showTotal: (t) => `${t.toLocaleString()} rows`, hideOnSinglePage: false }}
          locale={{ emptyText: filtered
            ? <EmptyState title="No rows match" hint="Try removing a filter." action={<Button size="small" onClick={p.onClearAll}>Clear filters</Button>} />
            : <EmptyState title="Rows appear here as they finish" /> }}
        />
      )}
    </div>
  );
}
