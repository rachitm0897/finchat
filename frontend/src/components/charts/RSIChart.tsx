import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
  Brush,
} from "recharts";

type Props = {
  data: any[];
};

export default function RSIChart({ data }: Props) {
  return (
    <div style={{ width: "100%", height: 220 }}>
      <ResponsiveContainer>
        <LineChart data={data}>
          <CartesianGrid stroke="#1f2937" strokeDasharray="3 3" />
          <XAxis dataKey="date" tick={{ fontSize: 11 }} />
          <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
          <Tooltip />
          <ReferenceLine y={30} stroke="#10b981" strokeDasharray="4 4" />
          <ReferenceLine y={70} stroke="#ef4444" strokeDasharray="4 4" />
          <Line type="monotone" dataKey="rsi" stroke="#f59e0b" strokeWidth={2} dot={false} />
          <Brush dataKey="date" height={20} stroke="#64748b" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}