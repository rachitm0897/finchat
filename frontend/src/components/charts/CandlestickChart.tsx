import {
  ResponsiveContainer,
  ComposedChart,
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

export default function CandlestickChart({ data }: Props) {
  const formatted = data.map((row) => ({
    ...row,
    high: row.high ?? row.close ?? null,
    low: row.low ?? row.close ?? null,
    close: row.close ?? null,
    short_ma: row.short_ma ?? null,
    long_ma: row.long_ma ?? null,
  }));

  return (
    <div style={{ width: "100%", height: 340 }}>
      <ResponsiveContainer>
        <ComposedChart data={formatted}>
          <CartesianGrid stroke="#1c2632" strokeDasharray="2 2" />
          <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#8fa2b7" }} minTickGap={24} />
          <YAxis tick={{ fontSize: 11, fill: "#8fa2b7" }} domain={["dataMin", "dataMax"]} />
          <Tooltip
            contentStyle={{
              background: "#0a1118",
              border: "1px solid #233140",
              borderRadius: 8,
              color: "#d8e4ef",
            }}
          />
          <Legend />
          <Line type="monotone" dataKey="high" stroke="#3b4a5f" dot={false} strokeWidth={1} />
          <Line type="monotone" dataKey="low" stroke="#3b4a5f" dot={false} strokeWidth={1} />
          <Line type="monotone" dataKey="close" stroke="#d8e4ef" dot={false} strokeWidth={2} />
          <Line type="monotone" dataKey="short_ma" stroke="#67b7ff" dot={false} strokeWidth={1.5} />
          <Line type="monotone" dataKey="long_ma" stroke="#f2b84b" dot={false} strokeWidth={1.5} />
          <Brush dataKey="date" height={18} stroke="#41576d" travellerWidth={10} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}