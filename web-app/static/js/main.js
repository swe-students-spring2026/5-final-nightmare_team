import { generatePlaylist, savePlaylist, recordEvent, getRecommendations, getPlaylists } from './api.js';

const GENRES = ['Pop', 'Rock', 'Hip-Hop', 'R&B', 'Electronic', 'Indie', 'Jazz', 'Country', 'Latin', 'Folk', 'Metal', 'Classical'];
const MOODS  = ['Happy', 'Sad', 'Energetic', 'Chill', 'Romantic', 'Aggressive', 'Melancholic', 'Party', 'Nostalgic', 'Motivational'];
const ERAS   = ['Any', '60s', '70s', '80s', '90s', '00s', '10s', '20s'];

const GENRE_COLOURS = ['#e91e63','#9c27b0','#3f51b5','#009688','#ff9800','#795548','#607d8b','#e53935','#00897b','#1e88e5','#6d4c41','#546e7a'];

const state = {
  seedSongs: [],
  genres: new Set(),
  moods: new Set(),
  era: 'any',
  size: 20,
  playlist: [],
};

// ── DOM refs ──────────────────────────────────────────────────────────────────
const form        = document.getElementById('generator-form');
const seedInput   = document.getElementById('seed-input');
const seedAddBtn  = document.getElementById('seed-add-btn');
const seedChips   = document.getElementById('seed-chips');
const genreChips  = document.getElementById('genre-chips');
const moodChips   = document.getElementById('mood-chips');
const eraChips    = document.getElementById('era-chips');
const sizeSlider  = document.getElementById('size-slider');
const sizeDisplay = document.getElementById('size-display');
const errorMsg    = document.getElementById('error-msg');
const generateBtn = document.getElementById('generate-btn');
const btnLabel    = document.getElementById('btn-label');
const btnSpinner  = document.getElementById('btn-spinner');
const resultsEl   = document.getElementById('results');
const resultsMeta = document.getElementById('results-meta');
const trackList   = document.getElementById('track-list');
const saveBtn       = document.getElementById('save-btn');
const regenBtn      = document.getElementById('regen-btn');
const toast         = document.getElementById('toast');
const recList       = document.getElementById('rec-list');
const recSubtitle   = document.getElementById('rec-subtitle');
const recRefreshBtn = document.getElementById('rec-refresh-btn');
const pageLayout    = document.getElementById('page-layout');
const showPlaylistsBtn = document.getElementById('show-playlists-btn');
const savedScreen   = document.getElementById('saved-playlists-screen');
const backToMainBtn = document.getElementById('back-to-main-btn');
const savedMeta     = document.getElementById('saved-playlists-meta');
const savedLoading  = document.getElementById('saved-playlists-loading');
const savedEmpty    = document.getElementById('saved-playlists-empty');
const savedList     = document.getElementById('saved-playlists-list');

let savedPlaylistsCache = [];
let mainScrollY = 0;

