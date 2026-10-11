import { ClockCircleOutlined, ClusterOutlined } from "@ant-design/icons";
import { Tag, Typography } from "antd";

import type { AppConfig } from "../../api/types";
import { engineGroups, secondsPerArticle } from "../../lib/estimate";
import { duration, num } from "../../lib/format";

const SIZES = [50, 500, 5_000, 30_000];

/** What the selection will cost before it runs: engines involved and an estimated duration. */
export function RunSummary({ config, selected }: { config: AppConfig; selected: string[] }) {
  const groups = engineGroups(selected, config.modules);
  const { perArticle, unknown } = secondsPerArticle(selected, config.modules);
  const rate = perArticle > 0 ? 1 / perArticle : null;
  return (
    <aside className="run-summary" aria-label="Run summary">
      <div className="run-summary-title">Your run</div>
      <div className="run-summary-big">
        {selected.length} <span>task{selected.length === 1 ? "" : "s"}</span>
      </div>
      {groups.length === 0 ? <Typography.Text type="secondary">Pick analyses to see the cost.</Typography.Text> : (
        <>
          <div className="rs-label"><ClusterOutlined /> Engines</div>
          <ul className="rs-engines">
            {groups.map((g) => (
              <li key={g.engine}>
                <span className="rs-engine">{g.engine}</span>
                <span className="muted small">{g.tasks.join(", ")}</span>
                {g.tasks.length > 1 && g.engine !== "local CPU" && <Tag variant="outlined" className="rs-shared">queue: {g.tasks.length}</Tag>}
              </li>
            ))}
          </ul>
          <div className="rs-label"><ClockCircleOutlined /> Estimated time</div>
          {rate ? (
            <>
              <div className="rs-rate">≈ {rate >= 10 ? Math.round(rate) : rate.toFixed(1)} articles/s</div>
              <table className="rs-table">
                <tbody>
                  {SIZES.map((n) => <tr key={n}><td>{num(n)} articles</td><td>{duration(n * perArticle)}</td></tr>)}
                </tbody>
              </table>
            </>
          ) : <div className="muted small">Only CPU tasks: thousands of articles per second.</div>}
          {unknown.length > 0 && <div className="muted small">Not benchmarked yet: {unknown.join(", ")}.</div>}
          <div className="rs-foot muted small">From single-task benchmarks on this GPU, 300–1,500-word articles.</div>
        </>
      )}
    </aside>
  );
}
