import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { spawn, execFile } from 'node:child_process';
import { promisify } from 'node:util';

const execFileAsync = promisify(execFile);

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Configurations via Environment Variables
const PORT = parseInt(process.env.PORT || '4175', 10);
const HOST = process.env.HOST || '0.0.0.0';
const DEFAULT_USER = process.env.DEFAULT_USER || 'admin';
const MUSIC_DIR = process.env.MUSIC_DIR || (fs.existsSync('/media/music') ? '/media/music' : '/vol2/1000/媒体/音乐');
const FNOS_DB_PATH = process.env.FNOS_DB_PATH || (fs.existsSync('/app/db/music.db') ? '/app/db/music.db' : '/usr/local/apps/@appdata/trim.music/db/music.db');
const FNOS_COVER_DIR = process.env.FNOS_COVER_DIR || (fs.existsSync('/app/cover') ? '/app/cover' : '/var/apps/trim.music/meta/cover');
const PUID = process.env.PUID || '1000';
const PGID = process.env.PGID || '1000';

const DATA_DIR = process.env.DATA_DIR || path.join(__dirname, 'data');
const CURRENT_TASK_FILE = path.join(DATA_DIR, 'current_task.json');
const HISTORY_FILE = path.join(DATA_DIR, 'history.json');
const LOG_FILE = path.join(DATA_DIR, 'live.log');
const DIST_DIR = path.join(__dirname, 'frontend', 'dist');
const FALLBACK_PUBLIC_DIR = path.join(__dirname, 'public');
function getPublicDir() {
  return fs.existsSync(DIST_DIR) ? DIST_DIR : FALLBACK_PUBLIC_DIR;
}

const DB_OPS_SCRIPT = path.join(__dirname, 'db_ops.py');
const MUSIC_MANAGER_SCRIPT = path.join(__dirname, 'scripts', 'music_manager.py');
const PLAYLIST_SYNC_SCRIPT = path.join(__dirname, 'scripts', 'playlist_sync.py');
const AUTH_SECRET_FILE = path.join(DATA_DIR, 'auth_secret.key');
const SETTINGS_FILE = path.join(DATA_DIR, 'settings.json');

const DEFAULT_SETTINGS = {
  download_source: 'kw',
  download_dir: process.env.MUSIC_DIR || (fs.existsSync('/media/music') ? '/media/music' : '/vol2/1000/媒体/音乐'),
  is_configured: true,
  available_sources: [
    { id: 'kw', name: '酷我音乐', desc: '高品质FLAC专线 · 推荐默认', default: true },
    { id: 'kg', name: '酷狗音乐', desc: '海棠/星海SVIP线路', default: false },
    { id: 'tx', name: 'QQ音乐', desc: '长青/溯音专线', default: false },
    { id: 'wy', name: '网易云音乐', desc: '163云音乐线路', default: false },
    { id: 'auto', name: '智能多源聚合', desc: '酷我优先，故障自动回退', default: false },
    { id: 'custom', name: '自定义音源', desc: '自建 API 端点 / 远程源脚本解析', default: false }
  ],
  custom_source: {
    name: '自建音乐解析服务',
    api_url: '',
    api_key: '',
    script_url: ''
  }
};

function getEffectiveMusicDir() {
  const settings = getSettings();
  if (settings.download_dir && typeof settings.download_dir === 'string' && settings.download_dir.trim()) {
    return settings.download_dir.trim();
  }
  return MUSIC_DIR;
}

function getSettings() {
  try {
    if (fs.existsSync(SETTINGS_FILE)) {
      return { ...DEFAULT_SETTINGS, ...JSON.parse(fs.readFileSync(SETTINGS_FILE, 'utf-8')) };
    }
  } catch (e) {}
  return DEFAULT_SETTINGS;
}

function saveSettings(settings) {
  try {
    fs.writeFileSync(SETTINGS_FILE, JSON.stringify(settings, null, 2), 'utf-8');
  } catch (e) {
    console.error('Failed to save settings:', e.message);
  }
}

if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

// Persistent HMAC Secret Key for session tokens
let AUTH_SECRET = '';
try {
  if (fs.existsSync(AUTH_SECRET_FILE)) {
    AUTH_SECRET = fs.readFileSync(AUTH_SECRET_FILE, 'utf-8').trim();
  }
} catch (e) {}
if (!AUTH_SECRET || AUTH_SECRET.length < 32) {
  AUTH_SECRET = crypto.randomBytes(32).toString('hex');
  try {
    fs.writeFileSync(AUTH_SECRET_FILE, AUTH_SECRET, 'utf-8');
  } catch (e) {}
}

