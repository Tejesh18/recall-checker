import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Served from https://tejesh18.github.io/recall-checker/
export default defineConfig({
  base: "/recall-checker/",
  plugins: [react()],
});
