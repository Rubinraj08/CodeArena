// ─── Code Editor & Submission ───

// Tab key support in textarea
const editor = document.getElementById('code-editor');
if (editor) {
  editor.addEventListener('keydown', e => {
    if (e.key === 'Tab') {
      e.preventDefault();
      const start = editor.selectionStart;
      const end = editor.selectionEnd;
      editor.value = editor.value.substring(0, start) + '    ' + editor.value.substring(end);
      editor.selectionStart = editor.selectionEnd = start + 4;
    }
  });
}

// Language templates
const TEMPLATES = {
  python: `# Write your Python solution here\n# Read input with: input()\n# Print output with: print()\n\n`,
  javascript: `// Write your JavaScript solution here\n// Read input: process.stdin (use readline)\n\n`,
  java: `import java.util.Scanner;\npublic class Solution {\n    public static void main(String[] args) {\n        Scanner sc = new Scanner(System.in);\n        // Your code here\n    }\n}\n`,
  cpp: `#include <iostream>\nusing namespace std;\nint main() {\n    // Your code here\n    return 0;\n}\n`,
  c: `#include <stdio.h>\nint main() {\n    // Your code here\n    return 0;\n}\n`
};

function setLanguage(lang, forced = false) {
  const cur = editor.value.trim();
  const defaultCodes = Object.values(TEMPLATES).map(t => t.trim());
  const isDefaultOrEmpty = !cur || defaultCodes.some(d => cur === d);

  if (forced || isDefaultOrEmpty || confirm('Switching language will reset your current code. Continue?')) {
    editor.value = TEMPLATES[lang] || '';
    document.getElementById('lang-select').value = lang;
    saveLanguage(lang);
    saveDraft(); // Save the new template as the draft
  } else {
    // Revert dropdown if cancelled
    document.getElementById('lang-select').value = currentLanguage();
  }
}

function currentLanguage() {
  return localStorage.getItem(`codearena_lang_${getTaskId()}`) || 'python';
}

function getTaskId() {
  return document.getElementById('task-id').value;
}

function saveLanguage(lang) {
  localStorage.setItem(`codearena_lang_${getTaskId()}`, lang);
}

function saveDraft() {
  localStorage.setItem(`codearena_draft_${getTaskId()}`, editor.value);
}

// ─── Initialization ───
if (editor) {
  const tid = getTaskId();
  const savedLang = localStorage.getItem(`codearena_lang_${tid}`) || 'python';
  const savedCode = localStorage.getItem(`codearena_draft_${tid}`);

  // Set language dropdown
  document.getElementById('lang-select').value = savedLang;

  // Load code
  if (savedCode) {
    editor.value = savedCode;
  } else {
    editor.value = TEMPLATES[savedLang] || TEMPLATES['python'];
  }

  // Save on change
  editor.addEventListener('input', saveDraft);
}

// Submit
let isSubmitting = false;

async function submitCode() {
  if (isSubmitting) return;
  
  const code = editor.value;
  const language = document.getElementById('lang-select').value;
  const taskId = document.getElementById('task-id').value;

  if (!code.trim()) {
    showToast('Write some code first!', 'error');
    return;
  }

  const submitBtn = document.getElementById('submit-btn');
  isSubmitting = true;
  submitBtn.disabled = true;
  submitBtn.classList.add('loading');
  submitBtn.textContent = '⏳ Evaluating...';

  const integrityData = typeof IntegrityMonitor !== 'undefined' ? IntegrityMonitor.getData() : {};

  try {
    const res = await fetch('/submit', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ code, language, task_id: taskId, ...integrityData })
    });
    const data = await res.json();
    showResults(data);
  } catch (err) {
    showToast('Submission failed. Try again.', 'error');
  } finally {
    isSubmitting = false;
    submitBtn.disabled = false;
    submitBtn.classList.remove('loading');
    submitBtn.textContent = '🚀 Submit';
  }
}

