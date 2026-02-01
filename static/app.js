/**
 * Reflect AI - Mindful Journaling App
 */

const PROMPTS = {
  free: { placeholder: 'Begin writing... Let your thoughts flow freely.' },
  gratitude: { placeholder: 'Today I\'m grateful for...\n\n1. \n2. \n3. ' },
  reflection: { placeholder: 'Today\'s highlights:\n\nWhat went well:\n\nWhat I learned:' },
  goals: { placeholder: 'My intentions:\n\n1. \n2. \n3. ' },
  emotions: { placeholder: 'Right now I\'m feeling...\n\nThis connects to...' }
};

const FALLBACK_QUOTES = [
  { text: 'In stillness, we find clarity.', sub: 'Take a breath.' },
  { text: 'Every thought has value.', sub: 'Your reflections matter.' },
  { text: 'Growth happens in quiet moments.', sub: 'Each entry is progress.' }
];

const MOOD_EMOJIS = { very_positive: '😊', positive: '🙂', neutral: '😌', negative: '😔', very_negative: '😢' };
const MOOD_LABELS = { very_positive: 'Joyful', positive: 'Content', neutral: 'Balanced', negative: 'Reflective', very_negative: 'Processing' };

// Initialize theme from localStorage
function initTheme() {
  const savedTheme = localStorage.getItem('theme') || 'light';
  if (savedTheme === 'dark') {
    document.body.classList.add('dark-theme');
    const btn = $('#themeToggle');
    if (btn) btn.textContent = '☀️';
  }
}

const state = {
  cursor: new Date(),
  selectedDate: null,
  view: 'month',
  draft: { text: '', photos: [], tags: [] },
  original: { text: '', photos: [], tags: [] }, // Track original state for change detection
  data: { entries: {} },
  stats: null,
  undo: null,
  savedMood: null,
  nudges: [] // Quick notes for generating entry
};

const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);
const pad = n => String(n).padStart(2, '0');
const dateKey = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const escapeHtml = s => { const d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; };
const formatMonthYear = d => d.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
const formatFullDate = d => d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });
const getDaysInMonth = d => new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate();
const getFirstDayOfMonth = d => new Date(d.getFullYear(), d.getMonth(), 1).getDay();

