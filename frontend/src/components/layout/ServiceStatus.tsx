import { Badge, Popover, Space, Typography } from "antd";

import { useAppConfig, useHealth } from "../../hooks/queries";
import { num } from "../../lib/format";

/** One quiet dot in the header; every engine's details are one hover away. */
export function ServiceStatus() {
  const health = useHealth();
  const config = useAppConfig();
  const h = health.data;
  if (!h) {
    return <Badge status={health.isError ? "error" : "processing"}
                  text={health.isError ? "Backend unreachable" : "Connecting"} />;
  }
  const titles = Object.fromEntries((config.data?.modules ?? []).map((m) => [m.name, m.title]));
  const engines = Object.values(h.engines ?? {});
  const onCpu = engines.filter((e) => e.ready && (e.degraded || (e.device && !/cuda|gpu|nvidia|geforce|rtx/i.test(e.device))));

  const content = (
    <Space orientation="vertical" size={12} style={{ maxWidth: 380 }}>
      {engines.map((e) => (
        <div key={e.name}>
          <Badge status={e.ready ? (onCpu.includes(e) ? "warning" : "success") : "processing"}
                 text={<b>{e.name}</b>} />
          <div className="muted small status-detail">
            {e.description && <>{e.description}<br /></>}
            {e.ready
              ? <>{e.device ? `on ${e.device}` : ""}{e.vram_reserved_mb ? ` · ${num(e.vram_reserved_mb)} MB` : ""}
                  {e.prompt_tps ? ` · ${num(Math.round(e.prompt_tps))} tok/s` : ""}</>
              : "Loading weights…"}
            <br />Runs: {e.modules.map((m) => titles[m] ?? m).join(", ")}
            {e.degraded && <><br /><span className="text-warning-strong">⚠ {e.degraded}</span></>}
          </div>
        </div>
      ))}
      {engines.length === 0 && <Typography.Text type="secondary">No model engines needed.</Typography.Text>}
    </Space>
  );

  return (
    <Popover content={content} title="Model engines" placement="bottomRight" trigger={["hover", "click"]}>
      <button type="button" className="status-chip" aria-label="Model status">
        <Badge status={h.status === "ready" ? (onCpu.length ? "warning" : "success") : "processing"} />
        <span>{h.status === "ready" ? "Models ready" : h.status === "degraded" ? "Models slowed: GPU memory" : "Models loading"}</span>
      </button>
    </Popover>
  );
}
