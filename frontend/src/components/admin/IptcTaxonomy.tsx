import { SearchOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { Input, Skeleton, Table, Tag } from "antd";
import { useMemo, useState } from "react";
import { request } from "../../api/client";
import { ErrorAlert } from "../common/ErrorAlert";

interface Topic { id: string; name: string; definition: string; children?: Topic[] }
interface Reference { source: string; version: string; concepts: number; license: string; license_url: string; attribution: string; tree: Topic[] }
function filterTree(nodes: Topic[], query: string): Topic[] {
  return nodes.flatMap((node) => {
    if (`${node.id} ${node.name} ${node.definition}`.toLocaleLowerCase().includes(query)) return [node];
    const children = filterTree(node.children ?? [], query);
    return children.length ? [{ ...node, children }] : [];
  });
}
function branches(nodes: Topic[]): string[] { return nodes.flatMap((node) => node.children?.length ? [node.id, ...branches(node.children)] : []); }
export function IptcTaxonomy() {
  const reference = useQuery({ queryKey: ["module-reference", "iptc"], queryFn: ({ signal }) => request<Reference>("/modules/iptc/reference", { signal }), staleTime: Infinity });
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<readonly React.Key[]>([]);
  const tree = useMemo(() => reference.data ? search.trim() ? filterTree(reference.data.tree, search.toLocaleLowerCase().trim()) : reference.data.tree : [], [reference.data, search]);
  if (reference.error) return <ErrorAlert error={reference.error} onRetry={() => reference.refetch()} />;
  if (!reference.data) return <Skeleton active />;
  const ref = reference.data;
  return <div className="result-section"><div className="result-intro"><h3>Official Media Topics</h3><p>{ref.concepts.toLocaleString()} active topics · 17 main subjects · version {ref.version}. Expand a subject to browse its children. The model uses these names and definitions.</p></div>
    <Input prefix={<SearchOutlined />} allowClear aria-label="Search IPTC taxonomy" placeholder="Search topics, definitions or medtop IDs" value={search} onChange={(event) => setSearch(event.target.value)} />
    <Table<Topic> className="result-table" size="small" rowKey="id" dataSource={tree} pagination={false} scroll={{ x: 800 }} columns={[
      { title: "Subject", dataIndex: "name", width: 280 },
      { title: "IPTC ID", dataIndex: "id", width: 165, render: (id: string) => <Tag className="mono">{id}</Tag> },
      { title: "Definition", dataIndex: "definition" },
    ]} expandable={{ expandedRowKeys: search.trim() ? branches(tree) : expanded, onExpandedRowsChange: setExpanded, indentSize: 14 }} />
    <p className="muted small">{ref.attribution} · <a href={ref.license_url} target="_blank" rel="noreferrer">{ref.license}</a> · <a href={ref.source} target="_blank" rel="noreferrer">Official IPTC vocabulary ↗</a>. The pinned standard is read-only; configure classification depth and thresholds in Settings.</p>
  </div>;
}