function signToken(payload) {
  const dataStr = Buffer.from(JSON.stringify(payload)).toString('base64url');
  const signature = crypto.createHmac('sha256', AUTH_SECRET).update(dataStr).digest('base64url');
  return `${dataStr}.${signature}`;
}

function verifyToken(token) {
  if (!token || typeof token !== 'string') return null;
  const parts = token.split('.');
  if (parts.length !== 2) return null;
  const [dataStr, signature] = parts;
  const expectedSig = crypto.createHmac('sha256', AUTH_SECRET).update(dataStr).digest('base64url');
  if (signature !== expectedSig) return null;
  try {
    const payload = JSON.parse(Buffer.from(dataStr, 'base64url').toString('utf-8'));
    if (payload.exp && Date.now() > payload.exp) return null;
    return payload;
  } catch (e) {
    return null;
  }
}

function parseCookies(req) {
  const list = {};
  const rc = req.headers.cookie;
  if (rc) {
    rc.split(';').forEach(cookie => {
      const parts = cookie.split('=');
      list[parts.shift().trim()] = decodeURIComponent(parts.join('='));
    });
  }
  return list;
}

function getSessionUser(req) {
  const cookies = parseCookies(req);
  const token = cookies.fn_music_token || (req.headers.authorization ? req.headers.authorization.replace(/^Bearer\s+/i, '') : '');
  if (!token) return null;
  return verifyToken(token);
}

// Database helper
async function callDbOps(...args) {
  const currentMusicDir = getEffectiveMusicDir();
  const env = {
    ...process.env,
    MUSIC_DIR: currentMusicDir,
    FNOS_DB_PATH,
    PUID,
    PGID
  };
  const { stdout } = await execFileAsync('python3', [DB_OPS_SCRIPT, ...args], { env, maxBuffer: 10 * 1024 * 1024 });
  return JSON.parse(stdout.trim());
}

// Self-contained Online Music Search via Kugou Official Public API
async function searchOnlineKugou(keyword, page = 1, pageSize = 20) {
  const kw = encodeURIComponent(keyword.trim());
  const url = `http://songsearch.kugou.com/song_search_v2?keyword=${kw}&page=${page}&pagesize=${pageSize}&platform=WebFilter&filter=2&iscorrection=1`;
  const resp = await fetch(url, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    }
  });
  const json = await resp.json();
  const rawList = json?.data?.lists || [];
  const defaultCover = 'https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=400&q=80';

  const badKeywords = ['dj', '伴奏', '铃声', '片段', 'demo', '重低音', '慢摇', '变速'];

  const results = [];
  for (const item of rawList) {
    const title = (item.SongName || '').replace(/<\/?em>/g, '').replace(/&nbsp;/g, ' ').trim();
    const artist = (item.SingerName || '').replace(/<\/?em>/g, '').replace(/&nbsp;/g, ' ').trim();
    const album = (item.AlbumName || '').replace(/<\/?em>/g, '').replace(/&nbsp;/g, ' ').trim();

    if (badKeywords.some(b => title.toLowerCase().includes(b))) {
      continue;
    }

    const img = (item.Image || '').replace('{size}', '400');
    const cover = img ? img.replace('http://', 'https://') : defaultCover;

    results.push({
      title,
      artist,
      album,
      cover,
      has_sq: !!(item.SQFileHash || item.HQFileHash),
      hash: item.FileHash || ''
    });
  }

  return results;
}

// State Management
let currentTask = {
  status: 'idle',
  playlist_name: '等待任务中...',
  platform: 'TRIM Music',
  target: 'public',
  user: 'all',
  total: 0,
  processed_count: 0,
  reused_count: 0,
  downloaded_count: 0,
  failed_count: 0,
  current_track: null,
  start_time: null,
  end_time: null,
  tracks: [],
  updated_at: new Date().toISOString()
};

try {
  if (fs.existsSync(CURRENT_TASK_FILE)) {
    const raw = fs.readFileSync(CURRENT_TASK_FILE, 'utf-8');
    currentTask = { ...currentTask, ...JSON.parse(raw) };
  }
} catch (e) {
  console.error('Failed to load current task:', e.message);
}

