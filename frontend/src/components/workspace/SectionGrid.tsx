import type { ReactNode } from "react";

type Props = {
  columns?: "split" | "single";
  children: ReactNode;
};

export default function SectionGrid({ columns = "split", children }: Props) {
  return <div className={`section-grid ${columns}`}>{children}</div>;
}
