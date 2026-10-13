/* ==========================================================================
   Presentation tier — views and interaction

   Renders what the API client returns and handles user input. This file
   contains no business rules: it does not decide which services to query,
   how to order results or how to word a summary. Those belong to the
   application logic tier, which is why this file only formats and displays.
   ========================================================================== */

/* --------------------------------------------------------------------------
   Theme
   -------------------------------------------------------------------------- */
const THEME_KEY = 'nexus-theme';

function readStoredTheme() {
  try { return window.localStorage.getItem(THEME_KEY); } catch (e) { return null; }
}
function storeTheme(theme) {
  try { window.localStorage.setItem(THEME_KEY, theme); } catch (e) { /* ignore */ }
}
function currentTheme() {
  const saved = readStoredTheme();
  return saved === 'light' || saved === 'dark' ? saved : 'dark';
}
function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  document.querySelectorAll('.theme-option').forEach((button) => {
    button.setAttribute('aria-pressed', String(button.dataset.theme === theme));
  });
}
applyTheme(currentTheme());

document.querySelectorAll('.theme-option').forEach((button) => {
  button.addEventListener('click', () => {
    applyTheme(button.dataset.theme);
    storeTheme(button.dataset.theme);
  });
});

const accentDots = document.querySelectorAll('.accent-dot');
accentDots.forEach((dot) => {
  dot.addEventListener('click', () => {
    accentDots.forEach((other) => other.setAttribute('aria-pressed', 'false'));
    dot.setAttribute('aria-pressed', 'true');
  });
});

/* --------------------------------------------------------------------------
   Formatting helpers
   -------------------------------------------------------------------------- */
const SOURCE_LABELS = { gmail: 'Gmail', calendar: 'Google Calendar', notion: 'Notion', slack: 'Slack', nexus: 'Nexus' };
const SOURCE_CLASSES = { gmail: 'badge-gmail', calendar: 'badge-calendar', notion: 'badge-notion', slack: 'badge-slack' };
const PRIORITY_CLASSES = { high: 'priority-high', medium: 'priority-med', low: 'priority-low' };
const PRIORITY_LABELS = { high: 'High', medium: 'Medium', low: 'Low' };

const ICONS = {
  gmail: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2.5" y="5" width="19" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></svg>',
  calendar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>',
  notion: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="4" y="3" width="16" height="18" rx="2"/><path d="M9 8v8l6-8v8"/></svg>',
  slack: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 3v8M15 13v8M3 15h8M13 9h8"/><circle cx="9" cy="15" r="2"/><circle cx="15" cy="9" r="2"/></svg>'
};

function formatDay(iso) {
  if (!iso) return 'No date';
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return 'No date';
  return when.toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' });
}

function formatTime(iso) {
  if (!iso) return '';
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return '';
  if (when.getHours() === 23 && when.getMinutes() === 59) return 'Due by end of day';
  return 'Due by ' + when.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
}

/* Text from the API is inserted with textContent, never innerHTML, so a
   value originating in an external service cannot inject markup. */
function buildTaskRow(item) {
  const row = document.createElement('li');
  row.className = `task-row ${PRIORITY_CLASSES[item.priority] || ''}`;

  const day = document.createElement('span');
  day.className = 'task-day';
  day.textContent = formatDay(item.due);

  const name = document.createElement('span');
  name.className = 'task-name';
  const icon = document.createElement('span');
  icon.className = SOURCE_CLASSES[item.source] || '';
  icon.style.display = 'contents';
  icon.innerHTML = ICONS[item.source] || '';
  const label = document.createElement('span');
  label.textContent = item.title;
  const tag = document.createElement('span');
  tag.className = 'priority-tag';
  tag.textContent = PRIORITY_LABELS[item.priority] || item.priority;
  name.append(icon, label, tag);

  const due = document.createElement('span');
  due.className = 'task-due';
  due.textContent = formatTime(item.due);

  row.append(day, name, due);
  return row;
}

