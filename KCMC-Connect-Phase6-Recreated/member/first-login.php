<?php
require_once __DIR__ . '/../lib/bootstrap.php';
kcmc_private_headers();

http_response_code(410);
?><!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><meta name="referrer" content="no-referrer"><title>Pastor Account Setup • KCMC Connect</title><link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css?v=3.0.0'))?>"></head>
<body class="portal-body"><main class="portal-shell portal-narrow">
  <a class="portal-back" href="<?=kcmc_h(kcmc_url('member/login.php'))?>">← Regular sign in</a>
  <section class="portal-card">
    <p class="eyebrow">KCMC CONNECT • ACCOUNT SETUP</p>
    <h1>Use your personal invitation.</h1>
    <p class="portal-lead">The shared pastor first-sign-in code has been retired. Pastor administrator accounts are now created only from a recipient-bound, one-time invitation issued through the KCMC Connect Access desk.</p>
    <p class="portal-alert warning">If you do not have a current invitation, ask a KCMC Connect administrator to create a new invitation for your name and email address.</p>
    <p><a class="btn gold" href="<?=kcmc_h(kcmc_url('member/login.php'))?>">Return to sign in</a></p>
  </section>
</main></body></html>
