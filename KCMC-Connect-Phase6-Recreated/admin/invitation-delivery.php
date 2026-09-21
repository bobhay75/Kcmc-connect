<?php
// Include-only view. A direct request must not render controls or fixture data.
if (!defined('KCMC_ROOT') || !isset($delivery, $current) || !is_array($delivery)) {
    http_response_code(404);
    exit;
}
?>
<section class="portal-card portal-section invite-delivery" data-invitation-delivery aria-labelledby="inviteDeliveryTitle">
  <p class="eyebrow">ONE PERSON • ONE PRIVATE LINK</p>
  <h2 id="inviteDeliveryTitle"><?=!empty($inviteSendSuccess) ? 'Invitation email submitted' : 'Invitation ready — not emailed'?></h2>
  <div class="invite-recipient">
    <strong data-invite-name><?=kcmc_h($delivery['name'])?></strong>
    <span data-invite-email><?=kcmc_h($delivery['email'])?></span>
    <span><?=kcmc_h($delivery['role'])?></span>
    <small>Expires <?=kcmc_h($delivery['expires_label'])?></small>
  </div>
  <p><?=!empty($inviteSendSuccess) ? 'The configured server mail transport accepted this invitation. Keep this page open until you have independently confirmed receipt; the private link is not shown again after you leave or refresh.' : 'Keep this page open until you have copied the invitation. The private link is not shown again after you leave or refresh.'?></p>
  <label class="invite-confirm" data-invite-confirm-label hidden>
    <input type="checkbox" data-invite-confirm>
    <span>I checked the recipient: send only to <strong><?=kcmc_h($delivery['name'])?></strong> at <strong><?=kcmc_h($delivery['email'])?></strong>.</span>
  </label>
  <div class="invite-actions" data-invite-actions hidden>
    <button class="btn gold" type="button" data-copy-invitation="message" disabled>Copy invitation email</button>
    <button class="btn secondary" type="button" data-copy-invitation="link" disabled>Copy link only</button>
  </div>
  <p class="invite-status" data-invite-status role="status" aria-live="polite" aria-atomic="true"><?=!empty($inviteSendSuccess) ? 'Server mail accepted the invitation. This does not prove inbox delivery; confirm receipt before relying on it.' : 'Nothing has been emailed. Check the name and email address before sending.'?></p>
  <div class="invite-actions" data-invite-compose hidden>
    <a class="btn gold" data-invite-gmail data-compose-url="<?=kcmc_h($delivery['gmail_url'])?>" role="link" aria-disabled="true" tabindex="-1" target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer">Open Gmail</a>
    <a class="btn secondary" data-invite-mail data-compose-url="<?=kcmc_h($delivery['email_url'])?>" role="link" aria-disabled="true" tabindex="-1">Open another email app</a>
  </div>
  <p><?=!empty($inviteSendSuccess) ? 'Manual copy and email controls remain available only as a fallback if the recipient does not receive the server-submitted message. Avoid sending a duplicate unless needed.' : 'Copy the email above, open Gmail, paste it into the message body, verify '?><strong>To: <?=kcmc_h($delivery['email'])?></strong><?=!empty($inviteSendSuccess) ? '' : ', then click '?><?php if (empty($inviteSendSuccess)): ?><strong>Send</strong>. The private link is not placed in Gmail’s address bar. This page cannot confirm delivery.<?php endif; ?></p>
  <details class="invite-manual" data-invite-manual>
    <summary>Show email and link / copy manually</summary>
    <p>No email window? Open <a href="https://mail.google.com/" target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer">Gmail</a> in a new tab, click Compose, and use these fields. On a computer, select text and press Ctrl+C (Command+C on Mac). On a phone, touch and hold, then Copy.</p>
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
</section>
