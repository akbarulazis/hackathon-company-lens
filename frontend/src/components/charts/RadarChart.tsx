"use client";

import {
  Radar,
  RadarChart as RechartsRadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

export interface ScoreDimension {
  dimension: string;
  score: number;
  fullMark: number;
}

interface RadarChartProps {
  data: ScoreDimension[];
  /** Fill color for the radar polygon */
  fillColor?: string;
  /** Stroke color for the radar polygon */
  strokeColor?: string;
}

/**
 * Reusable radar chart component for displaying a single company's
 * five score dimensions on axes scaled from 1.0 to 5.0.
 */
export default function RadarChart({
  data,
  fillColor = "#36d399",
  strokeColor = "#36d399",
}: RadarChartProps) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <RechartsRadarChart cx="50%" cy="50%" outerRadius="80%" data={data}>
        <PolarGrid />
        <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 12 }} />
        <PolarRadiusAxis
          angle={90}
          domain={[1, 5]}
          tickCount={5}
          tick={{ fontSize: 10 }}
        />
        <Tooltip
          formatter={(value: number) => [value.toFixed(2), "Score"]}
        />
        <Radar
          name="Score"
          dataKey="score"
          stroke={strokeColor}
          fill={fillColor}
          fillOpacity={0.3}
        />
      </RechartsRadarChart>
    </ResponsiveContainer>
  );
}
