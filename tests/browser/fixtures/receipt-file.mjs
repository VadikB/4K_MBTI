// One persistence path for the browser harness and the no-LLM export regression.
import fs from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

export function persistReceipt(file, value) {
  const bytes = JSON.stringify(value, null, 2) + '\n';
  const fd = fs.openSync(file, 'w', 0o600);
  try {
    fs.writeFileSync(fd, bytes);
    fs.fsyncSync(fd);
  } finally {
    fs.closeSync(fd);
  }
  const readback = fs.readFileSync(file, 'utf8');
  if (readback !== bytes) throw new Error('RECEIPT_PERSISTENCE_READBACK_MISMATCH');
  return createHash('sha256').update(readback).digest('hex');
}

export function isTerminalPreparationReceipt(receipt) {
  return ['completed', 'failed'].includes(receipt?.preparation_operation?.status);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const value = JSON.parse(fs.readFileSync(0, 'utf8'));
  const digest = persistReceipt(process.argv[2], value);
  process.stdout.write(JSON.stringify({ sha256: digest }) + '\n');
}
