import { generatePlaylist, savePlaylist, fetchPlaylists } from './api.js';

// ── Constants ──────────────────────────────────────────────────────────────

const GENRES = [
  'Pop', 'Rock', 'Hip-Hop', 'R&B', 'Electronic',
  'Indie', 'Jazz', 'Classical', 'Metal', 'Folk',
  'Soul', 'Lo-fi', 'Punk', 'Reggae', 'Country',
];

// Unique SVG paths used for placeholder album art colours
const COVER_COLOURS = [
  '#1DB954', '#E91429', '#509BF5', '#FF6437',
  '#AF2896', '#2D46B9', '#8D67AB', '#006450',
];

// ── State ──────────────────────────────────────────────────────────────────

let currentPlaylist = [];

// ── DOM refs ───────────────────────────────────────────────────────────────

const form            = document.getElementById('generatorForm');
const generateBtn     = document.getElementById('generateBtn');
const btnLabel        = document.getElementById('btnLabel');
const btnSpinner      = document.getElementById('btnSpinner');
const genreGrid       = document.getElementById('genreGrid');
const sizeSlider      = document.getElementById('playlistSize');
const sizeDisplay     = document.getElementById('sizeDisplay');
const resultsSection  = document.getElementById('resultsSection');
const trackList       = document.getElementById('trackList');
const trackCount      = document.getElementById('trackCount');
const saveBtn         = document.getElementById('saveBtn');
const regenerateBtn   = document.getElementById('regenerateBtn');
const saveToast       = document.getElementById('saveToast');
const formError       = document.getElementById('formError');
const healthBtn       = document.getElementById('healthBtn');
const healthDot       = document.getElementById('healthDot');
const healthLabel     = document.getElementById('healthLabel');
const menuToggle          = document.getElementById('menuToggle');
const sidebar             = document.getElementById('sidebar');
const sidebarBackdrop     = document.getElementById('sidebarBackdrop');

// Saved playlists
const savedSection        = document.getElementById('savedSection');
const playlistsListView   = document.getElementById('playlistsListView');
const playlistDetailView  = document.getElementById('playlistDetailView');
const playlistsList       = document.getElementById('playlistsList');
const playlistsLoading    = document.getElementById('playlistsLoading');
const playlistsEmpty      = document.getElementById('playlistsEmpty');
const playlistDetailMeta  = document.getElementById('playlistDetailMeta');
const playlistDetailTracks = document.getElementById('playlistDetailTracks');
const backToPlaylists      = document.getElementById('backToPlaylists');
const playlistsSort        = document.getElementById('playlistsSort');

// ── Initialise genres ──────────────────────────────────────────────────────

function initGenres() {
  genreGrid.innerHTML = GENRES.map((g) => `
    <label class="genre-chip cursor-pointer select-none">
      <input type="checkbox" name="genres" value="${g}" class="sr-only" />
      <span class="inline-block px-4 py-1.5 rounded-full border border-spotify-card
                   text-sm text-spotify-subtle transition-all duration-150
                   hover:border-white hover:text-white">
        ${g}
      </span>
    </label>
  `).join('');
}

// ── Range slider live value ────────────────────────────────────────────────

sizeSlider.addEventListener('input', () => {
  sizeDisplay.textContent = `${sizeSlider.value} tracks`;
});

// ── Mobile sidebar toggle ──────────────────────────────────────────────────

function openSidebar() {
  sidebar.classList.remove('-translate-x-full');
  sidebarBackdrop.classList.remove('hidden');
}

function closeSidebar() {
  sidebar.classList.add('-translate-x-full');
  sidebarBackdrop.classList.add('hidden');
}

menuToggle.addEventListener('click', openSidebar);
sidebarBackdrop.addEventListener('click', closeSidebar);

// ── Generate form submit ───────────────────────────────────────────────────

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  clearError();

  const vibe = document.getElementById('vibe').value.trim();
  if (!vibe) {
    showError('Please describe your vibe before generating.');
    return;
  }

  const selectedGenres = [...document.querySelectorAll('input[name="genres"]:checked')]
    .map((cb) => cb.value);

  const params = {
    vibe,
    genres:      selectedGenres,
    size:        sizeSlider.value,
    era:         document.getElementById('era').value.trim(),
    seedArtists: document.getElementById('seedArtists').value.trim(),
  };

  setLoading(true);

  try {
    const tracks = await generatePlaylist(params);
    currentPlaylist = tracks;
    renderPlaylist(tracks);
    resetForm();
  } catch (err) {
    showError('Something went wrong generating your playlist. Please try again.');
  } finally {
    setLoading(false);
  }
});

// ── Render playlist ────────────────────────────────────────────────────────

