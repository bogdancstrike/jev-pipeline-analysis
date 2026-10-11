import { RootProvider } from 'fumadocs-ui/provider/base';
import { CodeBlock, Pre } from 'fumadocs-ui/components/codeblock';
import { Callout } from 'fumadocs-ui/components/callout';
import { Tab, Tabs } from 'fumadocs-ui/components/tabs';
import type { ModuleInfo } from '../api/types';
import { PageHeader } from '../components/ui/PageHeader';
import './docs.css';

const SECTIONS = [['quickstart', 'Quickstart'], ['tasks', 'Choosing tasks'], ['inputs', 'Input formats'], ['results', 'Status & results'], ['operations', 'Cancel & delete'], ['errors', 'Errors & limits']];
const CURL = `curl --fail-with-body http://localhost:8088/api/jobs/text \\
  -H 'Content-Type: application/json' \\
  -d '{"texts":["A report about Bucharest."],"modules":["language","category","ner"]}'`;
const PYTHON = `import time
import requests

base = "http://localhost:8088/api"
response = requests.post(f"{base}/jobs/text", json={
    "texts": ["A report about Bucharest."],
    "modules": ["language", "category", "ner"],
}, timeout=30)
response.raise_for_status()
job = response.json()
while job["status"] not in {"done", "failed", "cancelled"}:
    time.sleep(2)
    response = requests.get(f"{base}/jobs/{job['id']}", timeout=30)
    response.raise_for_status()
    job = response.json()

# A completed job can contain task failures. Inspect both fields.
print(job["status"], job["failed_rows"], job["progress"])
response = requests.get(f"{base}/jobs/{job['id']}/result.csv", timeout=60)
response.raise_for_status()
with open("results.csv", "wb") as output:
    output.write(response.content)`;
function Code({ title, children }: { title: string; children: string }) { return <CodeBlock title={title}><Pre><code>{children}</code></Pre></CodeBlock>; }

