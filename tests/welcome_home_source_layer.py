"""Hash-bound in-memory projection of the approved welcome design for older proofs."""
from pathlib import Path
import hashlib
import json
import stat
import subprocess

ROOT=Path(__file__).resolve().parents[1]
PREFIX='KCMC-Connect-Phase6-Recreated/'
CANONICAL='b0c257edb8a42fc89fd6371c1bce7ee3efbd5ed9'
FIXTURE='tests/fixtures/welcome-home-reviewed.json'
PIN='578e741467d6868ff63b7542be24c18a6db540dd91e6dc8be81042e1d3ef1961'
MODIFIED=frozenset(['index.php','sw.js','manifest.webmanifest','assets/icons/icon-192.png','assets/icons/icon-512.png'])
ADDED=frozenset(['home-welcome.css','assets/visuals/kcmc-building-original-20261018.jpg'])

def require(ok,message):
    if not ok: raise AssertionError(message)

def blob(data):
    return hashlib.sha1(b'blob '+str(len(data)).encode('ascii')+b'\0'+data).hexdigest()

class WelcomeLayer:
    def __init__(self,root=ROOT,git_source=None):
        self.root=Path(root).resolve();self.app=self.root/PREFIX;self.git_source=Path(git_source or self.root).resolve()
        raw=(self.root/FIXTURE).read_bytes()
        require(hashlib.sha256(raw).hexdigest()==PIN,'Immutable welcome-design fixture hash required')
        self.fixture=json.loads(raw)
        require(set(self.fixture)=={'source_commit','modified','added'} and self.fixture['source_commit']=='1d14b582b73780c020ba3d489a3a2d58cf5f45e5','Exact welcome-design source context required')
        require(set(self.fixture['modified'])==MODIFIED and set(self.fixture['added'])==ADDED,'Exact five modified/two added public assets required')
        for group in ['modified','added']:
            for name,record in self.fixture[group].items():
                for parent in (self.app/name).parents:
                    if parent==self.app.parent: break
                    require(parent.is_dir() and not parent.is_symlink(),'Ordinary welcome-design parents required')
                p=self.app/name;info=p.lstat()
                require(stat.S_ISREG(info.st_mode) and not info.st_mode&0o111 and not p.is_symlink(),'Ordinary non-executable welcome-design file required: '+name)
                actual=p.read_bytes()
                require(len(actual)==record['after_bytes'] and hashlib.sha256(actual).hexdigest()==record['after_sha256'],'Only exact reviewed welcome-design bytes permitted: '+name)
                expected={'after_sha256','after_bytes'}
                if group=='modified': expected.add('before_git_blob' if name.startswith('assets/icons/') else 'before_utf8')
                require(set(record)==expected,'Bounded welcome-design record required: '+name)

    def before(self,name):
        require(name not in ADDED,'Added design asset has no historical preimage')
        if name not in MODIFIED: return (self.app/name).read_bytes()
        record=self.fixture['modified'][name]
        if 'before_utf8' in record: return record['before_utf8'].encode('utf-8')
        # Existing historical suites already require this immutable canonical
        # tree. Load binary preimages lazily, never add a new network/Git base.
        raw=subprocess.check_output(['git','--no-replace-objects','-C',str(self.git_source),'show',CANONICAL+':'+PREFIX+name])
        require(blob(raw)==record['before_git_blob'],'Exact canonical icon preimage required')
        return raw

    def restore_copy(self,destination):
        destination=Path(destination)
        require(destination.resolve()!=self.app,'Never project historical bytes into current application')
        for name in MODIFIED: (destination/name).write_bytes(self.before(name))
        for name in ADDED:
            p=destination/name
            require(hashlib.sha256(p.read_bytes()).hexdigest()==self.fixture['added'][name]['after_sha256'],'Only copied exact added asset may be removed')
            p.unlink()
