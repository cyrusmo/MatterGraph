import { readFileSync, readdirSync } from "node:fs";
import { basename, join } from "node:path";
import { gzipSync } from "node:zlib";

const output = new URL("../dist/", import.meta.url);
const assets = new URL("assets/", output);
const html = readFileSync(new URL("index.html", output), "utf8");
const initialFiles = [...html.matchAll(/<script[^>]+src="\/assets\/([^"]+\.js)"/g)]
  .map((match) => match[1]);
const allFiles = readdirSync(assets).filter((filename) => filename.endsWith(".js"));

function gzipBytes(filename) {
  return gzipSync(readFileSync(join(assets.pathname, basename(filename)))).byteLength;
}

const initialBytes = initialFiles.reduce((total, filename) => total + gzipBytes(filename), 0);
const totalBytes = allFiles.reduce((total, filename) => total + gzipBytes(filename), 0);
const initialLimit = 100 * 1024;
const totalLimit = 230 * 1024;

console.log(
  `JavaScript budgets: initial ${(initialBytes / 1024).toFixed(1)} KiB / 100 KiB; ` +
  `total ${(totalBytes / 1024).toFixed(1)} KiB / 230 KiB.`,
);
if (initialBytes > initialLimit || totalBytes > totalLimit) {
  process.exitCode = 1;
}
