import { TableOutlined, LineChartOutlined } from "@ant-design/icons";
import { Card, Segmented, Table } from "antd";
import { useState, type ReactNode } from "react";

/** A chart with its table view one click away: the accessible and exact reading. */
export function ChartCard<T extends object>({ title, extra, chart, rows, columns, rowKey }: {
  title: ReactNode; extra?: ReactNode; chart: ReactNode;
  rows: T[]; columns: { title: string; dataIndex: keyof T & string; align?: "right" }[]; rowKey: keyof T & string;
}) {
  const [view, setView] = useState<"chart" | "table">("chart");
  return (
    <Card size="small" className="module-card" title={title} extra={
      <span className="chart-card-extra">
        {extra}
        <Segmented size="small" value={view} onChange={(v) => setView(v as "chart" | "table")} aria-label="View"
                   options={[{ value: "chart", icon: <LineChartOutlined />, title: "Chart" },
                             { value: "table", icon: <TableOutlined />, title: "Table" }]} />
      </span>}>
      {view === "chart" ? chart : (
        <Table<T> size="small" rowKey={rowKey} dataSource={rows} pagination={rows.length > 10 ? { pageSize: 10 } : false}
                  columns={columns.map((c) => ({ ...c, key: c.dataIndex }))} scroll={{ x: "max-content" }} />
      )}
    </Card>
  );
}
