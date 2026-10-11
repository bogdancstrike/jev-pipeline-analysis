export interface Segment<S> { text: string; span?: S }

/**
 * Cut `text` into plain and marked segments. Spans are applied in start order; a span
 * overlapping an earlier one is dropped (NER output is flat, this is a safety net).
 */
export function segments<S extends { start: number; end: number }>(text: string, spans: S[]): Segment<S>[] {
  const out: Segment<S>[] = [];
  let pos = 0;
  for (const s of [...spans].sort((a, b) => a.start - b.start || b.end - a.end)) {
    if (s.start < pos || s.end <= s.start || s.end > text.length) continue;
    if (s.start > pos) out.push({ text: text.slice(pos, s.start) });
    out.push({ text: text.slice(s.start, s.end), span: s });
    pos = s.end;
  }
  if (pos < text.length) out.push({ text: text.slice(pos) });
  return out;
}
