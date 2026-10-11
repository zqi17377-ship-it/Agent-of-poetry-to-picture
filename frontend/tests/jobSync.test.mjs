import test from 'node:test';
import assert from 'node:assert/strict';
import {readJobSnapshot} from '../src/jobSync.ts';

test('a generation that already completed still loads its new versions', async () => {
  const calls = [];
  const artwork = {id: 'a', versions: [{id: 'new'}]};
  const result = await readJobSnapshot('j', async path => {
    calls.push(path);
    return path.startsWith('/jobs/') ? {id: 'j', artwork_id: 'a', status: 'succeeded'} : artwork;
  });
  assert.deepEqual(calls, ['/jobs/j', '/artworks/a']);
  assert.equal(result.artwork, artwork);
});

test('a transient completed-artwork fetch failure can be retried as a whole', async () => {
  let attempts = 0;
  const client = async path => {
    if (path.startsWith('/jobs/')) return {id: 'j', artwork_id: 'a', status: 'succeeded'};
    if (++attempts === 1) throw new Error('temporary offline');
    return {id: 'a', versions: [{id: 'saved'}]};
  };
  await assert.rejects(readJobSnapshot('j', client), /temporary offline/);
  assert.equal((await readJobSnapshot('j', client)).artwork.versions[0].id, 'saved');
});

test('an active job returns its real stage without unnecessary artwork reload', async () => {
  const calls = [];
  const result = await readJobSnapshot('j', async path => {
    calls.push(path);
    return {id: 'j', artwork_id: 'a', status: 'running', stage: 'generating'};
  });
  assert.deepEqual(calls, ['/jobs/j']);
  assert.equal(result.job.stage, 'generating');
  assert.equal(result.artwork, undefined);
});
