# KCMC repository reconciliation — October 15, 2026

This candidate updates only `/home/bobsome1/repositories/Kcmc-connect-live`. It never deploys to `/home/bobsome1/public_html/kcmc-connect`, reads production editorial/private records, changes owner configuration, invokes cPanel deployment, or stashes/resets/discards work. The default action, `check`, is read-only and performs no fetch.

The sole accepted starting commit is `154b779a0ea3d27a11300bfe0454f8a7c4aca355`. The exact target is the reviewed PR 139 deployment-guard merge commit, including the merged PR 135 fish source, `70134306b42fa3ecf421a0dfe7ef5d4cf3930ec8`. Later main updates do not advance this pin. Unknown HEAD, local tracked/untracked/ignored content, index changes or flags, nonstandard modes/ownership/links, alternate/sparse/shared state, unsafe configuration, unexpected origin, or failed raw-byte proof cause refusal. No mode normalization occurs. A fully clean target is a read-only no-op.

`align` may fetch only that SHA over canonical public HTTPS and fast-forward only after repeating the clean baseline proof. Hooks are disabled. The helper then verifies the complete target checkout and unchanged repository/config identity. If an attempted update cannot be verified it reports review required; it does not try to reset the repository.

## Source review

PR 135's reviewed head is `10a371c4e4e2df3617a9f4a45f8fb22d474d6434`, tree `5e180af5071b4bb59aadff0352c95659ad8e6ea4`. Its runtime scope is exactly `index.php`, `public-presentation.css`, and `sw.js`. There are 55 changed repository paths, with the remaining paths limited to supporting fixtures, tests and installer tooling.

Remote main `c925a7bca505801dd2c462f8bc3ef58a5db740d9` differs from PR 135's base `93c72f4fc430d311e01108d3a30d0561bb701c9d` in five Operations tooling/test/documentation files. Those paths have no overlap with PR 135. Merging the reviewed PR therefore retains both sets of work.

The successful host receipt verifies the `livecalendar` output hashes. The source branch uses the separately reviewed `main130` source variant. Those variants preserve their respective approved surrounding layout and calendar. The installed index and CSS are consequently not identical to the canonical source versions. A source merge is not evidence that a full application sync has been reviewed against all live customizations. The pinned PR 139 target includes the mandatory first deployment task comparing those three homepage files plus .htaccess, with explicit shell exit on refusal. Matching files allow the unchanged original task sequence; the check is not a full runtime parity proof.

## Deployment boundary

Do not use **Deploy HEAD** as part of repository alignment. Existing `.cpanel.yml` runs `rsync -a --delete` across the entire application tree. It preserves `config.php`, `data/content.json`, `data/private/`, and `backups/`, but does not preserve a host-local `.htaccess` or other host-only configuration. The source `.htaccess` contains no `KCMC_OPERATIONS_OWNER_USER_ID` setting. The scoped Operations release requires that setting in PHP web requests and deliberately never changes it. A broad sync can therefore overwrite an existing local `SetEnv` and deny owner access.

PR 135 fish source and PR 139 mandatory deployment preflight are merged. Align only a fully clean, exact approved checkout to the pinned PR 139 merge; retain scoped runtime installers. Alignment adopts the fish source and deployment guard in the repository checkout, but never deploys live application files. The guard deliberately blocks the observed canonical/live homepage and private .htaccess differences. Any future broad deployment needs a read-only inventory of host-specific configuration and runtime differences. It must stop on an unknown difference rather than replace or delete it.

The 37 temporary real-Git tests cover default/read-only check, clean fast-forward, target no-op, modes, flags, edits, ignored/untracked files, origin/configuration guards, failed fetch, concurrency drift, disabled hooks, restrictive umask, safe diagnostics, and post-update uncertainty. They perform no production or network operation.
