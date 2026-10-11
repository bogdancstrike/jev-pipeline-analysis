import { PlayCircleOutlined } from "@ant-design/icons";
import { Button } from "antd";
import { useState } from "react";

import type { SampleInfo } from "../../api/types";
import { num } from "../../lib/format";

const mb = (b: number) => (b < 1e6 ? `${Math.max(1, Math.round(b / 1e3))} KB` : `${(b / 1e6).toFixed(b < 1e7 ? 1 : 0)} MB`);

/** Built-in datasets (synthetic news articles, 300-1,500 words), started server-side. */
export function SamplePicker({ samples, disabled, busy, onRun }: {
  samples: SampleInfo[]; disabled: boolean; busy: boolean; onRun: (file: string) => void;
}) {
  const [picked, setPicked] = useState<string>(samples[0]?.file ?? "");
  if (!samples.length) return null;
  const current = samples.find((s) => s.file === picked) ?? samples[0];
  return (
    <div className="samples">
      <div className="samples-head">
        <span className="section-title" style={{ margin: 0 }}>Or use a sample</span>
        <span className="muted small">Synthetic news in 7 languages, 300–1,500 words each, with events reported by several outlets.</span>
      </div>
      <div className="sample-cards" role="radiogroup" aria-label="Sample dataset">
        {samples.map((s) => (
          <button key={s.file} type="button" role="radio" aria-checked={s.file === current.file}
                  className={`sample-card${s.file === current.file ? " is-on" : ""}`}
                  disabled={disabled || busy} onClick={() => setPicked(s.file)}>
            <span className="sample-rows">{s.rows != null ? num(s.rows) : s.file}</span>
            <span className="muted small">{s.rows != null ? "articles" : ""} · {mb(s.bytes)}</span>
          </button>
        ))}
      </div>
      <Button type="primary" icon={<PlayCircleOutlined />} disabled={disabled} loading={busy}
              onClick={() => onRun(current.file)}>
        Run on {current.rows != null ? `${num(current.rows)} articles` : current.file}
      </Button>
    </div>
  );
}
