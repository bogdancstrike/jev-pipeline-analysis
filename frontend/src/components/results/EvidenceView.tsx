import { AimOutlined, CloseOutlined, SearchOutlined } from "@ant-design/icons";
import { Button, Empty, Input, Tooltip } from "antd";
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";

interface Selection { title: string; values: string[] }
const EvidenceContext = createContext<(title: string, values: string[]) => void>(() => {});
export const useEvidence = () => useContext(EvidenceContext);

/** Merge overlapping sentence and entity matches, preserving the original text. */
export function evidenceRanges(text: string, values: string[]): [number, number][] {
  const ranges: [number, number][] = [];
  for (const value of new Set(values.map((v) => v.trim()).filter(Boolean))) {
    const sensitive = text.includes(value);
    const haystack = sensitive ? text : text.toLocaleLowerCase();
    const needle = sensitive ? value : value.toLocaleLowerCase();
    const word = /[\p{L}\p{N}_]/u;
    for (let at = haystack.indexOf(needle); at >= 0; at = haystack.indexOf(needle, at + needle.length)) {
      if (word.test(value[0]) && at > 0 && word.test(text[at - 1])) continue;
      if (word.test(value.at(-1)!) && at + value.length < text.length && word.test(text[at + value.length])) continue;
      ranges.push([at, at + value.length]);
    }
  }
  const merged: [number, number][] = [];
  for (const [start, end] of ranges.sort((a, b) => a[0] - b[0])) {
    const last = merged.at(-1);
    if (last && start <= last[1]) last[1] = Math.max(last[1], end);
    else merged.push([start, end]);
  }
  return merged;
}

export function EvidenceView({ text, children }: { text: string; children: ReactNode }) {
  const [selection, setSelection] = useState<Selection | null>(null);
  const source = useRef<HTMLDivElement>(null);
  const ranges = evidenceRanges(text, selection?.values ?? []);
  useEffect(() => {
    const container = source.current;
    const mark = container?.querySelector("mark");
    if (container && mark) container.scrollTo({ top: mark.offsetTop - 45, behavior: "smooth" });
    if (selection) container?.closest(".source-panel")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [selection]);
  const parts: ReactNode[] = [];
  let end = 0;
  for (const [start, next] of ranges) {
    parts.push(text.slice(end, start), <mark key={start} className="source-match">{text.slice(start, next)}</mark>);
    end = next;
  }
  parts.push(text.slice(end));
  return <EvidenceContext.Provider value={(title, values) => setSelection({ title, values })}>
    <div className="evidence-layout">
      <section className="source-panel" aria-label="Source text">
        <div className="source-heading"><div><AimOutlined /><strong>{selection ? selection.title : "Source text"}</strong></div>
          {selection && <Tooltip title="Clear highlight"><Button type="text" size="small" icon={<CloseOutlined />} aria-label="Clear source highlight" onClick={() => setSelection(null)} /></Tooltip>}</div>
        <p className="muted small" aria-live="polite">{selection ? ranges.length ? `${ranges.length} matching passage${ranges.length === 1 ? "" : "s"} highlighted` : "No exact passage found. This value may have been normalized or inferred." : "Select a result below to highlight its evidence in this document."}</p>
        <div ref={source} className="source-text" tabIndex={0} aria-label="Document source with selected evidence">{parts}</div>
      </section>
      {children}
    </div>
  </EvidenceContext.Provider>;
}

export function ResultSearch({ value, onChange, placeholder, count, unit = "results" }: {
  value: string; onChange: (value: string) => void; placeholder: string; count: number; unit?: string;
}) {
  return <div className="result-toolbar"><Input prefix={<SearchOutlined />} allowClear value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} aria-label={placeholder} /><span className="muted small">{count} {unit}</span></div>;
}

export function ResultEmpty({ description }: { description: string }) {
  return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={description} />;
}

export function EvidenceButton({ title, values, children }: { title: string; values: string[]; children: ReactNode }) {
  const show = useEvidence();
  return <button type="button" className="evidence-button" onClick={() => show(title, values)} title="Highlight in source text">{children}</button>;
}
