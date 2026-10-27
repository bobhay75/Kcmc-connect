#!/usr/bin/env python3
"""Build a review-only UI overlay from the inspected six-file host snapshot.

This is NOT an installer and does not disable direct endpoints or scheduled jobs.
"""
import argparse
import hashlib
from pathlib import Path

HASHES = {
 'index.php':'2e7fb75bae9bd4acbe63c91c1591fd0c2a0ff59944147bd9559468a94f115869',
 'bulletin.php':'3a2ad5c7483115309f867779b62ca341a45910af8745df5d04814267f9ca5a2e',
 'sw.js':'3d2d3ef3df76cbfebbd8848a8f616385d141aa5485c4262a2e0c08ee27234189',
 'lib/screen-navigation.php':'693c2317f8502f08968098570b637598cfc98f6668f4311236f8efa5b56f5993',
 'admin/index.php':'b20795e066136ef165656353bf74e2c23f9cb8379939f8823855f40291e6124b',
 'admin/home.php':'782cfd64cbfe83ba047f650bacd3d32e374de5065fb880acd515845f69d1ce63',
 'lib/bootstrap.php':'19a932424250b6bc33a5e844bfb942fb33a8194aa8bf912bf4494f1e27ba354e',
 'member/login.php':'c3a0b359d97be1ff0ba03660e114a426ee6a3ac8d51f53c7bd7449c69d5fcc91',
 'care.php':'e7055519d6efed05c363e75e27f14c4a4d570bc811a6ca2f65ec98a239987442',
}

def replace(s, old, new):
 if s.count(old) != 1: raise ValueError('Expected exactly one match for: '+old[:80])
 return s.replace(old,new,1)

def cut(s,start,end,replacement=''):
 if s.count(start)!=1 or s.count(end)!=1: raise ValueError('Missing or ambiguous boundary: '+start[:60])
 a=s.index(start); b=s.index(end,a); return s[:a]+replacement+s[b:]

