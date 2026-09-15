// Regressao atual. As evidencias da auditoria original permanecem congeladas.
const { spawnSync } = require('node:child_process');
const path = require('node:path');
const result = spawnSync(process.execPath, [
  '--test', path.resolve(__dirname, '../../tests/dashboard_rendering.test.cjs'),
], { stdio: 'inherit' });
if (result.error) throw result.error;
process.exitCode = result.status ?? 1;
