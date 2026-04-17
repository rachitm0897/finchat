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
    <div style={{ width: "100%", height: 320 }}>
      <ResponsiveContainer>
        <LineChart data={data}>
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
          <Legend />
          <Line type="monotone" dataKey="equity" stroke="#3dd9a4" strokeWidth={2.2} dot={false} />
          <Line type="monotone" dataKey="close" stroke="#8fa2b7" strokeWidth={1.2} dot={false} />
          <Brush dataKey="date" height={18} stroke="#41576d" travellerWidth={10} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}