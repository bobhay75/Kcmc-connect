<?php
require_once __DIR__ . '/../lib/bootstrap.php';
kcmc_private_headers();
http_response_code(410);
?><!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><meta name="referrer" content="no-referrer"><title>First Sign-In Retired • KCMC Connect</title><link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css?v=3.0.0'))?>"></head>
<body class="portal-body"><main class="portal-shell portal-narrow">
  <a class="portal-back" href="<?=kcmc_h(kcmc_url('member/login.php'))?>">← Regular sign in</a>
  <section class="portal-card">
    <p class="eyebrow">KCMC CONNECT • FIRST SIGN-IN MOVED</p>
    <h1>Use your personal invitation.</h1>
    <p class="portal-lead">The former pastor first-sign-in process has been retired. Pastor Tony and Pastor Barry must each receive a separate, one-time invitation created by a recovery administrator for their verified email address.</p>
    <p>If you already activated your invitation, return to the regular sign-in page. Otherwise, ask the KCMC recovery administrator to issue your individual invitation from Member access.</p>
    <div class="portal-actions"><a class="btn gold" href="<?=kcmc_h(kcmc_url('member/login.php'))?>">Return to sign in</a></div>
  </section>
</main></body></html>