/**
 * Injects track cards into #trackList and reveals the results section.
 * @param {Array<{id: number, title: string, artist: string, duration: string}>} tracks
 */
function renderPlaylist(tracks) {
  trackCount.textContent = `${tracks.length} tracks`;
  hideToast();

  trackList.innerHTML = tracks.map((track, index) => {
    const colour = COVER_COLOURS[index % COVER_COLOURS.length];
    const initials = track.artist.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase();
    return `
      <article class="track-card flex items-center gap-4 bg-spotify-surface hover:bg-spotify-card
                       rounded-lg px-4 py-3 group transition-colors duration-150"
               data-id="${track.id}">

        <!-- Index / play hover -->
        <div class="w-8 text-center shrink-0">
          <span class="track-num text-spotify-subtle text-sm group-hover:hidden">${index + 1}</span>
          <button class="play-btn hidden group-hover:flex items-center justify-center
                         text-white hover:text-spotify-green transition-colors"
                  aria-label="Play ${track.title}">
            <svg class="w-4 h-4 fill-current" viewBox="0 0 24 24">
              <path d="M8 5v14l11-7z"/>
            </svg>
          </button>
        </div>

        <!-- Cover art -->
        <div class="w-10 h-10 rounded shrink-0 flex items-center justify-center
                    text-xs font-bold text-white"
             style="background-color: ${colour}88; border: 1px solid ${colour}44;">
          ${initials}
        </div>

        <!-- Title & artist -->
        <div class="flex-1 min-w-0">
          <p class="text-sm font-semibold truncate">${escapeHtml(track.title)}</p>
          <p class="text-xs text-spotify-subtle truncate">${escapeHtml(track.artist)}</p>
        </div>

        <!-- Duration -->
        <span class="text-spotify-subtle text-xs shrink-0 mr-2">${track.duration}</span>

        <!-- Add button -->
        <button class="add-track shrink-0 w-7 h-7 rounded-full border border-spotify-subtle
                       flex items-center justify-center opacity-0 group-hover:opacity-100
                       hover:border-white hover:text-white transition-all duration-150"
                aria-label="Add ${escapeHtml(track.title)} to library"
                data-id="${track.id}">
          <svg class="w-3.5 h-3.5 fill-current" viewBox="0 0 24 24">
            <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>
          </svg>
        </button>
      </article>
    `;
  }).join('');

  // Delegate "add" button clicks
  trackList.addEventListener('click', onTrackAction, { once: true });

  resultsSection.classList.remove('hidden');
  resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ── Track action delegation ────────────────────────────────────────────────

function onTrackAction(e) {
  const addBtn = e.target.closest('.add-track');
  if (!addBtn) {
    // re-attach since we used { once }
    trackList.addEventListener('click', onTrackAction, { once: true });
    return;
  }
  const id   = Number(addBtn.dataset.id);
  const card = addBtn.closest('.track-card');
  addBtn.innerHTML = `
    <svg class="w-3.5 h-3.5 fill-current text-spotify-green" viewBox="0 0 24 24">
      <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
    </svg>`;
  addBtn.classList.add('border-spotify-green', 'opacity-100');
  addBtn.disabled = true;
  card.classList.add('ring-1', 'ring-spotify-green/30');

  // re-attach for other tracks
  trackList.addEventListener('click', onTrackAction, { once: true });
}

// ── Save to MongoDB ────────────────────────────────────────────────────────

saveBtn.addEventListener('click', async () => {
  if (!currentPlaylist.length) return;

  saveBtn.disabled = true;
  saveBtn.textContent = 'Saving…';

  let userId = null;
  try {
    const s = JSON.parse(localStorage.getItem('vibelist_settings') || '{}');
    userId = s.displayName || s.email || null;
  } catch { /* ignore parse errors */ }

  const result = await savePlaylist(currentPlaylist, userId);

  saveBtn.disabled = false;
  saveBtn.innerHTML = `
    <svg class="w-4 h-4 fill-current" viewBox="0 0 24 24">
      <path d="M17 3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0
               2-.9 2-2V7l-4-4zm-5 16c-1.66 0-3-1.34-3-3s1.34-3 3-3
               3 1.34 3 3-1.34 3-3 3zm3-10H5V5h10v4z"/>
    </svg>
    Save to MongoDB`;

  showToast(
    result?.ok === false
      ? `Error: ${result.message}`
      : 'Playlist saved to MongoDB!',
    result?.ok === false ? 'error' : 'success',
  );
});

// ── Regenerate ─────────────────────────────────────────────────────────────

regenerateBtn.addEventListener('click', () => {
  resultsSection.classList.add('hidden');
  currentPlaylist = [];
  window.scrollTo({ top: 0, behavior: 'smooth' });
});

// ── DB Health check ────────────────────────────────────────────────────────

healthBtn.addEventListener('click', async () => {
  healthLabel.textContent = 'Checking…';
  healthDot.className = 'w-2 h-2 rounded-full bg-yellow-400 animate-pulse';
  try {
    const res  = await fetch('/health');
    const data = await res.json();
    if (data.status === 'ok') {
      healthDot.className  = 'w-2 h-2 rounded-full bg-spotify-green';
      healthLabel.textContent = 'DB Connected';
    } else {
      throw new Error(data.mongo);
    }
  } catch {
    healthDot.className  = 'w-2 h-2 rounded-full bg-red-500';
    healthLabel.textContent = 'DB Unreachable';
  }
});

// ── Helpers ────────────────────────────────────────────────────────────────

function setLoading(loading) {
  generateBtn.disabled = loading;
  if (loading) {
    btnLabel.textContent = 'Generating…';
    btnSpinner.classList.remove('hidden');
    generateBtn.classList.add('opacity-80', 'cursor-not-allowed');
  } else {
    btnLabel.textContent = 'Generate Playlist';
    btnSpinner.classList.add('hidden');
    generateBtn.classList.remove('opacity-80', 'cursor-not-allowed');
  }
}

function resetForm() {
  document.getElementById('vibe').value        = '';
  document.getElementById('era').value         = '';
  document.getElementById('seedArtists').value = '';
  sizeSlider.value    = 20;
  sizeDisplay.textContent = '20 tracks';
  document.querySelectorAll('input[name="genres"]:checked')
    .forEach((cb) => { cb.checked = false; });
}

function showError(msg) {
  formError.textContent = msg;
  formError.classList.remove('hidden');
}

function clearError() {
  formError.textContent = '';
  formError.classList.add('hidden');
}

function showToast(msg, type = 'success') {
  saveToast.textContent = msg;
  saveToast.className = [
    'mt-4 px-4 py-3 rounded-lg text-sm font-medium',
    type === 'success'
      ? 'bg-green-900/60 border border-spotify-green text-green-300'
      : 'bg-red-900/60 border border-red-500 text-red-300',
  ].join(' ');
  saveToast.classList.remove('hidden');
}

function hideToast() {
  saveToast.classList.add('hidden');
}

/** Prevent XSS when injecting user-derived data into innerHTML. */
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Nav switching ──────────────────────────────────────────────────────────

const generatorSection = document.getElementById('generatorSection');
const navLinks = document.querySelectorAll('.nav-link[data-nav]');

function showView(view) {
  generatorSection.classList.toggle('hidden', view !== 'generator');
  resultsSection.classList.add('hidden');
  savedSection.classList.toggle('hidden', view !== 'saved');

  navLinks.forEach((link) => {
    const active = link.dataset.nav === view;
    link.classList.toggle('text-white', active);
    link.classList.toggle('bg-spotify-card', active);
    link.classList.toggle('font-semibold', active);
    link.classList.toggle('text-spotify-subtle', !active);
    link.classList.toggle('font-medium', !active);
  });
}

navLinks.forEach((link) => {
  link.addEventListener('click', (e) => {
    e.preventDefault();
    const view = link.dataset.nav;
    showView(view);
    if (view === 'saved') loadSavedPlaylists();
  });
});

// ── Saved playlists ────────────────────────────────────────────────────────

let cachedPlaylists = [];

function sortedPlaylists() {
  const order = playlistsSort.value;
  const copy = [...cachedPlaylists];
  if (order === 'oldest') {
    copy.sort((a, b) => new Date(a.savedAt) - new Date(b.savedAt));
  } else if (order === 'alpha') {
    copy.sort((a, b) => {
      const aLabel = (Array.isArray(a.tracks) && a.tracks[0]?.title) || '';
      const bLabel = (Array.isArray(b.tracks) && b.tracks[0]?.title) || '';
      return aLabel.localeCompare(bLabel);
    });
  } else {
    copy.sort((a, b) => new Date(b.savedAt) - new Date(a.savedAt));
  }
  return copy;
}

function renderPlaylistCards() {
  const playlists = sortedPlaylists();

  if (!playlists.length) {
    playlistsEmpty.classList.remove('hidden');
    playlistsList.innerHTML = '';
    return;
  }
  playlistsEmpty.classList.add('hidden');

  playlistsList.innerHTML = playlists.map((pl) => {
    const date = new Date(pl.savedAt).toLocaleDateString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric',
    });
    const count = Array.isArray(pl.tracks) ? pl.tracks.length : 0;
    const firstTitle = Array.isArray(pl.tracks) && pl.tracks[0]?.title
      ? escapeHtml(pl.tracks[0].title)
      : `${count} track${count !== 1 ? 's' : ''}`;
    const owner = pl.user_id
      ? `<span class="text-spotify-subtle text-xs">${escapeHtml(pl.user_id)}</span>` : '';
    return `
      <button class="playlist-card w-full text-left bg-spotify-surface hover:bg-spotify-card
                     rounded-xl px-5 py-4 transition-colors duration-150 flex items-center gap-4"
              data-id="${pl.id}">
        <div class="w-12 h-12 rounded-lg bg-spotify-green/10 border border-spotify-green/20
                    flex items-center justify-center shrink-0">
          <svg class="w-6 h-6 fill-current text-spotify-green" viewBox="0 0 24 24">
            <path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6z"/>
          </svg>
        </div>
        <div class="flex-1 min-w-0">
          <p class="text-sm font-semibold truncate">${firstTitle}</p>
          <div class="flex items-center gap-2 mt-0.5">${owner}
            <span class="text-spotify-subtle text-xs">${date}</span>
          </div>
        </div>
        <svg class="w-4 h-4 fill-current text-spotify-subtle shrink-0" viewBox="0 0 24 24">
          <path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/>
        </svg>
      </button>`;
  }).join('');

  playlistsList.addEventListener('click', (e) => {
    const card = e.target.closest('.playlist-card');
    if (!card) return;
    const pl = cachedPlaylists.find((p) => p.id === card.dataset.id);
    if (pl) renderPlaylistDetail(pl);
  }, { once: true });
}

