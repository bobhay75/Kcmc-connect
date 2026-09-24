<?php
// Include-only view. A direct request must not render controls or fixture data.
if (!defined('KCMC_ROOT') || !isset($delivery, $current) || !is_array($delivery)) {
    http_response_code(404);
    exit;
}
$inviteWasSent = !empty($inviteSendSuccess);
?>
<section class="portal-card portal-section invite-delivery" data-invitation-delivery aria-labelledby="inviteDeliveryTitle">
  <p class="eyebrow">ONE PERSON • ONE PRIVATE LINK</p>
  <h2 id="inviteDeliveryTitle"><?=$inviteWasSent ? 'Invitation sent' : 'Invitation ready — not emailed'?></h2>
  <div class="invite-recipient">
    <strong data-invite-name><?=kcmc_h($delivery['name'])?></strong>
    <span data-invite-email><?=kcmc_h($delivery['email'])?></span>
    <span><?=kcmc_h($delivery['role'])?></span>
    <small>Expires <?=kcmc_h($delivery['expires_label'])?></small>
  </div>

  <?php if ($inviteWasSent): ?>
    <p class="invite-status" role="status" aria-live="polite" aria-atomic="true">
      Invitation sent to <strong><?=kcmc_h($delivery['name'])?></strong> at <strong><?=kcmc_h($delivery['email'])?></strong>.
    </p>
    <p>The server accepted the message for delivery. Ask the recipient to check their inbox and spam/junk folder if it does not appear shortly.</p>
    <details class="invite-manual" data-invite-manual>
      <summary>Delivery problem? Show manual fallback</summary>
      <p>Use this only if the recipient does not receive the server-sent invitation. Sending it again can create a duplicate message.</p>
      <label for="inviteRecipient">Send only to</label>
      <input id="inviteRecipient" type="text" readonly value="<?=kcmc_h($delivery['email'])?>" autocomplete="off" spellcheck="false">
      <label for="inviteSubject">Email subject</label>
      <input id="inviteSubject" type="text" readonly value="<?=kcmc_h($delivery['subject'])?>" autocomplete="off" spellcheck="false">
      <label for="inviteMessage">Invitation email for <?=kcmc_h($delivery['name'])?></label>
      <textarea id="inviteMessage" data-invite-message readonly rows="12" autocomplete="off" spellcheck="false"><?=kcmc_h($delivery['message'])?></textarea>
      <label for="inviteLink">Private link for <?=kcmc_h($delivery['name'])?> only</label>
      <textarea id="inviteLink" data-invite-link readonly rows="3" autocomplete="off" spellcheck="false"><?=kcmc_h($delivery['link'])?></textarea>
    </details>
  <?php else: ?>
    <p>Nothing has been emailed. Check the recipient carefully before using the manual delivery controls.</p>
    <label class="invite-confirm" data-invite-confirm-label hidden>
      <input type="checkbox" data-invite-confirm>
      <span>I checked the recipient: send only to <strong><?=kcmc_h($delivery['name'])?></strong> at <strong><?=kcmc_h($delivery['email'])?></strong>.</span>
    </label>
    <div class="invite-actions" data-invite-actions hidden>
      <button class="btn gold" type="button" data-copy-invitation="message" disabled>Copy invitation email</button>
      <button class="btn secondary" type="button" data-copy-invitation="link" disabled>Copy link only</button>
    </div>
    <p class="invite-status" data-invite-status role="status" aria-live="polite" aria-atomic="true">Nothing has been emailed. Check the name and email address before sending.</p>
    <div class="invite-actions" data-invite-compose hidden>
      <a class="btn gold" data-invite-gmail data-compose-url="<?=kcmc_h($delivery['gmail_url'])?>" role="link" aria-disabled="true" tabindex="-1" target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer">Open Gmail</a>
      <a class="btn secondary" data-invite-mail data-compose-url="<?=kcmc_h($delivery['email_url'])?>" role="link" aria-disabled="true" tabindex="-1">Open another email app</a>
    </div>
    <details class="invite-manual" data-invite-manual>
      <summary>Show email and link / copy manually</summary>
      <label for="inviteRecipient">Send only to</label>
      <input id="inviteRecipient" type="text" readonly value="<?=kcmc_h($delivery['email'])?>" autocomplete="off" spellcheck="false">
      <label for="inviteSubject">Email subject</label>
      <input id="inviteSubject" type="text" readonly value="<?=kcmc_h($delivery['subject'])?>" autocomplete="off" spellcheck="false">
      <label for="inviteMessage">Invitation email for <?=kcmc_h($delivery['name'])?></label>
      <textarea id="inviteMessage" data-invite-message readonly rows="12" autocomplete="off" spellcheck="false"><?=kcmc_h($delivery['message'])?></textarea>
      <label for="inviteLink">Private link for <?=kcmc_h($delivery['name'])?> only</label>
      <textarea id="inviteLink" data-invite-link readonly rows="3" autocomplete="off" spellcheck="false"><?=kcmc_h($delivery['link'])?></textarea>
    </details>
    <noscript><p>JavaScript is off. Expand “Show email and link / copy manually” above. Nothing is sent automatically.</p></noscript>
  <?php endif; ?>
</section>
