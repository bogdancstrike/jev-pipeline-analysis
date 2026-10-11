import { memo } from "react";
import { CheckCircleFilled, CloseCircleFilled } from "@ant-design/icons";
import { Tooltip } from "antd";

export interface Outcome { key: string; label: string; ok: number; failed: number; pending: number }

/**
 * Success / failed / pending per module as one stacked bar each. Status colours are reserved
 * for this meaning and always ship with an icon + count, never colour alone.
 */
function OutcomeBarsInner({ rows }: { rows: Outcome[] }) {
  return (
    <div className="outcomes">
      <div className="legend">
        <span className="legend-item"><CheckCircleFilled style={{ color: "var(--good)" }} /> processed</span>
        <span className="legend-item"><CloseCircleFilled style={{ color: "var(--critical)" }} /> failed</span>
        <span className="legend-item"><span className="swatch swatch-pending" /> pending</span>
      </div>
      {rows.map((r) => {
        const total = Math.max(1, r.ok + r.failed + r.pending);
        return (
          <div key={r.key} className="outcome-row">
            <span className="timeline-label" title={r.label}>{r.label}</span>
            <Tooltip title={`${r.ok.toLocaleString()} processed · ${r.failed.toLocaleString()} failed · ${r.pending.toLocaleString()} pending`}>
              <div className="outcome-track" tabIndex={0}>
                {r.ok > 0 && <span style={{ flexGrow: r.ok, background: "var(--good)" }} />}
                {r.failed > 0 && <span style={{ flexGrow: r.failed, background: "var(--critical)" }} />}
                {r.pending > 0 && <span style={{ flexGrow: r.pending }} className="outcome-pending" />}
              </div>
            </Tooltip>
            <span className="timeline-value">
              {r.failed ? <span className="text-danger">{r.failed} failed</span> : `${Math.round((r.ok / total) * 100)}%`}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export const OutcomeBars = memo(OutcomeBarsInner);
