import { memo } from "react";
import { Progress, Space, Tag, Tooltip, Typography } from "antd";

import type { LabelResult, ModuleInfo } from "../../api/types";
import { pct } from "../../lib/format";
import { labelColor, labelOrder, labelText, labelTone, type Tone } from "../../lib/labels";

const TONE_TAG: Record<Tone, string | undefined> = {
  danger: "error", warning: "warning", success: "success", neutral: undefined,
};

function LabelTagInner({ module, label, review, compact }: { module: ModuleInfo; label: string; review?: boolean; compact?: boolean }) {
  const tone = labelTone(module.name, label);
  const color = tone ? TONE_TAG[tone] : labelColor(label, labelOrder(module));
  return (
    <Tooltip title={module.labels?.[label] || undefined} mouseEnterDelay={0.4}>
      <Tag color={color} variant={tone ? "filled" : "outlined"} className={review ? "tag-review" : undefined}
           style={{ marginInlineEnd: 0 }}>
        {labelText(module, label, compact)}
      </Tag>
    </Tooltip>
  );
}

/** Table cell: label, confidence, and an amber mark when the model was unsure. */
function LabelCellInner({ value, module }: { value: unknown; module: ModuleInfo }) {
  const r = value as LabelResult | null;
  if (!r) return <span className="muted">–</span>;
  const unsure = module.review_below !== undefined && r.confidence < module.review_below;
  return (
    <Tooltip title={unsure ? `Low confidence (${pct(r.confidence)}): worth a human look` : undefined}>
      <span className="cell-label">
        <LabelTag module={module} label={r.label} review={unsure} compact />
        <span className={unsure ? "conf conf-low" : "conf"}>{pct(r.confidence)}</span>
      </span>
    </Tooltip>
  );
}

/** Drawer: the label, the alternatives the model weighed, and module-specific extras. */
function LabelDetailInner({ value, module }: { value: unknown; module: ModuleInfo }) {
  const r = value as LabelResult | null;
  if (!r) return <span className="muted">No result (empty text).</span>;
  return (
    <Space orientation="vertical" size={8} style={{ width: "100%" }}>
      <div className="label-head">
        <LabelTag module={module} label={r.label} />
        <span className="muted small">
          {pct(r.confidence)} confident
          {r.score !== undefined && <> · score {r.score > 0 ? "+" : ""}{r.score.toFixed(2)}</>}
        </span>
      </div>
      {r.techniques && r.techniques.length > 0 && (
        <Space wrap size={4}>
          <Typography.Text type="secondary">Techniques:</Typography.Text>
          {r.techniques.map((t) => <LabelTag key={t} module={module} label={t} />)}
        </Space>
      )}
      {r.top && r.top.length > 1 && (
        <div className="prob-list">
          {r.top.map(([label, p]) => (
            <div key={label} className="prob-row">
              <span className="prob-label">{labelText(module, label)}</span>
              <Progress percent={Math.round(p * 100)} size="small" showInfo={false}
                        strokeColor={label === r.label ? undefined : "var(--text-3)"} />
              <span className="prob-value">{pct(p)}</span>
            </div>
          ))}
        </div>
      )}
    </Space>
  );
}

export const LabelCell = memo(LabelCellInner);

export const LabelDetail = memo(LabelDetailInner);

export const LabelTag = memo(LabelTagInner);
