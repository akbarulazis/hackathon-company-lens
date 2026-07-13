"use client";

import {
  BarChart as RechartsBarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

export interface ScoreBarData {
  dimension: string;
  score: number;
}

interface BarChartProps {
  data: ScoreBarData[];
  /** Bar color — if not provided, uses the score color banding */
  barColor?: string;
  /** Whether to use score-based color banding for each bar */
  useColorBanding?: boolean;
}

/** Returns the appropriate color for a score based on color banding rules */
function getScoreColor(score: number): string {
  if (score <= 1) return "#f87272"; // red
  if (score <= 2) return "#fbbd23"; // orange
  if (score <= 3) return "#f7c948"; // yellow
  if (score <= 4) return "#2dd4bf"; // teal
  return "#36d399"; // green
}

/**
 * Reusable bar chart component for displaying a single company's
 * five score dimensions on axes scaled from 1.0 to 5.0.
 */
export default function BarChart({
  data,
  barColor = "#36d399",
  useColorBanding = true,
}: BarChartProps) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <RechartsBarChart
        data={data}
        margin={{ top: 10, right: 30, left: 0, bottom: 5 }}
      >
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="dimension" tick={{ fontSize: 11 }} />
        <YAxis domain={[1, 5]} tickCount={5} />
        <Tooltip formatter={(value: number) => [value.toFixed(2), "Score"]} />
        <Bar dataKey="score" radius={[4, 4, 0, 0]}>
          {data.map((entry, index) => (
            <Cell
              key={`cell-${index}`}
              fill={useColorBanding ? getScoreColor(entry.score) : barColor}
            />
          ))}
        </Bar>
      </RechartsBarChart>
    </ResponsiveContainer>
  );
}
