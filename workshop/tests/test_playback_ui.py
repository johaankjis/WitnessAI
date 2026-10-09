"""Execute the actual UI in Node with a mocked DOM/player, without network."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_player_and_timeline_behavior():
    if not shutil.which('node'):
        pytest.skip('Node required for offline UI behavior tests')
    app = Path(__file__).resolve().parents[1] / 'app.js'
    script = r'''
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const nodes = new Map();
function node(id) {
  if (!nodes.has(id)) nodes.set(id, {
    innerHTML: '', textContent: '', style: {}, hidden: false, readyState: 1,
    currentTime: 0, duration: 60, listeners: {},
    classList: {toggle(){}, add(){}, remove(){}},
    addEventListener(event, cb) { (this.listeners[event] ||= []).push(cb); },
    emit(event) { for (const cb of this.listeners[event] || []) cb({}); },
    contains() { return false; }, querySelectorAll() { return []; }, removeAttribute(){},
    play() { return Promise.resolve(); }, load() { this.readyState = 0; },
    getAttribute(name) { return this[name]; }
  });
  return nodes.get(id);
}
const context = { location: {pathname: '/app/'},
  document: {getElementById: id => id === 'synthetic-note' ? null : node(id),
    addEventListener(){}, querySelector(){return null;}},
  console, fetch(){throw Error('Unexpected network');} };
vm.createContext(context);
let source = fs.readFileSync(process.argv[1], 'utf8');
source = source.replace('  load(false);\n})();',
  '  globalThis.testUI = {state, setupVideo, selectClaim, updatePlayback};\n})();');
vm.runInContext(source, context);
const ui = context.testUI;
const rows = Array.from({length:6}, (_, i) => ({
  claim: {id: 'c'+i, text: 'Claim '+i}, verdict: {verdict:'not_visible', verdict_label:'Not visible'},
  seek_sec: i * .5, seek_absolute_sec: 25 + i * .5, evidence: {}
}));
ui.state.review = {synthetic:false, incident:{evidence_window_sec:{start:25,end:30}},
  ui:{video_url:'/api/media/full',fallback_video_url:'/api/media/stream'}, claim_reviews:rows,
  timeline:rows.map(r => ({...r, claim_id:r.claim.id,label:r.claim.text})), statements:[]};
ui.setupVideo(ui.state.review);
const player = node('player');
assert.equal(player.src, '/app/api/media/full');
ui.selectClaim('c3');
assert.equal(player.currentTime, 26.5);
assert.match(node('inspector-body').innerHTML, /Claim 3/);
assert.equal((node('timeline').innerHTML.match(/type="button"/g)||[]).length, 6);
assert.match(node('timeline').innerHTML, /aria-current="true"/);
ui.updatePlayback();
assert.match(node('now-playing').textContent, /Parent 26.5s/);
assert.match(node('window-status').textContent, /inside reviewed window/);
player.currentTime = 40;
player.emit('timeupdate');
assert.match(node('window-status').textContent, /outside reviewed window/);
player.emit('error');
assert.equal(player.src, '/app/api/media/stream');
assert.equal(ui.state.videoMode, 'segment');
assert.match(node('media-note').textContent, /Segment fallback/);
// Latest selection wins while metadata is still pending.
ui.selectClaim('c4'); ui.selectClaim('c5');
player.readyState = 1; player.duration = 5; player.emit('loadedmetadata');
assert.equal(player.currentTime, 2.5);
assert.match(node('now-playing').textContent, /Parent 27.5s.*clip 2.5s/);
assert.match(node('inspector-body').innerHTML, /Claim 5/);
player.emit('error');
assert.match(node('media-note').textContent, /full video and segment fallback failed/);
assert.equal(player.src, '/app/api/media/stream'); // no retry loop
ui.state.review.synthetic = true;
context.document.createElement = () => ({ }); player.after = () => {};
ui.setupVideo(ui.state.review);
assert.equal(player.hidden, true);
assert.match(node('media-note').textContent, /SYNTHETIC FIXTURE/);
'''
    subprocess.run(['node', '-e', script, str(app)], check=True, capture_output=True, text=True)