/* --------------------------------------------------------------------------
   Home to conversation view
   -------------------------------------------------------------------------- */
const homeView = document.querySelector('#home-view');
const conversationView = document.querySelector('#conversation-view');
const askForm = document.querySelector('#ask-form');
const questionInput = document.querySelector('#question');
const askedQuestion = document.querySelector('#asked-question');
const summaryEl = document.querySelector('#assistant-summary');
const taskListEl = document.querySelector('#task-list');
const traceEl = document.querySelector('#trace-line');
const backButton = document.querySelector('#back-button');

function renderAnswer(answer) {
  askedQuestion.textContent = answer.question;
  summaryEl.textContent = answer.summary;

  taskListEl.replaceChildren(...answer.items.map(buildTaskRow));

  /* The trace line surfaces what the logic tier decided, which is the
     visible evidence that routing happened rather than a fixed response. */
  const trace = answer.trace || {};
  const sources = (trace.sources_used || []).map((s) => SOURCE_LABELS[s] || s);
  const parts = [];
  if (trace.intent) parts.push(`Intent: ${trace.intent}`);
  if (trace.parsed_by) parts.push(`Parsed by: ${trace.parsed_by === 'model' ? 'AI model' : 'rules'}`);
  if (sources.length) parts.push(`Queried: ${sources.join(', ')}`);
  if (typeof trace.cache_hits === 'number' && trace.cache_hits > 0) {
    parts.push(`${trace.cache_hits} from cache`);
  }
  if ((trace.sources_failed || []).length) {
    parts.push(`Unavailable: ${trace.sources_failed.join(', ')}`);
  }
  if (typeof trace.duration_ms === 'number') parts.push(`${trace.duration_ms} ms`);
  if (answer.offline) parts.push('sample data — backend not running');
  traceEl.textContent = parts.join('  ·  ');
}

async function submitQuestion(rawText) {
  const text = (rawText || '').trim() || 'What is due this week?';

  homeView.hidden = true;
  conversationView.hidden = false;
  summaryEl.textContent = 'Checking your connected apps…';
  taskListEl.replaceChildren();
  traceEl.textContent = '';
  backButton.focus();
  window.scrollTo({ top: 0 });

  /* A fixed reference date keeps the sample data meaningful regardless of
     when the prototype is opened. Remove once live services are connected. */
  const answer = await NexusAPI.ask(text, '2026-09-29');
  renderAnswer(answer);
}

if (askForm) {
  askForm.addEventListener('submit', (event) => {
    event.preventDefault();
    submitQuestion(questionInput.value);
  });
}

if (backButton) {
  backButton.addEventListener('click', () => {
    conversationView.hidden = true;
    homeView.hidden = false;
    if (questionInput) questionInput.focus();
    window.scrollTo({ top: 0 });
  });
}

document.querySelectorAll('.chip[data-question]').forEach((chip) => {
  chip.addEventListener('click', () => {
    questionInput.value = chip.dataset.question;
    questionInput.focus();
  });
});

const followupForm = document.querySelector('#followup-form');
if (followupForm) {
  followupForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const field = document.querySelector('#followup-input');
    const text = field.value.trim();
    if (text !== '') {
      field.value = '';
      submitQuestion(text);
    }
  });
}

/* --------------------------------------------------------------------------
   Voice input
   -------------------------------------------------------------------------- */
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const voiceStatus = document.querySelector('#voice-status');

function setStatus(message) {
  if (voiceStatus) voiceStatus.textContent = message;
}

