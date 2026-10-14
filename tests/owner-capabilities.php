<?php
declare(strict_types=1);
$tmp = sys_get_temp_dir().'/kcmc-owner-capabilities-'.bin2hex(random_bytes(6));
mkdir($tmp,0700);putenv('KCMC_PRIVATE_DATA_DIR='.$tmp);
require_once __DIR__.'/../KCMC-Connect-Phase6-Recreated/lib/prayer-care.php';
$checks=0;
function owner_check(bool $ok,string $label):void {global $checks;if(!$ok)throw new RuntimeException($label);$checks++;echo "PASS: $label\n";}
$owner=['id'=>'owner','active'=>true,'role'=>'recovery_admin'];
$other=['id'=>'other','active'=>true,'role'=>'recovery_admin'];
$member=['id'=>'member','active'=>true,'role'=>'member'];
try {
    putenv('KCMC_OPERATIONS_OWNER_USER_ID=owner');
    foreach(['member','prayer_team','pastor_admin','recovery_admin'] as $role) owner_check(kcmc_has_role([$role],$owner),'designated owner capability: '.$role);
    owner_check(kcmc_role($owner)==='recovery_admin','stored recovery identity retained');
    owner_check(kcmc_can_publish($owner)&&kcmc_can_manage_users($owner)&&kcmc_can_moderate_prayers($owner)&&kcmc_can_view_private_prayers($owner),'owner retains publishing and recovery plus prayer administration');
    owner_check(!kcmc_has_role([],$owner)&&!kcmc_has_role(['unknown_future_role'],$owner),'no empty or unknown role override');
    owner_check(!kcmc_is_designated_owner(array_replace($owner,['active'=>false])),'inactive owner never gains override');
    owner_check(!kcmc_care_member(array_replace($owner,['active'=>false])),'inactive owner denied ministry');
    owner_check(!kcmc_is_designated_owner(array_replace($owner,['role'=>'member'])),'matching ID without administrator role fails closed');
    owner_check(!kcmc_has_role(['pastor_admin'],array_replace($owner,['role'=>'member'])),'matching ordinary member never becomes pastor');
    owner_check(!kcmc_is_designated_owner(array_replace($owner,['id'=>''])),'empty ID denied');
    owner_check(!kcmc_care_member($other)&&!kcmc_can_view_private_prayers($other),'other recovery administrator still excluded from prayers');
    owner_check(kcmc_can_publish($other)&&kcmc_can_manage_users($other),'other recovery administrative capabilities unchanged');
    $s=kcmc_care_empty();$now=time();
    kcmc_care_apply($s,$member,'join',['confidential'=>'1'],$now);
    try {kcmc_care_apply($s,$other,'approve_warrior',['target'=>'member'],$now);throw new LogicException('Other recovery approved signup');} catch(DomainException $e) {owner_check(true,'other recovery cannot approve warrior');}
    kcmc_care_apply($s,$owner,'approve_warrior',['target'=>'member'],$now);
    owner_check(kcmc_care_warrior($s,$member),'owner approves pending warrior');
    owner_check($member['role']==='member'&&!kcmc_can_view_private_prayers($member),'warrior approval never grants legacy private prayer access');
    kcmc_care_apply($s,$member,'submit',['message'=>'Synthetic private request only.','kind'=>'need','audience'=>'pastoral'],$now);
    $id=array_key_last($s['entries']);
    try {kcmc_care_apply($s,$owner,'approve',['entry_id'=>$id],$now);throw new LogicException('Owner widened private audience');} catch(DomainException $e) {owner_check(true,'owner cannot publish a private-only request');}
    owner_check($s['entries'][$id]['audience']==='pastoral'&&$s['entries'][$id]['status']==='private','private audience unchanged');
    putenv('KCMC_OPERATIONS_OWNER_USER_ID=other');
    owner_check(!kcmc_care_leader($owner),'owner mismatch immediately removes override');
    putenv('KCMC_OPERATIONS_OWNER_USER_ID=');
    owner_check(!kcmc_care_member($owner)&&!kcmc_can_moderate_prayers($owner),'missing owner configuration fails closed');
    owner_check(kcmc_care_leader(['id'=>'pastor','active'=>true,'role'=>'pastor_admin']),'pastor permissions unchanged');
    echo "$checks owner capability checks passed.\n";
} finally {foreach(glob($tmp.'/*') as $p)unlink($p);rmdir($tmp);}
