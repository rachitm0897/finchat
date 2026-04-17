import type { ReactNode } from "react";

type Props = {
  title: string;
  subtitle?: string;
  action?: ReactNode;
};

export function SectionHeader({ title, subtitle, action }: Props) {
  return (
    <div className="section-heading-row">
      <div>
        <h2 className="section-title">{title}</h2>
        {subtitle ? <p className="panel-description">{subtitle}</p> : null}
      </div>
      {action ? <div className="section-action">{action}</div> : null}
    </div>
  );
}