function showToast(msg, dur = 3000) {
  const t = $('#toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), dur);
}

// Modal functions
let modalResolve = null;

function showModal(title, message, { showInput = false, showCancel = true, defaultValue = '', confirmText = 'OK', cancelText = 'Cancel' } = {}) {
  return new Promise(resolve => {
    modalResolve = resolve;
    $('#modalTitle').textContent = title;
    $('#modalMessage').textContent = message;
    const input = $('#modalInput');
    const cancelBtn = $('#modalCancel');
    const confirmBtn = $('#modalConfirm');
    
    if (showInput) {
      input.style.display = 'block';
      input.value = defaultValue;
      setTimeout(() => input.focus(), 100);
    } else {
      input.style.display = 'none';
    }
    
    cancelBtn.style.display = showCancel ? 'inline-flex' : 'none';
    cancelBtn.textContent = cancelText;
    confirmBtn.textContent = confirmText;
    
    $('#modal').classList.add('active');
  });
}

function closeModal(result) {
  $('#modal').classList.remove('active');
  if (modalResolve) {
    modalResolve(result);
    modalResolve = null;
  }
}

async function showAlert(title, message) {
  await showModal(title, message, { showCancel: false });
}

async function showPrompt(title, message, defaultValue = '') {
  return await showModal(title, message, { showInput: true, defaultValue });
}

async function showConfirm(title, message, confirmText = 'OK', cancelText = 'Cancel') {
  return await showModal(title, message, { showCancel: true, confirmText, cancelText });
}

// API
async function fetchData() {
  try {
    const r = await fetch('/api/entries');
    const d = await r.json();
    state.data = d?.entries ? d : { entries: {} };
  } catch { state.data = { entries: {} }; }
  updateCounts();
}

async function fetchStats() {
  try {
    const r = await fetch('/api/stats');
    state.stats = await r.json();
    updateStreak();
  } catch { state.stats = null; }
}

async function saveEntry(key, text, photos, tags) {
  try {
    const r = await fetch(`/api/entries/${key}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, photos, tags })
    });
    const d = await r.json();
    if (d.deleted) {
      delete state.data.entries[key];
      state.savedMood = null;
    } else if (d.entry) {
      state.data.entries[key] = d.entry;
      state.savedMood = d.entry.sentiment?.mood || null;
      if (d.encouragement) showToast(d.encouragement, 4000);
    }
    updateCounts();
    await fetchStats();
    return true;
  } catch (e) { showAlert('Error', 'Save failed: ' + e.message); return false; }
}

async function deleteEntry(key) {
  try {
    await fetch(`/api/entries/${key}`, { method: 'DELETE' });
    delete state.data.entries[key];
    state.savedMood = null;
    updateCounts();
    await fetchStats();
    return true;
  } catch (e) { showAlert('Error', 'Delete failed'); return false; }
}

// UI Updates
function updateCounts() {
  const c = Object.keys(state.data.entries).length;
  $('#entryCount').textContent = `${c} ${c === 1 ? 'entry' : 'entries'}`;
  let latest = null;
  for (const [k, e] of Object.entries(state.data.entries)) {
    const ts = e.updatedAt ? Date.parse(e.updatedAt) : 0;
    if (!latest || ts > latest.ts) latest = { ts };
  }
  $('#lastSaved').textContent = latest ? `Last saved ${new Date(latest.ts).toLocaleDateString()}` : '';
}

function updateStreak() {
  if (!state.stats) return;
  const s = state.stats.streak || {};
  const stats = state.stats;
  
  // Basic streak info
  const currentStreak = s.current_streak || 0;
  $('#streakNum').textContent = currentStreak;
  $('#streakRing').style.setProperty('--progress', Math.min(currentStreak / 7, 1) * 100);
  $('#weekStat').textContent = s.this_week || 0;
  $('#monthStat').textContent = s.this_month || 0;
  $('#totalStat').textContent = s.total_entries || 0;
  
  // Streak subtext
  const subtext = $('#streakSubtext');
  if (subtext) {
    if (currentStreak >= 30) {
      subtext.textContent = 'Incredible!';
    } else if (currentStreak >= 7) {
      subtext.textContent = 'On fire!';
    } else if (currentStreak > 0) {
      subtext.textContent = 'Keep going!';
    } else {
      subtext.textContent = 'Start today';
    }
  }
  
  $('#streakMessage').textContent = stats.encouragement || 'Begin your practice today.';
  
  // Visual Week Chain
  if (stats.week_chain) {
    const chainEl = $('#weekChain');
    if (chainEl) {
      chainEl.innerHTML = stats.week_chain.map(day => `
        <div class="chain-day ${day.has_entry ? 'has-entry' : ''} ${day.is_today ? 'today' : ''}">
          <span class="day-dot"></span>
          <span class="day-label">${day.day}</span>
        </div>
      `).join('');
    }
  }
  
  // Streak Alert
  const alertEl = $('#streakAlert');
  const alertText = $('#streakAlertText');
  if (alertEl && alertText) {
    if (stats.streak_status === 'at_risk') {
      alertEl.classList.remove('hidden');
      alertEl.classList.add('urgent');
      alertText.textContent = `⏰ Only ${Math.round(stats.hours_remaining)}h left to save your ${currentStreak}-day streak!`;
    } else if (stats.streak_status === 'reminder' && currentStreak > 0) {
      alertEl.classList.remove('hidden', 'urgent');
      alertText.textContent = `Don't forget to write today! ${Math.round(stats.hours_remaining)}h remaining.`;
    } else {
      alertEl.classList.add('hidden');
    }
  }
  
  // Write Today Button
  const writeBtn = $('#btnWriteToday');
  const hoursEl = $('#hoursRemaining');
  if (writeBtn) {
    if (stats.journaled_today) {
      writeBtn.classList.add('completed');
      writeBtn.querySelector('.btn-text').textContent = 'Today Complete ✓';
      if (hoursEl) hoursEl.textContent = '';
    } else {
      writeBtn.classList.remove('completed');
      writeBtn.querySelector('.btn-text').textContent = 'Write Today';
      if (hoursEl && stats.hours_remaining !== undefined) {
        const hrs = Math.round(stats.hours_remaining);
        hoursEl.textContent = hrs > 0 ? `${hrs}h left` : '';
      }
    }
  }
  
  // Weekly Goal
  if (stats.weekly_goal) {
    const goal = stats.weekly_goal;
    const goalProgress = $('#goalProgress');
    const barFill = $('#goalBarFill');
    if (goalProgress) goalProgress.textContent = `${goal.current}/${goal.target} days`;
    if (barFill) {
      barFill.style.width = `${goal.progress}%`;
      if (goal.progress >= 100) {
        barFill.classList.add('complete');
      } else {
        barFill.classList.remove('complete');
      }
    }
  }
  
  // Milestone Progress
  const milestoneSection = $('#milestoneSection');
  if (milestoneSection) {
    if (stats.next_milestone && currentStreak > 0) {
      const milestone = stats.next_milestone;
      milestoneSection.classList.remove('hidden');
      const targetEl = $('#milestoneTarget');
      const barEl = $('#milestoneBarFill');
      const remainEl = $('#milestoneRemaining');
      if (targetEl) targetEl.textContent = `${milestone.days} Days`;
      if (barEl) barEl.style.width = `${milestone.progress}%`;
      if (remainEl) remainEl.textContent = milestone.remaining === 1 
        ? '1 day to go!' 
        : `${milestone.remaining} days to go`;
    } else {
      milestoneSection.classList.add('hidden');
    }
  }
  
  // Badges
  const badgesGrid = $('#badgesGrid');
  if (badgesGrid && stats.badges) {
    const badgeIcons = {
      7: '🔥',
      14: '⭐',
      30: '💎',
      60: '🏆',
      100: '👑',
      365: '🌟'
    };
    badgesGrid.innerHTML = stats.badges.map(b => `
      <div class="badge-item ${b.achieved ? 'achieved' : ''}">
        <span class="badge-icon">${badgeIcons[b.days] || '🎯'}</span>
        <span class="badge-label">${b.label}</span>
      </div>
    `).join('');
  }
}

function updateWordCount() {
  const t = $('#noteArea').value;
  const w = t.trim().split(/\s+/).filter(Boolean).length;
  $('#editorWordCount').textContent = `${w} words`;
}

function updateMoodDisplay() {
  // Only show mood if it was saved (not during editing)
  if (state.savedMood) {
    const emoji = MOOD_EMOJIS[state.savedMood] || '';
    const label = MOOD_LABELS[state.savedMood] || '';
    $('#editorMood').textContent = `${emoji} ${label}`;
  } else {
    $('#editorMood').textContent = '';
  }
}

function updateClock() {
  $('#clock').textContent = new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
}

// Views
function showBrowse() {
  $('#browseView').classList.remove('hidden');
  $('#editorView').classList.remove('active');
}

function showEditor() {
  $('#browseView').classList.add('hidden');
  $('#editorView').classList.add('active');
}

function setView(v) {
  state.view = v;
  $$('.view-tab').forEach(t => t.classList.toggle('active', t.dataset.view === v));
  $$('.view-container').forEach(c => c.classList.remove('active'));
  
  // Hide navigation buttons in year view
  const navArrows = document.querySelector('.nav-arrows');
  if (navArrows) {
    navArrows.style.display = v === 'year' ? 'none' : 'flex';
  }
  
  if (v === 'month') { $('#monthView').classList.add('active'); renderCalendar(); }
  else if (v === 'year') { $('#yearView').classList.add('active'); renderYear(); }
  else if (v === 'insights') { $('#insightsView').classList.add('active'); renderInsights(); }
}

function render() {
  $('#monthTitle').textContent = formatMonthYear(state.cursor);
  $('#monthSubtitle').textContent = 'Click a day to write';
  renderCalendar();
}

function renderCalendar() {
  const g = $('#calendarGrid');
  const days = getDaysInMonth(state.cursor);
  const first = getFirstDayOfMonth(state.cursor);
  const total = Math.ceil((first + days) / 7) * 7;
  g.innerHTML = '';
  for (let i = 0; i < total; i++) {
    const cell = document.createElement('div');
    cell.className = 'day-cell';
    const d = i - first + 1;
    if (d < 1 || d > days) {
      cell.classList.add('empty');
      cell.innerHTML = '<span class="date">&nbsp;</span>';
    } else {
      const date = new Date(state.cursor.getFullYear(), state.cursor.getMonth(), d);
      const k = dateKey(date);
      const e = state.data.entries[k];
      if (e?.text?.trim()) cell.classList.add('has-entry');
      const mood = e?.sentiment?.mood;
      const emoji = mood ? MOOD_EMOJIS[mood] || '' : '';
      const prev = e?.text?.slice(0, 40) || '';
      cell.innerHTML = `<span class="date">${d}${emoji ? ` <span class="mood">${emoji}</span>` : ''}</span>${prev ? `<div class="preview">${escapeHtml(prev)}</div>` : ''}`;
      cell.addEventListener('click', () => openEditor(date));
    }
    g.appendChild(cell);
  }
}

// Editor
function openEditor(date) {
  state.selectedDate = new Date(date);
  const k = dateKey(state.selectedDate);
  const e = state.data.entries[k];
  state.draft = { text: e?.text || '', photos: e?.photos ? [...e.photos] : [], tags: e?.tags ? [...e.tags] : [] };
  // Store original state for unsaved changes detection
  state.original = { text: e?.text || '', photos: e?.photos ? [...e.photos] : [], tags: e?.tags ? [...e.tags] : [] };
  state.undo = null;
  state.nudges = [];
  
  // Store the saved mood (from the existing entry, if any)
  state.savedMood = e?.sentiment?.mood || null;
  
  $('#editorDateTitle').textContent = formatFullDate(state.selectedDate);
  updateMoodDisplay();
  $('#noteArea').value = state.draft.text;
  $('#btnUndo').disabled = true;
  renderMeta();
  updateWordCount();
  clearSuggestions();
  
  // Show nudges section if entry is empty (new entry)
  const hasExistingEntry = e?.text?.trim();
  showNudgesSection(!hasExistingEntry);
  
  showEditor();
  
  if (hasExistingEntry) {
    setTimeout(() => $('#noteArea').focus(), 100);
  } else {
    setTimeout(() => $('#nudgeInput').focus(), 100);
  }
}

function hasUnsavedChanges() {
  // Get current text from textarea (in case draft wasn't updated)
  const currentText = $('#noteArea')?.value || state.draft.text;
  
  // Compare text
  if (currentText !== state.original.text) return true;
  
  // Compare photos
  if (state.draft.photos.length !== state.original.photos.length) return true;
  if (state.draft.photos.some((p, i) => p !== state.original.photos[i])) return true;
  
  // Compare tags
  if (state.draft.tags.length !== state.original.tags.length) return true;
  if (state.draft.tags.some((t, i) => t !== state.original.tags[i])) return true;
  
  return false;
}

async function closeEditor() {
  // Check for unsaved changes
  if (hasUnsavedChanges()) {
    const confirmed = await showConfirm(
      'Unsaved Changes',
      'You have unsaved changes. Are you sure you want to leave?',
      'Leave',
      'Stay'
    );
    if (!confirmed) return;
  }
  
  state.selectedDate = null;
  state.savedMood = null;
  state.original = { text: '', photos: [], tags: [] };
  showBrowse();
  render();
}

function renderMeta() {
  const ta = $('#tagsArea');
  ta.innerHTML = '';
  state.draft.tags.forEach((t, i) => {
    const el = document.createElement('span');
    el.className = 'tag';
    el.innerHTML = `${escapeHtml(t)} <button type="button">×</button>`;
    el.querySelector('button').addEventListener('click', () => { state.draft.tags.splice(i, 1); renderMeta(); });
    ta.appendChild(el);
  });
  const ab = document.createElement('button');
  ab.className = 'add-tag-btn';
  ab.textContent = '+ tag';
  ab.addEventListener('click', async () => { 
    const t = await showPrompt('Add Tag', 'Enter a tag for this entry:'); 
    if (t?.trim()) { state.draft.tags.push(t.trim().slice(0, 30)); renderMeta(); } 
  });
  ta.appendChild(ab);

  const pg = $('#photosGrid');
  pg.innerHTML = '';
  state.draft.photos.forEach((s, i) => {
    const th = document.createElement('div');
    th.className = 'photo-thumb';
    th.innerHTML = `<img src="${s}" alt=""><button type="button">×</button>`;
    th.querySelector('button').addEventListener('click', () => { state.draft.photos.splice(i, 1); renderMeta(); });
    pg.appendChild(th);
  });
}

function addPhotos(files) {
  const rem = 10 - state.draft.photos.length;
  Array.from(files).slice(0, rem).forEach(f => {
    const r = new FileReader();
    r.onload = () => { state.draft.photos.push(r.result); renderMeta(); };
    r.readAsDataURL(f);
  });
}

function setPrompt(k) {
  $$('.prompt-chip').forEach(c => c.classList.toggle('active', c.dataset.prompt === k));
  $('#noteArea').placeholder = PROMPTS[k].placeholder;
}

// Nudges
function showNudgesSection(show) {
  const section = $('#nudgesSection');
  const textarea = $('#noteArea');
  if (show) {
    section.classList.add('active');
    textarea.style.display = 'none';
  } else {
    section.classList.remove('active');
    textarea.style.display = 'block';
  }
  renderNudges();
}

function renderNudges() {
  const list = $('#nudgesList');
  list.innerHTML = '';
  
  if (state.nudges.length === 0) {
    list.innerHTML = '<p style="color: var(--text-muted); font-size: 0.8125rem; text-align: center; padding: 8px;">No nudges yet. Add some moments from your day above.</p>';
  } else {
    state.nudges.forEach((nudge, i) => {
      const item = document.createElement('div');
      item.className = 'nudge-item';
      item.innerHTML = `<span>${escapeHtml(nudge)}</span><button type="button">×</button>`;
      item.querySelector('button').addEventListener('click', () => {
        state.nudges.splice(i, 1);
        renderNudges();
        updateGenerateButton();
      });
      list.appendChild(item);
    });
  }
}

function addNudge() {
  const input = $('#nudgeInput');
  const text = input.value.trim();
  if (text) {
    state.nudges.push(text);
    input.value = '';
    renderNudges();
    updateGenerateButton();
    input.focus();
  }
}

function updateGenerateButton() {
  $('#btnGenerateFromNudges').disabled = state.nudges.length === 0;
}

async function generateFromNudges() {
  if (state.nudges.length === 0) return;
  
  const btn = $('#btnGenerateFromNudges');
  btn.disabled = true;
  btn.textContent = 'Generating...';
  
  try {
    const r = await fetch('/api/generate-from-nudges', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        nudges: state.nudges,
        date: formatFullDate(state.selectedDate)
      })
    });
    const d = await r.json();
    
    if (d.entry) {
      $('#noteArea').value = d.entry;
      state.draft.text = d.entry;
      state.nudges = [];
      showNudgesSection(false);
      updateWordCount();
      showToast('Entry generated! Feel free to edit or polish it.');
      $('#noteArea').focus();
    } else if (d.error) {
      showAlert('Generation Failed', d.error);
    }
  } catch (e) {
    showAlert('Error', 'Could not generate entry. Please try again.');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Generate Entry from Nudges';
    updateGenerateButton();
  }
}