function wireMicrophone(selector, targetInput) {
  const button = document.querySelector(selector);
  if (!button || !targetInput) return;

  if (!SpeechRecognition) {
    button.addEventListener('click', () => {
      setStatus('Speech recognition is not supported in this browser. Please type your question instead.');
    });
    return;
  }

  const recognition = new SpeechRecognition();
  recognition.lang = 'en-US';
  recognition.interimResults = false;

  recognition.addEventListener('start', () => {
    button.classList.add('is-listening');
    button.setAttribute('aria-pressed', 'true');
    setStatus('Listening for your question…');
  });
  recognition.addEventListener('result', (event) => {
    targetInput.value = event.results[0][0].transcript;
    setStatus('Voice question captured. Select Ask Nexus to continue.');
  });
  recognition.addEventListener('error', () => {
    setStatus('Voice input was unavailable. Please type your question instead.');
  });
  recognition.addEventListener('end', () => {
    button.classList.remove('is-listening');
    button.setAttribute('aria-pressed', 'false');
  });

  button.addEventListener('click', () => {
    try { recognition.start(); } catch (error) { /* already running */ }
  });
}

wireMicrophone('#mic-button', questionInput);
wireMicrophone('#followup-mic', document.querySelector('#followup-input'));

/* --------------------------------------------------------------------------
   Settings — connected apps are listed from the registry, not hardcoded,
   so a plugin added in the data access tier appears here with no edit.
   -------------------------------------------------------------------------- */
const connectedHost = document.querySelector('#connected-apps');

if (connectedHost) {
  NexusAPI.plugins().then((list) => {
    const rows = list.map((plugin) => {
      const row = document.createElement('div');
      row.className = 'connected-row';

      const badge = document.createElement('span');
      badge.className = `app-badge ${SOURCE_CLASSES[plugin.name] || ''}`;
      badge.setAttribute('aria-hidden', 'true');
      badge.innerHTML = ICONS[plugin.name] || '';

      const text = document.createElement('div');
      const strong = document.createElement('strong');
      strong.textContent = plugin.display_name;
      const status = document.createElement('p');
      status.textContent = plugin.connected ? 'Connected' : 'Not connected';
      text.append(strong, status);

      const toggleId = `app-${plugin.name}`;
      const wrap = document.createElement('span');
      wrap.className = 'switch';
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.id = toggleId;
      input.setAttribute('role', 'switch');
      input.checked = Boolean(plugin.connected);
      const srLabel = document.createElement('label');
      srLabel.className = 'sr-only';
      srLabel.setAttribute('for', toggleId);
      srLabel.textContent = `${plugin.display_name} connection`;
      const track = document.createElement('span');
      track.className = 'track';
      track.setAttribute('aria-hidden', 'true');
      const thumb = document.createElement('span');
      thumb.className = 'thumb';
      thumb.setAttribute('aria-hidden', 'true');
      wrap.append(input, srLabel, track, thumb);

      row.append(badge, text, wrap);
      return row;
    });
    connectedHost.replaceChildren(...rows);
  });
}

/* ==========================================================================
   Work items — create, read, update, delete

   Added in Version 4. Every change goes through the API client and the list
   is redrawn from the server's response rather than from local state, so
   what the user sees is what the database holds.
   ========================================================================== */

const itemsList = document.querySelector('#items-list');
const itemForm = document.querySelector('#item-form');
const itemsStatus = document.querySelector('#items-status');
const syncButton = document.querySelector('#sync-button');

/* The sample data sits in this week, so the prototype pins its window
   rather than using the real date. Remove once services are live. */
const WINDOW_START = '2026-09-28';
const WINDOW_END = '2026-10-05';

let currentStatus = 'open';
let editingId = null;

function setItemsStatus(message) {
  if (itemsStatus) itemsStatus.textContent = message;
}

function formatDue(iso) {
  if (!iso) return 'No due date';
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return 'No due date';
  return when.toLocaleString(undefined, {
    weekday: 'short', month: 'short', day: 'numeric',
    hour: 'numeric', minute: '2-digit'
  });
}