export default function DocsPage({ modules }: { modules: ModuleInfo[] }) {
  return <RootProvider theme={{ enabled: false }} search={{ enabled: false }}><div className="api-docs">
    <PageHeader title="Pipeline API" description="Submit documents, choose analyses and retrieve structured results."
      actions={<a href="/api/docs" target="_blank" rel="noreferrer">Interactive API reference ↗</a>} />
    <div className="docs-layout"><article className="docs-content">
      <section id="quickstart"><h3>Quickstart</h3><p>The local API base URL is <code>http://localhost:8088/api</code>. Submission is asynchronous: a successful request returns HTTP 202 and a job snapshot containing its <code>id</code>. Poll that job to completion before downloading the CSV.</p>
        <Tabs items={['curl', 'Python']}><Tab><Code title="Create an analysis">{CURL}</Code></Tab><Tab><Code title="Submit, poll and download · pip install requests">{PYTHON}</Code></Tab></Tabs>
        <Callout title="Task settings come from Admin">The request selects tasks by name. Model engines, prompts, labels and thresholds use the effective server configuration when the job starts. Changing Admin settings affects new jobs.</Callout>
      </section>
      <section id="tasks"><h3>Choosing tasks</h3><p>Use the exact task <code>name</code>, not its display title. JSON requests accept <code>"modules": ["ner", "relations"]</code>; CSV uploads use a comma-separated form field. An omitted or empty list selects the server defaults. Dependencies are included automatically: Relations also runs Entities and Resolved entities.</p>
        <Code title="Discover enabled tasks, labels, dependencies and defaults">{'curl --fail-with-body http://localhost:8088/api/config'}</Code>
        <div className="docs-table-scroll"><table><thead><tr><th>Task name</th><th>Output</th><th>Requires</th></tr></thead><tbody>{modules.map((m) => <tr key={m.name}><td><code>{m.name}</code><br />{m.title}</td><td>{m.description}</td><td>{m.requires.join(', ') || '—'}</td></tr>)}</tbody></table></div>
        {!modules.length && <p>Task discovery is temporarily unavailable. Check <a href="/api/config">/api/config</a> when the backend is ready.</p>}
        <p>For a small, fast extraction run, select <code>["language", "ner", "entity_resolution"]</code>. Add <code>relations</code> and <code>fields</code> when you need their additional extraction work. Throughput depends on document length, selected tasks, model settings and GPU load.</p>
        <p>The additional tasks are <code>ioc</code>, <code>genre</code>, <code>emotion</code>, <code>extremism</code> and <code>temporal</code>. They are selectable but excluded from the default task list; include their names explicitly to run them. All non-none extremist narrative results require analyst review.</p>
        <Callout title="Identifiers and cyber indicators">Entities also extracts emails, validated phone numbers, Romanian CNPs, IBANs, labelled personal IDs and general numbers. Checksum or syntax validation does not establish identity or ownership. Cyber indicators returns the original span and a normalized value for defanged URLs, domains, IP addresses and hashes; a match does not imply maliciousness.</Callout>
        <h4>IPTC Media Topics</h4><p>Select <code>["iptc"]</code> to classify a document using the official IPTC subject names and definitions. The offline vocabulary pins version 2026-07-09: 1,085 active topics under 17 main subjects. Classification proceeds through the hierarchy and stops when a finer topic is unsupported or uncertain. Admin controls depth and confidence thresholds; each additional level adds model work.</p><p>Results include the <code>medtop:</code> ID, readable name, definition, confidence and scored subject path. A parent-ID filter also matches its descendants. Browse the full standard in Admin's IPTC taxonomy tab or retrieve it from <code>GET /api/modules/iptc/reference</code>.</p><Code title="IPTC request">{'{"texts":["Parliament approved the new law."],"modules":["iptc"]}'}</Code><p>Vocabulary: <a href="https://www.iptc.org/std/NewsCodes/treeview/mediatopic/mediatopic-en-US.html">IPTC Media Topics</a>, © 2026 IPTC, used under <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>. Retired concepts are excluded; active descendants are attached to their nearest active ancestor.</p>
      </section>
      <section id="inputs"><h3>Input formats</h3><h4>Pasted text / JSON</h4><p><code>POST /api/jobs/text</code> accepts a <code>texts</code> array, one document per item, and an optional <code>modules</code> array. Blank documents are removed. IDs are assigned starting at 1.</p><Code title="JSON request">{'{"texts":["First document", "Second document"],"modules":["language","category"]}'}</Code>
        <h4>CSV upload</h4><p>Upload UTF-8 CSV with a <code>text</code> column. An <code>id</code> column is required; other original columns are retained in the exported CSV. Quote fields containing commas or line breaks.</p><Code title="articles.csv">{'id,text\na1,"A report about Bucharest."\na2,"Another report, with a comma."'}</Code><Code title="Multipart request">{'curl --fail-with-body http://localhost:8088/api/jobs \\\n  -F "file=@articles.csv" \\\n  -F "modules=language,category,ner"'}</Code>
        <h4>Built-in samples</h4><p>Discover filenames in <code>GET /api/config</code>, then submit the sample by name.</p><Code title="Sample request">{'curl --fail-with-body http://localhost:8088/api/jobs/sample \\\n  -H "Content-Type: application/json" \\\n  -d \'{"sample":"sample-50.csv","modules":["language","category"]}\''}</Code>
        <h4>Temporal reference dates</h4><p>Temporal normalization parses supported English/Romanian date expressions locally. Relative expressions such as “yesterday” require a CSV column named <code>published_at</code>, <code>publication_date</code> or <code>date</code>, or an explicit <code>reference_date</code> in Admin. The Admin value takes precedence. Without a reference, relative expressions remain <code>missing_reference</code>; absolute dates can still normalize. This task never uses the processing date or a Qwen fallback.</p><Code title="CSV with a publication date">{'id,text,published_at\na1,"The incident happened yesterday.",2026-10-11'}</Code>
      </section>
      <section id="results"><h3>Status & results</h3><Code title="Replace JOB_ID with the returned id">{'curl --fail-with-body http://localhost:8088/api/jobs/JOB_ID\ncurl --fail-with-body http://localhost:8088/api/jobs/JOB_ID/rows?offset=0\\&limit=50\ncurl --fail-with-body http://localhost:8088/api/jobs/JOB_ID/rows/0\ncurl --fail-with-body http://localhost:8088/api/jobs/JOB_ID/summary\ncurl --fail-with-body http://localhost:8088/api/jobs/JOB_ID/metrics\ncurl --fail-with-body -o results.csv http://localhost:8088/api/jobs/JOB_ID/result.csv'}</Code>
        <p>Status is <code>queued</code>, <code>running</code>, <code>done</code>, <code>failed</code> or <code>cancelled</code>. A <code>done</code> run may still contain failed task results: inspect <code>failed_rows</code>, per-task <code>progress</code> errors and each row’s <code>errors</code> object. Low-confidence outputs appear in <code>review</code>.</p>
        <p>Row indices are zero-based. Paginated rows include compact results; <code>/rows/0</code> includes full text and detailed spans. Span offsets are start-inclusive/end-exclusive positions in the processed text. Filter rows with repeated <code>f=module:value</code>, <code>review=true</code>, <code>errors=true</code> or a text search <code>q</code>.</p><Code title="Filter example">{'curl --fail-with-body --get http://localhost:8088/api/jobs/JOB_ID/rows \\\n  --data-urlencode "f=category:technology" --data-urlencode "review=true"'}</Code>
        <p>For server-sent progress updates, connect to <code>GET /api/jobs/JOB_ID/events</code>. Each <code>data:</code> event is a job snapshot; close your connection after a terminal status.</p>
        <Callout type="warning" title="Download results before a restart">Full jobs and document results live in backend memory and expire after the configured retention period (default six hours after completion). A backend restart removes them. PostgreSQL retains run statistics and Admin settings, not full document results.</Callout>
      </section>
      <section id="operations"><h3>Cancel & delete</h3><p>Cancel stops processing and keeps available partial results. Deleting removes the job, its results and saved run history; its statistics disappear from the dashboard.</p><Code title="Cancel one job">{'curl --fail-with-body -X POST http://localhost:8088/api/jobs/JOB_ID/cancel'}</Code><Code title="Delete selected runs · HTTP 204 on success">{'curl --fail-with-body http://localhost:8088/api/runs/delete \\\n  -H "Content-Type: application/json" \\\n  -d \'{"ids":["JOB_ID","ANOTHER_JOB_ID"]}\''}</Code><p>Bulk deletion accepts 1–1,000 IDs. Missing or already deleted IDs are harmless. Active jobs are stopped before their history is removed. <code>DELETE /api/jobs/JOB_ID</code> deletes one available job and its history.</p>
      </section>
      <section id="errors"><h3>Errors & limits</h3><p>Check <code>GET /api/health</code> before submitting. Loading engines produce HTTP 503; honour <code>Retry-After</code>. Request errors use a structured JSON body with <code>error</code>, <code>message</code> and <code>details</code>. The response’s <code>x-request-id</code> helps correlate logs.</p>
        <div className="docs-table-scroll"><table><thead><tr><th>Status</th><th>Meaning</th></tr></thead><tbody><tr><td>404</td><td>Unknown/expired job, sample or row.</td></tr><tr><td>409</td><td>CSV requested while a job is still running.</td></tr><tr><td>413</td><td>Upload exceeds the configured size limit.</td></tr><tr><td>422</td><td>Invalid tasks, CSV, filters or request shape. Framework validation may return a detail array.</td></tr><tr><td>503</td><td>Required model is loading or unavailable.</td></tr></tbody></table></div>
        <p>JSON input accepts up to 1,000 documents per request. Row pagination accepts up to 500 results per page. CSV row/upload limits are published in <code>/api/config</code>. The default processed-text limit is 60,000 characters per document: pasted text above it is rejected, while CSV documents are processed up to that limit.</p>
        <p>This local deployment’s pipeline API does not require an API key. Model-service keys stay inside the backend; clients should call the pipeline rather than model containers.</p><p><a href="/api/openapi.json">OpenAPI schema</a> · <a href="/api/docs">Interactive endpoint reference</a> · Built with <a href="https://www.fumadocs.dev/docs/ui/components/codeblock">Fumadocs</a>.</p>
      </section>
    </article><nav className="docs-nav" aria-label="On this page"><strong>On this page</strong>{SECTIONS.map(([id, title]) => <a key={id} href={`#${id}`}>{title}</a>)}</nav></div>
  </div></RootProvider>;
}
