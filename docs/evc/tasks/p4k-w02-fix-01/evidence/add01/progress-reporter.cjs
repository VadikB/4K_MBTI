const fs = require('node:fs');
module.exports = class {
  onBegin() { this.done = 0; this.write('begin'); const owner = process.env.W02_OWNER_REGISTRY; if (fs.existsSync(owner)) fs.copyFileSync(owner, process.env.W02_RUN_RECEIPT); }
  write(value) { fs.writeFileSync(process.env.W02_PROGRESS, JSON.stringify({ progress_key: value })); }
  onTestBegin(test) { this.write(`test:${test.id}:${this.done}`); }
  onTestEnd(test, result) { this.done++; this.write(`done:${test.id}:${result.status}:${this.done}`); }
};
