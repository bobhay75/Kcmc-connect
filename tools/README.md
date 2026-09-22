# KCMC operational tools

## Post-deploy production smoke check

After **Update from Remote** and **Deploy HEAD Commit** in cPanel, run the read-only KCMC production smoke check from the repository checkout:

```bash
cd /home/bobsome1/repositories/Kcmc-connect-live
bash tools/production-smoke.sh
```

The default target is:

```text
https://bobsome1.com/kcmc-connect
```

A different HTTPS deployment can be supplied explicitly:

```bash
bash tools/production-smoke.sh https://example.org/kcmc-connect
```

### What it verifies

The smoke check performs GET requests only and verifies:

- the public KCMC Connect homepage is responding;
- public prayer-approval copy uses the role-based **Pastor administrator** wording;
- baseline security headers are present;
- the web-app manifest is live;
- the expected service-worker cache release marker is live;
- signed-out member and administrator routes redirect to member sign-in;
- Release Health, Content Restore, and Audit History remain protected when signed out;
- `config.php`, direct JSON data, private account data, and backups are not publicly readable.

A healthy deployment exits with status `0` and ends with:

```text
Result: 14 passed, 0 failed.
```

Any failed check exits nonzero and prints the specific failed gate. The script uses bounded connection/request timeouts and accepts HTTPS targets only.

### CI coverage

GitHub Actions does not run the smoke check against production. Instead, CI checks the script source and executes it against a mocked `curl` implementation that simulates:

- a healthy deployment;
- stale named-person prayer wording;
- login redirects;
- blocked private paths;
- rejection of a non-HTTPS target.

This keeps CI deterministic while preserving a single manual command for the real post-cPanel deployment check.
