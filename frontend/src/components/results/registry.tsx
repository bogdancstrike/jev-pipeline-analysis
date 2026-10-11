import type { ReactNode } from "react";

import type { ModuleInfo, ModuleKind } from "../../api/types";
import { EntitiesCell, EntitiesDetail, ResolvedCell, ResolvedDetail } from "./EntityViews";
import { LabelCell, LabelDetail } from "./LabelView";
import { ClusterCell, ClusterDetail, RelationsCell, RelationsDetail } from "./RelationViews";
import { FieldsCell, FieldsDetail } from "./RecordViews";
import { IndicatorDetail } from "./IndicatorView";
import { TemporalDetail } from "./TemporalView";

export interface RenderContext {
  module: ModuleInfo;
  modules: ModuleInfo[];
  jobId?: string;
  /** Filter the rows table by this module's value (label, entity id, cluster id). */
  onFilter?: (value: string) => void;
  onOpenRow?: (idx: number) => void;
}

interface Renderer {
  /** Compact form for a table cell; receives the module's `preview`. */
  cell: (value: unknown, ctx: RenderContext) => ReactNode;
  /** Full form for the row drawer; receives the module's full result. */
  detail: (value: unknown, ctx: RenderContext) => ReactNode;
}

/**
 * One renderer per result *kind* (see backend `core/modules.py: Kind`). A new backend
 * module of an existing kind needs no frontend change; a new kind needs one entry here.
 */
export const RENDERERS: Record<ModuleKind, Renderer> = {
  label: {
    cell: (v, c) => <LabelCell value={v} module={c.module} />,
    detail: (v, c) => <LabelDetail value={v} module={c.module} />,
  },
  entities: {
    cell: (v, c) => <EntitiesCell value={v} modules={c.modules} />,
    detail: (v, c) => c.module.name === "ioc" ? <IndicatorDetail value={v} /> : <EntitiesDetail value={v} modules={c.modules} />,
  },
  resolved: {
    cell: (v, c) => <ResolvedCell value={v} modules={c.modules} />,
    detail: (v, c) => <ResolvedDetail value={v} modules={c.modules} onFilter={c.onFilter} />,
  },
  relations: {
    cell: (v) => <RelationsCell value={v} />,
    detail: (v, c) => <RelationsDetail value={v} modules={c.modules} />,
  },
  record: {
    cell: (v) => <FieldsCell value={v} />,
    detail: (v, c) => c.module.name === "temporal" ? <TemporalDetail value={v} /> : <FieldsDetail value={v} />,
  },
  cluster: {
    cell: (v) => <ClusterCell value={v} />,
    detail: (v, c) => <ClusterDetail value={v} jobId={c.jobId} onOpenRow={c.onOpenRow} onFilter={c.onFilter} />,
  },
};

const FALLBACK: Renderer = {
  cell: (v) => <span className="mono small">{v == null ? "–" : JSON.stringify(v).slice(0, 60)}</span>,
  detail: (v) => <pre className="json">{JSON.stringify(v, null, 2)}</pre>,
};

export const rendererFor = (kind: string): Renderer => RENDERERS[kind as ModuleKind] ?? FALLBACK;