function skipNudges() {
  state.nudges = [];
  showNudgesSection(false);
  $('#noteArea').focus();
}

// Suggestions (read-only)
function clearSuggestions() {
  $('#suggestionsList').innerHTML = '<p class="suggestions-placeholder">Click "Get Suggestions" for AI-powered writing ideas.</p>';
}

async function fetchSuggestions() {
  const btn = $('#btnGetSuggestions');
  const list = $('#suggestionsList');
  btn.disabled = true;
  btn.textContent = 'Loading...';
  list.innerHTML = '<p class="suggestions-placeholder">Loading...</p>';
  try {
    const r = await fetch('/api/suggest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: $('#noteArea').value })
    });
    const d = await r.json();
    if (d.suggestions?.length) {
      list.innerHTML = d.suggestions.map(s => `
        <div class="suggestion-item">
          <span class="suggestion-type">${s.type}</span>
          <p>${escapeHtml(s.text)}</p>
        </div>
      `).join('');
    } else {
      list.innerHTML = `<p class="suggestions-placeholder">${d.error || 'No suggestions. Try writing more.'}</p>`;
    }
  } catch {
    list.innerHTML = '<p class="suggestions-placeholder">Could not load suggestions.</p>';
  } finally {
    btn.disabled = false;
    btn.textContent = 'Get Suggestions';
  }
}

