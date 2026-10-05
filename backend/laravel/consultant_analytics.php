<?php
// Managed by business-flows-telemetry-stack. Keep artifacts outside public storage.
use Illuminate\Support\Facades\Route;

Route::get('/admin/analytics/consultant-registrations', function () {
    $root = storage_path('app/private/consultant-analytics');
    abort_unless(is_file($root . '/current.json'), 503, 'Relatório ainda não publicado');
    $manifest = json_decode(file_get_contents($root . '/current.json'), true);
    abort_unless(is_array($manifest) && ($manifest['source'] ?? '') === 'database', 503);
    $id = $manifest['snapshot_id'] ?? '';
    abort_unless(preg_match('/\A[a-f0-9]{32}\z/', $id), 503);
    $report = $root . '/releases/' . $id . '.html';
    abort_unless(is_file($report) && hash_equals($manifest['sha256'] ?? '', hash_file('sha256', $report)), 503);
    return response()->file($report, [
        'Content-Type' => 'text/html; charset=UTF-8',
        'Cache-Control' => 'private, no-store, max-age=0',
        'Pragma' => 'no-cache',
        'X-Robots-Tag' => 'noindex, nofollow, noarchive',
        'X-Content-Type-Options' => 'nosniff',
        'X-Frame-Options' => 'SAMEORIGIN',
        'Content-Security-Policy' => "default-src 'none'; style-src 'unsafe-inline'; script-src 'sha256-__SCRIPT_SHA256__'; base-uri 'none'; frame-ancestors 'self'; form-action 'none'",
    ])->setPrivate();
})->middleware(['auth', 'verified', 'role:admin'])->name('admin.analytics.consultant-registrations');
