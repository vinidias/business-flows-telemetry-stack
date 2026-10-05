"""Copy only consultant reporting fields via verified SSH into a local DuckDB snapshot."""
import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

from extract import prepare_user_snapshot, register_in_duckdb
from registration_details import prepare_details
from generate_registration_dashboard import load_rows, render

ROOT = Path(__file__).resolve().parent


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True)
    parser.add_argument('--port', type=int, default=22)
    parser.add_argument('--user', required=True)
    parser.add_argument('--key', type=Path, required=True)
    parser.add_argument('--known-hosts', type=Path, required=True)
    parser.add_argument('--app-root', required=True)
    return parser.parse_args()


def connect(args):
    import paramiko
    client = paramiko.SSHClient()
    client.load_host_keys(str(args.known_hosts))
    client.connect(args.host, port=args.port, username=args.user, key_filename=str(args.key),
                   timeout=10, banner_timeout=15, auth_timeout=10,
                   look_for_keys=False, allow_agent=False)
    return client


def remote_php(client, app_root, code):
    stdin, stdout, stderr = client.exec_command('cd ' + shlex.quote(app_root) + ' && php', timeout=90)
    stdin.write(code)
    stdin.channel.shutdown_write()
    output = stdout.read()
    error = stderr.read()
    status = stdout.channel.recv_exit_status()
    if status:
        raise RuntimeError(f'Remote PHP failed with status {status}; report was not published')
    return output


def build_snapshot(payload, output_dir=None):
    snapshot_id = uuid.uuid4().hex
    root = Path(output_dir) if output_dir else ROOT / 'data' / 'snapshots' / snapshot_id
    root.mkdir(parents=True, exist_ok=False)
    users = pd.DataFrame(payload['users'])
    if users.empty:
        raise ValueError('Empty source; refusing to replace a report without verification')
    for field in ('created_at', 'updated_at'):
        if field in users:
            users[field] = pd.to_datetime(users[field], errors='raise')
    names = {str(k): str(v) for k, v in payload['category_names'].items()}
    normalize = lambda value: {str(k): v for k, v in value.items()} if isinstance(value, dict) else {}
    details = prepare_details(users, names, normalize(payload['documents']), normalize(payload['pix']))
    raw = root / 'users.parquet'
    prepare_user_snapshot(users, names).to_parquet(raw, index=False)
    database = root / 'analytics.duckdb'
    register_in_duckdb({'users': raw}, database)
    generated_at = datetime.now(timezone.utc).isoformat()
    detail_frame = pd.DataFrame(details)
    with duckdb.connect(str(database)) as con:
        con.execute('CREATE TABLE consultant_registration_details AS SELECT * FROM detail_frame')
        con.execute('CREATE TABLE report_snapshot (snapshot_id VARCHAR, generated_at VARCHAR, source VARCHAR)')
        con.execute('INSERT INTO report_snapshot VALUES (?, ?, ?)', [snapshot_id, generated_at, 'database'])
    dbt = Path(sys.executable).with_name('dbt.exe' if os.name == 'nt' else 'dbt')
    environment = dict(os.environ, DUCKDB_PATH=str(database.resolve()))
    for operation in ('run', 'test'):
        subprocess.run([str(dbt), operation, '--profiles-dir', '.', '--select', '+mart_consultant_registrations'],
                       cwd=ROOT / 'analytics', env=environment, check=True)
    with duckdb.connect(str(database), read_only=True) as con:
        if con.execute('SELECT COUNT(*) FROM consultant_registration_details').fetchone()[0] != len(details):
            raise RuntimeError('Detail count mismatch')
        if con.execute('SELECT SUM(registrations_count) FROM mart_consultant_registrations').fetchone()[0] != len(details):
            raise RuntimeError('Aggregate count mismatch')
    from datetime import date, timedelta
    cutoff = (date.today() - timedelta(days=29)).isoformat()
    visible_details = sorted([row for row in details if cutoff <= row['registered_at'][:10] <= date.today().isoformat()],
                             key=lambda row: row['registered_at'], reverse=True)
    report = root / 'report.html'
    report.write_text(render(load_rows(database), 'database', details_rows=visible_details, generated_at=generated_at), encoding='utf-8')
    manifest = {'snapshot_id': snapshot_id, 'source': 'database', 'generated_at': generated_at,
                'total_consultants': len(details), 'visible_consultants': len(visible_details),
                'sha256': hashlib.sha256(report.read_bytes()).hexdigest()}
    (root / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    # Promote the local pointer only after every check succeeds.
    pointer = ROOT / 'data' / 'latest_real_snapshot.json'
    temp = pointer.with_suffix('.tmp')
    temp.write_text(json.dumps({'directory': str(root.resolve()), **manifest}), encoding='utf-8')
    temp.replace(pointer)
    return manifest, report


def main():
    args = arguments()
    with connect(args) as client:
        payload = json.loads(remote_php(client, args.app_root, (ROOT / 'export_consultants.php').read_text(encoding='utf-8')))
    manifest, report = build_snapshot(payload)
    print(json.dumps({'report': str(report), **manifest}, ensure_ascii=False))


if __name__ == '__main__':
    main()
