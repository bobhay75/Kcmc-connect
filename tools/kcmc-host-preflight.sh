#!/usr/bin/env bash
# Read-only: explicit runtime allowlist, no application bootstrap or network.
set -u
printf '%s\n' 'KCMC read-only host preflight'
if command -v php >/dev/null 2>&1; then
  php -n -r 'echo "PHP ", PHP_VERSION, " (configuration not loaded)\n";'
else
  printf '%s\n' 'PHP unavailable on PATH'
fi
if ! command -v python3 >/dev/null 2>&1; then
  printf '%s\n' 'Python 3 unavailable; file/ref checks not run'
else
python3 - <<'PY'
import hashlib, os, stat, subprocess, sys
from pathlib import Path

APP = Path('/home/bobsome1/public_html/kcmc-connect')
REPO = Path('/home/bobsome1/repositories/Kcmc-connect-live')
APPROVED = '61c70f590735522adbfd6be02dab6888924a54fd'
PREFIX = 'KCMC-Connect-Phase6-Recreated/'
FILES = '''index.php
public-presentation.js
public-presentation.css
sw.js
admin/publication-designer.php
admin/publication-projects.php
assets/visuals/kcmc-congregation-gathering.jpg
assets/visuals/kcmc-family-outdoor-event.jpg
assets/visuals/kcmc-bridge-logo.jpg
assets/visuals/kcmc-kids-safari.jpg
assets/visuals/kcmc-kids-game-room.jpg
assets/visuals/kcmc-kids-summer-group.jpg
assets/visuals/kcmc-church-wordmark.jpg
assets/visuals/kcmc-bridge-wordmark.png
assets/visuals/kcmc-bridge-logo-composite.png
admin/index.php
admin/publication-media.php
admin/health.php
admin/audit.php
admin/timecards.php
member/timeclock.php
member/login.php
care.php
assets/visuals/kcmc-ministry-group.jpg
assets/visuals/kcmc-building-2024.webp
assets/visuals/kcmc-worship-2017.webp
assets/visuals/kcmc-stage-2014.webp'''.splitlines()

print('PYTHON', sys.version.split()[0])
print('APP', APP)
print('REPO', REPO)
print('APPROVED', APPROVED)

def safe_path(path):
    for part in [*reversed(path.parents), path]:
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise ValueError('SYMLINK_REFUSED')
    return info

git_env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
git_env.update(GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0')
def git(*args):
    return subprocess.run(['git', '--no-optional-locks', '-c', 'core.fsmonitor=false',
        '-c', 'core.hooksPath=/dev/null', '-c', 'status.renames=false', '-C', str(REPO), *args],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=git_env, timeout=20)

repo_ok = False
source_ok = False
try:
    safe_path(REPO)
    safe_path(REPO / '.git')
    if not (REPO / '.git').is_dir():
        raise ValueError('NON_DIRECTORY_GIT_REFUSED')
    for label, ref in [('HEAD', 'HEAD'), ('MAIN', 'refs/heads/main'),
                       ('ORIGIN_MAIN_LOCAL', 'refs/remotes/origin/main')]:
        result = git('rev-parse', '--verify', ref + '^{commit}')
        print(label, result.stdout.decode().strip() if result.returncode == 0 else 'UNAVAILABLE')
    branch = git('symbolic-ref', '--short', '-q', 'HEAD')
    print('BRANCH', branch.stdout.decode().strip() if branch.returncode == 0 else 'DETACHED_OR_UNAVAILABLE')
    repo_ok = True
    source_ok = git('cat-file', '-e', APPROVED + '^{commit}').returncode == 0
    print('APPROVED_OBJECT_LOCAL', 'YES' if source_ok else 'NO; no fetch performed')
    status = git('status', '--porcelain=v1', '--untracked-files=no', '--',
                 *[PREFIX + name for name in FILES])
    print('SCOPED_TRACKED_WORKTREE', status.stdout.decode().strip() or
          ('CLEAN' if status.returncode == 0 else 'UNAVAILABLE'))
except (OSError, ValueError, subprocess.SubprocessError) as error:
    print('REPO_CHECK', str(error) if isinstance(error, ValueError) else type(error).__name__)

for name in FILES:
    try:
        path = APP / name
        before = safe_path(path)
        mode = format(stat.S_IMODE(before.st_mode), '04o')
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            print('FILE', name, 'mode=' + mode, 'NON_REGULAR_OR_HARDLINK_REFUSED')
            continue
        digest = hashlib.sha256()
        with open(path, 'rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
        after = safe_path(path)
        if (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
            print('FILE', name, 'CHANGED_DURING_READ')
            continue
        state = 'SOURCE_UNAVAILABLE'
        if repo_ok and source_ok:
            source = git('cat-file', 'blob', APPROVED + ':' + PREFIX + name)
            if source.returncode == 0:
                state = 'MATCH_APPROVED' if hashlib.sha256(source.stdout).hexdigest() == digest.hexdigest() else 'DIFF_APPROVED'
        print('FILE', name, 'mode=' + mode, 'bytes=' + str(after.st_size),
              'sha256=' + digest.hexdigest(), state)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print('FILE', name, str(error) if isinstance(error, ValueError) else type(error).__name__)
print('Read-only preflight complete. No deployment, fetch, or application/data operation performed.')
PY
fi
