"""Exact functional delta; historical proof preimages only, never live writes."""
from pathlib import Path
import hashlib
import json
import stat

ROOT=Path(__file__).resolve().parents[1]
PREFIX='KCMC-Connect-Phase6-Recreated/'
FIXTURE='tests/fixtures/tony-functions-20261020-reviewed.json'
PIN='da2d61f88ac3c345347a27cd9b2ff937cc1c9f88fdc55e0fbf211695554713ad'
MODIFIED=frozenset(['admin/connections.php', 'admin/index.php', 'admin/save.php', 'api/connection.php', 'app.js', 'assets/visuals/SOURCE.md', 'bulletin.php', 'events.php', 'home-welcome.css', 'index.php', 'lib/visitor-welcome.php', 'public-presentation.js', 'sw.js'])
ADDED=frozenset(['assets/visuals/kcmc-front-porch-official.jpg', 'lib/public-features.php'])

def require(ok,message):
    if not ok: raise AssertionError(message)

class FunctionalLayer:
    def __init__(self,root=ROOT):
        self.root=Path(root).resolve();self.app=self.root/PREFIX
        raw=(self.root/FIXTURE).read_bytes()
        require(hashlib.sha256(raw).hexdigest()==PIN,'Exact immutable Tony functional fixture required')
        self.fixture=json.loads(raw)
        require(set(self.fixture)=={'source_commit','modified','added'} and self.fixture['source_commit']=='cac1420a905bba78a4a54651c69a8e77b57b2450','Exact functional source context required')
        require(set(self.fixture['modified'])==MODIFIED and set(self.fixture['added'])==ADDED,'Exact bounded functional membership required')
        self.preimages={}
        for group in ['modified','added']:
            for name,record in self.fixture[group].items():
                target=self.app/name
                for parent in target.parents:
                    if parent==self.app.parent: break
                    require(parent.is_dir() and not parent.is_symlink(),'Ordinary functional source parents required')
                require(target.is_file() and not target.is_symlink(),'Ordinary functional source required: '+name)
                info=target.lstat()
                require(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and not info.st_mode&0o111,'Non-executable ordinary functional source required: '+name)
                actual=target.read_bytes()
                require(set(record)==({'after_sha256','after_bytes','before_utf8'} if group=='modified' else {'after_sha256','after_bytes'}),'Bounded functional record required')
                require(len(actual)==record['after_bytes'] and hashlib.sha256(actual).hexdigest()==record['after_sha256'],'Only exact Tony functional bytes permitted: '+name)
                if group=='modified':self.preimages[name]=record['before_utf8'].encode('utf-8')
        self.paths=frozenset(PREFIX+n for n in MODIFIED|ADDED)
    def before(self,name):
        require(name not in ADDED,'Added functional source has no historical preimage')
        require(isinstance(name,str) and all(part and part not in ('.','..') for part in name.split('/')),'Bounded functional source name required')
        return self.preimages[name] if name in self.preimages else (self.app/name).read_bytes()
