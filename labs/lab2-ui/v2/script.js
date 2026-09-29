/* ==========================================================================
   Nexus — Version 2
   Shared behaviour for both pages. Runs on index.html and settings.html;
   each block checks for its elements before binding, so nothing errors
   on the page that does not contain them.
   ========================================================================== */

/* --------------------------------------------------------------------------
   1. Theme

   Order of precedence: a choice the user has saved, then the operating
   system preference, then dark. Storage is wrapped because browsers block
   it when a page is opened directly from the file system in some setups.
   -------------------------------------------------------------------------- */
const THEME_KEY = 'nexus-theme';

function readStoredTheme() {
  try {
    return window.localStorage.getItem(THEME_KEY);
  } catch (error) {
    return null;
  }
}

function storeTheme(theme) {
  try {
    window.localStorage.setItem(THEME_KEY, theme);
  } catch (error) {
    /* Storage unavailable — the theme still applies for this page view. */
  }
}

function currentTheme() {
  const saved = readStoredTheme();
  if (saved === 'light' || saved === 'dark') return saved;
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
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
    const theme = button.dataset.theme;
    applyTheme(theme);
    storeTheme(theme);
  });
});

/* Follow the system if the user has not chosen for themselves. */
window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', () => {
  if (!readStoredTheme()) applyTheme(currentTheme());
});

/* --------------------------------------------------------------------------
   2. Accent colour swatches (single-select group)
   -------------------------------------------------------------------------- */
const accentDots = document.querySelectorAll('.accent-dot');
accentDots.forEach((dot) => {
  dot.addEventListener('click', () => {
    accentDots.forEach((other) => other.setAttribute('aria-pressed', 'false'));
    dot.setAttribute('aria-pressed', 'true');
  });
});

/* --------------------------------------------------------------------------
   3. Home to conversation view

   This prototype shows a prepared response rather than calling an API.
   Focus moves to the response so keyboard and screen reader users are
   taken to the new content instead of being left at the input.
   -------------------------------------------------------------------------- */
const homeView = document.querySelector('#home-view');
const conversationView = document.querySelector('#conversation-view');
const askForm = document.querySelector('#ask-form');
const questionInput = document.querySelector('#question');
const askedQuestion = document.querySelector('#asked-question');
const backButton = document.querySelector('#back-button');

function showConversation(question) {
  const text = (question || '').trim();
  if (askedQuestion) {
    askedQuestion.textContent = text === '' ? 'What is due this week?' : text;
  }
  homeView.hidden = true;
  conversationView.hidden = false;
  backButton.focus();
  window.scrollTo({ top: 0 });
}

function showHome() {
  conversationView.hidden = true;
  homeView.hidden = false;
  if (questionInput) questionInput.focus();
  window.scrollTo({ top: 0 });
}

if (askForm) {
  askForm.addEventListener('submit', (event) => {
    event.preventDefault();
    showConversation(questionInput.value);
  });
}

if (backButton) {
  backButton.addEventListener('click', showHome);
}

/* Example question chips fill the input rather than submitting straight
   away, so the user can edit the wording before asking. */
document.querySelectorAll('.chip[data-question]').forEach((chip) => {
  chip.addEventListener('click', () => {
    questionInput.value = chip.dataset.question;
    questionInput.focus();
  });
});

/* Follow-up box re-runs the same prepared response. */
const followupForm = document.querySelector('#followup-form');
if (followupForm) {
  followupForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const field = document.querySelector('#followup-input');
    if (field.value.trim() !== '') {
      askedQuestion.textContent = field.value.trim();
      field.value = '';
    }
  });
}

/* --------------------------------------------------------------------------
   4. Voice input

   Uses the Web Speech API where available. Status messages are written to
   a live region so that the listening state is announced, not only shown
   through the button's colour.
   -------------------------------------------------------------------------- */
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const voiceStatus = document.querySelector('#voice-status');

function setStatus(message) {
  if (voiceStatus) voiceStatus.textContent = message;
}

function wireMicrophone(buttonId, targetInput) {
  const button = document.querySelector(buttonId);
  if (!button || !targetInput) return;

  if (!SpeechRecognition) {
    button.addEventListener('click', () => {
      setStatus('Speech recognition is not supported in this browser. Please type your question instead.');
    });
    return;
  }

  const recognition = new SpeechRecognition();
  recognition.lang = 'en-US';
  recognition.continuous = false;
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
    try {
      recognition.start();
    } catch (error) {
      /* start() throws if recognition is already running — safe to ignore. */
    }
  });
}

wireMicrophone('#mic-button', questionInput);
wireMicrophone('#followup-mic', document.querySelector('#followup-input'));
