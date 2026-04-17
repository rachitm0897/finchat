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
    const point: any = { date: row.date };
    datasets.forEach((dataset) => {
      point[dataset.name] = dataset.data[idx]?.equity ?? null;
    });
    return point;
  });

  const colors = ["#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#a855f7"];

  return (
    <div style={{ width: "100%", height: 320 }}>
      <ResponsiveContainer>
        <LineChart data={merged}>
          <CartesianGrid stroke="#1f2937" strokeDasharray="3 3" />
          <XAxis dataKey="date" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
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
          <Brush dataKey="date" height={20} stroke="#64748b" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}