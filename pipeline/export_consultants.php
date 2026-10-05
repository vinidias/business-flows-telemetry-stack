<?php
// Read-only export over SSH stdin; never install this script as a public endpoint.
require 'vendor/autoload.php';
$app = require 'bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

$columns = Schema::getColumnListing('users');
if (!in_array('professional_registration', $columns) ||
    (!in_array('formacao', $columns) && !in_array('professional_category_id', $columns))) {
    throw new RuntimeException('Professional registration source fields unavailable');
}
$allowed = ['id','user_type','status','created_at','updated_at','professional_registration',
    'professional_category_id','formacao','is_email_verified','email_verified_at'];
DB::beginTransaction();
$users = DB::table('users')->select(array_values(array_intersect($allowed, $columns)))
    ->whereIn('user_type', ['provider','consultant'])->whereNull('deleted_at')->get();
$names = DB::table('categories')->pluck('name', 'id');
$documents = [];
if (Schema::hasTable('documents') && Schema::hasTable('provider_documents')) {
    $required = DB::table('documents')->where('is_required', 1)->where('status', 1)
        ->where('type', 'provider_document')->whereNull('deleted_at')->pluck('id')->all();
    $approved = DB::table('provider_documents')->where('is_verified', 1)->whereNull('deleted_at')
        ->whereIn('document_id', $required)->get(['provider_id','document_id'])->groupBy('provider_id');
    foreach ($users as $user) {
        $ids = isset($approved[$user->id]) ? $approved[$user->id]->pluck('document_id')->all() : [];
        $documents[$user->id] = !$required ? 'unknown' : (!array_diff($required, $ids) ? 'verified' : 'unverified');
    }
}
$pix = [];
if (Schema::hasTable('banks')) {
    $bankColumns = Schema::getColumnListing('banks');
    $flag = in_array('is_pix_verified', $bankColumns) ? 'is_pix_verified' :
        (in_array('pix_verified_at', $bankColumns) ? 'pix_verified_at' : null);
    if ($flag) {
        $banks = DB::table('banks')->whereNull('deleted_at')->get(['provider_id', $flag])->groupBy('provider_id');
        foreach ($banks as $id => $items) {
            $states = $items->map(function ($bank) use ($flag) {
                $value = $bank->$flag;
                if ($flag === 'pix_verified_at') return $value ? 'verified' : 'unverified';
                return $value === null ? 'unknown' : ((int)$value === 1 ? 'verified' : 'unverified');
            })->all();
            $pix[$id] = in_array('verified', $states) ? 'verified' :
                (in_array('unknown', $states) ? 'unknown' : 'unverified');
        }
    }
}
echo json_encode(['users'=>$users,'category_names'=>$names,'documents'=>$documents,'pix'=>$pix], JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE);
DB::rollBack(); // The export is read-only; end the consistent read transaction.