// ── Init ──────────────────────────────────────────────────────────────────────
function init() {
  renderTagGroup(genreChips, GENRES, state.genres);
  renderTagGroup(moodChips, MOODS, state.moods);
  renderEraGroup();

  sizeSlider.addEventListener('input', () => {
    state.size = +sizeSlider.value;
    sizeDisplay.textContent = state.size;
  });

  seedInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); addSeedSong(); }
  });
  seedAddBtn.addEventListener('click', addSeedSong);

  genreChips.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-tag]');
    if (btn) toggleTag(state.genres, btn.dataset.tag, genreChips);
  });
  moodChips.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-tag]');
    if (btn) toggleTag(state.moods, btn.dataset.tag, moodChips);
  });
  eraChips.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-era]');
    if (btn) selectEra(btn.dataset.era);
  });

  trackList.addEventListener('click', handleTrackEvent);
  recList.addEventListener('click', handleAddRec);
  recRefreshBtn.addEventListener('click', () => loadRecommendations());
  form.addEventListener('submit', handleGenerate);
  saveBtn.addEventListener('click', handleSave);
  if (showPlaylistsBtn) showPlaylistsBtn.addEventListener('click', showSavedPlaylists);
  backToMainBtn.addEventListener('click', showMainPage);
  savedList.addEventListener('click', handleSavedPlaylistAction);
  regenBtn.addEventListener('click', () => {
    resultsEl.style.display = 'none';
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  loadRecommendations();
}

// ── Seed songs ────────────────────────────────────────────────────────────────
function addSeedSong() {
  const val = seedInput.value.trim();
  if (!val || state.seedSongs.includes(val)) { seedInput.value = ''; return; }
  state.seedSongs.push(val);
  seedInput.value = '';
  renderSeedChips();
}

function renderSeedChips() {
  seedChips.innerHTML = state.seedSongs.map((s, i) =>
    `<span style="display:inline-flex;align-items:center;gap:6px;background:#2a2a2a;border:1px solid #444;border-radius:9999px;padding:4px 12px;font-size:.8125rem;color:#fff;">
      ${escHtml(s)}
      <button type="button" data-idx="${i}" style="background:none;border:none;color:#888;cursor:pointer;font-size:.9rem;line-height:1;padding:0;">×</button>
    </span>`
  ).join('');
  seedChips.querySelectorAll('[data-idx]').forEach(btn => {
    btn.addEventListener('click', () => { state.seedSongs.splice(+btn.dataset.idx, 1); renderSeedChips(); });
  });
}

// ── Tag chips ─────────────────────────────────────────────────────────────────
function renderTagGroup(container, items, selectedSet) {
  container.innerHTML = items.map(item =>
    `<button type="button" class="chip ${selectedSet.has(item.toLowerCase()) ? 'chip-on' : 'chip-off'}" data-tag="${item.toLowerCase()}">${item}</button>`
  ).join('');
}

function toggleTag(set, value, container) {
  if (set.has(value)) set.delete(value); else set.add(value);
  container.querySelectorAll('[data-tag]').forEach(btn => {
    btn.className = `chip ${set.has(btn.dataset.tag) ? 'chip-on' : 'chip-off'}`;
  });
}

// ── Era ───────────────────────────────────────────────────────────────────────
function renderEraGroup() {
  eraChips.innerHTML = ERAS.map(era =>
    `<button type="button" class="chip ${state.era === era.toLowerCase() ? 'chip-on' : 'chip-off'}" data-era="${era.toLowerCase()}">${era}</button>`
  ).join('');
}

function selectEra(val) {
  state.era = val;
  eraChips.querySelectorAll('[data-era]').forEach(btn => {
    btn.className = `chip ${state.era === btn.dataset.era ? 'chip-on' : 'chip-off'}`;
  });
}

// ── Generate ──────────────────────────────────────────────────────────────────
async function handleGenerate(e) {
  e.preventDefault();
  const allTags = [
    ...state.genres,
    ...state.moods,
    ...(state.era !== 'any' ? [state.era] : []),
  ];
  if (allTags.length === 0 && state.seedSongs.length === 0) {
    showError('Pick at least one genre, mood, era, or seed song.');
    return;
  }
  clearError();
  setLoading(true);
  try {
    const data = await generatePlaylist({ tags: allTags, seedSongs: state.seedSongs, size: state.size });
    state.playlist = data.tracks;
    renderResults(data);
  } catch (err) {
    showError(err.message || 'Failed to generate playlist. Is the ml-app running?');
  } finally {
    setLoading(false);
  }
}

function renderResults(data) {
  const labels = { tags: 'tag-based', seeds: 'seed-based', mixed: 'mixed', random: 'random' };
  resultsMeta.textContent = `${data.size} songs · ${labels[data.source] || data.source}`;

  trackList.innerHTML = data.tracks.map((track, i) => {
    const colour = GENRE_COLOURS[i % GENRE_COLOURS.length];
    const initials = (track.artist || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
    const moodStr = (track.mood || []).slice(0, 2).join(', ');
    const sid = escHtml(track.song_id || '');
    return `
      <li style="display:flex;align-items:center;gap:12px;padding:10px 12px;border-radius:8px;transition:background .15s;"
          onmouseover="this.style.background='#1e1e1e'" onmouseout="this.style.background='transparent'">
        <span style="color:#555;font-size:.8rem;width:22px;text-align:right;flex-shrink:0;">${i + 1}</span>
        <div style="width:40px;height:40px;border-radius:6px;background:${colour};display:flex;align-items:center;justify-content:center;font-size:.75rem;font-weight:700;color:#fff;flex-shrink:0;">${initials}</div>
        <div style="flex:1;min-width:0;">
          <div style="font-weight:600;font-size:.9rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escHtml(track.title)}</div>
          <div style="color:#888;font-size:.8rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escHtml(track.artist)}${moodStr ? ' · ' + escHtml(moodStr) : ''}</div>
        </div>
        ${track.genre ? `<span style="font-size:.7rem;background:#2a2a2a;border:1px solid #333;border-radius:4px;padding:2px 8px;color:#aaa;flex-shrink:0;">${escHtml(track.genre)}</span>` : ''}
        ${track.era  ? `<span style="font-size:.7rem;color:#555;flex-shrink:0;">${escHtml(track.era)}</span>` : ''}
        <div style="display:flex;gap:4px;flex-shrink:0;">
          <button data-song="${sid}" data-event="like"
                  style="background:none;border:1px solid #333;border-radius:6px;padding:4px 8px;cursor:pointer;font-size:.85rem;color:#888;transition:all .15s;"
                  title="Like">👍</button>
          <button data-song="${sid}" data-event="dislike"
                  style="background:none;border:1px solid #333;border-radius:6px;padding:4px 8px;cursor:pointer;font-size:.85rem;color:#888;transition:all .15s;"
                  title="Dislike">👎</button>
        </div>
      </li>`;
  }).join('');

  resultsEl.style.display = 'block';
  resultsEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ── Save ──────────────────────────────────────────────────────────────────────
async function handleSave() {
  if (!state.playlist.length) return;
  saveBtn.disabled = true;
  saveBtn.innerHTML = '<svg style="display:inline;width:14px;height:14px;animation:spin 1s linear infinite;vertical-align:middle;margin-right:5px;" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" stroke-dasharray="31.4" stroke-dashoffset="10"/></svg>Saving…';
  const result = await savePlaylist(state.playlist, window.CURRENT_USER?.id || null);
  saveBtn.disabled = false;
  saveBtn.textContent = 'Save';
  if (result.ok) {
    showToast('Saved! Downloading CSV…');
    loadRecommendations();
    if (savedScreen.style.display === 'block') {
      loadSavedPlaylists();
    }
    const a = document.createElement('a');
    a.href = `/api/playlists/${result.id}/csv`;
    a.download = '';
    document.body.appendChild(a);
    a.click();
    a.remove();
  } else if (result.status === 401 || result.message?.includes('Sign in')) {
    showToast('Sign in to save playlists.', true);
    setTimeout(() => { window.location.href = '/login'; }, 1500);
  } else {
    showToast(result.message || 'Save failed.', true);
  }
}

// ── Saved playlists screen ───────────────────────────────────────────────────
async function showSavedPlaylists() {
  mainScrollY = window.scrollY;
  pageLayout.style.display = 'none';
  savedScreen.style.display = 'block';
  window.scrollTo({ top: 0, behavior: 'smooth' });
  await loadSavedPlaylists();
}

function showMainPage() {
  savedScreen.style.display = 'none';
  pageLayout.style.display = 'flex';
  window.scrollTo({ top: mainScrollY, behavior: 'smooth' });
}

async function loadSavedPlaylists() {
  savedLoading.style.display = 'block';
  savedEmpty.style.display = 'none';
  savedList.innerHTML = '';
  savedMeta.textContent = 'MongoDB saved playlists for your account.';

  try {
    const data = await getPlaylists();
    savedPlaylistsCache = data.playlists || [];
    savedLoading.style.display = 'none';

    if (!savedPlaylistsCache.length) {
      savedEmpty.style.display = 'block';
      savedMeta.textContent = 'No saved playlists yet.';
      return;
    }

    savedMeta.textContent = `${savedPlaylistsCache.length} saved playlist${savedPlaylistsCache.length === 1 ? '' : 's'}`;
    savedList.innerHTML = savedPlaylistsCache.map(renderSavedPlaylist).join('');
  } catch (err) {
    savedLoading.style.display = 'none';
    savedEmpty.style.display = 'block';
    savedEmpty.textContent = err.message || 'Could not load playlists.';
    savedMeta.textContent = 'Could not load saved playlists.';
  }
}

function renderSavedPlaylist(playlist, index) {
  const tracks = Array.isArray(playlist.tracks) ? playlist.tracks : [];
  const date = formatPlaylistDate(playlist.savedAt || playlist.createdAt);
  const previewRows = tracks.slice(0, 5).map((track, i) => renderSavedTrack(track, i)).join('');
  const extra = tracks.length > 5
    ? `<p style="color:#666;font-size:.78rem;margin:8px 0 0 46px;">${tracks.length - 5} more track${tracks.length - 5 === 1 ? '' : 's'}</p>`
    : '';

  return `
    <article style="background:#181818;border:1px solid #2a2a2a;border-radius:8px;padding:16px;">
      <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:14px;margin-bottom:12px;">
        <div style="min-width:0;">
          <h2 style="font-size:1rem;font-weight:700;margin:0 0 3px;">${tracks.length} tracks</h2>
          <p style="color:#888;font-size:.8rem;margin:0;">Saved ${escHtml(date)}</p>
        </div>
        <div style="display:flex;gap:8px;flex-shrink:0;">
          <button type="button" data-open-playlist="${index}"
                  style="background:#1DB954;color:#000;font-weight:600;border:none;border-radius:9999px;padding:7px 14px;font-size:.82rem;cursor:pointer;">
            Open
          </button>
          <a href="/api/playlists/${encodeURIComponent(playlist.id)}/csv" download
             style="background:#2a2a2a;color:#fff;border:1px solid #444;border-radius:9999px;padding:7px 14px;font-size:.82rem;text-decoration:none;">
            CSV
          </a>
        </div>
      </div>
      <ol style="list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:2px;">
        ${previewRows || '<li style="color:#666;font-size:.85rem;padding:10px 0;">No tracks stored in this playlist.</li>'}
      </ol>
      ${extra}
    </article>`;
}

function renderSavedTrack(track, index) {
  const colour = GENRE_COLOURS[index % GENRE_COLOURS.length];
  const initials = (track.artist || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
  const moodStr = Array.isArray(track.mood) ? track.mood.slice(0, 2).join(', ') : track.mood || '';
  return `
    <li class="track-row">
      <span style="color:#555;font-size:.8rem;width:22px;text-align:right;flex-shrink:0;">${index + 1}</span>
      <div style="width:34px;height:34px;border-radius:6px;background:${colour};display:flex;align-items:center;justify-content:center;font-size:.7rem;font-weight:700;color:#fff;flex-shrink:0;">${escHtml(initials)}</div>
      <div style="flex:1;min-width:0;">
        <div style="font-weight:600;font-size:.88rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escHtml(track.title || 'Untitled Track')}</div>
        <div style="color:#888;font-size:.78rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escHtml(track.artist || 'Unknown Artist')}${moodStr ? ' · ' + escHtml(moodStr) : ''}</div>
      </div>
      ${track.genre ? `<span style="font-size:.7rem;background:#2a2a2a;border:1px solid #333;border-radius:4px;padding:2px 8px;color:#aaa;flex-shrink:0;">${escHtml(track.genre)}</span>` : ''}
    </li>`;
}

function handleSavedPlaylistAction(e) {
  const openBtn = e.target.closest('[data-open-playlist]');
  if (!openBtn) return;

  const playlist = savedPlaylistsCache[Number(openBtn.dataset.openPlaylist)];
  if (!playlist) return;

  state.playlist = Array.isArray(playlist.tracks) ? playlist.tracks : [];
  showMainPage();
  renderResults({ tracks: state.playlist, source: 'saved', size: state.playlist.length });
}

function formatPlaylistDate(value) {
  if (!value) return 'recently';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value).slice(0, 10);
  return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

// ── Recommendations ───────────────────────────────────────────────────────────
async function loadRecommendations() {
  const userId = window.CURRENT_USER?.id;
  if (!userId) return;
  recList.innerHTML = '<p style="color:#555;font-size:.8rem;text-align:center;padding:12px 0;">Loading…</p>';
  try {
    const data = await getRecommendations(userId, 10);
    renderRecommendations(data);
  } catch {
    recList.innerHTML = '<p style="color:#555;font-size:.8rem;text-align:center;padding:12px 0;">Unavailable</p>';
  }
}

function renderRecommendations(data) {
  const isMock = data.source === 'mock';
  recSubtitle.textContent = isMock
    ? 'Like or save songs to personalise'
    : 'Based on your likes & saves';

  if (!data.recommendations?.length) {
    recList.innerHTML = '<p style="color:#555;font-size:.8rem;text-align:center;padding:12px 0;">No recommendations yet</p>';
    return;
  }

  recList.innerHTML = data.recommendations.map((track, i) => {
    const colour = GENRE_COLOURS[i % GENRE_COLOURS.length];
    const initials = (track.artist || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
    const inPlaylist = state.playlist.some(t => t.song_id === track.song_id);
    return `
      <div style="display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid #2a2a2a;">
        <div style="width:32px;height:32px;border-radius:5px;background:${colour};display:flex;align-items:center;justify-content:center;font-size:.7rem;font-weight:700;color:#fff;flex-shrink:0;">${initials}</div>
        <div style="flex:1;min-width:0;">
          <div style="font-size:.8rem;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escHtml(track.title)}</div>
          <div style="font-size:.73rem;color:#888;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escHtml(track.artist)}</div>
          <div style="font-size:.7rem;color:#1DB954;margin-top:1px;">score ${track.score.toFixed(2)}</div>
        </div>
        <button data-rec='${JSON.stringify({ song_id: track.song_id, title: track.title, artist: track.artist, genre: track.genre || null, mood: [], era: null, score: track.score })}'
                ${inPlaylist ? 'disabled' : ''}
                style="background:none;border:1px solid ${inPlaylist ? '#2a2a2a' : '#444'};color:${inPlaylist ? '#333' : '#aaa'};border-radius:6px;width:28px;height:28px;cursor:${inPlaylist ? 'default' : 'pointer'};font-size:1rem;flex-shrink:0;transition:all .15s;"
                ${inPlaylist ? '' : 'onmouseover="this.style.borderColor=\'#1DB954\';this.style.color=\'#1DB954\'" onmouseout="this.style.borderColor=\'#444\';this.style.color=\'#aaa\'"'}
                title="${inPlaylist ? 'Already in playlist' : 'Add to playlist'}">
          ${inPlaylist ? '✓' : '+'}
        </button>
      </div>`;
  }).join('');
}

function handleAddRec(e) {
  const btn = e.target.closest('[data-rec]');
  if (!btn || btn.disabled) return;
  const track = JSON.parse(btn.dataset.rec);
  if (state.playlist.some(t => t.song_id === track.song_id)) return;

  state.playlist.push(track);
  renderResults({ tracks: state.playlist, source: 'mixed', size: state.playlist.length });
  resultsEl.style.display = 'block';

  // Mark button as added
  btn.disabled = true;
  btn.textContent = '✓';
  btn.style.borderColor = '#2a2a2a';
  btn.style.color = '#333';
  btn.style.cursor = 'default';
  btn.onmouseover = null;
  btn.onmouseout = null;

  showToast(`"${escHtml(track.title)}" added to playlist`);
}

// ── Track events ──────────────────────────────────────────────────────────────
async function handleTrackEvent(e) {
  const btn = e.target.closest('[data-event]');
  if (!btn) return;
  const songId = btn.dataset.song;
  const eventType = btn.dataset.event;
  if (!songId) return;

  btn.disabled = true;
  const result = await recordEvent(songId, eventType);

  if (result.ok) {
    const isLike = eventType === 'like';
    btn.style.background = isLike ? 'rgba(29,185,84,.15)' : 'rgba(239,68,68,.15)';
    btn.style.borderColor = isLike ? '#1DB954' : '#ef4444';
    btn.style.color = isLike ? '#1DB954' : '#ef4444';
    const sibling = btn.parentElement.querySelector(`[data-event="${isLike ? 'dislike' : 'like'}"]`);
    if (sibling) sibling.disabled = true;
    loadRecommendations();
  } else {
    btn.disabled = false;
  }
}

// ── UI helpers ────────────────────────────────────────────────────────────────
function setLoading(on) {
  generateBtn.disabled = on;
  btnLabel.textContent = on ? 'Generating…' : 'Generate Playlist';
  btnSpinner.style.display = on ? 'block' : 'none';
  generateBtn.style.opacity = on ? '.7' : '1';
}

function showError(msg) { errorMsg.textContent = msg; errorMsg.style.display = 'block'; }
function clearError()   { errorMsg.style.display = 'none'; }

let toastTimer;
function showToast(msg, isError = false) {
  toast.textContent = msg;
  toast.style.borderColor = isError ? '#ef4444' : '#1DB954';
  toast.style.opacity = '1';
  toast.style.transform = 'translateY(0)';
  toast.style.pointerEvents = 'auto';
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(16px)';
    toast.style.pointerEvents = 'none';
  }, 3000);
}

function escHtml(str) {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

init();
