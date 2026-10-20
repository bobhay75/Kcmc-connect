#!/usr/bin/env python3
"""Pinned cPanel read-only acceptance. Creates private review staging; never applies."""
from __future__ import print_function
import hashlib,io,os,stat,subprocess,sys,tempfile,urllib.request,zipfile
from pathlib import Path
BUNDLE_REF='0cc99c3c50f2f589d238b605957f032a5a56c0c8'
BUNDLE_SHA256='680edad8969f5361cc73e48dcc004c44d6147c17e158c11ae6dfa7eb08edf3f3'
URL='https://raw.githubusercontent.com/bobhay75/Kcmc-connect/'+BUNDLE_REF+'/tools/kcmc-tony-functions-oct20/kcmc-tony-functions-review.zip'
HOME_ROOT=Path('/home/bobsome1')
APP=HOME_ROOT/'public_html/kcmc-connect'
def main():
    if len(sys.argv)!=1:raise RuntimeError('No arguments or apply mode are supported.')
    if (os.getuid(),os.geteuid(),os.getgid(),os.getegid())!=(2162,2162,2147,2147):raise RuntimeError('Run in the bobsome1 cPanel Terminal.')
    if HOME_ROOT.is_symlink() or not HOME_ROOT.is_dir():raise RuntimeError('Expected hosting home is unavailable.')
    print('Downloading and verifying the KCMC read-only review...',flush=True)
    with urllib.request.urlopen(URL,timeout=45) as response:raw=response.read(2*1024*1024+1)
    if len(raw)>2*1024*1024 or hashlib.sha256(raw).hexdigest()!=BUNDLE_SHA256:raise RuntimeError('Package verification failed. Nothing installed.')
    stage=Path(tempfile.mkdtemp(prefix='kcmc-tony-check-',dir=str(HOME_ROOT)))
    print('PRIVATE_STAGE='+str(stage),flush=True);print('ZIP_SHA256='+BUNDLE_SHA256,flush=True)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        seen=set()
        for info in archive.infolist():
            name=info.filename;parts=name.split('/')
            if name in seen or any(part in ('','.','..') for part in parts) or name.startswith('/') or '\\' in name or info.file_size>16*1024*1024 or stat.S_IFMT(info.external_attr>>16)!=stat.S_IFREG:
                raise RuntimeError('Unexpected archive member; review staging retained. Nothing installed.')
            seen.add(name);path=stage.joinpath(*parts);path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('xb') as out:out.write(archive.read(info))
            path.chmod(0o644)
    commands=[['check-release.py',str(APP)],['install-functions.py','check']]
    for args in commands:
        print('READ-ONLY CHECK: '+' '.join(args),flush=True)
        subprocess.run([sys.executable,'-I','-B']+args,cwd=str(stage),check=True)
    for php in ['/opt/alt/php82/usr/bin/php','/opt/cpanel/ea-php82/root/usr/bin/php']:
        if os.path.isfile(php) and os.access(php,os.X_OK):
            print('READ-ONLY MAIL FLAGS (CLI configuration; no mail sent):',flush=True)
            subprocess.run([php,str(stage/'mail-readiness.php')],cwd=str(stage),check=True)
            break
    else:print('Mail flags not checked: expected host PHP 8.2 CLI unavailable.',flush=True)
    print('CHECKS FINISHED. No installation, mail send or configuration change. Send this output for review.',flush=True)
if __name__=='__main__':
    try:main()
    except (OSError,RuntimeError,ValueError,subprocess.SubprocessError,zipfile.BadZipFile) as error:
        print('STOP: '+str(error)+' No apply command was run.',file=sys.stderr);sys.exit(1)
