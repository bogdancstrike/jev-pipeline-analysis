import { InboxOutlined } from "@ant-design/icons";
import type { ReactNode } from "react";

/** "Nothing here yet" and "nothing matched" are different states; the caller says which. */
export function EmptyState({ title, hint, icon, action }: {
  title: ReactNode; hint?: ReactNode; icon?: ReactNode; action?: ReactNode;
}) {
  return (
    <div className="empty" role="status">
      <div className="empty-icon">{icon ?? <InboxOutlined />}</div>
      <div className="empty-title">{title}</div>
      {hint && <div className="empty-hint">{hint}</div>}
      {action && <div className="empty-action">{action}</div>}
    </div>
  );
}