async function handleRewrite() {
  const ta = $('#noteArea');
  if (!ta.value.trim()) { showAlert('Nothing to polish', 'Write something first.'); return; }
  state.undo = { text: ta.value };
  $('#btnUndo').disabled = false;
  const btn = $('#btnRewrite');
  btn.disabled = true;
  btn.textContent = 'Polishing...';
  try {
    const r = await fetch('/api/rewrite', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: ta.value })
    });
    const d = await r.json();
    if (d.rewritten) { ta.value = d.rewritten; state.draft.text = d.rewritten; showToast('Polished!'); }
    else if (d.error) showAlert('Error', d.error);
  } catch (e) { showAlert('Error', 'Failed: ' + e.message); }
  finally { btn.disabled = false; btn.textContent = 'Polish Writing'; updateWordCount(); }
}

function handleUndo() {
  if (state.undo) {
    $('#noteArea').value = state.undo.text;
    state.draft.text = state.undo.text;
    state.undo = null;
    $('#btnUndo').disabled = true;
    updateWordCount();
    showToast('Undone');
  }
}

async function handleSave() {
  if (!state.selectedDate) return;
  const btn = $('#btnSave');
  btn.disabled = true;
  btn.textContent = 'Saving...';
  const k = dateKey(state.selectedDate);
  const text = $('#noteArea').value;
  
  // Track previous streak for milestone detection
  const prevStreak = state.stats?.streak?.current_streak || 0;
  const wasJournaledToday = state.stats?.journaled_today || false;
  
  const success = await saveEntry(k, text, state.draft.photos, state.draft.tags);
  
  if (success) {
    // Update original state to match saved state (no more unsaved changes)
    state.original = { 
      text: text, 
      photos: [...state.draft.photos], 
      tags: [...state.draft.tags] 
    };
    state.draft.text = text;
    // Update mood display only after save completes
    updateMoodDisplay();
    
    // Check for streak milestones
    const newStreak = state.stats?.streak?.current_streak || 0;
    const milestones = [7, 14, 30, 60, 100, 365];
    
    // If this was the first entry today and it extended the streak
    if (!wasJournaledToday && newStreak > prevStreak) {
      // Check if we hit a milestone
      for (const milestone of milestones) {
        if (newStreak >= milestone && prevStreak < milestone) {
          celebrateMilestone(milestone);
          break;
        }
      }
    }
    
    // Check weekly goal completion
    const weeklyGoal = state.stats?.weekly_goal;
    if (weeklyGoal && weeklyGoal.current === weeklyGoal.target) {
      setTimeout(() => {
        showToast('🎉 Weekly goal achieved! Great consistency!', 4000);
      }, 1500);
    }
  }
  
  btn.disabled = false;
  btn.textContent = 'Save';
}

function celebrateMilestone(days) {
  const messages = {
    7: ['🔥 One week streak!', 'You\'ve built a habit!'],
    14: ['⭐ Two weeks strong!', 'Consistency is your superpower!'],
    30: ['💎 30-day milestone!', 'You\'re a journaling champion!'],
    60: ['🏆 60 days!', 'Incredible dedication!'],
    100: ['👑 100-DAY STREAK!', 'You\'re absolutely legendary!'],
    365: ['🌟 ONE YEAR!', 'A full year of reflection!']
  };
  
  const [title, subtitle] = messages[days] || ['🎉 Milestone reached!', `${days} days of journaling!`];
  
  // Show special toast
  const toast = $('#toast');
  toast.innerHTML = `<div class="milestone-toast"><strong>${title}</strong><br><small>${subtitle}</small></div>`;
  toast.classList.add('show', 'milestone');
  
  // Trigger confetti effect
  createConfetti();
  
  setTimeout(() => {
    toast.classList.remove('show', 'milestone');
    toast.innerHTML = '';
  }, 5000);
}

