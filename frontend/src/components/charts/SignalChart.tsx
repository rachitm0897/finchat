import {
  ResponsiveContainer,
  ComposedChart,
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
    <div style={{ width: "100%", height: 320 }}>
      <ResponsiveContainer>
        <ComposedChart data={data}>
          <CartesianGrid stroke="#1c2632" strokeDasharray="2 2" />
          <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#8fa2b7" }} minTickGap={24} />
          <YAxis tick={{ fontSize: 11, fill: "#8fa2b7" }} />
          <Tooltip
            contentStyle={{
              background: "#0a1118",
              border: "1px solid #233140",
              borderRadius: 8,
              color: "#d8e4ef",
            }}
          />
          <Line type="monotone" dataKey="close" stroke="#d8e4ef" strokeWidth={1.8} dot={false} />
          <Scatter data={buySignals} dataKey="markerY" fill="#3dd9a4" />
          <Scatter data={sellSignals} dataKey="markerY" fill="#ff6b7a" />
          <Brush dataKey="date" height={18} stroke="#41576d" travellerWidth={10} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}