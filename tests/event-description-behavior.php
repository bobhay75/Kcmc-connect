<?php
declare(strict_types=1);
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/event-description-suggestions.php';
$path=__DIR__ . '/../KCMC-Connect-Phase6-Recreated/data/content.json';
$before=file_get_contents($path);
$data=json_decode($before,true,512,JSON_THROW_ON_ERROR);
$events=array_column($data['events'],null,'id');
$checks=0;
function check_description(bool $condition,string $name): void {
    global $checks;
    if(!$condition){fwrite(STDERR,"FAIL: $name\n");exit(1);}
    $checks++;echo "PASS: $name\n";
}
$ids=['griefshare-0902','mens-breakfast-0905','adult-bible-study-0913','ladies-fellowship-0917','jaffe-potluck-0929'];
foreach($ids as $id){
    $event=$events[$id];$original=$event;
    check_description(kcmc_event_description_suggestion($event)!==null,"$id offers an existing-reference suggestion");
    check_description($event===$original,"$id input is not mutated");
    $event['description']='Owner-written description';
    check_description(kcmc_event_description_suggestion($event)===null,"$id preserves owner text");
}
$event=$events['ladies-fellowship-0917'];
foreach(['id','title','date','time','location'] as $field){
    $changed=$event;$changed[$field]='changed';
    check_description(kcmc_event_description_suggestion($changed)===null,"changed $field rejects stale suggestion");
}
foreach([''," \n\t"] as $empty){
    $candidate=$event;$candidate['description']=$empty;
    check_description(kcmc_event_description_suggestion($candidate)!==null,'empty field gets an optional suggestion, not an automatic replacement');
}
foreach([null,[],123,'0'] as $value){
    $candidate=$event;$candidate['description']=$value;
    check_description(kcmc_event_description_suggestion($candidate)===null,'nonempty or malformed description is not replaced');
}
check_description(kcmc_event_description_suggestion([])===null,'unknown event rejected');
check_description(kcmc_event_description_suggestion($events['trunk-or-treat-2026'])===null,'Trunk or Treat existing description stays untouched');
$ladies=kcmc_event_description_suggestion($event);
$potluck=kcmc_event_description_suggestion($events['jaffe-potluck-0929']);
check_description(in_array($ladies['text'],$data['news']['outreach'],true),'Ladies Fellowship text exactly matches existing news');
check_description(in_array($potluck['text'],$data['news']['outreach'],true),'potluck text exactly matches existing news');
check_description(file_get_contents($path)===$before,'no content-file write occurred');
echo "Event description PHP checks: $checks passed.\n";
