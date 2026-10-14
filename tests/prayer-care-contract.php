<?php
declare(strict_types=1);
$tmp=sys_get_temp_dir().'/kcmc-care-'.bin2hex(random_bytes(6));mkdir($tmp,0700);
putenv('KCMC_PRIVATE_DATA_DIR='.$tmp);
require_once __DIR__.'/../KCMC-Connect-Phase6-Recreated/lib/prayer-care.php';
$checks=0;
function ok(bool $value,string $label):void{global $checks;if(!$value)throw new RuntimeException($label);$checks++;echo "PASS: $label\n";}
function rejects(callable $fn,string $label):void{try{$fn();}catch(DomainException|RuntimeException $e){ok(true,$label);return;}throw new RuntimeException('Expected refusal: '.$label);}
$alice=['id'=>'alice','active'=>true,'role'=>'member','display_name'=>'Alice Test'];
$bob=['id'=>'bob','active'=>true,'role'=>'member','display_name'=>'Bob Test'];
$pastor=['id'=>'pastor','active'=>true,'role'=>'pastor_admin','display_name'=>'Pastor Test'];
$recovery=['id'=>'recovery','active'=>true,'role'=>'recovery_admin'];
$team=['id'=>'legacy-team','active'=>true,'role'=>'prayer_team'];
$now=1792008000;$s=kcmc_care_empty();
function act(array &$s,array $u,string $action,array $input=[]):void{global $now;kcmc_care_apply($s,$u,$action,$input,$now);}
function entry(array &$s,array $u,string $audience='pastoral',string $kind='need'):string{act($s,$u,'submit',['message'=>'Synthetic confidential words only.','audience'=>$audience,'kind'=>$kind,'consent'=>$audience==='pastoral'?'':'1']);return array_key_last($s['entries']);}
try{
 file_put_contents($tmp.'/prayers.json','LEGACY PRIVATE SENTINEL');
 $initial=kcmc_care_read();ok($initial===kcmc_care_empty(),'read of new ministry is empty; never imports legacy');
 ok(!file_exists($tmp.'/prayer-care.json'),'GET does not create ministry store');
 rejects(fn()=>act($s,$recovery,'join',['confidential'=>'1']),'recovery account denied');
 rejects(fn()=>act($s,array_replace($alice,['active'=>false]),'join',['confidential'=>'1']),'inactive member denied');
 rejects(fn()=>act($s,$alice,'join'),'confidentiality agreement required');
 act($s,$alice,'join',['confidential'=>'1']);ok(!kcmc_care_warrior($s,$alice),'signup waits for approval');
 rejects(fn()=>act($s,$bob,'approve_warrior',['target'=>'alice']),'member cannot approve signup');
 act($s,$pastor,'approve_warrior',['target'=>'alice']);ok(kcmc_care_warrior($s,$alice),'pastor approves signup');
 ok($alice['role']==='member'&&!kcmc_can_view_private_prayers($alice),'signup does not grant legacy prayer-team role');
 $private=entry($s,$bob);ok(!kcmc_care_visible($s['entries'][$private],$s,$alice,$now),'private needs hidden from warriors');
 ok(!kcmc_care_visible($s['entries'][$private],$s,$team,$now),'legacy prayer-team role cannot see new pastoral-only needs');
 ok(kcmc_care_visible($s['entries'][$private],$s,$bob,$now)&&kcmc_care_visible($s['entries'][$private],$s,$pastor,$now),'author and pastoral leader can see private need');
 rejects(fn()=>act($s,$pastor,'approve',['entry_id'=>$private]),'pastor cannot widen private audience');
 rejects(fn()=>act($s,$bob,'submit',['kind'=>'need','audience'=>'team','message'=>'Long enough words']),'sharing requires explicit permission');
 $shared=entry($s,$bob,'team');ok(!kcmc_care_visible($s['entries'][$shared],$s,$alice,$now),'pending team need hidden');
 rejects(fn()=>act($s,$alice,'approve',['entry_id'=>$shared]),'member cannot approve need');
 act($s,$pastor,'approve',['entry_id'=>$shared]);ok(kcmc_care_shared($s['entries'][$shared],$s,$alice,$now),'approved team need visible to approved warrior');
 ok(!kcmc_care_visible($s['entries'][$shared],$s,$team,$now),'legacy team does not bypass new approval');
 act($s,$alice,'pray',['entry_id'=>$shared]);act($s,$alice,'pray',['entry_id'=>$shared]);ok($s['commitments'][$shared]===['alice'],'pray action idempotent for member');
 act($s,$bob,'join',['confidential'=>'1']);act($s,$pastor,'approve_warrior',['target'=>'bob']);act($s,$bob,'pray',['entry_id'=>$shared]);ok(count($s['commitments'][$shared])===2,'multiple members can carry a need');
 rejects(fn()=>act($s,$alice,'close',['entry_id'=>$shared]),'warrior cannot close another persons request');
 rejects(fn()=>act($s,$alice,'update',['entry_id'=>$shared,'message'=>'Unauthorized rewritten words']),'warrior cannot edit another persons request');
 act($s,$bob,'update',['entry_id'=>$shared,'message'=>'Updated synthetic details require approval.']);ok($s['entries'][$shared]['status']==='pending'&&!kcmc_care_visible($s['entries'][$shared],$s,$alice,$now),'updated words require fresh approval');
 act($s,$pastor,'approve',['entry_id'=>$shared]);act($s,$bob,'private',['entry_id'=>$shared]);ok(!kcmc_care_visible($s['entries'][$shared],$s,$alice,$now),'withdrawn consent immediately removes shared visibility');
 $members=entry($s,$bob,'members');act($s,$pastor,'approve',['entry_id'=>$members]);ok(kcmc_care_shared($s['entries'][$members],$s,$team,$now),'member audience reaches verified member roles');
 ok(!kcmc_care_visible($s['entries'][$members],$s,$recovery,$now),'recovery excluded even from member audience');
 ok(!kcmc_care_shared($s['entries'][$members],$s,$alice,$now+31*86400),'expired need excluded');
 $before=count($s['entries']);act($s,$bob,'answered',['entry_id'=>$members]);ok(count($s['entries'])===$before&&!kcmc_care_shared($s['entries'][$members],$s,$alice,$now),'answered never publishes original as praise');
 $praise=entry($s,$bob,'members','praise');ok(!kcmc_care_visible($s['entries'][$praise],$s,$alice,$now),'praise sharing waits for approval');act($s,$pastor,'approve',['entry_id'=>$praise]);ok(kcmc_care_shared($s['entries'][$praise],$s,$alice,$now),'approved praise visible');
 rejects(fn()=>act($s,$alice,'pray',['entry_id'=>$praise]),'cannot adopt praise as prayer need');
 act($s,$pastor,'decline_warrior',['target'=>'alice']);ok(!kcmc_care_warrior($s,$alice),'leader can revoke warrior approval');
 act($s,$bob,'leave');ok(!kcmc_care_warrior($s,$bob)&&!in_array('bob',$s['commitments'][$shared],true),'leaving removes memberships and personal commitments');
 kcmc_care_save($alice,'join',['confidential'=>'1'],0);$raw=file_get_contents($tmp.'/prayer-care.json');
 rejects(fn()=>kcmc_care_save($bob,'join',['confidential'=>'1'],0),'stale form refused under lock');ok(file_get_contents($tmp.'/prayer-care.json')===$raw,'stale write preserves exact store');
 kcmc_care_save($pastor,'approve_warrior',['target'=>'alice'],1);ok(file_get_contents($tmp.'/prayer-care.json.previous.json')===$raw,'previous version backed up privately');
 ok(file_get_contents($tmp.'/prayers.json')==='LEGACY PRIVATE SENTINEL','legacy prayer bytes unchanged');
 file_put_contents($tmp.'/prayer-care.json','broken');rejects(fn()=>kcmc_care_save($bob,'join',['confidential'=>'1'],2),'corrupt storage fails closed');ok(file_get_contents($tmp.'/prayer-care.json')==='broken','corrupt store not overwritten');
 echo "$checks Prayer & Care checks passed.\n";
}finally{foreach(glob($tmp.'/*') as $p)unlink($p);rmdir($tmp);}
