import { CheckCircleFilled, ClockCircleOutlined, CloseCircleFilled, LoadingOutlined, StopOutlined } from "@ant-design/icons";
import { Tag } from "antd";

import type { JobStatus } from "../../api/types";

const LOOK: Record<JobStatus, { color: string; text: string; icon: React.ReactNode }> = {
  queued: { color: "default", text: "Queued", icon: <ClockCircleOutlined /> },
  running: { color: "processing", text: "Running", icon: <LoadingOutlined /> },
  done: { color: "success", text: "Done", icon: <CheckCircleFilled /> },
  failed: { color: "error", text: "Failed", icon: <CloseCircleFilled /> },
  cancelled: { color: "warning", text: "Cancelled", icon: <StopOutlined /> },
};

export function StatusTag({ status }: { status: JobStatus }) {
  const l = LOOK[status];
  return <Tag color={l.color} icon={l.icon} variant="filled" style={{ marginInlineEnd: 0 }}>{l.text}</Tag>;
}