function createConfetti() {
  const colors = ['#2563eb', '#7c3aed', '#16a34a', '#fbbf24', '#ef4444', '#ec4899'];
  const confettiCount = 50;
  
  for (let i = 0; i < confettiCount; i++) {
    const confetti = document.createElement('div');
    confetti.className = 'confetti';
    confetti.style.cssText = `
      left: ${Math.random() * 100}vw;
      background: ${colors[Math.floor(Math.random() * colors.length)]};
      animation-delay: ${Math.random() * 0.5}s;
      animation-duration: ${2 + Math.random() * 2}s;
    `;
    document.body.appendChild(confetti);
    
    setTimeout(() => confetti.remove(), 4000);
  }
}

async function handleDelete() {
  if (!state.selectedDate) return;
  const confirmed = await showConfirm(
    'Delete Entry', 
    'Are you sure you want to delete this entry? This cannot be undone.',
    'Delete',
    'Cancel'
  );
  if (!confirmed) return;
  await deleteEntry(dateKey(state.selectedDate));
  // Reset original state since entry is deleted
  state.original = { text: '', photos: [], tags: [] };
  await closeEditor();
}

// Year View
async function renderYear() {
  const c = $('#yearContent');
  const b = $('#yearBreadcrumb');
  b.innerHTML = '<button class="btn ghost" onclick="renderYear()">All Years</button>';
  c.innerHTML = '<p style="color:var(--text-muted);padding:16px;">Loading...</p>';
  try {
    const r = await fetch('/api/years');
    const y = await r.json();
    if (!y.length) { c.innerHTML = '<p style="color:var(--text-muted);padding:16px;">No entries yet.</p>'; return; }
    c.innerHTML = `<div class="year-grid">${y.map(yr => `<div class="year-item" onclick="loadMonths(${yr})"><div class="num">${yr}</div><div class="label">Year</div></div>`).join('')}</div>`;
  } catch { c.innerHTML = '<p style="color:var(--text-muted);padding:16px;">Failed.</p>'; }
}

window.loadMonths = async function(yr) {
  const c = $('#yearContent');
  const b = $('#yearBreadcrumb');
  b.innerHTML = `<button class="btn ghost" onclick="renderYear()">Years</button><span>›</span><span>${yr}</span>`;
  c.innerHTML = '<p style="color:var(--text-muted);padding:16px;">Loading...</p>';
  try {
    const r = await fetch(`/api/years/${yr}/months`);
    const m = await r.json();
    const n = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    c.innerHTML = `<div class="year-grid">${m.map(mo => `<div class="year-item" onclick="goMonth(${yr},${mo})"><div class="num">${n[mo-1]}</div><div class="label">${yr}</div></div>`).join('')}</div>`;
  } catch { c.innerHTML = '<p style="color:var(--text-muted);padding:16px;">Failed.</p>'; }
};

window.goMonth = function(y, m) { 
  state.cursor = new Date(y, m - 1, 1); 
  setView('month'); 
  render(); 
};

// Insights & Charts
let charts = {};

function destroyCharts() {
  Object.values(charts).forEach(c => c?.destroy?.());
  charts = {};
}

const chartColors = {
  primary: '#2563eb',
  primaryLight: 'rgba(37, 99, 235, 0.1)',
  positive: '#10b981',
  neutral: '#6b7280',
  negative: '#ef4444',
  mood: {
    very_positive: '#10b981',
    positive: '#34d399',
    neutral: '#6b7280',
    negative: '#f59e0b',
    very_negative: '#ef4444'
  }
};

async function renderInsights() {
  const c = $('#insightsContent');
  c.innerHTML = '<p style="color:var(--text-muted);">Loading insights...</p>';
  destroyCharts();
  
  // Get current month/year from cursor
  const year = state.cursor.getFullYear();
  const month = state.cursor.getMonth() + 1; // JS months are 0-indexed
  const monthParam = `?year=${year}&month=${month}`;
  
  try {
    const [cr, sr] = await Promise.all([
      fetch(`/api/insights/charts${monthParam}`),
      fetch(`/api/insights/summary${monthParam}`)
    ]);
    const [chartData, summaryData] = await Promise.all([cr.json(), sr.json()]);
    
    const monthName = chartData.month_name || formatMonthYear(state.cursor);
    
    let h = `<div class="insights-header">
      <h3>${monthName}</h3>
      <span class="entry-count">${chartData.total_entries || 0} entries</span>
    </div>`;
    
    // AI Summary Card
    if (summaryData.summary) {
      const moodEmoji = summaryData.avg_mood > 0.3 ? '😊' : summaryData.avg_mood > 0 ? '🙂' : summaryData.avg_mood > -0.3 ? '😌' : '😔';
      const trajectoryLabel = summaryData.mood_trajectory === 'improving' ? '↗️ Improving' : 
                              summaryData.mood_trajectory === 'declining' ? '↘️ Needs care' : '→ Steady';
      h += `<div class="summary-card">
        <div class="summary-header">
          <h4>✨ Monthly Reflection</h4>
          <div class="summary-stats">
            <span class="stat">${moodEmoji} ${trajectoryLabel}</span>
            ${summaryData.top_themes?.length ? `<span class="stat">🏷️ ${summaryData.top_themes.slice(0, 3).join(', ')}</span>` : ''}
          </div>
        </div>
        <div class="summary-text">${escapeHtml(summaryData.summary).replace(/\n\n/g, '</p><p>').replace(/\n/g, '<br>')}</div>
        ${summaryData.insights?.length ? `
          <div class="summary-insights">
            <h5>Key Patterns</h5>
            <ul>${summaryData.insights.map(i => `<li>${escapeHtml(i)}</li>`).join('')}</ul>
          </div>
        ` : ''}
      </div>`;
    } else if (summaryData.message) {
      h += `<div class="summary-card empty">
        <p>${escapeHtml(summaryData.message)}</p>
      </div>`;
    }
    
    // Charts section
    h += `<div id="overviewTab">
      ${chartData.has_data ? `
        <div class="charts-grid">
          <div class="chart-card full-width">
            <div class="chart-header">
              <h4>📈 How Your Mood Changes</h4>
              <p class="chart-subtitle">Your emotional journey throughout the month</p>
            </div>
            <div class="chart-container wide"><canvas id="moodTrendChart"></canvas></div>
          </div>
          
          <div class="chart-card">
            <div class="chart-header">
              <h4>😊 Your Emotional Balance</h4>
              <p class="chart-subtitle">How balanced are you?</p>
            </div>
            <div class="chart-container small"><canvas id="moodDistChart"></canvas></div>
          </div>
          
          <div class="chart-card">
            <div class="chart-header">
              <h4>📝 ${chartData.best_day ? `Your Best Days (${chartData.best_day}s)` : 'When You Journal Most'}</h4>
              <p class="chart-subtitle">Your journaling patterns</p>
            </div>
            <div class="chart-container"><canvas id="dayDistChart"></canvas></div>
          </div>
          
          <div class="chart-card">
            <div class="chart-header">
              <h4>🏷️ What's On Your Mind</h4>
              <p class="chart-subtitle">Topics you've been exploring</p>
            </div>
            <div class="chart-container"><canvas id="themesChart"></canvas></div>
          </div>
          
          <div class="chart-card">
            <div class="chart-header">
              <h4>📅 Your Consistency</h4>
              <p class="chart-subtitle">Weekly journaling habits</p>
            </div>
            <div class="chart-container"><canvas id="weeklyEntriesChart"></canvas></div>
          </div>
          
          <div class="chart-card">
            <div class="chart-header">
              <h4>✍️ Reflection Depth</h4>
              <p class="chart-subtitle">How much you're writing</p>
            </div>
            <div class="chart-container"><canvas id="wordCountChart"></canvas></div>
          </div>
        </div>
      ` : `<div class="card empty-state"><p>${chartData.message || 'No entries for this month yet.'}</p></div>`}
    </div>`;
    
    
    c.innerHTML = h;
    
    // Render charts if we have data
    if (chartData.has_data) {
      setTimeout(() => renderCharts(chartData), 50);
    }
  } catch (e) {
    console.error('Insights error:', e);
    c.innerHTML = '<div class="card"><p style="color:var(--text-muted);">Failed to load insights.</p></div>';
  }
}

