import type { ReactNode } from "react";

type Props = {
  title: string;
  description: string;
  children: ReactNode;
};

export default function WorkspacePage({ title, description, children }: Props) {
  return (
    <section className="workspace-page">
      <div className="workspace-page-header">
        <div>
          <h2 className="workspace-page-title">{title}</h2>
          <p className="workspace-page-description">{description}</p>
        </div>
      </div>
      <div className="workspace-page-body">{children}</div>
    </section>
  );
}
