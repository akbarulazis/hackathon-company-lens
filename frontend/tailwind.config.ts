import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#111111",
        "ink-muted": "#626260",
        "ink-subtle": "#7b7b78",
        canvas: "#f5f1ec",
        "surface-1": "#ffffff",
        "surface-2": "#ebe7e1",
        hairline: "#d3cec6",
        "fin-orange": "#ff5600",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [require("@tailwindcss/typography"), require("daisyui")],
  daisyui: {
    themes: [
      {
        companylens: {
          primary: "#111111",
          "primary-content": "#ffffff",
          secondary: "#626260",
          "secondary-content": "#ffffff",
          accent: "#ff5600",
          "accent-content": "#ffffff",
          neutral: "#111111",
          "neutral-content": "#ffffff",
          "base-100": "#ffffff",
          "base-200": "#f5f1ec",
          "base-300": "#ebe7e1",
          "base-content": "#111111",
          info: "#3abff8",
          success: "#16a34a",
          warning: "#fbbd23",
          error: "#b91c1c",
        },
      },
    ],
  },
};

export default config;
