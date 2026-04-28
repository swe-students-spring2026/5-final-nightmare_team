'use strict';

// ── Constants ──────────────────────────────────────────────────────────────

const STORAGE_KEY = 'vibelist_settings';

const GENRES = [
  'Pop', 'Rock', 'Hip-Hop', 'R&B', 'Electronic',
  'Indie', 'Jazz', 'Classical', 'Metal', 'Folk',
  'Soul', 'Lo-fi', 'Punk', 'Reggae', 'Country',
];

const DEFAULT_SETTINGS = {
  displayName: '',
  email: '',
  defaultPlaylistSize: 20,
  preferredGenres: [],
  defaultEra: 'any',
  autoSave: false,
  publicPlaylists: false,
  spotifyConnected: true,
};

// ── State ──────────────────────────────────────────────────────────────────

let savedSettings = { ...DEFAULT_SETTINGS };
let isDirty = false;

// ── DOM refs ───────────────────────────────────────────────────────────────

const settingsForm          = document.getElementById('settingsForm');
const displayNameInput      = document.getElementById('displayName');
const emailInput            = document.getElementById('email');
const defaultSizeInput      = document.getElementById('defaultPlaylistSize');
const defaultEraSelect      = document.getElementById('defaultEra');
const autoSaveToggle        = document.getElementById('autoSave');
const publicPlaylistsToggle = document.getElementById('publicPlaylists');
const spotifyBtn            = document.getElementById('spotifyBtn');
const spotifyBadge          = document.getElementById('spotifyBadge');
const spotifyStatus         = document.getElementById('spotifyStatus');
const genreChipsContainer   = document.getElementById('genreChips');
const avatarPlaceholder     = document.getElementById('avatarPlaceholder');
const avatarInitials        = document.getElementById('avatarInitials');
const uploadPhotoBtn        = document.getElementById('uploadPhotoBtn');
const saveBar               = document.getElementById('saveBar');
const saveBtn               = document.getElementById('saveBtn');
const discardBtn            = document.getElementById('discardBtn');
const toastEl               = document.getElementById('toast');
const clearHistoryBtn       = document.getElementById('clearHistoryBtn');
const deleteAccountBtn      = document.getElementById('deleteAccountBtn');
const healthBtn             = document.getElementById('healthBtn');
const healthDot             = document.getElementById('healthDot');
const healthLabel           = document.getElementById('healthLabel');
const menuToggle            = document.getElementById('menuToggle');
const sidebar               = document.getElementById('sidebar');
const sidebarBackdrop       = document.getElementById('sidebarBackdrop');

// ── Genre chips ────────────────────────────────────────────────────────────

function initGenreChips() {
  genreChipsContainer.innerHTML = GENRES.map((g) => `
    <label class="genre-chip-settings cursor-pointer select-none">
      <input type="checkbox" value="${g}" class="sr-only" />
      <span class="inline-block px-3 py-1.5 rounded-full border border-spotify-card
                   text-sm text-spotify-subtle transition-all duration-150
                   hover:border-white hover:text-white">
        ${g}
      </span>
    </label>
  `).join('');

  genreChipsContainer.addEventListener('change', markDirty);
}

// ── Load settings ──────────────────────────────────────────────────────────

function loadSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) savedSettings = { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
  } catch {
    savedSettings = { ...DEFAULT_SETTINGS };
  }
  applyToUI(savedSettings);
  isDirty = false;
  renderSaveBar();
}

function applyToUI(s) {
  displayNameInput.value        = s.displayName || '';
  emailInput.value              = s.email || '';
  defaultSizeInput.value        = s.defaultPlaylistSize ?? 20;
  defaultEraSelect.value        = s.defaultEra || 'any';
  autoSaveToggle.checked        = !!s.autoSave;
  publicPlaylistsToggle.checked = !!s.publicPlaylists;

  document.querySelectorAll('.genre-chip-settings input').forEach((cb) => {
    cb.checked = (s.preferredGenres || []).includes(cb.value);
  });

  updateSpotifyUI(s.spotifyConnected);
  updateAvatar(s.displayName);
}

