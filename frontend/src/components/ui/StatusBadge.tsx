type Props = {
  label: string;
  tone?: "success" | "danger" | "neutral";
};

export function StatusBadge({ label, tone = "neutral" }: Props) {
  return <span className={`status-badge ${tone}`}>{label}</span>;
}
