import { defineConfig } from "@hey-api/openapi-ts";

export default defineConfig({
  input: "../../openapi.json",
  output: "src/gen",
  plugins: [
    {
      name: "@hey-api/typescript",
      enums: "javascript",
    },
  ],
});
