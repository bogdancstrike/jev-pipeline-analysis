import type { ReactNode } from "react";

/** Every page opens the same way: what this is, one line on why it matters, its actions. */
export function PageHeader({ title, description, meta, actions, back }: {
  title: ReactNode; description?: ReactNode; meta?: ReactNode; actions?: ReactNode; back?: ReactNode;
}) {
  return (
    <div className="page-header">
      <div className="page-header-main">
        {back}
        <h2 className="page-title">{title}</h2>
        {description && <p className="page-description">{description}</p>}
        {meta && <div className="page-meta">{meta}</div>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  );
}
