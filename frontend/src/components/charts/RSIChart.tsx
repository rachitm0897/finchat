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
    <div style={{ width: "100%", height: 240 }}>
      <ResponsiveContainer>
        <LineChart data={data}>
          <CartesianGrid stroke="#1c2632" strokeDasharray="2 2" />
          <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#8fa2b7" }} minTickGap={24} />
          <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "#8fa2b7" }} />
          <Tooltip
            contentStyle={{
              background: "#0a1118",
              border: "1px solid #233140",
              borderRadius: 8,
              color: "#d8e4ef",
            }}
          />
          <ReferenceLine y={30} stroke="#3dd9a4" strokeDasharray="4 4" />
          <ReferenceLine y={50} stroke="#3b4a5f" strokeDasharray="3 3" />
          <ReferenceLine y={70} stroke="#ff6b7a" strokeDasharray="4 4" />
          <Line type="monotone" dataKey="rsi" stroke="#9c7cff" strokeWidth={2} dot={false} />
          <Brush dataKey="date" height={18} stroke="#41576d" travellerWidth={10} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}