/* ==========================================================================
   Presentation tier — API client

   The ONLY file in the front end that knows the backend exists. Views call
   these functions and receive plain objects; they never build a URL or
   handle a response code. Moving the backend, changing a route or adding
   authentication is a change to this file alone.

   When the API is unreachable — which is the case if index.html is opened
   directly from the file system with no server running — each function
   falls back to a bundled sample response so the interface still renders.
   The fallback is a development convenience, not a second source of truth.
   ========================================================================== */

const NexusAPI = (() => {
  const BASE_URL = 'http://127.0.0.1:8000';
  const TIMEOUT_MS = 4000;

  let online = null; // null = not yet determined

  /* Sample response used when the backend is not running. Mirrors the
     shape of POST /api/ask exactly, so the views need no special case. */
  const SAMPLE_ANSWER = {
    question: 'What is due this week?',
    summary: 'You have 9 items across Google Calendar, Gmail, Notion and Slack. 3 are marked as high priority.',
    items: [
      { item_id: 'msg-8841', source: 'gmail', title: 'Review contract feedback from Sarah', due: '2026-09-28T17:00:00', priority: 'high' },
      { item_id: 'evt-301', source: 'calendar', title: 'Design Sync with Product Team', due: '2026-09-29T10:30:00', priority: 'medium' },
      { item_id: 'pg-5512', source: 'notion', title: 'Update Q3 roadmap documentation', due: '2026-09-29T23:59:00', priority: 'low' },
      { item_id: 'msg-8902', source: 'gmail', title: 'Follow up on outstanding team invoices', due: '2026-09-30T12:00:00', priority: 'medium' },
      { item_id: 'pg-5530', source: 'notion', title: 'Submit weekly progress report', due: '2026-10-01T16:00:00', priority: 'high' },
      { item_id: 'evt-318', source: 'calendar', title: 'Weekly Standup & Retrospective', due: '2026-10-02T16:00:00', priority: 'low' },
      { item_id: 'msg-8915', source: 'gmail', title: 'Conference travel approval', due: '2026-10-03T09:00:00', priority: 'low' },
      { item_id: 'msg-C04-1771', source: 'slack', title: 'Unanswered mention in #product-design', due: '2026-09-29T09:15:00', priority: 'medium' },
      { item_id: 'msg-C09-1802', source: 'slack', title: 'Deployment window confirmation needed in #engineering', due: '2026-10-01T11:00:00', priority: 'high' }
    ],
    trace: {
      intent: 'week_overview',
      parsed_by: 'rules',
      sources_used: ['calendar', 'gmail', 'notion', 'slack'],
      sources_failed: [],
      cache_hits: 0,
      item_count: 9,
      duration_ms: 0
    },
    offline: true
  };

  const SAMPLE_PLUGINS = [
    { name: 'calendar', display_name: 'Google Calendar', kind: 'calendar', connected: true },
    { name: 'gmail', display_name: 'Gmail', kind: 'mail', connected: true },
    { name: 'notion', display_name: 'Notion', kind: 'notes', connected: true },
    { name: 'slack', display_name: 'Slack', kind: 'chat', connected: true }
  ];

  /* Wraps fetch with a timeout so a missing backend fails in four seconds
     rather than leaving the interface waiting indefinitely. */
  async function request(path, options = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
    try {
      const response = await fetch(BASE_URL + path, {
        ...options,
        signal: controller.signal,
        headers: { 'Content-Type': 'application/json', ...(options.headers || {}) }
      });
      if (!response.ok) {
        throw new Error(`API returned ${response.status}`);
      }
      online = true;
      return await response.json();
    } finally {
      clearTimeout(timer);
    }
  }

  async function ask(question, today = null) {
    const body = today ? { question, today } : { question };
    try {
      return await request('/api/ask', { method: 'POST', body: JSON.stringify(body) });
    } catch (error) {
      online = false;
      return { ...SAMPLE_ANSWER, question: question || SAMPLE_ANSWER.question };
    }
  }

  async function plugins() {
    try {
      return await request('/api/plugins');
    } catch (error) {
      online = false;
      return SAMPLE_PLUGINS;
    }
  }

  async function history(limit = 10) {
    try {
      return await request(`/api/history?limit=${limit}`);
    } catch (error) {
      online = false;
      return [];
    }
  }

  function isOnline() {
    return online;
  }

  /* ---- Work items: the four CRUD verbs plus sync ----
     Each returns parsed JSON, or throws so the caller can show a message.
     Unlike ask() these do not fall back to sample data: a create that
     silently did nothing would be worse than an honest failure. */

  async function listItems({ start, end, status = 'open', source } = {}) {
    const params = new URLSearchParams({ status });
    if (start) params.set('start', start);
    if (end) params.set('end', end);
    if (source) params.set('source', source);
    return request(`/api/items?${params.toString()}`);
  }

  async function createItem(item) {
    return request('/api/items', { method: 'POST', body: JSON.stringify(item) });
  }

  async function updateItem(id, fields) {
    return request(`/api/items/${id}`, { method: 'PATCH', body: JSON.stringify(fields) });
  }

  async function deleteItem(id) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
    try {
      const response = await fetch(`${BASE_URL}/api/items/${id}`, {
        method: 'DELETE', signal: controller.signal
      });
      if (!response.ok) throw new Error(`API returned ${response.status}`);
      online = true;
      return true;
    } finally {
      clearTimeout(timer);
    }
  }

  async function syncServices(start, end) {
    return request('/api/sync', { method: 'POST', body: JSON.stringify({ start, end }) });
  }

  return {
    ask, plugins, history, isOnline,
    listItems, createItem, updateItem, deleteItem, syncServices
  };
})();
