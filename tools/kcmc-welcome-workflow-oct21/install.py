from pathlib import Path
import hashlib,json,datetime,shutil,os,sys,re,subprocess,tempfile
HERE=Path(__file__).resolve().parent
ROOT=Path('/home/bobsome1/public_html/kcmc-connect')
if '--root' in sys.argv:ROOT=Path(sys.argv[sys.argv.index('--root')+1]).resolve()
for rel,h in json.loads((HERE/'manifest.json').read_text()).items():
 if hashlib.sha256((HERE/'payload'/rel).read_bytes()).hexdigest()!=h:raise SystemExit('STOP: Package verification failed: '+rel)
changes={str(p.relative_to(HERE/'payload')):p.read_bytes() for p in (HERE/'payload').rglob('*.php')}
p=ROOT/'admin/connections.php';s=p.read_text()
needle='<form class="status-form" method="post">'
link='<a class="btn secondary" style="display:inline-block;margin:0 0 10px" href="<?=kcmc_h(kcmc_url(\'admin/welcome.php?id=\'.rawurlencode((string)($row[\'id\']??\'\'))))?>">Prepare welcome</a>'
if 'admin/welcome.php?id=' not in s:
 if s.count(needle)!=1:raise SystemExit('STOP: Connections layout differs; nothing changed.')
 s=s.replace(needle,link+needle)
# Private admin-only mail readiness: no messages are sent by loading the inbox.
inc="require_once __DIR__ . '/../lib/visitor-welcome.php';"
if "'/../lib/connection-welcome.php'" not in s:
 if inc not in s:raise SystemExit('STOP: Connections welcome support differs.')
 s=s.replace(inc,inc+"\nrequire_once __DIR__ . '/../lib/connection-welcome.php';")
if 'data-automatic-welcome-status' not in s:
 marker='<h1>Connection inbox</h1>'
 if s.count(marker)!=1:raise SystemExit('STOP: Inbox heading differs.')
 s=s.replace(marker,marker+'<p data-automatic-welcome-status><?php if(!empty(kcmc_connection_welcome_settings()[\'ready\'])): ?>Automatic welcome response: enabled for new connection signups.<?php else: ?>Automatic welcome response needs a configured church mail sender. Staff can prepare welcome drafts below.<?php endif; ?></p>')
# Show automatic delivery status for all connection kinds, not just visits.
s=s.replace("<?php if($kind==='visit'):?><br><small>Welcome email:",'<br><small>Welcome email:').replace("</small><?php endif;?></span><span class=\"note\">",'</small></span><span class="note">')
changes['admin/connections.php']=s.encode()
api=ROOT/'api/connection.php';s=api.read_text()
old="require_once __DIR__ . '/../lib/visitor-welcome.php';"
if "'/../lib/connection-welcome.php'" not in s:
 if old not in s:raise SystemExit('STOP: Connection endpoint differs.')
 s=s.replace(old,old+"\nrequire_once __DIR__ . '/../lib/connection-welcome.php';")
if 'kcmc_connection_welcome_send(' not in s:
 if s.count("if ($kind === 'visit') {")!=1 or s.count('kcmc_visitor_welcome_send(')!=1:raise SystemExit('STOP: Automatic welcome hook differs.')
 s=s.replace("if ($kind === 'visit') {","if (in_array($kind, ['visit', 'serve', 'groups'], true)) {")
 s=s.replace('kcmc_visitor_welcome_send(','kcmc_connection_welcome_send(')
changes['api/connection.php']=s.encode()
# Retire RSVP navigation only; preserve every existing response and endpoint.
for p in (ROOT/'admin').glob('*.php'):
 if p.name in ['rsvps.php','rsvps-export.php']:continue
 rel=str(p.relative_to(ROOT));s=changes.get(rel,p.read_bytes()).decode()
 s=re.sub(r"^[ \t]*\$groups\['People & care'\]\[\] = \['admin/rsvps.php', 'Event RSVPs', 'Review event responses.'\];\n",'',s,flags=re.M)
 s=re.sub(r'<a\b(?:(?!</a>).)*?(?:admin/rsvps\.php)(?:(?!</a>).)*?</a>','',s,flags=re.S)
 # The old RSVP statistic is no longer needed in the admin health screen.
 s=re.sub(r'<div class="health-stat"><span>New event RSVPs</span>.*?</div>','',s,flags=re.S)
 if s.encode()!=p.read_bytes() or rel in changes:changes[rel]=s.encode()
php=shutil.which('php')
if not php:
 for candidate in ['/opt/alt/php83/usr/bin/php','/opt/alt/php82/usr/bin/php','/opt/cpanel/ea-php82/root/usr/bin/php']:
  if Path(candidate).is_file():php=candidate;break
if not php:raise SystemExit('STOP: PHP CLI unavailable; no deployment.')
with tempfile.TemporaryDirectory(prefix='kcmc-welcome-check-') as stage:
 for i,(rel,data) in enumerate(changes.items()):
  target=Path(stage)/(str(i)+'.php');target.write_bytes(data)
  result=subprocess.run([php,'-l',str(target)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
  if result.returncode:raise SystemExit('STOP: PHP syntax check failed for '+rel+'\n'+result.stdout+result.stderr)
result=subprocess.run([php,str(HERE/'tests.php'),str(ROOT)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
if result.returncode:raise SystemExit('STOP: Welcome workflow checks failed.\n'+result.stdout+result.stderr)
print(result.stdout.strip())
if 'apply' not in sys.argv:print('CHECK PASSED. No live files changed.');sys.exit(0)
backup=ROOT.parent.parent/('kcmc-welcome-workflow-backup-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'));backup.mkdir(parents=True);record={}
for rel in changes:
 p=ROOT/rel;record[rel]=p.exists()
 if p.exists():
  dest=backup/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(str(p),str(dest))
(backup/'files.json').write_text(json.dumps(record))
written=[]
try:
 for rel,data in changes.items():
  p=ROOT/rel;p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.welcome-tmp');tmp.write_bytes(data)
  if p.exists():shutil.copymode(str(p),str(tmp))
  else:tmp.chmod(0o644)
  os.replace(str(tmp),str(p));written.append(rel)
except Exception:
 for rel in reversed(written):
  if record[rel]:shutil.copy2(str(backup/rel),str(ROOT/rel))
  elif (ROOT/rel).exists():(ROOT/rel).unlink()
 raise
print('SUCCESS: Connection welcome drafts, welcome package and automatic response installed. Event RSVP admin links removed; existing records retained.')
print('Backup: '+str(backup))
# Report readiness without sending any test or live email.
check="require "+repr(str(ROOT/'lib/bootstrap.php'))+";require "+repr(str(ROOT/'lib/connection-welcome.php'))+";echo !empty(kcmc_connection_welcome_settings()['ready'])?'Automatic welcome mail: READY':'Automatic welcome mail: SENDER CONFIGURATION NEEDED';"
r=subprocess.run([php,'-r',check],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
print(r.stdout.strip() if r.returncode==0 else 'Check automatic welcome sender status in the Connections inbox.')
