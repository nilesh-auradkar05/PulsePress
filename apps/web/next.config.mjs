import path from "node:path";

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Produce a self-contained server bundle for the Docker image.
  output: "standalone",
  // Scope file tracing to this app (the repo root has unrelated lockfiles).
  outputFileTracingRoot: path.join(import.meta.dirname),
};

export default nextConfig;
