db = db.getSiblingDB('webapp');

db.createCollection('users');
db.createCollection('playlists');
db.createCollection('songs');

db.playlists.createIndex({ user_id: 1, created_at: -1 });
db.playlists.createIndex({ "params.genres": 1 });
db.songs.createIndex({ external_id: 1 }, { unique: true });
db.songs.createIndex(
  { cached_at: 1 },
  { expireAfterSeconds: 604800 }
);