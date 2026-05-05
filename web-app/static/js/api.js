/**
 * API service — calls the Flask backend which proxies to ml-app.
 */

/**
 * @param {{ tags: string[], seedSongs: string[], size: number }} params
 * @returns {Promise<{ tracks: object[], source: string, size: number }>}
 */
export async function generatePlaylist({ tags, seedSongs, size }) {
  const res = await fetch('/api/generate-playlist', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tags, seed_songs: seedSongs, size }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || `Request failed (${res.status})`);
  }
  return data;
}

/**
 * @param {string} userId
 * @param {number} k
 * @returns {Promise<{ user_id: string, source: string, recommendations: object[] }>}
 */
export async function getRecommendations(userId, k = 10) {
  const res = await fetch(`/api/recommendations/${encodeURIComponent(userId)}?k=${k}`);
  if (!res.ok) throw new Error(`Recommendations unavailable (${res.status})`);
  return res.json();
}

/**
 * @param {string} songId
 * @param {'like'|'dislike'} eventType
 * @returns {Promise<{ ok: boolean }>}
 */
export async function recordEvent(songId, eventType) {
  try {
    const res = await fetch('/api/events', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ song_id: songId, event_type: eventType }),
    });
    return { ok: res.ok };
  } catch {
    return { ok: false };
  }
}

/**
 * @param {object[]} tracks
 * @param {string|null} userId
 * @returns {Promise<{ ok: boolean, id?: string, message?: string }>}
 */
export async function savePlaylist(tracks, userId) {
  try {
    const res = await fetch('/api/playlists', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tracks,
        savedAt: new Date().toISOString(),
        user_id: userId || null,
      }),
    });
    const data = await res.json();
    return { ...data, status: res.status };
  } catch {
    return { ok: false, message: 'Network error — could not reach the server.' };
  }
}
