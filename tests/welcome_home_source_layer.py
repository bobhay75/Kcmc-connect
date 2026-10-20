"""Hash-bound in-memory projection of the approved welcome design for older proofs."""
from pathlib import Path
import hashlib
import json
import stat
import subprocess
from tony_function_source_layer import FunctionalLayer, FIXTURE as FUNCTION_FIXTURE, MODIFIED as FUNCTION_MODIFIED, ADDED as FUNCTION_ADDED

ROOT=Path(__file__).resolve().parents[1]
PREFIX='KCMC-Connect-Phase6-Recreated/'
CANONICAL='b0c257edb8a42fc89fd6371c1bce7ee3efbd5ed9'
FIXTURE='tests/fixtures/welcome-home-reviewed.json'
PIN='578e741467d6868ff63b7542be24c18a6db540dd91e6dc8be81042e1d3ef1961'
BRAND_FIXTURE='tests/fixtures/brand-family-20261020-reviewed.json'
BRAND_PIN='957cb0f89b449928c4e09e7910cdbb07118ad0137dccd3d30cbd6d5977f8b7ed'
BRAND_MODIFIED=frozenset(['index.php','home-welcome.css','sw.js'])
BRAND_ADDED=frozenset('assets/visuals/kcmc-'+n+'-20261018.jpg' for n in [
    'traditional-sanctuary','traditional-worship','traditional-front','traditional-message',
    'contemporary-gathering','contemporary-fellowship','contemporary-music','contemporary-room',
    'contemporary-room-portrait','contemporary-after-service'])
MODIFIED=frozenset(['index.php','sw.js','manifest.webmanifest','assets/icons/icon-192.png','assets/icons/icon-512.png'])
WELCOME_ADDED=frozenset(['home-welcome.css','assets/visuals/kcmc-building-original-20261018.jpg'])
ADDED=WELCOME_ADDED | BRAND_ADDED | FUNCTION_ADDED

def require(ok,message):
    if not ok: raise AssertionError(message)

def blob(data):
    return hashlib.sha1(b'blob '+str(len(data)).encode('ascii')+b'\0'+data).hexdigest()

class WelcomeLayer:
    def __init__(self,root=ROOT,git_source=None):
        self.root=Path(root).resolve();self.app=self.root/PREFIX;self.git_source=Path(git_source or self.root).resolve()
        self.functions=FunctionalLayer(self.root)
        # Current branding is a separately pinned reversible layer. The October
        # 19 fixture and every earlier security/provenance proof stay immutable.
        brand_raw=(self.root/BRAND_FIXTURE).read_bytes()
        require(hashlib.sha256(brand_raw).hexdigest()==BRAND_PIN,'Immutable October 20 branding fixture hash required')
        self.brand=json.loads(brand_raw)
        require(set(self.brand)=={'source_commit','modified','added'} and self.brand['source_commit']=='ca0d6197b4be7339fd5937f216202a7e5fbdd13d','Exact October 20 branding source context required')
        require(set(self.brand['modified'])==BRAND_MODIFIED and set(self.brand['added'])==BRAND_ADDED,'Exact three branding files and ten supplied photos required')
        self.brand_before={}
        for group in ['modified','added']:
            for name,record in self.brand[group].items():
                p=self.app/name
                for parent in p.parents:
                    if parent==self.app.parent: break
                    require(parent.is_dir() and not parent.is_symlink(),'Ordinary branding parents required')
                require(p.is_file() and not p.is_symlink(),'Ordinary branding file required: '+name)
                info=p.lstat()
                require(stat.S_ISREG(info.st_mode) and not info.st_mode&0o111,'Non-executable branding file required: '+name)
                actual=self.functions.before(name)
                require(len(actual)==record['after_bytes'] and hashlib.sha256(actual).hexdigest()==record['after_sha256'],'Only exact reviewed October 20 branding bytes permitted: '+name)
                expected={'after_sha256','after_bytes'} | ({'before_utf8'} if group=='modified' else set())
                require(set(record)==expected,'Bounded branding record required: '+name)
                if group=='modified': self.brand_before[name]=record['before_utf8'].encode('utf-8')
        raw=(self.root/FIXTURE).read_bytes()
        require(hashlib.sha256(raw).hexdigest()==PIN,'Immutable welcome-design fixture hash required')
        self.fixture=json.loads(raw)
        require(set(self.fixture)=={'source_commit','modified','added'} and self.fixture['source_commit']=='1d14b582b73780c020ba3d489a3a2d58cf5f45e5','Exact welcome-design source context required')
        require(set(self.fixture['modified'])==MODIFIED and set(self.fixture['added'])==WELCOME_ADDED,'Exact five modified/two added public assets required')
        for group in ['modified','added']:
            for name,record in self.fixture[group].items():
                for parent in (self.app/name).parents:
                    if parent==self.app.parent: break
                    require(parent.is_dir() and not parent.is_symlink(),'Ordinary welcome-design parents required')
                p=self.app/name
                require(p.exists() or p.is_symlink(),'Ordinary non-executable welcome-design file required: '+name)
                info=p.lstat()
                require(stat.S_ISREG(info.st_mode) and not info.st_mode&0o111 and not p.is_symlink(),'Ordinary non-executable welcome-design file required: '+name)
                actual=self.brand_before.get(name,self.functions.before(name))
                require(len(actual)==record['after_bytes'] and hashlib.sha256(actual).hexdigest()==record['after_sha256'],'Only exact reviewed welcome-design bytes permitted: '+name)
                expected={'after_sha256','after_bytes'}
                if group=='modified': expected.add('before_git_blob' if name.startswith('assets/icons/') else 'before_utf8')
                require(set(record)==expected,'Bounded welcome-design record required: '+name)
        self.paths=frozenset(PREFIX+n for n in MODIFIED | ADDED | FUNCTION_MODIFIED)

    def before(self,name):
        require(name not in ADDED,'Added design asset has no historical preimage')
        if name not in MODIFIED: return self.functions.before(name)
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
        for name,data in self.functions.preimages.items(): (destination/name).write_bytes(data)
        for name in MODIFIED: (destination/name).write_bytes(self.before(name))
        for name in ADDED:
            p=destination/name
            record=self.functions.fixture['added'].get(name) or self.brand['added'].get(name) or self.brand['modified'].get(name) or self.fixture['added'][name]
            require(hashlib.sha256(p.read_bytes()).hexdigest()==record['after_sha256'],'Only copied exact added asset may be removed')
            p.unlink()
