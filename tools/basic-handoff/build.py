#!/usr/bin/env python3
"""Create a review-only, clean-directory basic KCMC handoff candidate.

Never reads or writes the live host; not an installer or a migration tool.
"""
import argparse
import shutil
from pathlib import Path

source = Path(__file__).resolve().parents[2] / 'KCMC-Connect-Phase6-Recreated'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('destination', type=Path, help='A new, empty local directory')
args = parser.parse_args()
dest = args.destination.absolute()
if dest.exists() or dest == source or source in dest.parents or dest in source.parents:
    parser.error('destination must not exist or contain the source tree')
if any(p.is_symlink() for p in source.rglob('*')):
    parser.error('source contains symlinks; inspect before building')

def ignore(directory, names):
    relative = Path(directory).relative_to(source)
    excluded = set()
    if relative == Path('.'):
        excluded.update({'config.php', 'backups', 'SETUP-CREDENTIALS.txt', 'DEPLOY.md', 'ICON-REPAIR.md', 'PHASE6-COMMIT.txt', 'RELEASE-MANIFEST.txt', 'RELEASE_NOTES.md', 'README.md'})
    if relative == Path('data'):
        excluded.add('private')
    return excluded.intersection(names)

shutil.copytree(source, dest, ignore=ignore)
allow = {
    'admin': {'index.php','home.php','login.php','setup.php','save.php','posts.php','event-create.php','connections.php','connections-export.php','rsvps.php','rsvps-export.php','event-descriptions.js','publishing-desk.js'},
    'member': {'login.php','logout.php'},
    'api': {'content.php','connection.php','rsvp.php'},
}
for folder, keep in allow.items():
    for item in (dest / folder).iterdir():
        if item.name not in keep:
            if item.is_dir(): shutil.rmtree(item)
            else: item.unlink()
for name in ['payroll.php','timeclock.php','team-workspace.php','publication-drafts.php','prayer-care.php','push-subscriptions.php','invitation-delivery.php','invitation-mailer.php','password-lifecycle.php']:
    (dest / 'lib' / name).unlink(missing_ok=True)
(dest / 'HANDOFF-STATUS.txt').write_text('REVIEW CANDIDATE ONLY. Not production-ready. Do not deploy or overwrite live data.\n')
print(f'Created review candidate: {dest}')
