import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Brush,
} from "recharts";

type Props = {
  data: any[];
};

export default function DrawdownChart({ data }: Props) {
  return (
    <div style={{ width: "100%", height: 260 }}>
      <ResponsiveContainer>
        <LineChart data={data}>
          <CartesianGrid stroke="#1f2937" strokeDasharray="3 3" />
          <XAxis dataKey="date" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          <Line type="monotone" dataKey="drawdown_pct" stroke="#ef4444" strokeWidth={2} dot={false} />
          <Brush dataKey="date" height={20} stroke="#64748b" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}