/* datetime-local needs "YYYY-MM-DDTHH:MM" with no zone or seconds. */
function toLocalInput(iso) {
  if (!iso) return '';
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return '';
  const pad = (n) => String(n).padStart(2, '0');
  return `${when.getFullYear()}-${pad(when.getMonth() + 1)}-${pad(when.getDate())}`
       + `T${pad(when.getHours())}:${pad(when.getMinutes())}`;
}

function buildReadRow(item) {
  const row = document.createElement('li');
  row.className = `item-row ${PRIORITY_CLASSES[item.priority] || ''}`;
  if (item.status === 'done') row.classList.add('is-done');

  // UPDATE: toggling status
  const check = document.createElement('input');
  check.type = 'checkbox';
  check.className = 'item-check';
  check.checked = item.status === 'done';
  check.id = `check-${item.id}`;
  check.addEventListener('change', () => {
    toggleStatus(item.id, check.checked ? 'done' : 'open');
  });

  const checkLabel = document.createElement('label');
  checkLabel.className = 'sr-only';
  checkLabel.setAttribute('for', check.id);
  checkLabel.textContent = `Mark "${item.title}" as ${item.status === 'done' ? 'open' : 'done'}`;

  const body = document.createElement('div');
  body.className = 'item-body';
  const title = document.createElement('div');
  title.className = 'item-title';
  title.textContent = item.title;

  const meta = document.createElement('div');
  meta.className = 'item-meta';
  const due = document.createElement('span');
  due.textContent = formatDue(item.due_at);
  const source = document.createElement('span');
  source.textContent = SOURCE_LABELS[item.source] || 'Nexus';
  const priority = document.createElement('span');
  priority.textContent = PRIORITY_LABELS[item.priority] || item.priority;
  meta.append(due, source, priority);
  body.append(title, meta);

  const actions = document.createElement('div');
  actions.className = 'item-actions';

  const edit = document.createElement('button');
  edit.type = 'button';
  edit.className = 'icon-button';
  edit.textContent = 'Edit';
  edit.setAttribute('aria-label', `Edit "${item.title}"`);
  edit.addEventListener('click', () => { editingId = item.id; refreshItems(); });

  const remove = document.createElement('button');
  remove.type = 'button';
  remove.className = 'icon-button danger';
  remove.textContent = 'Delete';
  remove.setAttribute('aria-label', `Delete "${item.title}"`);
  remove.addEventListener('click', () => removeItem(item));

  actions.append(edit, remove);
  row.append(check, checkLabel, body, actions);
  return row;
}

function buildEditRow(item) {
  const row = document.createElement('li');
  row.className = 'item-row';

  const form = document.createElement('div');
  form.className = 'item-edit';
  form.style.gridColumn = '1 / -1';

  const title = document.createElement('input');
  title.className = 'text-input';
  title.type = 'text';
  title.value = item.title;
  title.maxLength = 300;
  title.setAttribute('aria-label', 'Task title');

  const split = document.createElement('div');
  split.className = 'item-edit-row';

  const due = document.createElement('input');
  due.className = 'text-input';
  due.type = 'datetime-local';
  due.value = toLocalInput(item.due_at);
  due.setAttribute('aria-label', 'Due date and time');

  const priorityWrap = document.createElement('div');
  priorityWrap.className = 'select-wrap';
  const priority = document.createElement('select');
  priority.className = 'select-input';
  priority.setAttribute('aria-label', 'Priority');
  ['high', 'medium', 'low'].forEach((value) => {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = PRIORITY_LABELS[value];
    option.selected = item.priority === value;
    priority.append(option);
  });
  priorityWrap.append(priority);
  split.append(due, priorityWrap);

  const actions = document.createElement('div');
  actions.className = 'item-edit-actions';
  const save = document.createElement('button');
  save.type = 'button';
  save.className = 'primary-button';
  save.textContent = 'Save';
  save.addEventListener('click', () => {
    saveEdit(item.id, {
      title: title.value,
      due_at: due.value ? `${due.value}:00` : null,
      priority: priority.value
    });
  });
  const cancel = document.createElement('button');
  cancel.type = 'button';
  cancel.className = 'icon-button';
  cancel.textContent = 'Cancel';
  cancel.addEventListener('click', () => { editingId = null; refreshItems(); });
  actions.append(save, cancel);

  form.append(title, split, actions);
  row.append(form);
  return row;
}

