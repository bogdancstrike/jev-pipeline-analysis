import type { ReactNode } from "react";

/** A titled block inside a page: numbered steps on forms, plain titles elsewhere. */
export function Section({ title, step, extra, description, children, className }: {
  title: ReactNode; step?: number; extra?: ReactNode; description?: ReactNode; children: ReactNode; className?: string;
}) {
  return (
    <section className={`section${className ? ` ${className}` : ""}`}>
      <div className="section-head">
        <div className="section-head-main">
          {step !== undefined && <span className="section-step" aria-hidden>{step}</span>}
          <div>
            <h3 className="section-heading">{title}</h3>
            {description && <p className="section-description">{description}</p>}
          </div>
        </div>
        {extra && <div className="section-extra">{extra}</div>}
      </div>
      {children}
    </section>
  );
}
