// Smoke test: verify hyparquet + compressors can read our zstd-compressed parquet files.
// Run: node site/smoke.mjs
import { parquetReadObjects } from 'hyparquet';
import { compressors } from 'hyparquet-compressors';
import { readFile } from 'node:fs/promises';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '..');

const cases = [
  'data/series/copper/latest.parquet',
  'data/series/copper/2025.parquet',
  'data/series/tin/latest.parquet',
  'data/series/antimony/latest.parquet',
  'data/exchange.parquet',
  'data/raw/2026.parquet',
  'data/news/2026.parquet',
];

let passed = 0, failed = 0;
for (const rel of cases) {
  try {
    const buf = await readFile(resolve(ROOT, rel));
    const rows = await parquetReadObjects({ file: buf.buffer, compressors });
    if (!Array.isArray(rows) || rows.length === 0) throw new Error('empty rows');
    const first = rows[0];
    if (first.date == null) throw new Error(`first row missing 'date': ${JSON.stringify(first).slice(0, 100)}`);
    console.log(`✓ ${rel} — ${rows.length} rows, sample: ${first.date}`);
    passed++;
  } catch (e) {
    console.error(`✗ ${rel} — ${e.message}`);
    failed++;
  }
}

// Verify metal series shape
try {
  const buf = await readFile(resolve(ROOT, 'data/series/copper/latest.parquet'));
  const rows = await parquetReadObjects({ file: buf.buffer, compressors });
  const r = rows[0];
  const required = ['date', 'lme_3m_close', 'lme_3m_change', 'inv_current', 'shfe_premium_usd', 'krw_rate'];
  const missing = required.filter(k => !(k in r));
  if (missing.length) throw new Error(`missing fields: ${missing.join(', ')}`);
  console.log(`✓ schema check — copper latest has all required fields`);
  passed++;
} catch (e) {
  console.error(`✗ schema check — ${e.message}`);
  failed++;
}

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed > 0 ? 1 : 0);
