import { execSync } from "node:child_process";
import { mkdirSync, rmSync } from "node:fs";

rmSync("clients/ts", { recursive: true, force: true });
mkdirSync("clients/ts", { recursive: true });

execSync(
  [
    "pnpm exec openapi-generator-cli generate",
    "-i docs/openapi.yaml",
    "-g typescript-fetch",
    "-o clients/ts",
    "--additional-properties=supportsES6=true,withSeparateModelsAndApi=true"
  ].join(" "),
  { stdio: "inherit" }
);
