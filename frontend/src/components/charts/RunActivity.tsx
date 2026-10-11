import type { RunRecord } from "../../api/types";
import { num } from "../../lib/format";
import { niceTicks } from "./LineChart";

export interface ActivityDay { key: string; label: string; records: number; runs: number }

/** Calendar days in the browser's timezone, including days without runs. */
export function activityDays(runs: RunRecord[], now = new Date()): ActivityDay[] {
  return Array.from({ length: 7 }, (_, index) => {
    const day = new Date(now);
    day.setHours(0, 0, 0, 0);
    day.setDate(day.getDate() - (6 - index));
    const end = new Date(day);
    end.setDate(end.getDate() + 1);
    const daily = runs.filter((run) => run.status === "done" && run.created_at * 1000 >= day.getTime() && run.created_at * 1000 < end.getTime());
    return { key: day.toISOString(), label: day.toLocaleDateString(undefined, { month: "short", day: "numeric" }),
      records: daily.reduce((sum, run) => sum + run.total, 0), runs: daily.length };
  });
}

export function RunActivity({ days }: { days: ActivityDay[] }) {
  const width = 540, height = 130, left = 48, right = 12, top = 20, bottom = 28;
  const ticks = niceTicks(Math.max(1, ...days.map((day) => day.records)));
  const max = ticks[ticks.length - 1] || 1;
  const plotHeight = height - top - bottom;
  const step = (width - left - right) / days.length;
  const y = (value: number) => top + plotHeight * (1 - value / max);
  return <div className="activity-chart">
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Records processed per day over the last seven days. ${days.map((day) => `${day.label}: ${num(day.records)} records in ${day.runs} runs`).join(". ")}`}>
      {ticks.map((tick) => <g key={tick}><line x1={left} x2={width - right} y1={y(tick)} y2={y(tick)} stroke="var(--grid)" />
        <text x={left - 8} y={y(tick)} dy="0.32em" textAnchor="end" className="chart-axis">{Intl.NumberFormat(undefined, { notation: "compact" }).format(tick)}</text></g>)}
      {days.map((day, index) => {
        const x = left + step * index + step / 2;
        return <g key={day.key}>
          <rect x={x - step * 0.28} y={y(day.records)} width={step * 0.56} height={plotHeight * day.records / max} rx={4} fill="var(--series-3)">
            <title>{day.label}: {num(day.records)} records · {day.runs} runs</title>
          </rect>
          {day.records > 0 && <text x={x} y={y(day.records) - 7} textAnchor="middle" className="activity-chart-value">{Intl.NumberFormat(undefined, { notation: "compact" }).format(day.records)}</text>}
          <text x={x} y={height - 12} textAnchor="middle" className="chart-axis">{day.label}</text>
        </g>;
      })}
    </svg>
  </div>;
}
