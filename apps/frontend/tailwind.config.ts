import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Role palette used by the graph view and legend. Pinning the
        // colours here keeps the legend/graph in sync (single source).
        role: {
          PASIVO: "#3b82f6",
          ACTIVO: "#ef4444",
          REPRESENTADO: "#f59e0b",
          FINANCIADOR: "#8b5cf6",
          DONANTE: "#10b981",
        },
        // Node-type palette: persons, organisations, events. Picked to
        // contrast on a dark canvas.
        node: {
          person: "#60a5fa",
          organisation: "#fbbf24",
          event: "#94a3b8",
        },
      },
    },
  },
  plugins: [],
};

export default config;
