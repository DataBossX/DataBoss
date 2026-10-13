import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const source = await readFile(new URL('../src/serviceStatusPresentation.js', import.meta.url), 'utf8').catch(() => '');
const module = source ? await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`) : {};

test('configured credentials are unverified rather than online', () => {
  assert.equal(typeof module.serviceStatusPresentation, 'function', 'missing status presentation');
  const view = module.serviceStatusPresentation('configured_unverified');
  assert.equal(view.label, 'CONFIGURED · UNVERIFIED');
  assert.equal(view.dotClass.includes('green'), false);
});
test('paused configuration has its own label', () => {
  assert.equal(module.serviceStatusPresentation?.('paused').label, 'PAUSED');
});
test('missing credentials have a configuration label', () => {
  assert.equal(module.serviceStatusPresentation?.('unavailable').label, 'NOT CONFIGURED');
});
test('missing and unknown observations remain unknown', () => {
  assert.equal(module.serviceStatusPresentation?.().label, 'UNKNOWN');
  assert.equal(module.serviceStatusPresentation?.('new_unknown_status').label, 'UNKNOWN');
});
test('legacy boolean callers keep their existing labels', () => {
  assert.equal(module.serviceStatusPresentation?.(undefined, true).label, 'ONLINE');
  assert.equal(module.serviceStatusPresentation?.(undefined, false).label, 'OFFLINE');
});
test('inherited object names remain unknown', () => {
  for (const status of ['constructor', 'toString', '__proto__', 'hasOwnProperty']) {
    assert.equal(module.serviceStatusPresentation(status).label, 'UNKNOWN');
  }
});