// ── Save settings ──────────────────────────────────────────────────────────

function saveSettings() {
  const current = readFromUI();
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(current));
    savedSettings = current;
    isDirty = false;
    renderSaveBar();
    showToast('Settings Saved!', 'success');
  } catch {
    showToast('Could not save — storage may be full.', 'error');
  }
}

function readFromUI() {
  const size = Math.min(50, Math.max(5, parseInt(defaultSizeInput.value, 10) || 20));
  defaultSizeInput.value = size;

  return {
    displayName:         displayNameInput.value.trim(),
    email:               emailInput.value.trim(),
    defaultPlaylistSize: size,
    preferredGenres:     [...document.querySelectorAll('.genre-chip-settings input:checked')]
                           .map((cb) => cb.value),
    defaultEra:          defaultEraSelect.value,
    autoSave:            autoSaveToggle.checked,
    publicPlaylists:     publicPlaylistsToggle.checked,
    spotifyConnected:    savedSettings.spotifyConnected,
  };
}

// ── Dirty / save bar ───────────────────────────────────────────────────────

function markDirty() {
  isDirty = true;
  renderSaveBar();
}

function renderSaveBar() {
  saveBar.classList.toggle('hidden', !isDirty);
}

// ── Spotify integration ────────────────────────────────────────────────────

function updateSpotifyUI(connected) {
  if (connected) {
    spotifyBadge.classList.remove('hidden');
    spotifyStatus.textContent = 'Syncing your library';
    spotifyBtn.textContent    = 'Disconnect';
    spotifyBtn.className      =
      'px-4 py-2 rounded-full text-sm font-semibold border border-spotify-subtle ' +
      'text-spotify-subtle hover:border-red-400 hover:text-red-400 transition-colors';
  } else {
    spotifyBadge.classList.add('hidden');
    spotifyStatus.textContent = 'Connect to stream and save directly to your library';
    spotifyBtn.textContent    = 'Connect Spotify';
    spotifyBtn.className      =
      'px-4 py-2 rounded-full text-sm font-bold bg-spotify-green text-black ' +
      'hover:bg-green-400 active:scale-95 transition-all duration-150';
  }
}

spotifyBtn.addEventListener('click', () => {
  savedSettings.spotifyConnected = !savedSettings.spotifyConnected;
  updateSpotifyUI(savedSettings.spotifyConnected);
  markDirty();
});

// ── Avatar ─────────────────────────────────────────────────────────────────

function updateAvatar(name) {
  if (!name || !name.trim()) {
    avatarInitials.textContent = '?';
    return;
  }
  const initials = name.trim()
    .split(/\s+/)
    .map((w) => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();
  avatarInitials.textContent = initials;
}

displayNameInput.addEventListener('input', () => {
  updateAvatar(displayNameInput.value);
  markDirty();
});

// Photo upload
const photoInput = document.createElement('input');
photoInput.type   = 'file';
photoInput.accept = 'image/*';

uploadPhotoBtn.addEventListener('click', () => photoInput.click());

photoInput.addEventListener('change', (e) => {
  const file = e.target.files?.[0];
  if (!file) return;

  if (file.size > 2 * 1024 * 1024) {
    showToast('Image must be under 2 MB.', 'error');
    photoInput.value = '';
    return;
  }

  const reader = new FileReader();
  reader.onload = (ev) => {
    avatarPlaceholder.style.backgroundImage    = `url(${ev.target.result})`;
    avatarPlaceholder.style.backgroundSize     = 'cover';
    avatarPlaceholder.style.backgroundPosition = 'center';
    avatarInitials.style.display = 'none';
    markDirty();
  };
  reader.readAsDataURL(file);
  photoInput.value = '';
});

// ── Toast ──────────────────────────────────────────────────────────────────

let toastTimer = null;

function showToast(msg, type = 'success') {
  const ok = type === 'success';

  const icon = ok
    ? `<svg class="w-4 h-4 fill-current shrink-0" viewBox="0 0 24 24">
         <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
       </svg>`
    : `<svg class="w-4 h-4 fill-current shrink-0" viewBox="0 0 24 24">
         <path d="M12 2C6.47 2 2 6.47 2 12s4.47 10 10 10 10-4.47
                  10-10S17.53 2 12 2zm5 13.59L15.59 17 12 13.41 8.41
                  17 7 15.59 10.59 12 7 8.41 8.41 7 12 10.59 15.59
                  7 17 8.41 13.41 12 17 15.59z"/>
       </svg>`;

  toastEl.className = [
    'fixed top-6 right-6 z-50 px-5 py-3 rounded-xl shadow-2xl',
    'flex items-center gap-2.5 text-sm font-semibold toast-enter',
    ok
      ? 'bg-green-900/90 backdrop-blur border border-spotify-green text-green-300'
      : 'bg-red-900/90 backdrop-blur border border-red-500 text-red-300',
  ].join(' ');

  toastEl.innerHTML = `${icon}<span>${msg}</span>`;

  if (toastTimer) clearTimeout(toastTimer);

  toastTimer = setTimeout(() => {
    toastEl.style.cssText = 'opacity:0;transform:translateX(12px);transition:opacity .3s,transform .3s;';
    setTimeout(() => {
      toastEl.classList.add('hidden');
      toastEl.style.cssText = '';
    }, 300);
  }, 3000);
}

// ── Form events ────────────────────────────────────────────────────────────

emailInput.addEventListener('input', markDirty);
defaultSizeInput.addEventListener('input', markDirty);
defaultEraSelect.addEventListener('change', markDirty);
autoSaveToggle.addEventListener('change', markDirty);
publicPlaylistsToggle.addEventListener('change', markDirty);

settingsForm.addEventListener('submit', (e) => {
  e.preventDefault();
  saveSettings();
});

saveBtn.addEventListener('click', saveSettings);

discardBtn.addEventListener('click', () => {
  applyToUI(savedSettings);
  isDirty = false;
  renderSaveBar();
});

// ── Danger zone ────────────────────────────────────────────────────────────

clearHistoryBtn.addEventListener('click', () => {
  if (!confirm('Clear all generation history? This cannot be undone.')) return;
  showToast('Generation history cleared.', 'success');
});

deleteAccountBtn.addEventListener('click', () => {
  if (!confirm('Delete your account? All data will be permanently removed.')) return;
  if (!confirm('This is irreversible. Click OK to confirm account deletion.')) return;
  showToast('Account deletion requested.', 'error');
});

// ── DB Health ──────────────────────────────────────────────────────────────

healthBtn.addEventListener('click', async () => {
  healthLabel.textContent = 'Checking…';
  healthDot.className = 'w-2 h-2 rounded-full bg-yellow-400 animate-pulse';
  try {
    const res  = await fetch('/health');
    const data = await res.json();
    if (data.status === 'ok') {
      healthDot.className     = 'w-2 h-2 rounded-full bg-spotify-green';
      healthLabel.textContent = 'DB Connected';
    } else {
      throw new Error(data.mongo);
    }
  } catch {
    healthDot.className     = 'w-2 h-2 rounded-full bg-red-500';
    healthLabel.textContent = 'DB Unreachable';
  }
});

// ── Mobile sidebar ────────────────────────────────────────────────────────

menuToggle.addEventListener('click', () => {
  sidebar.classList.remove('-translate-x-full');
  sidebarBackdrop.classList.remove('hidden');
});

sidebarBackdrop.addEventListener('click', () => {
  sidebar.classList.add('-translate-x-full');
  sidebarBackdrop.classList.add('hidden');
});

// ── Boot ───────────────────────────────────────────────────────────────────

initGenreChips();
loadSettings();