p=argparse.ArgumentParser(description=__doc__);p.add_argument('snapshot',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
if a.output.exists(): p.error('output must not already exist')
source=a.snapshot.resolve(strict=True)
if source in a.output.absolute().parents or a.output.absolute() in source.parents: p.error('directories must not overlap')
files={}
for name,digest in HASHES.items():
 path=source/name
 if name in ('lib/bootstrap.php','member/login.php','care.php') and not path.exists():
  path=Path(__file__).resolve().parents[1]/'kcmc-manual-timeclock-oct16'/'evidence'/'prerequisite'/name
 if path.is_symlink() or not path.is_file(): raise ValueError('Missing or linked file: '+name)
 raw=path.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=digest: raise ValueError('Snapshot mismatch: '+name)
 files[name]=raw.decode('utf-8')

s=files['index.php']
s=replace(s,"<?=kcmc_screen_back($member ? 'member/' : '')?>", "<?=kcmc_screen_back('')?>")
s=cut(s,'        <a class="menu-account"','\n      </nav>', '''        <a class="menu-account" href="<?=kcmc_h(kcmc_url('admin/login.php'))?>">Administration</a>''')
s=replace(s,"<a href=\"<?=kcmc_h(kcmc_url($member ? 'member/' : 'admin/login.php'))?>\"><?=$member ? 'My account' : 'Sign In'?></a>","<a href=\"<?=kcmc_h(kcmc_url('admin/login.php'))?>\">Administration</a>")
files['index.php']=s
s=files['bulletin.php'];files['bulletin.php']=replace(s,'Prayer requests and prayer details are available only after verified member sign-in.','For prayer or support, contact the church office.')
s=files['lib/screen-navigation.php'];files['lib/screen-navigation.php']=cut(s,'    if ($signedIn) {',"    return '<nav")
s=files['admin/index.php'];s=replace(s,'<h1>Publishing Desk</h1><p class="muted">Publish approved church content while member prayer stays private.</p>','<h1>Church content</h1><p class="muted">Update contact details, announcements, bulletin, service links and events.</p>')
s=cut(s,'<div><a href="<?=kcmc_h(kcmc_url(\'admin/home.php\'))?>">← Administration','</div></div><?php if($msg)', '''<div><a href="<?=kcmc_h(kcmc_url())?>">Home</a> · <a href="<?=kcmc_h(kcmc_url('admin/connections.php'))?>">Connections</a> · <form class="signout-form" method="post" action="<?=kcmc_h(kcmc_url('member/logout.php'))?>"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><button type="submit">Sign out</button></form>''')
s=replace(s,' <a class="btnx" style="display:inline-block;text-decoration:none" href="<?=kcmc_h(kcmc_url(\'admin/backup.php\'))?>">Download backup</a>','')
files['admin/index.php']=s
files['admin/home.php']="<?php\nrequire_once __DIR__ . '/../lib/bootstrap.php';\nkcmc_require_role(['pastor_admin', 'recovery_admin']);\nheader('Location: ' . kcmc_url('admin/'));\nexit;\n"
s=files['sw.js'];s=replace(s,'kcmc-connect-v3.0.3-public-only-tony-functions-20261020','kcmc-connect-v3.0.3-public-only-basic-handoff-tony-functions-20261026');s=cut(s,'function safePushPayload(',"self.addEventListener('install'");s=cut(s,"self.addEventListener('push'", "self.addEventListener('fetch'");files['sw.js']=s

s=files['lib/bootstrap.php']
anchor="require_once __DIR__ . '/post-controls.php';\n"
guard="""
// Basic handoff profile: retain public endpoints and basic administration only.
if (PHP_SAPI !== 'cli') {
    $route = str_replace('\\\\', '/', (string)($_SERVER['SCRIPT_NAME'] ?? ''));
    if (preg_match('~/(admin|member|api)/~i', $route)) {
        if (!preg_match('~/(admin|member|api)/([^/]+\\.php)(?:/|$)~', $route, $match)) {
            http_response_code(404); header('Cache-Control: no-store'); exit('Not found.');
        }
        $allowed = [
            'admin' => ['index.php', 'home.php', 'login.php', 'setup.php', 'save.php', 'posts.php', 'event-create.php', 'connections.php', 'connections-export.php', 'rsvps.php', 'rsvps-export.php'],
            'member' => ['login.php', 'logout.php'],
            'api' => ['content.php', 'connection.php', 'rsvp.php'],
        ];
        if (!in_array($match[2], $allowed[$match[1]], true)) {
            http_response_code(404); header('Cache-Control: no-store'); exit('Not found.');
        }
    }
}
"""
files['lib/bootstrap.php']=replace(s,anchor,anchor+guard)
s=files['member/login.php']
s=replace(s,"$next = kcmc_safe_next((string)($_GET['next'] ?? $_POST['next'] ?? ''), 'member/');", "$next = kcmc_url('admin/');")
s=replace(s,"if (kcmc_current_user()) {\n    header('Location: ' . $next);\n    exit;\n}","if ($existing = kcmc_current_user()) {\n    if (kcmc_has_role(['pastor_admin', 'recovery_admin'], $existing)) { header('Location: ' . $next); exit; }\n    kcmc_logout_user();\n}")
s=replace(s,"if ($user && !empty($user['active']) && password_verify", "if ($user && !empty($user['active']) && in_array(kcmc_role($user), ['pastor_admin', 'recovery_admin'], true) && password_verify")
s=replace(s,'Staff and authorized ministry teams sign in here.', 'Church administrators sign in here.')
s=replace(s,'<p class="portal-fine"><strong>Forgot your password?</strong> Ask a KCMC Connect administrator for a recipient-bound, one-time password-reset link.</p>', '<p class="portal-fine">For sign-in help, contact the church office.</p>')
s=replace(s,'    <p class="portal-fine"><strong>Need staff or authorized ministry access?</strong> Use the recipient-bound, one-time invitation issued by a KCMC Connect administrator to create your password.</p>\n','')
files['member/login.php']=s
s=files['care.php'];files['care.php']=cut(s,'<div class="privacy-lock">','<p class="portal-fine">')

for name,content in files.items():
 out=a.output/name;out.parent.mkdir(parents=True,exist_ok=True);out.write_text(content,encoding='utf-8')
print('Review-only overlay created:', a.output)
print('Not an installer. Additional route restrictions, dependencies, and testing are required.')
