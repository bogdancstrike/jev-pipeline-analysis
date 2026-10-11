import { Tooltip } from "antd";
import { useState, memo } from "react";

export interface Bar { key: string; label: string; value: number; color?: string; hint?: string }

/**
 * Horizontal bars as a list: readable labels, exact counts, and each row a filter button.
 * Chosen over a chart library: the question is always "how many of each", answered at a glance.
 */
function BarListInner({ bars, total, selected, onSelect, limit = 8 }: {
  bars: Bar[]; total?: number; selected?: string; onSelect?: (key: string) => void; limit?: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const max = Math.max(1, ...bars.map((b) => b.value));
  const shown = expanded ? bars : bars.slice(0, limit);
  const rest = bars.length - shown.length;
  return (
    <ul className="barlist">
      {shown.map((b) => {
        const share = total ? ` · ${Math.round((b.value / total) * 100)}%` : "";
        const active = selected === b.key;
        return (
          <li key={b.key}>
            <Tooltip title={b.hint} placement="left" mouseEnterDelay={0.4}>
              <button type="button" className={`barlist-row${active ? " is-active" : ""}`}
                      disabled={!onSelect} onClick={() => onSelect?.(b.key)}
                      aria-pressed={active} aria-label={`${b.label}: ${b.value}`}>
                <span className="barlist-fill" style={{ width: `${(b.value / max) * 100}%`, background: b.color }} />
                <span className="barlist-label">{b.label}</span>
                <span className="barlist-value">{b.value.toLocaleString()}<span className="muted">{share}</span></span>
              </button>
            </Tooltip>
          </li>
        );
      })}
      {(rest > 0 || expanded) && bars.length > limit && (
        <li>
          <button type="button" className="link-btn barlist-more" onClick={() => setExpanded(!expanded)}>
            {expanded ? "Show fewer" : `Show ${rest} more`}
          </button>
        </li>
      )}
    </ul>
  );
}

export const BarList = memo(BarListInner);
