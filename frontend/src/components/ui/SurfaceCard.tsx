import type { ReactNode } from "react";

type Props = {
  children: ReactNode;
  className?: string;
};

export function SurfaceCard({ children, className = "" }: Props) {
  return <section className={`surface-card ${className}`.trim()}>{children}</section>;
}
