import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Scatter,
  Brush,
} from "recharts";

type Props = {
  data: any[];
};

export default function SignalChart({ data }: Props) {
  const buySignals = data
    .filter((d) => d.event === "BUY")
    .map((d) => ({ ...d, markerY: d.close }));

  const sellSignals = data
    .filter((d) => d.event === "SELL")
    .map((d) => ({ ...d, markerY: d.close }));

  return (
    <div style={{ width: "100%", height: 300 }}>
      <ResponsiveContainer>
        <LineChart data={data}>
          <CartesianGrid stroke="#1f2937" strokeDasharray="3 3" />
          <XAxis dataKey="date" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          <Line type="monotone" dataKey="close" stroke="#60a5fa" strokeWidth={2} dot={false} />
          <Scatter data={buySignals} dataKey="markerY" fill="#22c55e" />
          <Scatter data={sellSignals} dataKey="markerY" fill="#ef4444" />
          <Brush dataKey="date" height={20} stroke="#64748b" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}