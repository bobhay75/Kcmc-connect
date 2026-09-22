'use strict';
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

const root = path.join(__dirname, '../KCMC-Connect-Phase6-Recreated');
const client = fs.readFileSync(path.join(root, 'member/push-settings.js'), 'utf8');
const worker = fs.readFileSync(path.join(root, 'sw.js'), 'utf8');
const page = fs.readFileSync(path.join(root, 'member/notifications.php'), 'utf8');
const api = fs.readFileSync(path.join(root, 'api/push-subscription.php'), 'utf8');

assert.match(client, /enable\?\.addEventListener\('click'/, 'permission path must start from explicit Enable click');
assert.match(client, /Notification\.requestPermission\(\)/, 'browser permission is requested');
assert.match(client, /pushManager\.subscribe\(/, 'PushManager subscription is created');
assert.match(client, /action:\s*'unsubscribe'/, 'client supports unsubscribe');
assert.doesNotMatch(client, /localStorage|sessionStorage|sendBeacon|XMLHttpRequest/, 'push client stores no subscription secrets locally');
assert.match(worker, /addEventListener\('push'/, 'service worker handles push events');
assert.match(worker, /showNotification\(/, 'service worker displays a user-visible notification');
assert.match(worker, /addEventListener\('notificationclick'/, 'service worker handles notification clicks');
assert.match(worker, /(?:member|admin|api|data|backups)/, 'notification targets exclude private paths');
assert.match(page, /Push notifications are not enabled on the KCMC server yet/, 'page fails closed when server push is unconfigured');
assert.match(api, /kcmc_require_login\(\)/, 'subscription API requires an authenticated user');
assert.match(api, /kcmc_verify_csrf/, 'subscription API requires CSRF validation');
assert.doesNotMatch(page, /private_key|VAPID_PRIVATE|push_vapid_private/i, 'private VAPID material is never rendered');
console.log('Push subscription client contract checks passed.');
