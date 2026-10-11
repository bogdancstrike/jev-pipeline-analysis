import { memo } from "react";
import type { ReactNode } from "react";

type Tone = "default" | "warning" | "danger" | "success";

/**
 * A number that answers one question. Label in sentence case, value in tabular figures,
 * an optional hint for context; tone only when the number is a state (warnings, failures).
 */
function StatTileInner({ label, value, hint, icon, tone = "default", onClick }: {
  label: string; value: ReactNode; hint?: ReactNode; icon?: ReactNode; tone?: Tone; onClick?: () => void;
}) {
  const body = (
    <>
      {icon && <span className="stat-icon" aria-hidden>{icon}</span>}
      <span className="stat-text">
        <span className="stat-label">{label}</span>
        <span className="stat-value">{value}</span>
        {hint && <span className="stat-hint">{hint}</span>}
      </span>
    </>
  );
  const cls = `stat-tile stat-${tone}${onClick ? " stat-clickable" : ""}`;
  return onClick
    ? <button type="button" className={cls} onClick={onClick}>{body}</button>
    : <div className={cls}>{body}</div>;
}

export function StatRow({ children }: { children: ReactNode }) {
  return <div className="stat-row">{children}</div>;
}

export const StatTile = memo(StatTileInner);
