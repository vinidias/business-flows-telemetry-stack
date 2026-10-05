import hashlib
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import duckdb
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pipeline'))
from deploy_report import validate_snapshot
from extract import prepare_user_snapshot
from registration_details import prepare_details
import ssh_report


def test_production_formacao_mapping_without_category_id():
    users = pd.DataFrame([{'id':1,'user_type':'provider','status':1,'created_at':'2026-10-05',
                          'formacao':'Agronomia','professional_registration':'CREA 100/GO'}])
    aggregate = prepare_user_snapshot(users)
    assert aggregate.iloc[0].professional_fields_available
    assert aggregate.iloc[0].professional_category_name == 'Agronomia'
    assert prepare_details(users)[0]['category'] == 'Agronomia'


def test_failed_transform_preserves_previous_snapshot_pointer(tmp_path, monkeypatch):
    (tmp_path / 'data').mkdir()
    pointer = tmp_path / 'data' / 'latest_real_snapshot.json'
    pointer.write_text('{"previous":"valid report"}')
    monkeypatch.setattr(ssh_report, 'ROOT', tmp_path)
    def fail(*args, **kwargs):
        raise RuntimeError('dbt failed')
    monkeypatch.setattr(ssh_report.subprocess, 'run', fail)
    payload = {'users':[{'id':1,'user_type':'provider','status':1,'created_at':'2026-10-05',
                        'formacao':'Agronomia','professional_registration':'CREA 10'}],
               'category_names':{},'documents':{},'pix':{}}
    with pytest.raises(RuntimeError, match='dbt failed'):
        ssh_report.build_snapshot(payload, tmp_path / 'staged')
    assert pointer.read_text() == '{"previous":"valid report"}'


@pytest.mark.parametrize('problem', ['none','demo','hash','stale','mismatch'])
def test_publication_gate(tmp_path, problem):
    content = b'<html>real report fixture</html>'
    (tmp_path / 'report.html').write_bytes(content)
    timestamp = datetime.now(timezone.utc) - timedelta(hours=25 if problem == 'stale' else 0)
    manifest = {'snapshot_id':'a'*32,'generated_at':timestamp.isoformat(),
                'source':'synthetic_demo' if problem == 'demo' else 'database',
                'sha256':hashlib.sha256(content).hexdigest() if problem != 'hash' else 'bad'}
    (tmp_path / 'manifest.json').write_text(json.dumps(manifest))
    with duckdb.connect(str(tmp_path / 'analytics.duckdb')) as con:
        con.execute('CREATE TABLE report_snapshot (snapshot_id VARCHAR, generated_at VARCHAR, source VARCHAR)')
        con.execute('INSERT INTO report_snapshot VALUES (?, ?, ?)',
                    ['b'*32 if problem == 'mismatch' else 'a'*32, timestamp.isoformat(), 'database'])
    if problem == 'none':
        assert validate_snapshot(tmp_path)[1] == content
    else:
        with pytest.raises(ValueError):
            validate_snapshot(tmp_path)
