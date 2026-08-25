#!/usr/bin/env node
"use strict";

const { spawn } = require("child_process");
const path = require("path");

const script = path.join(__dirname, "..", "cli", "grokbot_usage.py");
const child = spawn("python3", [script, ...process.argv.slice(2)], {
  stdio: "inherit",
});
child.on("error", (err) => {
  console.error("grokbot-usage needs python3 on PATH (Python 3.10+).");
  console.error(err.message);
  process.exit(2);
});
child.on("exit", (code, signal) => {
  if (signal) {
    process.exit(1);
  }
  process.exit(code == null ? 1 : code);
});