function renderCharts(data) {
  const commonOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false }
    }
  };
  
  // 1. Mood Trend Line Chart
  const moodTrendCtx = document.getElementById('moodTrendChart')?.getContext('2d');
  if (moodTrendCtx) {
    const labels = data.mood_trend.map(d => d.date);
    const values = data.mood_trend.map(d => d.score);
    charts.moodTrend = new Chart(moodTrendCtx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          data: values,
          borderColor: chartColors.primary,
          backgroundColor: chartColors.primaryLight,
          borderWidth: 2,
          fill: true,
          tension: 0.3,
          spanGaps: true,
          pointRadius: values.map(v => v !== null ? 4 : 0),
          pointBackgroundColor: values.map(v => 
            v === null ? 'transparent' : v > 0.2 ? chartColors.positive : v < -0.2 ? chartColors.negative : chartColors.neutral
          )
        }]
      },
      options: {
        ...commonOptions,
        scales: {
          y: { min: -1, max: 1, grid: { color: 'rgba(0,0,0,0.05)' } },
          x: { grid: { display: false }, ticks: { maxTicksLimit: 7 } }
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: ctx => ctx.raw !== null ? `Mood: ${ctx.raw > 0.2 ? 'Positive' : ctx.raw < -0.2 ? 'Negative' : 'Neutral'} (${ctx.raw})` : 'No entry'
            }
          }
        }
      }
    });
  }
  
  // 2. Mood Distribution Doughnut
  const moodDistCtx = document.getElementById('moodDistChart')?.getContext('2d');
  if (moodDistCtx) {
    const labels = ['Joyful', 'Content', 'Balanced', 'Reflective', 'Processing'];
    const values = [
      data.mood_distribution.very_positive,
      data.mood_distribution.positive,
      data.mood_distribution.neutral,
      data.mood_distribution.negative,
      data.mood_distribution.very_negative
    ];
    charts.moodDist = new Chart(moodDistCtx, {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{
          data: values,
          backgroundColor: [
            chartColors.mood.very_positive,
            chartColors.mood.positive,
            chartColors.mood.neutral,
            chartColors.mood.negative,
            chartColors.mood.very_negative
          ],
          borderWidth: 0
        }]
      },
      options: {
        ...commonOptions,
        cutout: '60%',
        plugins: {
          legend: { display: true, position: 'bottom', labels: { boxWidth: 12, padding: 8 } }
        }
      }
    });
  }
  
  // 3. Day Distribution Bar Chart
  const dayDistCtx = document.getElementById('dayDistChart')?.getContext('2d');
  if (dayDistCtx) {
    charts.dayDist = new Chart(dayDistCtx, {
      type: 'bar',
      data: {
        labels: data.day_distribution.days.map(d => d.slice(0, 3)),
        datasets: [{
          label: 'Entries',
          data: data.day_distribution.counts,
          backgroundColor: chartColors.primary,
          borderRadius: 4
        }]
      },
      options: {
        ...commonOptions,
        scales: {
          y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.05)' } },
          x: { grid: { display: false } }
        }
      }
    });
  }
  
  // 4. Themes Bar Chart
  const themesCtx = document.getElementById('themesChart')?.getContext('2d');
  if (themesCtx && data.themes.labels.length > 0) {
    charts.themes = new Chart(themesCtx, {
      type: 'bar',
      data: {
        labels: data.themes.labels,
        datasets: [{
          data: data.themes.counts,
          backgroundColor: [
            '#2563eb', '#7c3aed', '#db2777', '#ea580c', 
            '#16a34a', '#0891b2', '#4f46e5', '#be123c'
          ],
          borderRadius: 4
        }]
      },
      options: {
        ...commonOptions,
        indexAxis: 'y',
        scales: {
          x: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.05)' } },
          y: { grid: { display: false } }
        }
      }
    });
  }
  
  // 5. Weekly Entries Chart
  const weeklyEntriesCtx = document.getElementById('weeklyEntriesChart')?.getContext('2d');
  if (weeklyEntriesCtx) {
    charts.weeklyEntries = new Chart(weeklyEntriesCtx, {
      type: 'bar',
      data: {
        labels: data.weekly_entries.map(w => w.week),
        datasets: [{
          label: 'Entries',
          data: data.weekly_entries.map(w => w.count),
          backgroundColor: chartColors.positive,
          borderRadius: 4
        }]
      },
      options: {
        ...commonOptions,
        scales: {
          y: { beginAtZero: true, max: 7, grid: { color: 'rgba(0,0,0,0.05)' } },
          x: { grid: { display: false } }
        }
      }
    });
  }
  
  // 6. Word Count Trend
  const wordCountCtx = document.getElementById('wordCountChart')?.getContext('2d');
  if (wordCountCtx) {
    charts.wordCount = new Chart(wordCountCtx, {
      type: 'line',
      data: {
        labels: data.weekly_words.map(w => w.week),
        datasets: [{
          label: 'Avg Words',
          data: data.weekly_words.map(w => w.avg_words),
          borderColor: '#7c3aed',
          backgroundColor: 'rgba(124, 58, 237, 0.1)',
          borderWidth: 2,
          fill: true,
          tension: 0.3
        }]
      },
      options: {
        ...commonOptions,
        scales: {
          y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.05)' } },
          x: { grid: { display: false } }
        }
      }
    });
  }
}


