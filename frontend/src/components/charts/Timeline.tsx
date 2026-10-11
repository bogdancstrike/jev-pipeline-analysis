import { Tooltip } from "antd";

export interface Span { key: string; label: string; start: number; end: number; color: string; detail: string; group: string }

/**
 * When each module ran within the job: one bar per module from first to last batch, colour
 * by engine (identity), labelled directly so colour is never the only channel.
 */
export function Timeline({ spans, total, groups }: {
  spans: Span[]; total: number; groups: { key: string; label: string; color: string }[];
}) {
  const max = Math.max(total, ...spans.map((s) => s.end), 0.001);
  return (
    <div className="timeline">
      <div className="legend" aria-label="Legend">
        {groups.map((g) => <span key={g.key} className="legend-item"><span className="swatch" style={{ background: g.color }} />{g.label}</span>)}
      </div>
      {spans.map((s) => (
        <div key={s.key} className="timeline-row">
          <span className="timeline-label" title={s.label}>{s.label}</span>
          <div className="timeline-track">
            <Tooltip title={s.detail}>
              <span className="timeline-bar" tabIndex={0} aria-label={`${s.label}: ${s.detail}`}
                    style={{ left: `${(s.start / max) * 100}%`, width: `max(4px, ${((s.end - s.start) / max) * 100}%)`, background: s.color }} />
            </Tooltip>
          </div>
          <span className="timeline-value">{s.end.toFixed(1)} s</span>
        </div>
      ))}
    </div>
  );
}
