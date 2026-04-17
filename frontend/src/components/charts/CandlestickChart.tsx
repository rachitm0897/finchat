import {
  ResponsiveContainer,
  ComposedChart,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Bar,
  Brush,
} from "recharts";

type Props = {
  data: any[];
};

export default function CandlestickChart({ data }: Props) {
  const formatted = data.map((row) => {
    const open = row.open ?? row.close;
    const close = row.close ?? row.open;
    const high = row.high ?? Math.max(open, close);
    const low = row.low ?? Math.min(open, close);
    return {
      ...row,
      wick: high - low,
      body: Math.abs(close - open),
      base: Math.min(open, close),
    };
  });

  return (
    <div style={{ width: "100%", height: 320 }}>
      <ResponsiveContainer>
        <ComposedChart data={formatted}>
          <CartesianGrid stroke="#1f2937" strokeDasharray="3 3" />
          <XAxis dataKey="date" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          <Bar dataKey="wick" stackId="a" fill="#64748b" />
          <Bar dataKey="body" stackId="a" fill="#22c55e" />
          <Brush dataKey="date" height={20} stroke="#64748b" />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}