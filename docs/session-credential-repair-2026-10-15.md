# Password-change session revocation

The existing application checks the account ID and active status on each private request, but a password change or reset leaves sessions on other browsers authenticated. This repair binds each successful sign-in to the exact stored credential used at authentication. A changed password hash causes older sessions to require fresh sign-in at their next authenticated lookup, including the optional account lookup on public pages.

The session stores a random per-session nonce and an HMAC-SHA256 fingerprint of a domain marker, account ID and stored password hash. The password and its stored hash are not copied into the session or audit log. No account fields, roles, owner settings, content, invitations or private records are migrated by installation. The sole designated owner keeps all existing master-admin authority.

Existing sessions without this binding must sign in once after installation. Automatically attaching a current credential to an old session would incorrectly preserve access after an earlier reset. New sign-ins, invitation activation and initial account setup receive the binding through the existing central login helper. A password reset keeps its existing sign-in redirect and does not authenticate the bearer.

An ordinary password change rechecks the old credential against the current account under the existing users-store lock. It returns the exact updated account snapshot and binds only the submitting browser to it. This browser gets a new session ID and CSRF token while keeping its original 12-hour absolute expiry. Other sessions are rejected on their next lookup. The existing 30-minute idle expiry, 15-minute session-ID rotation, private headers and role checks remain in force.

Automatic password-hash upgrades at sign-in also return and bind the updated snapshot. An expected-hash and active-account comparison prevents a delayed rehash from overwriting a concurrent reset or account deactivation. Hash upgrades also require other sessions to sign in again because the stored hash changes.

The runtime scope is exactly four files: `lib/session-lifetime.php`, `lib/bootstrap.php`, `member/login.php` and `member/password.php`. `member/activate.php`, `member/reset-password.php`, account permissions and owner configuration remain byte-for-byte unchanged. Rollout must verify all four exact source files and install the helper before its consumers. This is separate from the earlier four-file timecard/token/skip-link release.

Verification uses temporary synthetic accounts only: a socket-free PHP credential contract and real PHP HTTP routes with separate browser cookie jars. Coverage includes current-browser retention, other-browser rejection, anonymous and signed-in resets, legacy/tampered sessions, automatic rehash, concurrent reset/deactivation, ID/CSRF rotation, original absolute expiry, unchanged account fields and preserved editorial content. A prior-source negative control must reproduce stale-session access. Real staff acceptance and the host's exact preimage still require separate verification; local source checks do not establish production installation.

Revocation takes effect when an authenticated lookup next checks the current account. It does not cancel a request that was already authorized, and it does not change the separate reset-token lifecycle or cross-store transaction behavior.