// Import/Export
async function handleExport() {
  try {
    const r = await fetch('/api/export');
    const d = await r.json();
    const b = new Blob([JSON.stringify(d, null, 2)], { type: 'application/json' });
    const u = URL.createObjectURL(b);
    const a = document.createElement('a');
    a.href = u;
    a.download = `reflect-ai-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(u);
    showToast('Exported!');
  } catch { alert('Export failed.'); }
}

async function handleImport(f) {
  if (!f) return;
  const r = new FileReader();
  r.onload = async () => {
    try {
      const d = JSON.parse(r.result);
      if (!d.entries) { showAlert('Invalid File', 'This file does not contain valid journal data.'); return; }
      await fetch('/api/import', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(d) });
      await fetchData();
      render();
      showToast('Imported!');
    } catch { showAlert('Error', 'Could not read file.'); }
  };
  r.readAsText(f);
}

async function handleClear() {
  const confirmed = await showConfirm(
    'Clear All Data', 
    'Delete ALL entries? This cannot be undone.',
    'Clear All',
    'Cancel'
  );
  if (!confirmed) return;
  await fetch('/api/clear', { method: 'DELETE' });
  state.data = { entries: {} };
  await fetchStats();
  render();
  showToast('Cleared.');
}

// Loader
async function runLoader() {
  const greetingEl = $('#loaderGreeting');
  const bar = $('#progressBar');
  
  // Initial state
  greetingEl.innerHTML = '<span class="loading-text">Preparing your space...</span>';
  
  await new Promise(r => setTimeout(r, 400));
  bar.style.width = '20%';
  
  await new Promise(r => setTimeout(r, 300));
  bar.style.width = '35%';
  
  // Fetch personalized greeting
  let greetingData = null;
  try {
    const r = await fetch('/api/greeting');
    greetingData = await r.json();
  } catch (e) {
    console.log('Using fallback greeting');
  }
  
  bar.style.width = '50%';
  await new Promise(r => setTimeout(r, 400));
  
  bar.style.width = '65%';
  
  // Display greeting with smooth transition
  if (greetingData?.message) {
    let statsHtml = '';
    if (greetingData.streak > 0) {
      statsHtml = `<div class="stats"><span class="stat-item">🔥 ${greetingData.streak}-day streak</span></div>`;
    } else if (greetingData.has_entries && greetingData.total_entries > 0) {
      statsHtml = `<div class="stats"><span class="stat-item">📖 ${greetingData.total_entries} entries</span></div>`;
    }
    greetingEl.style.opacity = '0';
    greetingEl.innerHTML = `
      <span class="time-label">${greetingData.greeting}</span>
      <p class="message">${escapeHtml(greetingData.message)}</p>
      ${statsHtml}
    `;
    greetingEl.style.transition = 'opacity 0.6s ease';
    await new Promise(r => setTimeout(r, 100));
    greetingEl.style.opacity = '1';
  } else {
    const fallback = FALLBACK_QUOTES[Math.floor(Math.random() * FALLBACK_QUOTES.length)];
    greetingEl.style.opacity = '0';
    greetingEl.innerHTML = `
      <p class="message">"${fallback.text}"</p>
      <div class="stats"><span class="stat-item">${fallback.sub}</span></div>
    `;
    greetingEl.style.transition = 'opacity 0.6s ease';
    await new Promise(r => setTimeout(r, 100));
    greetingEl.style.opacity = '1';
  }
  
  // Extended reading time
  bar.style.width = '75%';
  await new Promise(r => setTimeout(r, 1800));
  
  bar.style.width = '88%';
  await new Promise(r => setTimeout(r, 1000));
  
  bar.style.width = '100%';
  await new Promise(r => setTimeout(r, 500));
  
  $('#loader').classList.add('hidden');
  $('#app').classList.add('ready');
}

// Events
function setup() {
  $('#prevBtn').addEventListener('click', () => { 
    const newDate = new Date(state.cursor);
    newDate.setMonth(newDate.getMonth() - 1);
    state.cursor = newDate;
    render(); 
    if (state.view === 'insights') renderInsights();
    if (state.view === 'year') renderYear();
  });
  $('#nextBtn').addEventListener('click', () => { 
    const newDate = new Date(state.cursor);
    newDate.setMonth(newDate.getMonth() + 1);
    state.cursor = newDate;
    render(); 
    if (state.view === 'insights') renderInsights();
    if (state.view === 'year') renderYear();
  });
  $('#themeToggle').addEventListener('click', () => {
    document.body.classList.toggle('dark-theme');
    const isDark = document.body.classList.contains('dark-theme');
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
    $('#themeToggle').textContent = isDark ? '☀️' : '🌙';
  });
  $$('.view-tab').forEach(t => t.addEventListener('click', () => setView(t.dataset.view)));
  $('#btnToday').addEventListener('click', () => { 
    state.cursor = new Date(); 
    render();
    setView('month'); 
  });
  $('#btnWriteToday').addEventListener('click', () => {
    state.cursor = new Date();
    render();
    openEditor(new Date());
  });
  $('#btnInsightsNav').addEventListener('click', () => setView('insights'));
  $('#btnExport').addEventListener('click', handleExport);
  $('#btnImport').addEventListener('click', () => $('#importFile').click());
  $('#importFile').addEventListener('change', e => handleImport(e.target.files[0]));
  $('#btnClear').addEventListener('click', handleClear);
  $('#btnBack').addEventListener('click', closeEditor);
  $('#btnSave').addEventListener('click', handleSave);
  $('#btnDelete').addEventListener('click', handleDelete);
  $('#btnUndo').addEventListener('click', handleUndo);
  $('#btnRewrite').addEventListener('click', handleRewrite);
  $('#btnGetSuggestions').addEventListener('click', fetchSuggestions);
  $('#btnAddPhoto').addEventListener('click', () => $('#photoInput').click());
  $('#photoInput').addEventListener('change', e => addPhotos(e.target.files));
  $$('.prompt-chip').forEach(c => c.addEventListener('click', () => setPrompt(c.dataset.prompt)));
  $('#noteArea').addEventListener('input', () => { state.draft.text = $('#noteArea').value; updateWordCount(); });
  
  // Nudges events
  $('#btnAddNudge').addEventListener('click', addNudge);
  $('#nudgeInput').addEventListener('keydown', e => { if (e.key === 'Enter') addNudge(); });
  $('#btnGenerateFromNudges').addEventListener('click', generateFromNudges);
  $('#btnSkipNudges').addEventListener('click', skipNudges);
  
  // Modal events
  $('#modalConfirm').addEventListener('click', () => {
    const input = $('#modalInput');
    closeModal(input.style.display === 'none' ? true : input.value);
  });
  $('#modalCancel').addEventListener('click', () => closeModal(null));
  $('.modal-backdrop').addEventListener('click', () => closeModal(null));
  $('#modalInput').addEventListener('keydown', e => {
    if (e.key === 'Enter') $('#modalConfirm').click();
    if (e.key === 'Escape') closeModal(null);
  });
}

// Weather
const WEATHER_CODES = {
  0: { icon: '☀️', desc: 'Clear sky', theme: 'sunny' },
  1: { icon: '🌤️', desc: 'Mainly clear', theme: 'sunny' },
  2: { icon: '⛅', desc: 'Partly cloudy', theme: 'cloudy' },
  3: { icon: '☁️', desc: 'Overcast', theme: 'cloudy' },
  45: { icon: '🌫️', desc: 'Foggy', theme: 'cloudy' },
  48: { icon: '🌫️', desc: 'Depositing rime fog', theme: 'cloudy' },
  51: { icon: '🌧️', desc: 'Light drizzle', theme: 'rainy' },
  53: { icon: '🌧️', desc: 'Moderate drizzle', theme: 'rainy' },
  55: { icon: '🌧️', desc: 'Dense drizzle', theme: 'rainy' },
  61: { icon: '🌧️', desc: 'Slight rain', theme: 'rainy' },
  63: { icon: '🌧️', desc: 'Moderate rain', theme: 'rainy' },
  65: { icon: '🌧️', desc: 'Heavy rain', theme: 'rainy' },
  71: { icon: '🌨️', desc: 'Slight snow', theme: 'cloudy' },
  73: { icon: '🌨️', desc: 'Moderate snow', theme: 'cloudy' },
  75: { icon: '❄️', desc: 'Heavy snow', theme: 'cloudy' },
  77: { icon: '🌨️', desc: 'Snow grains', theme: 'cloudy' },
  80: { icon: '🌦️', desc: 'Slight showers', theme: 'rainy' },
  81: { icon: '🌦️', desc: 'Moderate showers', theme: 'rainy' },
  82: { icon: '⛈️', desc: 'Violent showers', theme: 'rainy' },
  85: { icon: '🌨️', desc: 'Slight snow showers', theme: 'cloudy' },
  86: { icon: '🌨️', desc: 'Heavy snow showers', theme: 'cloudy' },
  95: { icon: '⛈️', desc: 'Thunderstorm', theme: 'rainy' },
  96: { icon: '⛈️', desc: 'Thunderstorm with hail', theme: 'rainy' },
  99: { icon: '⛈️', desc: 'Thunderstorm with heavy hail', theme: 'rainy' }
};

async function fetchWeather() {
  const card = $('#weatherCard');
  const loadingEl = card.querySelector('.weather-loading');
  const contentEl = card.querySelector('.weather-content');
  const errorEl = card.querySelector('.weather-error');
  
  try {
    // Get user's location
    const position = await new Promise((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(resolve, reject, {
        enableHighAccuracy: false,
        timeout: 10000,
        maximumAge: 300000 // 5 min cache
      });
    });
    
    const { latitude, longitude } = position.coords;
    
    // Fetch weather from Open-Meteo (free, no API key needed)
    const weatherUrl = `https://api.open-meteo.com/v1/forecast?latitude=${latitude}&longitude=${longitude}&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,is_day&timezone=auto`;
    const weatherRes = await fetch(weatherUrl);
    const weatherData = await weatherRes.json();
    
    // Fetch location name using reverse geocoding
    const geoUrl = `https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=${latitude}&longitude=${longitude}&localityLanguage=en`;
    const geoRes = await fetch(geoUrl);
    const geoData = await geoRes.json();
    
    const current = weatherData.current;
    const code = current.weather_code;
    const weatherInfo = WEATHER_CODES[code] || { icon: '🌡️', desc: 'Unknown', theme: 'cloudy' };
    const isDay = current.is_day === 1;
    
    // Update UI
    $('#weatherIcon').textContent = isDay ? weatherInfo.icon : '🌙';
    $('#weatherTemp').textContent = Math.round(current.temperature_2m);
    $('#weatherDesc').textContent = weatherInfo.desc;
    $('#weatherLocation').textContent = `📍 ${geoData.city || geoData.locality || geoData.principalSubdivision || 'Your location'}`;
    $('#weatherHumidity').textContent = `${current.relative_humidity_2m}%`;
    $('#weatherWind').textContent = `${Math.round(current.wind_speed_10m)} km/h`;
    $('#weatherFeelsLike').textContent = `${Math.round(current.apparent_temperature)}°`;
    
    // Show content
    loadingEl.classList.add('hidden');
    errorEl.classList.add('hidden');
    contentEl.classList.remove('hidden');
    
  } catch (error) {
    console.log('Weather fetch failed:', error.message);
    loadingEl.classList.add('hidden');
    contentEl.classList.add('hidden');
    errorEl.classList.remove('hidden');
  }
}

// Init
async function init() {
  initTheme();
  updateClock();
  setInterval(updateClock, 1000);
  setup();
  await fetchData();
  await fetchStats();
  render();
  runLoader();
  
  // Fetch weather (non-blocking)
  fetchWeather();
  // Refresh weather every 30 minutes
  setInterval(fetchWeather, 30 * 60 * 1000);
}

document.addEventListener('DOMContentLoaded', init);