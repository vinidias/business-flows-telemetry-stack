"""Exercise the browser filter/pagination handlers with a small DOM fixture."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
from generate_registration_dashboard import QUERY_SCRIPT


@pytest.mark.skipif(shutil.which("node") is None, reason="Node required for JavaScript behavior checks")
def test_combined_filters_dates_empty_results_and_pagination():
    fixture = """
const assert = require('node:assert/strict');
const element = () => ({value:'', hidden:false, disabled:false, textContent:'', handlers:{},
  addEventListener(name, fn) { this.handlers[name] = fn; }});
const ids = Object.fromEntries(['registration-search','registration-from','registration-to',
  'query-prev','query-next','query-count','query-empty'].map(id => [id, element()]));
const filters = ['category','status','documents','email','pix'].map(key =>
  Object.assign(element(), {dataset:{filter:key}}));
const rows = Array.from({length:31}, (_, i) => ({hidden:false,
  cells: [String(i), 'CRM ' + i, 'Medicina', i < 20 ? '2026-10-01' : '2026-10-05'].map(textContent => ({textContent})),
  dataset:{category:'Medicina', status: i % 2 ? 'active':'inactive', documents:'verified', email:'unverified', pix:'unknown'}}));
ids['registration-query'] = {querySelectorAll(selector) {
  return selector === 'tbody tr' ? rows : filters;
}};
global.document = {getElementById(id) {return ids[id];}};
const visible = () => rows.filter(row => !row.hidden);
"""
    checks = """
assert.equal(visible().length, 25);
ids['query-next'].handlers.click();
assert.equal(visible().length, 6);
assert.equal(ids['query-next'].disabled, true);
filters[1].value = 'active'; filters[1].handlers.change();
assert.equal(visible().length, 15);
assert.equal(ids['query-prev'].disabled, true);
ids['registration-from'].value='2026-10-05'; ids['registration-from'].handlers.change();
assert.equal(visible().length, 5);
ids['registration-to'].value='2026-10-01'; ids['registration-to'].handlers.change();
assert.equal(visible().length, 0);
assert.equal(ids['query-empty'].hidden, false);
ids['registration-to'].value=''; ids['registration-to'].handlers.change();
ids['registration-search'].value='CRM 21'; ids['registration-search'].handlers.input();
assert.equal(visible().length, 1);
assert.equal(ids['query-empty'].hidden, true);
"""
    script = fixture + QUERY_SCRIPT.removeprefix("<script>").removesuffix("</script>") + checks
    result = subprocess.run([shutil.which("node")], input=script, text=True, capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr
