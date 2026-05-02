/**
 * Mock API service — simulates a 1.5 s network round-trip.
 * Replace generatePlaylist() body with a real fetch() call once the
 * Node.js / Python backend is wired up.
 */

const MOCK_POOL = [
  { id: 1,  title: "Electric Feel",          artist: "MGMT",                   duration: "3:49" },
  { id: 2,  title: "Motion Picture Soundtrack", artist: "Radiohead",           duration: "5:15" },
  { id: 3,  title: "Teardrop",               artist: "Massive Attack",          duration: "5:29" },
  { id: 4,  title: "Breathe",                artist: "Pink Floyd",              duration: "2:43" },
  { id: 5,  title: "Everlong",               artist: "Foo Fighters",            duration: "4:10" },
  { id: 6,  title: "Black",                  artist: "Pearl Jam",               duration: "5:43" },
  { id: 7,  title: "Karma Police",           artist: "Radiohead",               duration: "4:21" },
  { id: 8,  title: "Unfinished Sympathy",    artist: "Massive Attack",          duration: "5:08" },
  { id: 9,  title: "Do I Wanna Know?",       artist: "Arctic Monkeys",          duration: "4:32" },
  { id: 10, title: "Glycerine",              artist: "Bush",                    duration: "4:24" },
  { id: 11, title: "Champagne Supernova",    artist: "Oasis",                   duration: "7:27" },
  { id: 12, title: "Fake Plastic Trees",     artist: "Radiohead",               duration: "4:50" },
  { id: 13, title: "Scar Tissue",            artist: "Red Hot Chili Peppers",   duration: "3:37" },
  { id: 14, title: "The Less I Know The Better", artist: "Tame Impala",         duration: "3:36" },
  { id: 15, title: "Ribs",                   artist: "Lorde",                   duration: "3:49" },
  { id: 16, title: "Yellow",                 artist: "Coldplay",                duration: "4:26" },
  { id: 17, title: "Creep",                  artist: "Radiohead",               duration: "3:56" },
  { id: 18, title: "Breezeblocks",           artist: "alt-J",                   duration: "3:48" },
  { id: 19, title: "Take Me to Church",      artist: "Hozier",                  duration: "4:01" },
  { id: 20, title: "The Night We Met",       artist: "Lord Huron",              duration: "3:28" },
  { id: 21, title: "Midnight City",          artist: "M83",                     duration: "4:03" },
  { id: 22, title: "Skinny Love",            artist: "Bon Iver",                duration: "3:58" },
  { id: 23, title: "Dreams",                 artist: "Fleetwood Mac",           duration: "4:14" },
  { id: 24, title: "Everybody Wants to Rule the World", artist: "Tears for Fears", duration: "4:11" },
  { id: 25, title: "Running Up That Hill",   artist: "Kate Bush",               duration: "5:02" },
  { id: 26, title: "Video Games",            artist: "Lana Del Rey",            duration: "4:39" },
  { id: 27, title: "Bloom",                  artist: "Odesza",                  duration: "4:22" },
  { id: 28, title: "No Surprises",           artist: "Radiohead",               duration: "3:48" },
  { id: 29, title: "Float On",               artist: "Modest Mouse",            duration: "3:28" },
  { id: 30, title: "Come As You Are",        artist: "Nirvana",                 duration: "3:38" },
  { id: 31, title: "Cigarettes & Alcohol",   artist: "Oasis",                   duration: "4:50" },
  { id: 32, title: "Dark Fantasy",           artist: "Kanye West",              duration: "5:02" },
  { id: 33, title: "Retrograde",             artist: "James Blake",             duration: "4:11" },
  { id: 34, title: "Motion",                 artist: "Bonobo",                  duration: "5:44" },
  { id: 35, title: "Holocene",               artist: "Bon Iver",                duration: "5:37" },
  { id: 36, title: "Crystalised",            artist: "The xx",                  duration: "3:02" },
  { id: 37, title: "New Soul",               artist: "Yael Naim",               duration: "3:41" },
  { id: 38, title: "Sofia",                  artist: "Clairo",                  duration: "3:26" },
  { id: 39, title: "Liability",              artist: "Lorde",                   duration: "3:00" },
  { id: 40, title: "Obstacles",              artist: "Syd Matters",             duration: "3:43" },
  { id: 41, title: "River",                  artist: "Leon Bridges",            duration: "3:13" },
  { id: 42, title: "Would That I",           artist: "Hozier",                  duration: "4:51" },
  { id: 43, title: "Wait",                   artist: "M83",                     duration: "4:09" },
  { id: 44, title: "Another Love",           artist: "Tom Odell",               duration: "4:06" },
  { id: 45, title: "Be Here Now",            artist: "Ray LaMontagne",          duration: "4:34" },
  { id: 46, title: "Poison & Wine",          artist: "The Civil Wars",          duration: "3:42" },
  { id: 47, title: "Blue Ridge Mountains",   artist: "Fleet Foxes",             duration: "3:44" },
  { id: 48, title: "Mykonos",                artist: "Fleet Foxes",             duration: "4:02" },
  { id: 49, title: "Lua",                    artist: "Bright Eyes",             duration: "3:41" },
  { id: 50, title: "Lua",                    artist: "Sufjan Stevens",          duration: "7:58" },
];

/** Shuffle helper (Fisher–Yates). */
function shuffle(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

/**
 * @param {object} params - { vibe, genres, size, era, seedArtists }
 * @returns {Promise<Array>} Resolves with an array of track objects.
 */
export function generatePlaylist(params) {
  return new Promise((resolve) => {
    setTimeout(() => {
      const size = Math.min(Math.max(Number(params.size) || 20, 5), 50);
      const tracks = shuffle(MOCK_POOL).slice(0, size);
      resolve(tracks);
    }, 1500);
  });
}

/**
 * @param {Array} tracks - The playlist to persist.
 * @param {string|null} userId - The display name / user identifier from settings.
 * @returns {Promise<{ok: boolean, message: string}>}
 */
export function savePlaylist(tracks, userId) {
  return fetch('/api/playlists', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ tracks, savedAt: new Date().toISOString(), user_id: userId || null }),
  })
    .then((res) => res.json())
    .catch(() => ({ ok: false, message: 'Network error — could not reach the server.' }));
}
