"""Publish a validated real snapshot behind the existing Laravel admin login."""
import base64
import hashlib
import json
import re
import shlex
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

import duckdb

from ssh_report import ROOT, arguments, connect, remote_php
from generate_registration_dashboard import QUERY_SCRIPT


def validate_snapshot(root):
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('source') != 'database' or not re.fullmatch('[a-f0-9]{32}', manifest.get('snapshot_id', '')):
        raise ValueError('Only a real identified snapshot can be published')
    created = datetime.fromisoformat(manifest['generated_at'])
    if not timedelta(0) <= datetime.now(timezone.utc) - created <= timedelta(hours=24):
        raise ValueError('Extract a fresh snapshot before publishing')
    content = (root / 'report.html').read_bytes()
    if hashlib.sha256(content).hexdigest() != manifest['sha256']:
        raise ValueError('Report checksum mismatch')
    with duckdb.connect(str(root / 'analytics.duckdb'), read_only=True) as con:
        row = con.execute('SELECT snapshot_id, generated_at, source FROM report_snapshot').fetchone()
        if row != (manifest['snapshot_id'], manifest['generated_at'], 'database'):
            raise ValueError('Database and report snapshot mismatch')
    return manifest, content


def run(client, command):
    _, out, err = client.exec_command(command, timeout=30)
    output, error = out.read(), err.read()
    status = out.channel.recv_exit_status()
    if status:
        raise RuntimeError(f'Remote validation failed (exit {status}); deployment stopped')
    return output


def probe_access(client, app_root, role):
    # In-memory auth and session only; never changes real users, passwords or sessions.
    selector = "null" if role == 'anonymous' else "App\\Models\\User::role('" + role + "')->firstOrFail()"
    code = r'''<?php
require 'vendor/autoload.php';
$app=require 'bootstrap/app.php';
$request=Illuminate\Http\Request::create('/admin/analytics/consultant-registrations','GET',[],[],[],['HTTP_ACCEPT'=>'application/json']);
$app->instance('request', $request);
$kernel=$app->make(Illuminate\Contracts\Http\Kernel::class);
$kernel->bootstrap();
config(['session.driver'=>'array']);
$user=__USER__;
if ($user) { $user->email_verified_at=now(); Illuminate\Support\Facades\Auth::guard('web')->setUser($user); }
$response=$kernel->handle($request);
echo json_encode(['status'=>$response->getStatusCode(),'cache'=>$response->headers->get('Cache-Control')]);
'''.replace('__USER__', selector)
    return json.loads(remote_php(client, app_root, code))


def main():
    args = arguments()
    pointer = json.loads((ROOT / 'data' / 'latest_real_snapshot.json').read_text(encoding='utf-8'))
    manifest, content = validate_snapshot(Path(pointer['directory']))
    snapshot_id = manifest['snapshot_id']
    template = (ROOT.parent / 'backend' / 'laravel' / 'consultant_analytics.php').read_text(encoding='utf-8')
    script = QUERY_SCRIPT.removeprefix('<script>').removesuffix('</script>')
    script_hash = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    route_content = template.replace('__SCRIPT_SHA256__', script_hash).encode()
    app = args.app_root.rstrip('/')
    routes = app + '/routes/web.php'
    route_path = app + '/routes/consultant_analytics.php'
    private = app + '/storage/app/private/consultant-analytics'
    backup = app + '/storage/app/deployment_backups/analytics_' + snapshot_id + '_' + uuid.uuid4().hex[:8]
    include = b"require __DIR__ . '/consultant_analytics.php';"
    with connect(args) as client, client.open_sftp() as sftp:
        def read(path):
            try:
                with sftp.open(path, 'rb') as f: return f.read()
            except FileNotFoundError: return None

        def write(path, data):
            with sftp.open(path, 'wb') as f: f.write(data)
            sftp.chmod(path, 0o600)

        def replace(path, data):
            temp = path + '.stage_' + snapshot_id
            write(temp, data)
            sftp.posix_rename(temp, path)

        baseline = read(routes)
        old_route, old_pointer = read(route_path), read(private + '/current.json')
        if baseline is None or b'?>' in baseline:
            raise RuntimeError('Unexpected web routes format')
        if old_route and b'Managed by business-flows-telemetry-stack' not in old_route:
            raise RuntimeError('Route file exists and is not owned by this deployment')
        cache_state = remote_php(client, app, "<?php require 'vendor/autoload.php'; $app=require 'bootstrap/app.php'; $app->make(Illuminate\\Contracts\\Console\\Kernel::class)->bootstrap(); echo json_encode($app->routesAreCached());")
        if json.loads(cache_state):
            raise RuntimeError('Routes are cached; review deployment procedure before changing them')
        run(client, 'mkdir -p -- ' + ' '.join(shlex.quote(p) for p in (private + '/releases', backup)))
        write(backup + '/web.php', baseline)
        if old_route: write(backup + '/consultant_analytics.php', old_route)
        if old_pointer: write(backup + '/current.json', old_pointer)
        route_stage = route_path + '.stage_' + snapshot_id
        write(route_stage, route_content)
        run(client, 'php -l ' + shlex.quote(route_stage))
        new_web = baseline if include in baseline else baseline + b'\n' + include + b'\n'
        web_stage = routes + '.stage_' + snapshot_id
        write(web_stage, new_web)
        run(client, 'php -l ' + shlex.quote(web_stage))
        report_path = private + '/releases/' + snapshot_id + '.html'
        write(report_path, content)
        if hashlib.sha256(read(report_path)).hexdigest() != manifest['sha256']:
            raise RuntimeError('Upload checksum mismatch')
        if read(routes) != baseline:
            raise RuntimeError('Routes changed concurrently; no activation performed')
        try:
            sftp.posix_rename(route_stage, route_path)
            replace(private + '/current.json', json.dumps(manifest).encode())
            sftp.posix_rename(web_stage, routes)
            results = {role: probe_access(client, app, role) for role in ('anonymous','provider','admin')}
            if [results[r]['status'] for r in ('anonymous','provider','admin')] != [401,403,200]:
                raise RuntimeError('Authentication probes failed: ' + json.dumps(results))
            if 'no-store' not in results['admin']['cache']:
                raise RuntimeError('Missing private cache policy')
            print(json.dumps({'published':True,'snapshot_id':snapshot_id,'access_tests':results,'backup':backup}))
        except Exception:
            replace(routes, baseline)
            if old_route: replace(route_path, old_route)
            elif read(route_path) == route_content: sftp.remove(route_path)
            if old_pointer: replace(private + '/current.json', old_pointer)
            elif read(private + '/current.json') is not None: sftp.remove(private + '/current.json')
            raise


if __name__ == '__main__':
    main()