function showResults(data) {
  const modal = document.getElementById('result-modal');
  modal.classList.add('open');

  const scoreEl = document.getElementById('modal-score');
  scoreEl.textContent = Math.round(data.score) + '%';
  scoreEl.className = 'score-number ' + (data.status === 'pass' ? 'pass' : 'fail');

  document.getElementById('modal-status').textContent =
    data.status === 'pass' ? '✅ All Tests Passed!' :
    data.status === 'fail' ? '❌ Some Tests Failed' : '⚠️ Error in Code';

  document.getElementById('modal-passed').textContent = `${data.passed}/${data.total} test cases passed`;

  if (data.status === 'pass') {
    if (typeof IntegrityMonitor !== 'undefined') IntegrityMonitor.resetState();
    clearDraft();
  }

  const xpEl = document.getElementById('modal-xp');
  if (data.xp_earned > 0) {
    xpEl.textContent = `+${data.xp_earned} XP earned!`;
    xpEl.style.display = 'block';
    xpEl.className = 'alert alert-success';
  } else if (data.xp_penalty > 0) {
    xpEl.textContent = `-${data.xp_penalty} XP (Integrity Penalty)`;
    xpEl.style.display = 'block';
    xpEl.className = 'alert alert-danger';
  } else { 
    xpEl.style.display = 'none'; 
  }

  // Test results
  const list = document.getElementById('test-results-list');
  list.innerHTML = '';
  (data.results || []).forEach((r, i) => {
    const div = document.createElement('div');
    div.className = `test-result ${r.passed ? 'pass' : 'fail'}`;
    div.innerHTML = `
      <span>${r.passed ? '✅' : '❌'}</span>
      <span>Test ${i + 1}</span>
      ${!r.passed && r.error ? `<span class="text-muted text-sm">${escHtml(r.error)}</span>` : ''}
      ${!r.passed && r.actual !== undefined ? `<span class="text-muted text-sm">Got: ${escHtml(String(r.actual))}</span>` : ''}
    `;
    list.appendChild(div);
  });

  // AI Mentor
  const aiToggle = document.getElementById('ai-toggle-btn');
  const aiContainer = document.getElementById('ai-mentor-container');
  const aiContent = document.getElementById('ai-analysis-content');

  if (data.ai_analysis) {
    aiToggle.style.display = 'block';
    aiContent.innerHTML = data.ai_analysis;
  } else {
    aiToggle.style.display = 'none';
    aiContainer.style.display = 'none';
  }

  // Integrity warning
  const intWarn = document.getElementById('modal-integrity');
  if (data.is_flagged) {
    intWarn.style.display = 'block';
    intWarn.innerHTML = '⚠️ <strong>Integrity Alert:</strong> Suspicious activity detected. Your teacher will be notified.';
  } else { intWarn.style.display = 'none'; }

  // Update output pane
  updateOutputPane(data);
}

function updateOutputPane(data) {
  const pane = document.getElementById('output-content');
  if (!pane) return;
  pane.innerHTML = data.results?.map((r, i) =>
    `<div class="test-result ${r.passed ? 'pass' : 'fail'}">
      ${r.passed ? '✅' : '❌'} Test ${i+1}
      ${r.error ? ` — <span class="text-red">${escHtml(r.error)}</span>` : ''}
    </div>`
  ).join('') || '';
}

function closeModal() {
  document.getElementById('result-modal').classList.remove('open');
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function toggleAiMentor() {
  const container = document.getElementById('ai-mentor-container');
  const btn = document.getElementById('ai-toggle-btn');
  if (container.style.display === 'none') {
    container.style.display = 'block';
    btn.textContent = '🙈 Hide AI Feedback';
    container.scrollIntoView({ behavior: 'smooth' });
  } else {
    container.style.display = 'none';
    btn.textContent = '🤖 View AI Feedback';
  }
}

// Run sample (test against visible cases only)
async function runSample() {
  const btn = document.getElementById('run-btn');
  btn.disabled = true; btn.textContent = '▶ Running...';
  await submitCode();
  btn.disabled = false; btn.textContent = '▶ Run';
}
// Reset persistence on success
function clearDraft() {
  const tid = getTaskId();
  localStorage.removeItem(`codearena_draft_${tid}`);
  localStorage.removeItem(`codearena_lang_${tid}`);
}