/* READ */
async function refreshItems() {
  if (!itemsList) return;
  try {
    const items = await NexusAPI.listItems({
      start: WINDOW_START, end: WINDOW_END, status: currentStatus
    });

    if (!items.length) {
      const empty = document.createElement('li');
      empty.className = 'items-empty';
      empty.textContent = currentStatus === 'done'
        ? 'Nothing completed yet.'
        : 'No tasks here. Add one above, or sync your connected apps.';
      itemsList.replaceChildren(empty);
      setItemsStatus('');
      return;
    }

    itemsList.replaceChildren(
      ...items.map((item) => (item.id === editingId ? buildEditRow(item) : buildReadRow(item)))
    );
    setItemsStatus(`${items.length} shown`);
  } catch (error) {
    const failed = document.createElement('li');
    failed.className = 'items-empty';
    failed.textContent = 'Could not reach the server. Start the backend with: uvicorn backend.main:app --reload';
    itemsList.replaceChildren(failed);
    setItemsStatus('');
  }
}

/* CREATE */
if (itemForm) {
  itemForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const title = document.querySelector('#new-title');
    const due = document.querySelector('#new-due');
    const priority = document.querySelector('#new-priority');

    if (!title.value.trim()) return;

    setItemsStatus('Saving\u2026');
    try {
      await NexusAPI.createItem({
        title: title.value.trim(),
        due_at: due.value ? `${due.value}:00` : null,
        priority: priority.value
      });
      title.value = '';
      due.value = '';
      priority.value = 'medium';
      title.focus();
      await refreshItems();
    } catch (error) {
      setItemsStatus('Could not save that task.');
    }
  });
}

/* UPDATE */
async function toggleStatus(id, status) {
  setItemsStatus('Updating\u2026');
  try {
    await NexusAPI.updateItem(id, { status });
    await refreshItems();
  } catch (error) {
    setItemsStatus('Could not update that task.');
  }
}

async function saveEdit(id, fields) {
  if (!fields.title.trim()) {
    setItemsStatus('A task needs a title.');
    return;
  }
  setItemsStatus('Saving\u2026');
  try {
    await NexusAPI.updateItem(id, fields);
    editingId = null;
    await refreshItems();
  } catch (error) {
    setItemsStatus('Could not save those changes.');
  }
}

/* DELETE */
async function removeItem(item) {
  if (!window.confirm(`Delete "${item.title}"?`)) return;
  setItemsStatus('Deleting\u2026');
  try {
    await NexusAPI.deleteItem(item.id);
    await refreshItems();
  } catch (error) {
    setItemsStatus('Could not delete that task.');
  }
}

/* Filters */
document.querySelectorAll('.items-filters .chip[data-status]').forEach((chip) => {
  chip.addEventListener('click', () => {
    document.querySelectorAll('.items-filters .chip[data-status]').forEach((other) => {
      other.setAttribute('aria-pressed', String(other === chip));
    });
    currentStatus = chip.dataset.status;
    editingId = null;
    refreshItems();
  });
});

/* Sync */
if (syncButton) {
  syncButton.addEventListener('click', async () => {
    setItemsStatus('Syncing\u2026');
    try {
      const report = await NexusAPI.syncServices(WINDOW_START, WINDOW_END);
      const names = report.synced.map((s) => SOURCE_LABELS[s] || s);
      setItemsStatus(`Synced ${names.join(', ')}`);
      await refreshItems();
    } catch (error) {
      setItemsStatus('Could not sync. Is the backend running?');
    }
  });
}

if (itemsList) refreshItems();
