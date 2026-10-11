import { useMemo, useRef, useState, memo } from "react";

/**
 * An axis bound that only grows, in 25% steps: a live chart must not rescale every second
 * (the whole line re-squeezes and reads as flicker), only when the data outgrows it.
 */
export function useStableMax(value: number, floor = 1): number {
  const ref = useRef(Math.max(floor, value));
  if (value > ref.current) ref.current = Math.max(value, ref.current * 1.25);
  return ref.current;
}

export interface Point { x: number; y: number }

/** Clean round ticks: 0 / 50 / 100 ... */
export function niceTicks(max: number, count = 4): number[] {
  if (max <= 0) return [0];
  const raw = max / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw;
  const ticks = [];
  for (let v = 0; v <= max + step * 0.001; v += step) ticks.push(Math.round(v * 1000) / 1000);
  if (ticks[ticks.length - 1] < max) ticks.push(ticks[ticks.length - 1] + step);
  return ticks;
}

/**
 * One series over time: 2px line, ~10% area wash, hairline grid, crosshair + tooltip on hover.
 * One series only (no legend box: the card title names it). For several, use small multiples.
 */
function LineChartInner({ points, height = 200, xLabel, format = (v) => v.toLocaleString(), xFormat = (v) => `${v}s`,
                            color = "var(--series-1)", ariaLabel, xMax: xMaxHint, yMax: yMaxHint }: {
  points: Point[]; height?: number; xLabel?: string; format?: (v: number) => string; xFormat?: (v: number) => string;
  color?: string; ariaLabel: string;
  /** Fixed or growing axis bounds; without them the axes follow the data (fine for finished runs). */
  xMax?: number; yMax?: number;
}) {
  const ref = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  const W = 640, H = height, L = 48, R = 16, T = 12, B = 28;
  const { xs, ys, yTicks, xMax, path, area } = useMemo(() => {
    const xMax = Math.max(1, xMaxHint ?? 0, ...points.map((p) => p.x));
    const yTicks = niceTicks(Math.max(1, yMaxHint ?? 0, ...points.map((p) => p.y)));
    const yMax = yTicks[yTicks.length - 1] || 1;
    const xs = (x: number) => L + (x / xMax) * (W - L - R);
    const ys = (y: number) => T + (1 - y / yMax) * (H - T - B);
    const path = points.map((p, i) => `${i ? "L" : "M"}${xs(p.x).toFixed(1)},${ys(p.y).toFixed(1)}`).join("");
    const area = points.length ? `${path}L${xs(points[points.length - 1].x)},${ys(0)}L${xs(points[0].x)},${ys(0)}Z` : "";
    return { xs, ys, yTicks, xMax, path, area };
  }, [points, H, xMaxHint, yMaxHint]);

  const onMove = (e: React.MouseEvent) => {
    const r = ref.current?.getBoundingClientRect();
    if (!r || !points.length) return;
    const x = ((e.clientX - r.left) / r.width) * W;
    let best = 0;
    for (let i = 1; i < points.length; i++) if (Math.abs(xs(points[i].x) - x) < Math.abs(xs(points[best].x) - x)) best = i;
    setHover(best);
  };
  const hp = hover !== null ? points[hover] : null;

  if (!points.length) return <div className="chart-empty muted small">Waiting for data…</div>;
  return (
    <div className="chart">
      <svg ref={ref} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={ariaLabel} onMouseMove={onMove}
           onMouseLeave={() => setHover(null)} preserveAspectRatio="none">
        {yTicks.map((t) => (
          <g key={t}>
            <line x1={L} x2={W - R} y1={ys(t)} y2={ys(t)} stroke="var(--grid)" strokeWidth={1} />
            <text x={L - 8} y={ys(t)} dy="0.32em" textAnchor="end" className="chart-axis">{format(t)}</text>
          </g>
        ))}
        {[0, xMax / 2, xMax].map((t) => (
          <text key={t} x={xs(t)} y={H - 8} textAnchor={t === 0 ? "start" : t === xMax ? "end" : "middle"}
                className="chart-axis">{xFormat(Math.round(t))}</text>
        ))}
        <path d={area} fill={color} opacity={0.1} className="chart-anim" />
        <path className="chart-anim" d={path} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round"
              vectorEffect="non-scaling-stroke" />
        {points.length === 1 && <circle cx={xs(points[0].x)} cy={ys(points[0].y)} r={4} fill={color} />}
        {hp && (
          <g>
            <line x1={xs(hp.x)} x2={xs(hp.x)} y1={T} y2={H - B} stroke="var(--text-3)" strokeWidth={1} vectorEffect="non-scaling-stroke" />
            <circle cx={xs(hp.x)} cy={ys(hp.y)} r={5} fill={color} stroke="var(--surface)" strokeWidth={2} vectorEffect="non-scaling-stroke" />
          </g>
        )}
      </svg>
      {hp && (
        <div className="chart-tip" style={{ left: `${(xs(hp.x) / W) * 100}%` }}>
          <b>{format(hp.y)}</b><span className="muted"> at {xFormat(hp.x)}{xLabel ? ` ${xLabel}` : ""}</span>
        </div>
      )}
    </div>
  );
}

export const LineChart = memo(LineChartInner);
