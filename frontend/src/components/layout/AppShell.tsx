import type { ReactNode } from "react";

type Props = {
  sidebar: ReactNode;
  topbar: ReactNode;
  children: ReactNode;
};

export default function AppShell({ sidebar, topbar, children }: Props) {
  return (
    <div className="app-shell">
      <aside className="app-sidebar">{sidebar}</aside>
      <div className="app-main">
        <header className="app-topbar">{topbar}</header>
        <main className="app-workspace">{children}</main>
      </div>
    </div>
  );
}
