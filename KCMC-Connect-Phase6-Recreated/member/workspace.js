(function () {
  'use strict';
  var statusNames = {open: 'Open', in_progress: 'In progress', done: 'Done'};
  var priorityRank = {high: 0, normal: 1, low: 2};
  function filteredTasks(tasks, filter) {
    return tasks.filter(function (task) {
      return filter === 'all' || (filter === 'done' ? task.status === 'done' : task.status !== 'done');
    });
  }
  function sortedTasks(tasks, sort, today) {
    function key(task) {
      var done = Number(task.status === 'done'), blocked = task.blocked ? 0 : 1;
      var date = task.due_date || '9999-99-99', bucket = !task.due_date ? 3 : task.due_date < today ? 0 : task.due_date === today ? 1 : 2;
      var priority = priorityRank[task.priority] === undefined ? 1 : priorityRank[task.priority];
      var end = [task.created_at || 0, String(task.id)];
      if (sort === 'priority') return [done, priority, blocked, bucket, date].concat(end);
      if (sort === 'due') return [done, bucket, date, blocked, priority].concat(end);
      return [done, blocked, bucket, priority, date].concat(end);
    }
    return tasks.slice().sort(function (a, b) {
      var ka = key(a), kb = key(b);
      for (var i = 0; i < ka.length; i++) { var result = typeof ka[i] === 'number' ? ka[i] - kb[i] : ka[i].localeCompare(kb[i]); if (result) return result; }
      return 0;
    });
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {filteredTasks: filteredTasks, sortedTasks: sortedTasks};
  if (typeof document === 'undefined') return;
  var root = document.getElementById('workspace');
  if (!root) return;
  var $ = function (id) { return document.getElementById(id); };
  var preferences = $('work-preferences'), editor = $('work-editor'), commentForm = $('work-comment-form');
  var state = {tasks: [], users: [], publications: [], canManage: false, selected: '', context: null,
    today: '', preferenceRevision: 0, preferencesDirty: false, initialized: false, stopped: false,
    editorKey: '', editorRevision: 0, editorDirty: false, editorDrafts: new Map(), commentDrafts: new Map(),
    comments: [], commentSignature: '', listSignature: '', statusDirty: false, mutation: false,
    timer: null, failures: 0, refreshFlight: null, networkTail: Promise.resolve(), latestRevision: -1};
  function node(tag, className, text) {
    var el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
  }
  function field(form, name) { return form.elements.namedItem(name); }
  function notice(text) { $('work-notice').textContent = text; }
  function taskById(id) { return state.tasks.find(function (task) { return task.id === id; }); }
  function contextKey(context) { return context ? context.kind + ':' + context.id : ''; }
  function currentPreferences() {
    return {view: field(preferences, 'view').value, sort: field(preferences, 'sort').value, statusfilter: field(preferences, 'statusfilter').value};
  }
  function randomNonce() {
    var bytes = new Uint8Array(18);
    if (window.crypto && window.crypto.getRandomValues) window.crypto.getRandomValues(bytes);
    else for (var i = 0; i < bytes.length; i++) bytes[i] = Math.floor(Math.random() * 256);
    return Array.from(bytes, function (n) { return n.toString(16).padStart(2, '0'); }).join('');
  }
  function safeError(error) {
    if (error.status === 401) return 'Your session ended. Sign in again, then reopen Work. Your drafts remain here until you leave this page.';
    if (error.status === 403) return 'Your workspace access changed. Reopen your account to check access. Your drafts remain here until you leave this page.';
    if (error.status === 404) return 'This task or conversation is no longer available to your account. Your draft is kept.';
    if (error.status === 409) return 'This item changed in another window. Your draft is kept.';
    if (error.status === 422) return 'Check the required fields, dates and text lengths, then try again. Your draft is kept.';
    return 'Work could not connect or save just now. Try again; your draft is kept.';
  }
  function stopForAccess(error) {
    if (error.status !== 401 && error.status !== 403) return;
    state.stopped = true;
    window.clearTimeout(state.timer);
    notice(safeError(error));
  }
  function api(action, data) {
    var run = async function () {
      if (state.stopped) { var stopped = new Error('stopped'); stopped.status = 401; throw stopped; }
      var url = new URL(root.dataset.api, window.location.href);
      var options = {credentials: 'same-origin', cache: 'no-store', headers: {'Accept': 'application/json'}};
      if (data !== undefined) {
        options.method = 'POST'; options.headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify(Object.assign({}, data, {action: action, csrf: root.dataset.csrf}));
      } else url.searchParams.set('action', action);
      var controller = new AbortController(), timeout = window.setTimeout(function () { controller.abort(); }, 20000);
      options.signal = controller.signal;
      try {
        var response = await fetch(url.toString(), options), result;
        try { result = await response.json(); } catch (_) { result = null; }
        if (!response.ok || !result || result.ok !== true) {
          var error = new Error('workspace request failed'); error.status = response.status; error.code = result && result.code;
          stopForAccess(error); throw error;
        }
        return result;
      } finally { window.clearTimeout(timeout); }
    };
    var promise = state.networkTail.then(run, run);
    state.networkTail = promise.catch(function () {});
    return promise;
  }
  function threadApi(context) {
    var original = root.dataset.api;
    var url = new URL(original, window.location.href);
    url.searchParams.set('kind', context.kind); url.searchParams.set('id', context.id);
    // api() captures its URL only when the serialized request runs, so pass an
    // action with parameters through a separate explicit request URL instead.
    return apiGetThread(url.toString());
  }
  function apiGetThread(url) {
    var run = async function () {
      if (state.stopped) { var stopped = new Error('stopped'); stopped.status = 401; throw stopped; }
      var controller = new AbortController(), timeout = window.setTimeout(function () { controller.abort(); }, 20000);
      var target = new URL(url); target.searchParams.set('action', 'thread');
      try {
        var response = await fetch(target.toString(), {credentials: 'same-origin', cache: 'no-store', headers: {'Accept': 'application/json'}, signal: controller.signal});
        var result; try { result = await response.json(); } catch (_) { result = null; }
        if (!response.ok || !result || result.ok !== true) {
          var error = new Error('workspace request failed'); error.status = response.status;
          stopForAccess(error); throw error;
        }
        return result;
      } finally { window.clearTimeout(timeout); }
    };
    var promise = state.networkTail.then(run, run); state.networkTail = promise.catch(function () {}); return promise;
  }
  function makeTaskButton(task) {
    var button = node('button', 'work-task'); button.type = 'button'; button.dataset.taskId = task.id;
    button.setAttribute('aria-pressed', String(task.id === state.selected));
    button.appendChild(node('span', 'work-task-title', task.title));
    var meta = (task.assignee_name || 'Unassigned') + ' · ' + statusNames[task.status];
    if (task.due_date) meta += ' · Due ' + task.due_date;
    button.appendChild(node('span', 'work-task-meta', meta));
    var flags = node('span', 'work-task-flags');
    if (task.priority === 'high') flags.appendChild(node('span', 'work-task-flag', 'High priority'));
    if (task.blocked) flags.appendChild(node('span', 'work-task-flag', 'Blocked'));
    if (task.status !== 'done' && task.due_date && task.due_date < state.today) flags.appendChild(node('span', 'work-task-flag overdue', 'Overdue'));
    if (task.comment_count) flags.appendChild(node('span', 'work-task-flag', task.comment_count + (task.comment_count === 1 ? ' comment' : ' comments')));
    if (flags.childNodes.length) button.appendChild(flags);
    button.addEventListener('click', function () { selectTask(task.id); });
    return button;
  }
  function renderTasks(force) {
    var prefs = currentPreferences(), tasks = sortedTasks(filteredTasks(state.tasks, prefs.statusfilter), prefs.sort, state.today);
    var signature = JSON.stringify([tasks, prefs, state.selected]);
    if (!force && signature === state.listSignature) return;
    state.listSignature = signature;
    var focusedId = document.activeElement && document.activeElement.dataset.taskId;
    var container = $('work-tasks'); container.replaceChildren(); container.setAttribute('aria-busy', 'false');
    $('work-count').textContent = tasks.length + (tasks.length === 1 ? ' task' : ' tasks');
    if (!tasks.length) { container.appendChild(node('p', 'work-empty', state.canManage ? 'No tasks in this view. Create an assignment or change Show above.' : 'No tasks in this view. Assignments shared with you will appear here.')); return; }
    if (prefs.view === 'board') {
      var board = node('div', 'work-board');
      Object.keys(statusNames).forEach(function (status) {
        var column = node('section', 'work-board-column'); column.appendChild(node('h3', '', statusNames[status]));
        var list = node('div', 'work-task-list'); tasks.filter(function (t) { return t.status === status; }).forEach(function (task) { list.appendChild(makeTaskButton(task)); });
        if (!list.childNodes.length) list.appendChild(node('p', 'work-empty', 'No tasks'));
        column.appendChild(list); board.appendChild(column);
      }); container.appendChild(board);
    } else if (prefs.view === 'timeline') {
      var schedule = node('div', 'work-schedule'), groups = new Map();
      tasks.slice().sort(function (a, b) { return (a.due_date || a.start_date || '9999-12-31').localeCompare(b.due_date || b.start_date || '9999-12-31') || String(a.title).localeCompare(String(b.title)); }).forEach(function (task) { var date = task.due_date || task.start_date || ''; if (!groups.has(date)) groups.set(date, []); groups.get(date).push(task); });
      groups.forEach(function (items, date) { schedule.appendChild(node('h3', '', date ? 'Due / scheduled ' + date : 'No date set')); var list = node('div', 'work-task-list'); items.forEach(function (task) { list.appendChild(makeTaskButton(task)); }); schedule.appendChild(list); });
      container.appendChild(schedule);
    } else {
      var list = node('div', 'work-task-list'); tasks.forEach(function (task) { list.appendChild(makeTaskButton(task)); }); container.appendChild(list);
    }
    if (focusedId) Array.from(container.querySelectorAll('[data-task-id]')).some(function (button) { if (button.dataset.taskId === focusedId) { button.focus({preventScroll: true}); return true; } return false; });
  }
  function renderDetail(switched) {
    var task = taskById(state.selected);
    $('work-detail').hidden = !task; $('work-no-selection').hidden = !!task;
    if (!task) return;
    $('work-context-title').textContent = task.title;
    var summary = $('work-task-summary'); summary.replaceChildren();
    if (task.body) summary.appendChild(node('p', 'work-detail-body', task.body));
    var meta = (task.assignee_name || 'Unassigned') + ' · ' + (task.priority || 'normal') + ' priority';
    if (task.start_date) meta += ' · Starts ' + task.start_date;
    if (task.due_date) meta += ' · Due ' + task.due_date;
    if (task.blocked) meta += ' · Blocked';
    summary.appendChild(node('p', 'work-detail-meta', meta));
    $('work-edit').hidden = !state.canManage;
    if (switched || !state.statusDirty) $('work-status').value = task.status;
    if (state.editorKey === task.id && !editor.hidden && state.editorRevision !== task.revision && state.editorDirty) $('work-editor-note').textContent = 'This task has newer details, shown above. Your unsaved draft is kept. Saving will first check its original revision.';
  }
  function editorValues() {
    var values = {};
    ['title', 'body', 'assigned_to', 'start_date', 'due_date', 'priority', 'status', 'publication_id'].forEach(function (name) { values[name] = field(editor, name).value; });
    values.blocked = field(editor, 'blocked').checked; return values;
  }
  function keepEditorDraft() {
    if (state.editorKey && state.editorDirty) {
      var previous = state.editorDrafts.get(state.editorKey), draft = {values: editorValues(), revision: state.editorRevision};
      if (previous && previous.conflictRevision !== undefined) draft.conflictRevision = previous.conflictRevision;
      state.editorDrafts.set(state.editorKey, draft);
    }
  }
  function fillPicker(picker, values, emptyLabel) {
    var previous = picker.value; picker.replaceChildren();
    var option = node('option', '', emptyLabel); option.value = ''; picker.appendChild(option);
    values.forEach(function (item) { var opt = node('option', '', item.name); opt.value = item.id; picker.appendChild(opt); });
    if (Array.from(picker.options).some(function (opt) { return opt.value === previous; })) picker.value = previous;
    else if (previous) { var missing = node('option', '', 'Previously selected — unavailable'); missing.value = previous; missing.disabled = true; picker.appendChild(missing); picker.value = previous; }
  }
  function setPickerValue(picker, value) {
    if (value && !Array.from(picker.options).some(function (option) { return option.value === value; })) {
      var unavailable = node('option', '', 'Previously assigned — unavailable'); unavailable.value = value; unavailable.disabled = true; picker.appendChild(unavailable);
    }
    picker.value = value;
  }
  function openEditor(key) {
    keepEditorDraft();
    var task = key === 'new' ? {title: '', body: '', assigned_to: '', start_date: '', due_date: '', priority: 'normal', status: 'open', blocked: false, publication_id: '', revision: 0} : taskById(key);
    if (!task || !state.canManage) return;
    var draft = state.editorDrafts.get(key), reviewConflict = draft && draft.conflictRevision !== undefined;
    // Reopening this task displays its latest details above the preserved draft.
    // A background conflict must not silently rebase a different open editor.
    if (reviewConflict && key !== 'new') { draft = {values: draft.values, revision: task.revision}; state.editorDrafts.set(key, draft); }
    var values = draft ? draft.values : task;
    state.editorKey = key; state.editorRevision = draft ? draft.revision : task.revision; state.editorDirty = !!draft;
    fillPicker(field(editor, 'assigned_to'), state.users, 'Unassigned'); fillPicker(field(editor, 'publication_id'), state.publications, 'None');
    Object.keys(values).forEach(function (name) { var input = field(editor, name); if (input) { if (name === 'blocked') input.checked = !!values[name]; else if (name === 'assigned_to' || name === 'publication_id') setPickerValue(input, values[name] || ''); else input.value = values[name] || ''; } });
    $('work-editor-heading').textContent = key === 'new' ? 'New task' : 'Edit task';
    $('work-editor-note').textContent = reviewConflict ? 'This task changed. Latest details are shown above; your draft below is unchanged. Review both, then save again to apply your draft to the latest revision.' : draft ? 'Your unsaved draft is restored.' : '';
    editor.hidden = false; field(editor, 'title').focus();
  }
  function saveCommentDraft() {
    var key = contextKey(state.context); if (!key) return;
    var existing = state.commentDrafts.get(key) || {nonce: randomNonce(), parent_id: ''};
    var body = field(commentForm, 'body').value;
    if (existing.attempted && existing.body !== body) { existing.nonce = randomNonce(); existing.attempted = false; }
    existing.body = body; state.commentDrafts.set(key, existing);
  }
  function restoreCommentDraft() {
    var draft = state.commentDrafts.get(contextKey(state.context)) || {body: '', parent_id: '', nonce: randomNonce()};
    state.commentDrafts.set(contextKey(state.context), draft); field(commentForm, 'body').value = draft.body;
    $('work-replying').hidden = !draft.parent_id;
    $('work-replying-label').textContent = draft.parent_id ? 'Replying to ' + (draft.parent_name || 'a comment') : '';
    $('work-comment-status').textContent = draft.body ? 'Your draft is kept in this tab.' : '';
  }
  function setContext(context) {
    saveCommentDraft(); state.context = context; state.comments = []; state.commentSignature = '';
    $('work-thread').hidden = !context;
    if (!context) return;
    $('work-thread-title').textContent = context.kind === 'publication' ? context.label + ' · conversation' : 'Task conversation';
    $('work-comments').replaceChildren(); $('work-thread-notice').textContent = 'Loading conversation…'; restoreCommentDraft();
  }
  function selectTask(id) {
    keepEditorDraft(); editor.hidden = true; state.selected = id; state.statusDirty = false;
    $('work-task-status').textContent = ''; $('work-publication-thread').value = '';
    var task = taskById(id); setContext(task ? {kind: 'task', id: id, label: task.title} : null);
    renderTasks(true); renderDetail(true);
    if (state.context) fetchThread().catch(function (error) { $('work-thread-notice').textContent = safeError(error); });
  }
  function renderComments(comments) {
    var signature = JSON.stringify(comments); if (signature === state.commentSignature) return;
    state.commentSignature = signature; state.comments = comments;
    var list = $('work-comments'); list.replaceChildren();
    comments.forEach(function (comment) {
      var item = node('li', 'work-comment'); item.dataset.commentId = comment.id;
      var header = node('div', 'work-comment-header'); header.appendChild(node('strong', '', comment.author_name));
      var time = node('time', '', formatTime(comment.created_at)), stamp = new Date(typeof comment.created_at === 'number' ? comment.created_at * 1000 : comment.created_at); if (!Number.isNaN(stamp.getTime())) time.dateTime = stamp.toISOString(); header.appendChild(time); item.appendChild(header);
      if (comment.parent_id) { var parent = comments.find(function (c) { return c.id === comment.parent_id; }); item.appendChild(node('p', 'work-comment-reply', 'Reply to ' + (parent ? parent.author_name : 'an earlier comment'))); }
      item.appendChild(node('p', 'work-comment-body', comment.body));
      var reply = node('button', '', 'Reply'); reply.type = 'button'; reply.addEventListener('click', function () {
        saveCommentDraft(); var draft = state.commentDrafts.get(contextKey(state.context)); if (draft.attempted && draft.parent_id !== comment.id) { draft.nonce = randomNonce(); draft.attempted = false; } draft.parent_id = comment.id; draft.parent_name = comment.author_name;
        restoreCommentDraft(); field(commentForm, 'body').focus();
      }); item.appendChild(reply); list.appendChild(item);
    });
    $('work-thread-notice').textContent = comments.length ? '' : 'No comments yet.';
  }
  function formatTime(value) { var date = new Date(typeof value === 'number' ? value * 1000 : value); return Number.isNaN(date.getTime()) ? '' : date.toLocaleString(undefined, {month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'}); }
  async function fetchThread() {
    if (!state.context) return;
    var context = Object.assign({}, state.context), key = contextKey(context), result = await threadApi(context);
    if (contextKey(state.context) !== key) return;
    renderComments(Array.isArray(result.comments) ? result.comments : []);
  }
  function acceptList(result) {
    if (typeof result.revision === 'number' && result.revision < state.latestRevision) return;
    if (typeof result.revision === 'number') state.latestRevision = result.revision;
    state.tasks = Array.isArray(result.tasks) ? result.tasks : []; state.users = Array.isArray(result.users) ? result.users : [];
    state.publications = Array.isArray(result.publications) ? result.publications : []; state.canManage = result.can_manage === true;
    state.today = result.server_today || ''; state.preferenceRevision = result.preferences.revision;
    if (!state.preferencesDirty) ['view', 'sort', 'statusfilter'].forEach(function (name) { field(preferences, name).value = result.preferences[name]; });
    $('work-new').hidden = !state.canManage; $('work-publication-context').hidden = !state.canManage || !state.publications.length;
    $('work-intro').textContent = state.canManage ? 'Assign work, keep dates in view and discuss each task where it belongs.' : 'Your assignments and the conversation around them.';
    fillPicker($('work-publication-thread'), state.publications, 'Choose a publication…');
    if (state.selected && !taskById(state.selected)) {
      keepEditorDraft(); editor.hidden = true; state.selected = '';
      if (state.context && state.context.kind === 'task') { saveCommentDraft(); setContext(null); }
      notice('A task is no longer available to your account. Any unsent draft is kept in this tab.');
    }
    if (!state.canManage) { keepEditorDraft(); editor.hidden = true; $('work-edit').hidden = true; }
    renderTasks(false); renderDetail(false); state.initialized = true;
  }
  function schedule() {
    window.clearTimeout(state.timer);
    if (state.stopped || document.hidden) return;
    state.timer = window.setTimeout(poll, Math.min(60000, 10000 * Math.pow(2, state.failures)));
  }
  async function refresh(includeThread) {
    if (state.refreshFlight) return state.refreshFlight;
    state.refreshFlight = (async function () { var result = await api('list'); acceptList(result); if (includeThread && state.context) await fetchThread(); })();
    try { await state.refreshFlight; } finally { state.refreshFlight = null; }
  }
  async function poll() {
    if (document.hidden || state.stopped) return;
    if (state.mutation) { schedule(); return; }
    try { await refresh(true); state.failures = 0; if ($('work-notice').textContent === 'Loading your work…') notice(''); }
    catch (error) { state.failures = Math.min(state.failures + 1, 3); notice(safeError(error)); }
    finally { schedule(); }
  }
  async function mutate(form, operation) {
    if (state.mutation || state.stopped) { if (state.stopped) notice('Reopen your account and sign in again before saving. Your draft is kept.'); return; }
    state.mutation = true; var buttons = Array.from(form.querySelectorAll('button[type=submit]')); buttons.forEach(function (button) { button.disabled = true; });
    try { if (state.refreshFlight) { try { await state.refreshFlight; } catch (_) {} } await operation(); }
    finally { buttons.forEach(function (button) { button.disabled = false; }); state.mutation = false; schedule(); }
  }
  preferences.addEventListener('change', function () { state.preferencesDirty = true; $('work-preference-status').textContent = 'Choices not saved'; renderTasks(true); });
  preferences.addEventListener('submit', function (event) {
    event.preventDefault(); var chosen = currentPreferences(), revision = state.preferenceRevision; mutate(preferences, async function () {
      try { var result = await api('preferences', {revision: revision, preferences: chosen}); state.preferenceRevision = result.preferences.revision; state.preferencesDirty = JSON.stringify(currentPreferences()) !== JSON.stringify(chosen); $('work-preference-status').textContent = state.preferencesDirty ? 'Choices saved; your newer choices are not saved yet.' : 'Choices saved'; }
      catch (error) { if (error.status === 409) { try { await refresh(false); } catch (_) {} $('work-preference-status').textContent = 'Choices changed elsewhere. Your choices are kept; review and save again.'; } else $('work-preference-status').textContent = safeError(error); }
    });
  });
  $('work-new').addEventListener('click', function () { openEditor('new'); });
  $('work-edit').addEventListener('click', function () { openEditor(state.selected); });
  $('work-editor-close').addEventListener('click', function () { keepEditorDraft(); editor.hidden = true; });
  editor.addEventListener('input', function () { state.editorDirty = true; keepEditorDraft(); });
  editor.addEventListener('change', function () { state.editorDirty = true; keepEditorDraft(); });
  editor.addEventListener('submit', function (event) {
    event.preventDefault(); if (!editor.reportValidity()) return;
    var key = state.editorKey, values = editorValues(), revision = state.editorRevision; keepEditorDraft();
    mutate(editor, async function () {
      try {
        var payload = {task: values}; if (key !== 'new') { payload.task_id = key; payload.revision = revision; }
        var result = await api(key === 'new' ? 'create' : 'update', payload);
        if (state.editorKey === key) keepEditorDraft();
        var current = state.editorDrafts.get(key), changedDuringSave = current && JSON.stringify(current.values) !== JSON.stringify(values);
        if (changedDuringSave) {
          state.editorDrafts.set(result.task.id, {values: current.values, revision: result.task.revision});
          if (key !== result.task.id) state.editorDrafts.delete(key);
        } else state.editorDrafts.delete(key);
        if (state.editorKey === key) { state.editorKey = result.task.id; state.editorRevision = result.task.revision; state.editorDirty = !!changedDuringSave; }
        await refresh(false);
        if (state.editorKey === result.task.id && (state.selected === key || (key === 'new' && !editor.hidden)) && taskById(result.task.id)) selectTask(result.task.id);
        notice(changedDuringSave ? 'Task saved. Your newer unsaved edits are kept; open Edit task to continue.' : 'Task saved.');
      } catch (error) {
        if (error.status === 409) {
          try {
            await refresh(false); if (state.editorKey === key) keepEditorDraft();
            var latest = taskById(key), draft = state.editorDrafts.get(key) || {values: values, revision: revision};
            if (latest) {
              if (state.editorKey === key && state.selected === key && !editor.hidden) {
                state.editorRevision = latest.revision; draft.revision = latest.revision; delete draft.conflictRevision;
                $('work-editor-note').textContent = 'This task changed. Latest details are shown above; your draft below is unchanged. Review both, then save again to apply your draft to the latest revision.';
              } else {
                draft.conflictRevision = latest.revision;
                notice('A task changed while you were working elsewhere. Its unsaved draft is kept; reopen it to review the latest details.');
              }
            }
            state.editorDrafts.set(key, draft);
          } catch (_) {
            if (state.editorKey === key && !editor.hidden) $('work-editor-note').textContent = 'This task changed. Your draft is kept. Reconnect before reviewing the latest version.';
            else notice('A task changed. Its draft is kept. Reconnect before reviewing the latest version.');
          }
        } else if (state.editorKey === key && !editor.hidden) $('work-editor-note').textContent = safeError(error);
        else notice(safeError(error));
      }
    });
  });
  $('work-status').addEventListener('change', function () { state.statusDirty = true; });
  $('work-status-form').addEventListener('submit', function (event) {
    event.preventDefault(); var task = taskById(state.selected), chosen = $('work-status').value; if (!task) return;
    var id = task.id, revision = task.revision;
    mutate($('work-status-form'), async function () {
      try {
        await api('status', {task_id: id, revision: revision, status: chosen});
        if (state.selected === id && $('work-status').value === chosen) state.statusDirty = false;
        await refresh(false);
        if (state.selected === id) $('work-task-status').textContent = state.statusDirty ? 'Status saved. Your newer choice is not saved yet.' : 'Status updated.';
        else notice('Task status saved.');
      } catch (error) {
        if (error.status === 409) {
          try { await refresh(false); } catch (_) {}
          if (state.selected === id) $('work-task-status').textContent = 'Task changed. Latest details are shown; your selected status is kept. Review and update again.';
          else notice('Another task changed. Reopen it to review before updating its status.');
        } else if (state.selected === id) $('work-task-status').textContent = safeError(error);
        else notice(safeError(error));
      }
    });
  });
  $('work-publication-thread').addEventListener('change', function () {
    var id = this.value; if (!id) { if (state.selected) selectTask(state.selected); else setContext(null); return; }
    var publication = state.publications.find(function (p) { return p.id === id; }); if (!publication) return;
    setContext({kind: 'publication', id: id, label: publication.name}); fetchThread().catch(function (error) { $('work-thread-notice').textContent = safeError(error); });
  });
  commentForm.addEventListener('input', saveCommentDraft);
  $('work-reply-cancel').addEventListener('click', function () { saveCommentDraft(); var draft = state.commentDrafts.get(contextKey(state.context)); if (draft) { if (draft.attempted && draft.parent_id) { draft.nonce = randomNonce(); draft.attempted = false; } draft.parent_id = ''; draft.parent_name = ''; restoreCommentDraft(); } });
  commentForm.addEventListener('submit', function (event) {
    event.preventDefault(); if (!state.context || !commentForm.reportValidity()) return;
    saveCommentDraft(); var context = Object.assign({}, state.context), key = contextKey(context), draft = Object.assign({}, state.commentDrafts.get(key));
    state.commentDrafts.get(key).attempted = true;
    mutate(commentForm, async function () {
      try {
        await api('comment', {context: {kind: context.kind, id: context.id}, body: draft.body, parent_id: draft.parent_id, nonce: draft.nonce});
        // Do not erase words typed while the request was in flight.
        var current = state.commentDrafts.get(key);
        if (current && current.body === draft.body && current.parent_id === draft.parent_id) state.commentDrafts.delete(key);
        else if (current) current.nonce = randomNonce();
        if (contextKey(state.context) === key) { restoreCommentDraft(); $('work-comment-status').textContent = 'Comment posted.'; await fetchThread(); }
        await refresh(false);
      } catch (error) { if (contextKey(state.context) === key) $('work-comment-status').textContent = safeError(error); }
    });
  });
  document.addEventListener('visibilitychange', function () { window.clearTimeout(state.timer); if (!document.hidden && !state.stopped) poll(); });
  window.addEventListener('beforeunload', function (event) {
    saveCommentDraft(); keepEditorDraft();
    var dirty = state.editorDrafts.size > 0 || Array.from(state.commentDrafts.values()).some(function (draft) { return !!draft.body.trim(); });
    if (dirty) { event.preventDefault(); event.returnValue = ''; }
  });
  poll();
}());
