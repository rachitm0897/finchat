import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
  Brush,
} from "recharts";

type Props = {
  data: any[];
};

export default function EquityChart({ data }: Props) {
  return (
    <div style={{ width: "100%", height: 300 }}>
      <ResponsiveContainer>
        <LineChart data={data}>
          <CartesianGrid stroke="#1f2937" strokeDasharray="3 3" />
          <XAxis dataKey="date" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          <Legend />
          <Line type="monotone" dataKey="equity" stroke="#3b82f6" strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="close" stroke="#9ca3af" strokeWidth={1} dot={false} />
          <Brush dataKey="date" height={20} stroke="#64748b" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}