playlistsSort.addEventListener('change', renderPlaylistCards);

async function loadSavedPlaylists() {
  playlistsListView.classList.remove('hidden');
  playlistDetailView.classList.add('hidden');
  playlistsList.innerHTML = '';
  playlistsEmpty.classList.add('hidden');
  playlistsLoading.classList.remove('hidden');

  let userId = null;
  try {
    const s = JSON.parse(localStorage.getItem('vibelist_settings') || '{}');
    userId = s.displayName || s.email || null;
  } catch { /* ignore */ }

  cachedPlaylists = await fetchPlaylists(userId);
  playlistsLoading.classList.add('hidden');
  renderPlaylistCards();
}

function renderPlaylistDetail(pl) {
  playlistsListView.classList.add('hidden');
  playlistDetailView.classList.remove('hidden');

  const date = new Date(pl.savedAt).toLocaleDateString(undefined, {
    year: 'numeric', month: 'long', day: 'numeric',
  });
  const owner = pl.user_id ? `· <span class="font-medium text-white">${escapeHtml(pl.user_id)}</span>` : '';
  playlistDetailMeta.innerHTML = `
    <h2 class="text-2xl font-bold mb-1">${Array.isArray(pl.tracks) ? pl.tracks.length : 0} Tracks</h2>
    <p class="text-spotify-subtle text-sm">Saved ${date} ${owner}</p>`;

  const tracks = Array.isArray(pl.tracks) ? pl.tracks : [];
  if (!tracks.length) {
    playlistDetailTracks.innerHTML = '<p class="text-spotify-subtle text-sm py-4">No tracks in this playlist.</p>';
    return;
  }

  playlistDetailTracks.innerHTML = tracks.map((track, index) => {
    const colour = COVER_COLOURS[index % COVER_COLOURS.length];
    const title = escapeHtml(track.title || track.song_id || 'Unknown');
    const artist = escapeHtml(track.artist || '');
    const initials = artist.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase() || '?';
    return `
      <article class="flex items-center gap-4 bg-spotify-surface rounded-lg px-4 py-3">
        <span class="w-8 text-center text-spotify-subtle text-sm shrink-0">${index + 1}</span>
        <div class="w-10 h-10 rounded shrink-0 flex items-center justify-center
                    text-xs font-bold text-white"
             style="background-color:${colour}88;border:1px solid ${colour}44">
          ${initials}
        </div>
        <div class="flex-1 min-w-0">
          <p class="text-sm font-semibold truncate">${title}</p>
          <p class="text-xs text-spotify-subtle truncate">${artist}</p>
        </div>
        ${track.duration ? `<span class="text-spotify-subtle text-xs shrink-0">${escapeHtml(track.duration)}</span>` : ''}
      </article>`;
  }).join('');
}

backToPlaylists.addEventListener('click', () => {
  playlistDetailView.classList.add('hidden');
  playlistsListView.classList.remove('hidden');
  loadSavedPlaylists();
});

// ── Boot ───────────────────────────────────────────────────────────────────

initGenres();
