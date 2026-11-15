// Только внешний предохранитель; штатные guards проверяются отдельно.
import net from 'node:net';
import http from 'node:http';
import https from 'node:https';
import fs from 'node:fs';
let blocked = 0;
const deny = () => { blocked++; throw Error('AUDIT_EXTERNAL_NETWORK_GUARD'); };
net.Socket.prototype.connect = deny;
http.request = deny; http.get = deny; https.request = deny; https.get = deny;
globalThis.fetch = deny;
process.on('exit', () => {
  if (process.env.AUDIT_GUARD_FILE) {
    const value = JSON.stringify({ outgoing_calls_intercepted: blocked }) + '\n';
    fs.writeFileSync(process.env.AUDIT_GUARD_FILE, value);
    fs.writeFileSync(process.env.AUDIT_GUARD_FILE.replace(/\.json$/, '-' + process.pid + '.json'), value);
  }
});
