import { readdir, rm } from "node:fs/promises";
import { resolve } from "node:path";

const projectRoot = resolve(import.meta.dirname, "..");
const distDir = resolve(projectRoot, "web", "dist");
const expectedDistDir = resolve(projectRoot, "web", "dist");

if (distDir !== expectedDistDir) {
  throw new Error(`Refusing to clean unexpected directory: ${distDir}`);
}

for (const entry of await readdir(distDir, { withFileTypes: true })) {
  await rm(resolve(distDir, entry.name), { recursive: true, force: true });
}