function saveCurrentTask() {
  try {
    fs.writeFileSync(CURRENT_TASK_FILE, JSON.stringify(currentTask, null, 2), 'utf-8');
  } catch (e) {
    console.error('Failed to save current task:', e.message);
  }
}

function appendLog(line) {
  const timestamp = new Date().toLocaleTimeString();
  const logLine = `[${timestamp}] ${line}\n`;
  try {
    fs.appendFileSync(LOG_FILE, logLine, 'utf-8');
  } catch (e) {}
  broadcastSSE('log', { text: logLine.trim() });
}

// SSE Push Mechanism
const sseClients = new Set();
function broadcastSSE(event, data) {
  const msg = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
  for (const client of sseClients) {
    client.write(msg);
  }
}

let activeChildProcess = null;

// HTTP Server
const server = http.createServer(async (req, res) => {
  const reqUrl = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
  const pathname = reqUrl.pathname;

  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  // Fallback context: Default User
  let sessionUser = getSessionUser(req);
  if (!sessionUser) {
    sessionUser = {
      username: DEFAULT_USER,
      uid: parseInt(PUID, 10),
      isAdmin: true,
      isDefault: true
    };
  }

  // ==================== SSE 实时推流 ====================
  if (pathname === '/api/stream') {
    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      'Connection': 'keep-alive',
      'X-Accel-Buffering': 'no'
    });
    res.write(`event: init\ndata: ${JSON.stringify(currentTask)}\n\n`);
    sseClients.add(res);

    req.on('close', () => {
      sseClients.delete(res);
    });
    return;
  }

  // ==================== 业务 API ====================
  if (pathname === '/api/status' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify({ ok: true, data: currentTask, isRunning: !!activeChildProcess }));
    return;
  }

  // Settings API
  if (pathname === '/api/settings' && req.method === 'GET') {
    const settings = getSettings();
    settings.effective_music_dir = getEffectiveMusicDir();
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify({ ok: true, data: settings }));
    return;
  }

  if (pathname === '/api/settings' && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      try {
        const { download_source, download_dir, is_configured, custom_source } = JSON.parse(body || '{}');
        const validSources = ['kw', 'kg', 'tx', 'wy', 'auto', 'custom'];
        const current = getSettings();

        if (download_source && validSources.includes(download_source)) {
          current.download_source = download_source;
        }

        if (download_dir && typeof download_dir === 'string' && download_dir.trim()) {
          const targetDir = download_dir.trim();
          if (!fs.existsSync(targetDir)) {
            try {
              fs.mkdirSync(targetDir, { recursive: true });
            } catch (mkdirErr) {
              res.writeHead(400, { 'Content-Type': 'application/json; charset=utf-8' });
              res.end(JSON.stringify({ ok: false, error: `无法创建目录: ${mkdirErr.message}` }));
              return;
            }
          }
          current.download_dir = targetDir;
        }

        if (typeof is_configured === 'boolean') {
          current.is_configured = is_configured;
        }

        if (custom_source && typeof custom_source === 'object') {
          current.custom_source = {
            name: (custom_source.name || '自建音乐解析服务').trim(),
            api_url: (custom_source.api_url || '').trim(),
            api_key: (custom_source.api_key || '').trim(),
            script_url: (custom_source.script_url || '').trim()
          };
        }

        saveSettings(current);
        appendLog(`[系统设置] 下载设置已更新 (音源: ${current.download_source.toUpperCase()}, 目录: ${current.download_dir || getEffectiveMusicDir()})`);
        current.effective_music_dir = getEffectiveMusicDir();
        res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ ok: true, data: current }));
      } catch (e) {
        res.writeHead(500, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ ok: false, error: e.message }));
      }
    });
    return;
  }

  // Authorized Directories API (fnOS authorized libraries & volume candidates)
  if (pathname === '/api/settings/directories' && req.method === 'GET') {
    try {
      const data = await callDbOps('list_authorized_directories');
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: true, data }));
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: false, error: e.message }));
    }
    return;
  }

  // Verify Directory API
  if (pathname === '/api/settings/verify-directory' && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', async () => {
      try {
        const { path: dirPath } = JSON.parse(body || '{}');
        if (!dirPath || typeof dirPath !== 'string') {
          res.writeHead(400, { 'Content-Type': 'application/json; charset=utf-8' });
          res.end(JSON.stringify({ ok: false, error: '缺少目录路径' }));
          return;
        }
        const data = await callDbOps('verify_directory', dirPath.trim());
        res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ ok: true, data }));
      } catch (e) {
        res.writeHead(500, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ ok: false, error: e.message }));
      }
    });
    return;
  }

  // Users API
  if (pathname === '/api/users' && req.method === 'GET') {
    try {
      const data = await callDbOps('list_users');
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: true, data }));
    } catch (e) {
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: true, data: [{ id: 1, name: DEFAULT_USER, role: 'admin' }] }));
    }
    return;
  }

  // History API
  if (pathname === '/api/history' && req.method === 'GET') {
    let history = [];
    try {
      if (fs.existsSync(HISTORY_FILE)) {
        history = JSON.parse(fs.readFileSync(HISTORY_FILE, 'utf-8'));
      }
    } catch (e) {}
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify({ ok: true, data: history }));
    return;
  }

  // Delete History Item
  if (pathname === '/api/history/delete' && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      try {
        const { id } = JSON.parse(body);
        let history = [];
        if (fs.existsSync(HISTORY_FILE)) {
          history = JSON.parse(fs.readFileSync(HISTORY_FILE, 'utf-8'));
        }
        history = history.filter(h => h.id !== id);
        fs.writeFileSync(HISTORY_FILE, JSON.stringify(history, null, 2), 'utf-8');
        res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ ok: true }));
      } catch (e) {
        res.writeHead(500, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ ok: false, error: e.message }));
      }
    });
    return;
  }

  // Clear History
  if (pathname === '/api/history/clear' && req.method === 'POST') {
    try {
      fs.writeFileSync(HISTORY_FILE, '[]', 'utf-8');
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: true }));
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: false, error: e.message }));
    }
    return;
  }

  // fnOS scraped cover cache (content-addressed by cover_guid, with multi-type fallback)
  const coverMatch = pathname.match(/^\/api\/covers\/(playlist|track|album|artist)\/([a-f0-9]{32})$/i);
  if (coverMatch && req.method === 'GET') {
    const [, rawType, rawGuid] = coverMatch;
    const initialType = rawType.toLowerCase();
    const guid = rawGuid.toLowerCase();
    const requestedSize = reqUrl.searchParams.get('size') || '160';
    const size = new Set(['120', '160', '400', '600', '800']).has(requestedSize) ? requestedSize : '160';

    // Search candidates in primary type first, then fallback across all cover types
    const typesToSearch = [initialType, 'album', 'track', 'artist', 'playlist'].filter((t, i, arr) => arr.indexOf(t) === i);
    let coverPath = null;

    for (const curType of typesToSearch) {
      const typeRoot = path.resolve(FNOS_COVER_DIR, curType);
      const shardRoot = path.resolve(typeRoot, guid.slice(0, 2));
      const candidates = [
        path.resolve(shardRoot, `${guid}_w${size}.jpg`),
        path.resolve(shardRoot, `${guid}_w400.jpg`),
        path.resolve(shardRoot, `${guid}_w160.jpg`),
        path.resolve(shardRoot, `${guid}_w600.jpg`),
        path.resolve(shardRoot, guid)
      ];
      coverPath = candidates.find(c => c.startsWith(`${typeRoot}${path.sep}`) && fs.existsSync(c) && fs.statSync(c).isFile());
      if (coverPath) break;
    }

    if (!coverPath) {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('Cover not found');
      return;
    }

    const header = Buffer.alloc(12);
    const fd = fs.openSync(coverPath, 'r');
    const bytesRead = fs.readSync(fd, header, 0, header.length, 0);
    fs.closeSync(fd);
    const signature = header.subarray(0, bytesRead);
    let contentType = 'application/octet-stream';
    if (signature[0] === 0xff && signature[1] === 0xd8 && signature[2] === 0xff) contentType = 'image/jpeg';
    else if (signature.subarray(0, 8).equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]))) contentType = 'image/png';
    else if (signature.subarray(0, 4).toString('ascii') === 'RIFF' && signature.subarray(8, 12).toString('ascii') === 'WEBP') contentType = 'image/webp';
    else if (signature.subarray(0, 3).toString('ascii') === 'GIF') contentType = 'image/gif';

    res.writeHead(200, {
      'Content-Type': contentType,
      'Cache-Control': 'public, max-age=86400, immutable',
      'X-Content-Type-Options': 'nosniff'
    });
    fs.createReadStream(coverPath).pipe(res);
    return;
  }

  // Playlists API
  if (pathname === '/api/playlists' && req.method === 'GET') {
    try {
      const data = await callDbOps('list_playlists');
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: true, data }));
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: false, error: e.message }));
    }
    return;
  }

  // Playlist Tracks API
  if (pathname === '/api/playlists/tracks' && req.method === 'GET') {
    const name = reqUrl.searchParams.get('name') || '';
    if (!name) {
      res.writeHead(400, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: false, error: '歌单名称不能为空' }));
      return;
    }
    try {
      const data = await callDbOps('get_playlist_tracks', name);
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: true, data }));
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: false, error: e.message }));
    }
    return;
  }

  // Rename Playlist API
  if (pathname === '/api/playlists/rename' && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', async () => {
      try {
        const { old_name, new_name } = JSON.parse(body);
        const result = await callDbOps('rename_playlist', old_name, new_name);
        res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify(result));
      } catch (e) {
        res.writeHead(500, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ ok: false, error: e.message }));
      }
    });
    return;
  }

  // Update Playlist Visible Users API
  if (pathname === '/api/playlists/update-users' && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', async () => {
      try {
        const { name, user_ids } = JSON.parse(body);
        if (!name || !Array.isArray(user_ids)) {
          res.writeHead(400, { 'Content-Type': 'application/json; charset=utf-8' });
          res.end(JSON.stringify({ ok: false, error: '缺少歌单名称或用户列表' }));
          return;
        }
        const result = await callDbOps('update_playlist_users', name, JSON.stringify(user_ids));
        res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify(result));
      } catch (e) {
        res.writeHead(500, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ ok: false, error: e.message }));
      }
    });
    return;
  }

  // Remove Tracks from Playlist API
  if (pathname === '/api/playlists/remove-tracks' && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', async () => {
      try {
        const { name, track_ids, remove_physical } = JSON.parse(body);
        if (!name || !Array.isArray(track_ids) || track_ids.length === 0) {
          res.writeHead(400, { 'Content-Type': 'application/json; charset=utf-8' });
          res.end(JSON.stringify({ ok: false, error: '缺少歌单名称或曲目列表' }));
          return;
        }
        const result = await callDbOps('remove_playlist_tracks', name, JSON.stringify(track_ids), remove_physical ? 'true' : 'false');
        res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify(result));
      } catch (e) {
        res.writeHead(500, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ ok: false, error: e.message }));
      }
    });
    return;
  }

  // Delete Playlist API
  if (pathname === '/api/playlists/delete' && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', async () => {
      try {
        const { name, delete_tracks } = JSON.parse(body);
        const result = await callDbOps('delete_playlist', name, delete_tracks ? 'true' : 'false');
        res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify(result));
      } catch (e) {
        res.writeHead(500, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ ok: false, error: e.message }));
      }
    });
    return;
  }

  // Search Library Tracks API
  if (pathname === '/api/tracks/search' && req.method === 'GET') {
    const q = reqUrl.searchParams.get('q') || '';
    const page = reqUrl.searchParams.get('page') || '1';
    const limit = reqUrl.searchParams.get('limit') || '50';
    try {
      const data = await callDbOps('search_tracks', q, page, limit);
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: true, data }));
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: false, error: e.message }));
    }
    return;
  }

  // Delete Single Track API
  if (pathname === '/api/tracks/delete' && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', async () => {
      try {
        const { track_id, remove_physical } = JSON.parse(body);
        const result = await callDbOps('delete_track', track_id, remove_physical !== false ? 'true' : 'false');
        res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify(result));
      } catch (e) {
        res.writeHead(500, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ ok: false, error: e.message }));
      }
    });
    return;
  }

  // Get Duplicate Tracks API
  if (pathname === '/api/tracks/duplicates' && req.method === 'GET') {
    const q = reqUrl.searchParams.get('q') || '';
    try {
      const data = await callDbOps('find_duplicates', q);
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: true, data }));
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: false, error: e.message }));
    }
    return;
  }

  // Batch Delete Tracks API
  if (pathname === '/api/tracks/batch-delete' && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', async () => {
      try {
        const { track_ids, remove_physical } = JSON.parse(body);
        if (!Array.isArray(track_ids) || track_ids.length === 0) {
          res.writeHead(400, { 'Content-Type': 'application/json; charset=utf-8' });
          res.end(JSON.stringify({ ok: false, error: '未提供待删除的曲目 ID 列表' }));
          return;
        }
        const result = await callDbOps('batch_delete_tracks', JSON.stringify(track_ids), remove_physical !== false ? 'true' : 'false');
        res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify(result));
      } catch (e) {
        res.writeHead(500, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ ok: false, error: e.message }));
      }
    });
    return;
  }

  // Online Music Search API (Self-Contained + Library Deduplication)
  if (pathname === '/api/search/online' && req.method === 'GET') {
    const q = reqUrl.searchParams.get('q') || reqUrl.searchParams.get('keyword') || '';
    if (!q.trim()) {
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: true, data: [] }));
      return;
    }

    try {
      const songs = await searchOnlineKugou(q.trim());

      let checkResults = [];
      try {
        checkResults = await callDbOps('batch_check', JSON.stringify(songs.map(s => ({ title: s.title, artist: s.artist }))));
      } catch (e) {
        console.error('Batch check error:', e.message);
      }

      const merged = songs.map((s, idx) => ({
        ...s,
        exists: checkResults[idx] ? checkResults[idx].exists : false,
        local_path: checkResults[idx] ? checkResults[idx].path : '',
        local_id: checkResults[idx] ? checkResults[idx].id : null
      }));

      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: true, data: merged }));
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: false, error: e.message }));
    }
    return;
  }

  // Single Song Download API
  if (pathname === '/api/download/single' && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', async () => {
      try {
        const { artist, song, album, cover, quality, source } = JSON.parse(body || '{}');
        if (!song || !artist) {
          res.writeHead(400, { 'Content-Type': 'application/json; charset=utf-8' });
          res.end(JSON.stringify({ ok: false, error: '缺少歌曲名或歌手名' }));
          return;
        }

        const reqQuality = (quality || 'flac').toLowerCase().trim();
        const settings = getSettings();
        const chosenSource = source || settings.download_source || 'kw';

        // Check if track already exists in library
        try {
          const existsCheck = await callDbOps('check_song_exists', song, artist);
          if (existsCheck && existsCheck.exists) {
            res.writeHead(400, { 'Content-Type': 'application/json; charset=utf-8' });
            res.end(JSON.stringify({
              ok: false,
              error: `【${artist} - ${song}】在 NAS 曲库中已存在，禁止重复下载！`,
              path: existsCheck.path
            }));
            return;
          }
        } catch (checkErr) {
          console.error('Check exists before download error:', checkErr.message);
        }

        if (activeChildProcess) {
          res.writeHead(409, { 'Content-Type': 'application/json; charset=utf-8' });
          res.end(JSON.stringify({ ok: false, error: '当前已有任务正在运行中，请稍候' }));
          return;
        }

        const taskTitle = `${artist} - ${song}`;
        currentTask = {
          status: 'downloading',
          playlist_name: `单曲下载: ${taskTitle} (${reqQuality.toUpperCase()})`,
          platform: '全网搜索单曲',
          target: 'public',
          user: 'all',
          total: 1,
          processed_count: 0,
          reused_count: 0,
          downloaded_count: 0,
          failed_count: 0,
          current_track: {
            title: song,
            artist: artist,
            album: album || song,
            step: `正在解析 ${reqQuality.toUpperCase()} 音频流与歌词...`,
            cover: cover || ''
          },
          start_time: new Date().toISOString(),
          end_time: null,
          tracks: [{ title: song, artist: artist, album: album || '', status: 'downloading' }],
          updated_at: new Date().toISOString()
        };
        saveCurrentTask();
        broadcastSSE('status', currentTask);

        try { fs.writeFileSync(LOG_FILE, `=== 开始单曲下载任务: ${taskTitle} [${reqQuality.toUpperCase()}] ===\n`, 'utf-8'); } catch (e) {}

        const args = ['-u', MUSIC_MANAGER_SCRIPT, '--artist', artist, '--song', song, '--quality', reqQuality, '--source', chosenSource, '--force'];
        if (album) args.push('--album', album);

        appendLog(`启动单曲下载: python3 ${args.join(' ')}`);

        const currentMusicDir = getEffectiveMusicDir();
        const childEnv = {
          ...process.env,
          PYTHONUNBUFFERED: '1',
          MUSIC_DIR: currentMusicDir,
          FNOS_DB_PATH,
          PUID,
          PGID
        };

        const child = spawn('python3', args, { env: childEnv });
        activeChildProcess = child;

        child.stdout.on('data', chunk => {
          for (const line of chunk.toString().split('\n')) {
            if (line.trim()) appendLog(line.trim());
          }
        });

        child.stderr.on('data', chunk => {
          for (const line of chunk.toString().split('\n')) {
            if (line.trim()) appendLog(`[STDERR] ${line.trim()}`);
          }
        });

        child.on('close', code => {
          activeChildProcess = null;
          appendLog(`单曲抓取进程已结束，退出码: ${code}`);
          if (code === 0) {
            currentTask.status = 'success';
            currentTask.downloaded_count = 1;
            currentTask.end_time = new Date().toISOString();
            currentTask.current_track = null;
            if (currentTask.tracks[0]) currentTask.tracks[0].status = 'downloaded';

            // Archive to history
            const historyItem = {
              id: Date.now(),
              type: 'song',
              playlist_name: `${artist} - ${song}`,
              title: song,
              artist: artist,
              album: album || '',
              quality: reqQuality,
              cover: cover || '',
              platform: '全网单曲下载',
              target: 'public',
              user: 'all',
              total: 1,
              reused_count: 0,
              downloaded_count: 1,
              failed_count: 0,
              start_time: currentTask.start_time,
              end_time: currentTask.end_time,
              duration: Math.max(1, Math.round((new Date(currentTask.end_time) - new Date(currentTask.start_time)) / 1000)),
              status: 'success'
            };
            let history = [];
            try {
              if (fs.existsSync(HISTORY_FILE)) history = JSON.parse(fs.readFileSync(HISTORY_FILE, 'utf-8'));
              history.unshift(historyItem);
              fs.writeFileSync(HISTORY_FILE, JSON.stringify(history.slice(0, 100), null, 2), 'utf-8');
            } catch (e) {}
          } else {
            currentTask.status = 'failed';
            currentTask.failed_count = 1;
            currentTask.end_time = new Date().toISOString();
            if (currentTask.tracks[0]) currentTask.tracks[0].status = 'failed';
          }
          saveCurrentTask();
          broadcastSSE('status', currentTask);
        });

        res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ ok: true, message: '单曲下载流水线已成功拉起' }));
      } catch (err) {
        res.writeHead(500, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ ok: false, error: err.message }));
      }
    });
    return;
  }

  // Update Status API (Internal push from playlist_sync)
  if (pathname === '/api/update-status' && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      try {
        const update = JSON.parse(body);
        currentTask = {
          ...currentTask,
          ...update,
          updated_at: new Date().toISOString()
        };
        saveCurrentTask();
        broadcastSSE('status', currentTask);

        if (update.status === 'success') {
          const historyItem = {
            id: Date.now(),
            type: 'playlist',
            playlist_name: update.playlist_name || currentTask.playlist_name,
            platform: update.platform || currentTask.platform,
            target: update.target || currentTask.target,
            user: update.user || currentTask.user,
            total: update.total || currentTask.total,
            reused_count: update.reused_count || currentTask.reused_count,
            downloaded_count: update.downloaded_count || currentTask.downloaded_count,
            failed_count: update.failed_count || currentTask.failed_count,
            start_time: currentTask.start_time,
            end_time: update.end_time || new Date().toISOString(),
            duration: currentTask.start_time ? Math.round((new Date(update.end_time || Date.now()) - new Date(currentTask.start_time)) / 1000) : 0,
            status: 'success'
          };
          let history = [];
          try {
            if (fs.existsSync(HISTORY_FILE)) history = JSON.parse(fs.readFileSync(HISTORY_FILE, 'utf-8'));
            history.unshift(historyItem);
            fs.writeFileSync(HISTORY_FILE, JSON.stringify(history.slice(0, 100), null, 2), 'utf-8');
          } catch (e) {}
        }

        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: true }));
      } catch (e) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: false, error: e.message }));
      }
    });
    return;
  }

  // Start Playlist Task API
  if (pathname === '/api/tasks/start' && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      try {
        const { url, target = 'public', user = DEFAULT_USER, source } = JSON.parse(body);
        if (!url) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ ok: false, error: 'url is required' }));
          return;
        }

        if (activeChildProcess) {
          res.writeHead(409, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ ok: false, error: '已有任务正在运行中' }));
          return;
        }

        const settings = getSettings();
        const chosenSource = source || settings.download_source || 'kw';

        currentTask = {
          status: 'parsing',
          playlist_name: '正在解析中...',
          platform: '第三方平台',
          target,
          user,
          total: 0,
          processed_count: 0,
          reused_count: 0,
          downloaded_count: 0,
          failed_count: 0,
          current_track: null,
          start_time: new Date().toISOString(),
          end_time: null,
          tracks: [],
          updated_at: new Date().toISOString()
        };
        saveCurrentTask();
        broadcastSSE('status', currentTask);

        try { fs.writeFileSync(LOG_FILE, `=== 开始同步任务: ${url} ===\n`, 'utf-8'); } catch (e) {}

        const currentMusicDir = getEffectiveMusicDir();
        const childEnv = {
          ...process.env,
          PYTHONUNBUFFERED: '1',
          PORT: PORT.toString(),
          MUSIC_DIR: currentMusicDir,
          FNOS_DB_PATH,
          PUID,
          PGID
        };

        const args = ['-u', PLAYLIST_SYNC_SCRIPT, '--url', url, '--target', target, '--user', user, '--source', chosenSource];
        const child = spawn('python3', args, { env: childEnv });
        activeChildProcess = child;

        child.stdout.on('data', chunk => {
          for (const line of chunk.toString().split('\n')) {
            if (line.trim()) appendLog(line.trim());
          }
        });

        child.stderr.on('data', chunk => {
          for (const line of chunk.toString().split('\n')) {
            if (line.trim()) appendLog(`[STDERR] ${line.trim()}`);
          }
        });

        child.on('close', code => {
          activeChildProcess = null;
          appendLog(`任务进程已结束，退出码: ${code}`);
          if (code !== 0 && currentTask.status !== 'success') {
            currentTask.status = 'failed';
            currentTask.end_time = new Date().toISOString();
            saveCurrentTask();
            broadcastSSE('status', currentTask);
          }
        });

        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: true, message: '任务已启动' }));
      } catch (err) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: false, error: err.message }));
      }
    });
    return;
  }

  // Stop Task API
  if (pathname === '/api/tasks/stop' && req.method === 'POST') {
    if (activeChildProcess) {
      activeChildProcess.kill('SIGTERM');
      activeChildProcess = null;
      currentTask.status = 'stopped';
      currentTask.end_time = new Date().toISOString();
      saveCurrentTask();
      broadcastSSE('status', currentTask);
      appendLog('用户手动中止了当前任务');
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ ok: true, message: '任务已终止' }));
    } else {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ ok: true, message: '当前没有正在运行的任务' }));
    }
    return;
  }

  // Logs API
  if (pathname === '/api/logs' && req.method === 'GET') {
    let logs = '';
    try {
      if (fs.existsSync(LOG_FILE)) logs = fs.readFileSync(LOG_FILE, 'utf-8');
    } catch (e) {}
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ ok: true, data: logs }));
    return;
  }

  // ==================== 静态资源服务 (前端 UI) ====================
  const publicDir = getPublicDir();
  let filePath = path.join(publicDir, pathname === '/' ? 'index.html' : pathname);
  const mimeTypes = {
    '.html': 'text/html; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.json': 'application/json',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.webp': 'image/webp',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
    '.ttf': 'font/ttf'
  };

  if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
    const ext = path.extname(filePath).toLowerCase();
    res.writeHead(200, { 'Content-Type': mimeTypes[ext] || 'application/octet-stream' });
    fs.createReadStream(filePath).pipe(res);
    return;
  }

  // SPA fallback
  const fallbackIndex = path.join(publicDir, 'index.html');
  if (fs.existsSync(fallbackIndex) && fs.statSync(fallbackIndex).isFile()) {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    fs.createReadStream(fallbackIndex).pipe(res);
    return;
  }

  res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
  res.end('404 Not Found');
});

server.listen(PORT, HOST, () => {
  console.log(`🎵 TRIM Music Hub running at http://${HOST}:${PORT}`);
  console.log(`📁 Music Root: ${MUSIC_DIR}`);
  console.log(`💽 fnOS DB: ${FNOS_DB_PATH}`);
  console.log(`🖼️ fnOS Covers: ${FNOS_COVER_DIR}`);
});
