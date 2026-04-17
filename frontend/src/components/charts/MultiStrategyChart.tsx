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
  datasets: { name: string; data: any[] }[];
};

export default function MultiStrategyChart({ datasets }: Props) {
  if (!datasets.length) return null;

  const merged = datasets[0].data.map((row, idx) => {
    const point: Record<string, string | number | null> = { date: row.date };
    datasets.forEach((dataset) => {
      point[dataset.name] = dataset.data[idx]?.equity ?? null;
    });
    return point;
  });

  const colors = ["#67b7ff", "#3dd9a4", "#f2b84b", "#ff6b7a", "#9c7cff", "#7ee0ff"];

  return (
    <div style={{ width: "100%", height: 340 }}>
      <ResponsiveContainer>
        <LineChart data={merged}>
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
          {datasets.map((dataset, idx) => (
            <Line
              key={dataset.name}
              type="monotone"
              dataKey={dataset.name}
              stroke={colors[idx % colors.length]}
              strokeWidth={2}
              dot={false}
            />
          ))}
          <Brush dataKey="date" height={18} stroke="#41576d" travellerWidth={10} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}