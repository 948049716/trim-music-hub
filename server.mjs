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
const PUBLIC_DIR = fs.existsSync(DIST_DIR) ? DIST_DIR : FALLBACK_PUBLIC_DIR;

const DB_OPS_SCRIPT = path.join(__dirname, 'db_ops.py');
const MUSIC_MANAGER_SCRIPT = path.join(__dirname, 'scripts', 'music_manager.py');
const PLAYLIST_SYNC_SCRIPT = path.join(__dirname, 'scripts', 'playlist_sync.py');
const AUTH_SECRET_FILE = path.join(DATA_DIR, 'auth_secret.key');
const SETTINGS_FILE = path.join(DATA_DIR, 'settings.json');
const MUSIC_ACCOUNTS_FILE = path.join(DATA_DIR, 'music_accounts.json');
const MUSIC_ACCOUNT_SCRIPT = path.join(__dirname, 'scripts', 'music_account.py');

const DEFAULT_SETTINGS = {
  download_source: 'kw',
  download_dir: MUSIC_DIR,
  is_configured: true,
  available_sources: [
    { id: 'kw', name: '酷我音乐', desc: '高品质FLAC专线 · 推荐默认', default: true },
    { id: 'kg', name: '酷狗音乐', desc: '海棠/星海SVIP线路', default: false },
    { id: 'tx', name: 'QQ音乐', desc: '长青/溯音专线', default: false },
    { id: 'wy', name: '网易云音乐', desc: '163云音乐线路', default: false },
    { id: 'auto', name: '智能多源聚合', desc: '酷我优先，故障自动回退', default: false },
    { id: 'custom', name: '自定义音源', desc: '自建 API 端点 / 远程源脚本解析', default: false }
  ],
  custom_source: { name: '自建音乐解析服务', api_url: '', api_key: '', script_url: '' }
};

function getSettings() {
  let saved = {};
  try {
    if (fs.existsSync(SETTINGS_FILE)) saved = JSON.parse(fs.readFileSync(SETTINGS_FILE, 'utf-8'));
  } catch (e) {
    console.error('Failed to load settings:', e.message);
  }
  return {
    ...DEFAULT_SETTINGS,
    ...saved,
    available_sources: DEFAULT_SETTINGS.available_sources.map(source => ({ ...source })),
    custom_source: { ...DEFAULT_SETTINGS.custom_source, ...(saved.custom_source || {}) }
  };
}

function getEffectiveMusicDir() {
  const downloadDir = getSettings().download_dir;
  return typeof downloadDir === 'string' && downloadDir.trim() ? downloadDir.trim() : MUSIC_DIR;
}

function saveSettings(settings) {
  fs.writeFileSync(SETTINGS_FILE, JSON.stringify(settings, null, 2), 'utf-8');
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

function isUserPersonalPlaylist(playlist, userId, allUsers) {
  if (!playlist) return false;
  const usersStr = String(playlist.users || '');
  if (usersStr.includes('所有成员') || usersStr.includes('公共')) return false;
  const uids = Array.isArray(playlist.user_ids) ? playlist.user_ids : [];
  if (uids.length === 0) return false;
  if (Array.isArray(allUsers) && allUsers.length > 0 && allUsers.every(u => uids.includes(u.id))) {
    return false;
  }
  return uids.includes(userId);
}

const defaultWsHost = fs.existsSync('/.dockerenv') ? '172.17.0.1' : '127.0.0.1';
const FNOS_WS_URL = process.env.FNOS_WS_URL || `ws://${defaultWsHost}:5666/websocket?type=main`;

async function authenticateWithFnOS(username, password) {
  return new Promise((resolve) => {
    let resolved = false;
    let ws;
    try {
      ws = new WebSocket(FNOS_WS_URL);
    } catch (e) {
      return resolve({ ok: false, error: `无法连接飞牛系统认证网关: ${e.message}` });
    }

    const timer = setTimeout(() => {
      if (!resolved) {
        resolved = true;
        try { ws.close(); } catch (e) {}
        resolve({ ok: false, error: '连接飞牛认证网关超时，请检查 NAS 状态' });
      }
    }, 6000);

    ws.onopen = () => {
      const reqid = Date.now().toString(16) + '00000001';
      ws.send(JSON.stringify({
        req: 'user.login',
        reqid,
        user: String(username || '').trim(),
        password: String(password || ''),
        stay: 1,
        deviceName: 'TRIM Music Hub',
        deviceType: 'Web'
      }));
    };

    ws.onmessage = (event) => {
      if (resolved) return;
      try {
        const data = JSON.parse(event.data);
        if (data.result === 'succ') {
          resolved = true;
          clearTimeout(timer);
          try { ws.close(); } catch (e) {}
          resolve({ ok: true, data });
        } else {
          resolved = true;
          clearTimeout(timer);
          try { ws.close(); } catch (e) {}
          const errorMsg = data.errmsg || (data.errno === 131072 ? '飞牛账号或密码错误（若连续输错5次将被系统临时锁定1小时）' : `登录失败 (${data.errno || '未知错误'})`);
          resolve({ ok: false, error: errorMsg, errno: data.errno });
        }
      } catch (e) {
        resolved = true;
        clearTimeout(timer);
        try { ws.close(); } catch (e) {}
        resolve({ ok: false, error: '解析飞牛网关返回数据失败' });
      }
    };

    ws.onerror = (err) => {
      if (resolved) return;
      resolved = true;
      clearTimeout(timer);
      resolve({ ok: false, error: '连接飞牛网关失败: ' + (err.message || '网络异常') });
    };
  });
}

const MUSIC_PROVIDER_META = {
  netease: { id: 'netease', name: '网易云音乐', available: true, login_method: 'cookie', hint: '支持读取已创建和收藏的歌单' },
  qq: { id: 'qq', name: 'QQ音乐', available: true, login_method: 'cookie', hint: '支持读取已创建和收藏的歌单' },
  bodian: { id: 'bodian', name: '波点音乐', available: false, login_method: 'unavailable', hint: '暂未发现稳定、安全的账号歌单接口' }
};

function readJsonFile(filePath, fallback) {
  try {
    if (fs.existsSync(filePath)) return JSON.parse(fs.readFileSync(filePath, 'utf-8'));
  } catch (e) {}
  return fallback;
}

function writePrivateJson(filePath, value) {
  fs.writeFileSync(filePath, JSON.stringify(value, null, 2), { encoding: 'utf-8', mode: 0o600 });
  try { fs.chmodSync(filePath, 0o600); } catch (e) {}
}

function encryptionKey() {
  return crypto.createHash('sha256').update(AUTH_SECRET).digest();
}

function encryptSecret(value) {
  const iv = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv('aes-256-gcm', encryptionKey(), iv);
  const encrypted = Buffer.concat([cipher.update(String(value), 'utf8'), cipher.final()]);
  return { iv: iv.toString('base64'), tag: cipher.getAuthTag().toString('base64'), data: encrypted.toString('base64') };
}

function decryptSecret(payload) {
  if (!payload?.iv || !payload?.tag || !payload?.data) return '';
  const decipher = crypto.createDecipheriv('aes-256-gcm', encryptionKey(), Buffer.from(payload.iv, 'base64'));
  decipher.setAuthTag(Buffer.from(payload.tag, 'base64'));
  return Buffer.concat([decipher.update(Buffer.from(payload.data, 'base64')), decipher.final()]).toString('utf8');
}

function loadMusicAccounts() {
  return readJsonFile(MUSIC_ACCOUNTS_FILE, {});
}

function publicMusicAccount(provider, saved = {}) {
  return {
    ...MUSIC_PROVIDER_META[provider],
    connected: !!saved.connected,
    nickname: saved.nickname || '',
    avatar: saved.avatar || '',
    user_id: saved.user_id || '',
    connected_at: saved.connected_at || null
  };
}

async function runMusicAccountHelper(provider, action, cookie) {
  return new Promise((resolve, reject) => {
    const child = spawn('python3', [MUSIC_ACCOUNT_SCRIPT, provider, action], {
      env: { ...process.env, PYTHONUNBUFFERED: '1' },
      stdio: ['pipe', 'pipe', 'pipe']
    });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', chunk => { stdout += chunk.toString(); });
    child.stderr.on('data', chunk => { stderr += chunk.toString(); });
    child.on('error', reject);
    child.on('close', code => {
      try {
        const result = JSON.parse(stdout.trim() || '{}');
        if (code !== 0 && !result.error) result.error = stderr.trim() || '账号服务请求失败';
        resolve(result);
      } catch (e) {
        reject(new Error(stderr.trim() || '账号服务返回了无效数据'));
      }
    });
    child.stdin.end(JSON.stringify({ cookie }));
  });
}

function readRequestJson(req, maxBytes = 1024 * 1024) {
  return new Promise((resolve, reject) => {
    let body = '';
    let settled = false;
    req.on('data', chunk => {
      if (settled) return;
      body += chunk;
      if (Buffer.byteLength(body) > maxBytes) {
        settled = true;
        reject(new Error('请求内容过大'));
      }
    });
    req.on('end', () => {
      if (settled) return;
      try { resolve(body ? JSON.parse(body) : {}); }
      catch (e) { reject(new Error('请求内容不是有效 JSON')); }
    });
    req.on('error', reject);
  });
}

function startPlaylistTask(url, target = 'public', user = DEFAULT_USER, provider = '', providerCookie = '', source = '', options = {}) {
  if (!url) return { ok: false, status: 400, error: 'url is required' };
  if (activeChildProcess) return { ok: false, status: 409, error: '已有任务正在运行中' };

  const chosenSource = source || getSettings().download_source || 'kw';
  const currentMusicDir = getEffectiveMusicDir();
  const globalQuality = (options.quality || 'flac').toLowerCase().trim();
  const validQuality = ['flac', '320k', '128k'].includes(globalQuality) ? globalQuality : 'flac';
  let selectedTracksFile = '';
  if (Array.isArray(options.tracks) && options.tracks.length) {
    selectedTracksFile = path.join(DATA_DIR, `playlist_tracks_${Date.now()}_${crypto.randomBytes(4).toString('hex')}.json`);
    fs.writeFileSync(selectedTracksFile, JSON.stringify(options.tracks), 'utf-8');
  }

  currentTask = {
    status: 'parsing', playlist_name: options.playlistName || '正在解析中...', platform: '第三方平台', target, user,
    cover: options.coverUrl || '',
    total: 0, processed_count: 0, reused_count: 0, downloaded_count: 0, failed_count: 0,
    current_track: null, start_time: new Date().toISOString(), end_time: null, tracks: [], updated_at: new Date().toISOString()
  };
  saveCurrentTask();
  broadcastSSE('status', currentTask);
  try { fs.writeFileSync(LOG_FILE, `=== 开始同步任务: ${url} ===\n`, 'utf-8'); } catch (e) {}

  const args = ['-u', PLAYLIST_SYNC_SCRIPT, '--url', url, '--target', target, '--user', user, '--source', chosenSource, '--quality', validQuality];
  if (options.playlistName) args.push('--playlist-name', options.playlistName);
  if (options.coverUrl) args.push('--cover-url', options.coverUrl);
  if (selectedTracksFile) args.push('--tracks-file', selectedTracksFile);
  const child = spawn('python3', args, {
    env: { ...process.env, PYTHONUNBUFFERED: '1', PORT: PORT.toString(), MUSIC_DIR: currentMusicDir, FNOS_DB_PATH, PUID, PGID, THIRD_PARTY_PROVIDER: provider, THIRD_PARTY_COOKIE: providerCookie }
  });
  activeChildProcess = child;
  child.stdout.on('data', chunk => chunk.toString().split('\n').filter(Boolean).forEach(line => appendLog(line.trim())));
  child.stderr.on('data', chunk => chunk.toString().split('\n').filter(Boolean).forEach(line => appendLog(`[STDERR] ${line.trim()}`)));
  child.on('close', code => {
    activeChildProcess = null;
    if (selectedTracksFile) {
      try { fs.rmSync(selectedTracksFile, { force: true }); } catch (e) {}
    }
    appendLog(`任务进程已结束，退出码: ${code}`);
    if (code !== 0 && currentTask.status !== 'success') {
      currentTask.status = 'failed';
      currentTask.end_time = new Date().toISOString();
      saveCurrentTask();
      broadcastSSE('status', currentTask);
    }
  });
  return { ok: true, status: 200, message: '任务已启动' };
}

// Database helper
async function callDbOps(...args) {
  const env = {
    ...process.env,
    MUSIC_DIR: getEffectiveMusicDir(),
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
  const normalizedKeyword = keyword.trim().toLowerCase();
  const excludedKeywords = badKeywords.filter(term => !normalizedKeyword.includes(term));

  const results = [];
  for (const item of rawList) {
    const title = (item.SongName || '').replace(/<\/?em>/g, '').replace(/&nbsp;/g, ' ').trim();
    const artist = (item.SingerName || '').replace(/<\/?em>/g, '').replace(/&nbsp;/g, ' ').trim();
    const album = (item.AlbumName || '').replace(/<\/?em>/g, '').replace(/&nbsp;/g, ' ').trim();

    if (excludedKeywords.some(term => title.toLowerCase().includes(term))) {
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

  return { results, total: Number(json?.data?.total || json?.data?.totalHits || 0), page, pageSize };
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

  // 获取会话用户（基于 Token / Cookie）
  const sessionUser = getSessionUser(req);

  // ==================== 身份认证 API (公开访问) ====================
  if (pathname === '/api/auth/login' && req.method === 'POST') {
    try {
      const { username, password } = await readRequestJson(req);
      if (!username || !password) {
        res.writeHead(400, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ ok: false, error: '请输入飞牛账号和密码' }));
        return;
      }

      const authRes = await authenticateWithFnOS(username, password);
      if (!authRes.ok) {
        res.writeHead(401, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ ok: false, error: authRes.error }));
        return;
      }

      // 获取用户在飞牛音乐中的对应角色和 ID
      let userId = 1000;
      let role = 'member';
      try {
        const users = await callDbOps('list_users');
        const matched = (users || []).find(u => u.name && u.name.toLowerCase() === String(username).toLowerCase());
        if (matched) {
          userId = matched.id;
          role = matched.role || 'member';
        }
      } catch (e) {
        console.error('Failed to query users from music.db:', e.message);
      }

      const isAdmin = role === 'admin';
      const sessionData = {
        username: String(username).trim(),
        userId,
        role,
        isAdmin,
        exp: Date.now() + 30 * 24 * 60 * 60 * 1000 // 30天有效
      };
      const token = signToken(sessionData);

      // 设置 30 天 HttpOnly Cookie
      res.setHeader('Set-Cookie', `fn_music_token=${token}; Path=/; Max-Age=${30 * 24 * 3600}; SameSite=Lax; HttpOnly`);
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: true, user: sessionData, token }));
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: false, error: e.message }));
    }
    return;
  }

  if (pathname === '/api/auth/logout' && req.method === 'POST') {
    res.setHeader('Set-Cookie', 'fn_music_token=; Path=/; Max-Age=0; SameSite=Lax; HttpOnly');
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify({ ok: true, message: '已退出登录' }));
    return;
  }

  if (pathname === '/api/auth/me' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
    if (!sessionUser) {
      res.end(JSON.stringify({ ok: true, loggedIn: false }));
    } else {
      res.end(JSON.stringify({ ok: true, loggedIn: true, user: sessionUser }));
    }
    return;
  }

  // ==================== 全局未登录拦截 ====================
  if (pathname.startsWith('/api/')) {
    if (!sessionUser) {
      res.writeHead(401, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: false, error: '未登录或登录已失效，请重新登录飞牛账号', needLogin: true }));
      return;
    }
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
    if (!sessionUser.isAdmin) {
      res.writeHead(403, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: false, error: '权限不足：仅管理员可以修改系统与音源设置' }));
      return;
    }
    try {
      const { download_source, download_dir, is_configured, custom_source } = await readRequestJson(req);
      const validSources = ['kw', 'kg', 'tx', 'wy', 'auto', 'custom'];
      const current = getSettings();
      if (download_source !== undefined) {
        if (!validSources.includes(download_source)) throw new Error('不支持的下载音源');
        current.download_source = download_source;
      }
      if (download_dir !== undefined) {
        if (typeof download_dir !== 'string' || !download_dir.trim()) throw new Error('下载目录不能为空');
        const targetDir = download_dir.trim();
        if (!fs.existsSync(targetDir)) fs.mkdirSync(targetDir, { recursive: true });
        current.download_dir = targetDir;
      }
      if (typeof is_configured === 'boolean') current.is_configured = is_configured;
      if (custom_source && typeof custom_source === 'object') {
        current.custom_source = {
          name: String(custom_source.name || '自建音乐解析服务').trim(),
          api_url: String(custom_source.api_url || '').trim(),
          api_key: String(custom_source.api_key || '').trim(),
          script_url: String(custom_source.script_url || '').trim()
        };
      }
      saveSettings(current);
      appendLog(`[系统设置] 下载设置已更新 (音源: ${current.download_source.toUpperCase()}, 目录: ${current.download_dir || getEffectiveMusicDir()})`);
      current.effective_music_dir = getEffectiveMusicDir();
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: true, data: current }));
    } catch (e) {
      res.writeHead(400, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: false, error: e.message }));
    }
    return;
  }

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

  if (pathname === '/api/settings/verify-directory' && req.method === 'POST') {
    if (!sessionUser.isAdmin) {
      res.writeHead(403, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: false, error: '权限不足：仅管理员可以验证目录权限' }));
      return;
    }
    try {
      const { path: dirPath } = await readRequestJson(req);
      if (!dirPath || typeof dirPath !== 'string') throw new Error('缺少目录路径');
      const data = await callDbOps('verify_directory', dirPath.trim());
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: true, data }));
    } catch (e) {
      res.writeHead(400, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: false, error: e.message }));
    }
    return;
  }

  // Third-party music accounts. Credentials are encrypted and remain server-side.
  if (pathname === '/api/music-accounts' && req.method === 'GET') {
    const saved = loadMusicAccounts();
    const data = Object.keys(MUSIC_PROVIDER_META).map(provider => publicMusicAccount(provider, saved[provider]));
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify({ ok: true, data }));
    return;
  }

  const accountMatch = pathname.match(/^\/api\/music-accounts\/(netease|qq|bodian)(?:\/(playlists|import))?$/);
  if (accountMatch) {
    const provider = accountMatch[1];
    const action = accountMatch[2] || '';
    const meta = MUSIC_PROVIDER_META[provider];
    const saved = loadMusicAccounts();

    if (!meta.available) {
      res.writeHead(501, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: false, error: meta.hint }));
      return;
    }

    if (!action && req.method === 'POST') {
      try {
        const body = await readRequestJson(req);
        const cookie = String(body.cookie || '').trim();
        if (!cookie) throw new Error('请粘贴登录 Cookie');
        const status = await runMusicAccountHelper(provider, 'status', cookie);
        if (!status.connected) {
          res.writeHead(400, { 'Content-Type': 'application/json; charset=utf-8' });
          res.end(JSON.stringify({ ok: false, error: status.error || '登录状态验证失败' }));
          return;
        }
        saved[provider] = {
          secret: encryptSecret(cookie), connected: true, nickname: status.nickname || meta.name,
          avatar: status.avatar || '', user_id: status.user_id || '', connected_at: new Date().toISOString()
        };
        writePrivateJson(MUSIC_ACCOUNTS_FILE, saved);
        res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ ok: true, data: publicMusicAccount(provider, saved[provider]) }));
      } catch (e) {
        res.writeHead(400, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ ok: false, error: e.message }));
      }
      return;
    }

    if (!action && req.method === 'DELETE') {
      delete saved[provider];
      writePrivateJson(MUSIC_ACCOUNTS_FILE, saved);
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: true }));
      return;
    }

    if (action === 'playlists' && req.method === 'GET') {
      try {
        if (!saved[provider]?.secret) throw new Error('请先连接账号');
        const cookie = decryptSecret(saved[provider].secret);
        const result = await runMusicAccountHelper(provider, 'playlists', cookie);
        if (!result.connected) throw new Error(result.error || '登录状态已失效');
        res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ ok: true, data: result.playlists || [] }));
      } catch (e) {
        res.writeHead(400, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ ok: false, error: e.message }));
      }
      return;
    }

    if (action === 'import' && req.method === 'POST') {
      try {
        const body = await readRequestJson(req);
        const urls = Array.isArray(body.urls) ? body.urls.filter(url => typeof url === 'string' && url.trim()).map(url => url.trim()) : [];
        if (urls.length !== 1) throw new Error('当前一次只能导入一个歌单，完成后可继续选择下一个');
        if (!saved[provider]?.secret) throw new Error('请先连接账号');
        const providerCookie = decryptSecret(saved[provider].secret);
        const result = startPlaylistTask(urls[0], body.target || 'public', body.user || DEFAULT_USER, provider, providerCookie);
        res.writeHead(result.status, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify(result.ok ? { ok: true, message: result.message } : { ok: false, error: result.error }));
      } catch (e) {
        res.writeHead(400, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ ok: false, error: e.message }));
      }
      return;
    }
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
    if (!sessionUser.isAdmin) {
      res.writeHead(403, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: false, error: '权限不足：仅管理员可以删除操作记录' }));
      return;
    }
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
    if (!sessionUser.isAdmin) {
      res.writeHead(403, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: false, error: '权限不足：仅管理员可以清空操作记录' }));
      return;
    }
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

  // fnOS scraped cover cache. Track records can point at album or artist art,
  // so resolve the requested namespace first and then fall back across all caches.
  const coverMatch = pathname.match(/^\/api\/covers\/(playlist|track|album|artist)\/([a-f0-9]{32})$/i);
  if (coverMatch && req.method === 'GET') {
    const [, rawType, rawGuid] = coverMatch;
    const initialType = rawType.toLowerCase();
    const guid = rawGuid.toLowerCase();
    const requestedSize = reqUrl.searchParams.get('size') || '160';
    const size = new Set(['120', '160', '400', '600', '800']).has(requestedSize) ? requestedSize : '160';
    const typesToSearch = [initialType, 'album', 'track', 'artist', 'playlist']
      .filter((item, index, list) => list.indexOf(item) === index);
    let coverPath = null;

    for (const currentType of typesToSearch) {
      const typeRoot = path.resolve(FNOS_COVER_DIR, currentType);
      const shardRoot = path.resolve(typeRoot, guid.slice(0, 2));
      const candidates = [
        path.resolve(shardRoot, `${guid}_w${size}.jpg`),
        path.resolve(shardRoot, `${guid}_w400.jpg`),
        path.resolve(shardRoot, `${guid}_w160.jpg`),
        path.resolve(shardRoot, `${guid}_w120.jpg`),
        path.resolve(shardRoot, `${guid}_w600.jpg`),
        path.resolve(shardRoot, `${guid}_w800.jpg`),
        path.resolve(shardRoot, guid)
      ];
      coverPath = candidates.find(candidate => candidate.startsWith(`${typeRoot}${path.sep}`) && fs.existsSync(candidate) && fs.statSync(candidate).isFile());
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
        if (!sessionUser.isAdmin) {
          const users = await callDbOps('list_users');
          const playlists = await callDbOps('list_playlists');
          const target = (playlists || []).find(p => p.name === old_name);
          if (!target) {
            res.writeHead(404, { 'Content-Type': 'application/json; charset=utf-8' });
            res.end(JSON.stringify({ ok: false, error: '歌单不存在' }));
            return;
          }
          if (!isUserPersonalPlaylist(target, sessionUser.userId, users)) {
            res.writeHead(403, { 'Content-Type': 'application/json; charset=utf-8' });
            res.end(JSON.stringify({ ok: false, error: '权限不足：普通用户仅可重命名属于自己的个人专属歌单，无法重命名公共歌单' }));
            return;
          }
        }
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
    if (!sessionUser.isAdmin) {
      res.writeHead(403, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: false, error: '权限不足：仅管理员可以调整歌单的可见成员' }));
      return;
    }
    try {
      const { name, user_ids } = await readRequestJson(req);
      if (!name || !Array.isArray(user_ids)) throw new Error('缺少歌单名称或用户列表');
      const result = await callDbOps('update_playlist_users', name, JSON.stringify(user_ids));
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify(result));
    } catch (e) {
      res.writeHead(400, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: false, error: e.message }));
    }
    return;
  }

  // Remove Tracks from Playlist API
  if (pathname === '/api/playlists/remove-tracks' && req.method === 'POST') {
    try {
      const { name, track_ids, remove_physical } = await readRequestJson(req);
      if (!name || !Array.isArray(track_ids) || track_ids.length === 0) throw new Error('缺少歌单名称或曲目列表');

      if (!sessionUser.isAdmin) {
        const users = await callDbOps('list_users');
        const playlists = await callDbOps('list_playlists');
        const target = (playlists || []).find(p => p.name === name);
        if (!target) {
          res.writeHead(404, { 'Content-Type': 'application/json; charset=utf-8' });
          res.end(JSON.stringify({ ok: false, error: '歌单不存在' }));
          return;
        }
        if (!isUserPersonalPlaylist(target, sessionUser.userId, users)) {
          res.writeHead(403, { 'Content-Type': 'application/json; charset=utf-8' });
          res.end(JSON.stringify({ ok: false, error: '权限不足：普通用户仅可编辑属于自己的个人专属歌单，无法编辑公共歌单' }));
          return;
        }
        if (remove_physical) {
          res.writeHead(403, { 'Content-Type': 'application/json; charset=utf-8' });
          res.end(JSON.stringify({ ok: false, error: '权限不足：普通用户禁止物理删除 NAS 本地音乐文件' }));
          return;
        }
      }

      const result = await callDbOps('remove_playlist_tracks', name, JSON.stringify(track_ids), (sessionUser.isAdmin && remove_physical) ? 'true' : 'false');
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify(result));
    } catch (e) {
      res.writeHead(400, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: false, error: e.message }));
    }
    return;
  }

  // Delete Playlist API
  if (pathname === '/api/playlists/delete' && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', async () => {
      try {
        const { name, delete_tracks } = JSON.parse(body);

        if (!sessionUser.isAdmin) {
          const users = await callDbOps('list_users');
          const playlists = await callDbOps('list_playlists');
          const target = (playlists || []).find(p => p.name === name);
          if (!target) {
            res.writeHead(404, { 'Content-Type': 'application/json; charset=utf-8' });
            res.end(JSON.stringify({ ok: false, error: '歌单不存在' }));
            return;
          }
          if (!isUserPersonalPlaylist(target, sessionUser.userId, users)) {
            res.writeHead(403, { 'Content-Type': 'application/json; charset=utf-8' });
            res.end(JSON.stringify({ ok: false, error: '权限不足：普通用户仅可删除自己创建的个人专属歌单，无法删除公共歌单或其他成员歌单' }));
            return;
          }
          if (delete_tracks) {
            res.writeHead(403, { 'Content-Type': 'application/json; charset=utf-8' });
            res.end(JSON.stringify({ ok: false, error: '权限不足：普通用户禁止删除 NAS 本地音乐文件' }));
            return;
          }
        }

        const result = await callDbOps('delete_playlist', name, (sessionUser.isAdmin && delete_tracks) ? 'true' : 'false');
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
    if (!sessionUser.isAdmin) {
      res.writeHead(403, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: false, error: '权限不足：普通用户禁止物理删除曲库歌曲' }));
      return;
    }
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
    if (!sessionUser.isAdmin) {
      res.writeHead(403, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: false, error: '权限不足：普通用户禁止批量删除曲库歌曲' }));
      return;
    }
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
      const page = Math.max(1, Number(reqUrl.searchParams.get('page') || '1'));
      const pageSize = Math.min(50, Math.max(1, Number(reqUrl.searchParams.get('page_size') || '20')));
      const searchResult = await searchOnlineKugou(q.trim(), page, pageSize);
      const songs = searchResult.results;

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
      res.end(JSON.stringify({ ok: true, data: merged, page, page_size: pageSize, total: searchResult.total, has_more: searchResult.total ? page * pageSize < searchResult.total : songs.length === pageSize }));
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

        const requestedQuality = (quality || 'flac').toLowerCase().trim();
        const reqQuality = ['flac', '320k', '128k'].includes(requestedQuality) ? requestedQuality : 'flac';
        const chosenSource = source || getSettings().download_source || 'kw';

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

        const childEnv = {
          ...process.env,
          PYTHONUNBUFFERED: '1',
          MUSIC_DIR: getEffectiveMusicDir(),
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
            cover: update.cover || currentTask.cover || (currentTask.tracks && currentTask.tracks[0] && (currentTask.tracks[0].cover || currentTask.tracks[0].pic || currentTask.tracks[0].image)) || '',
            start_time: currentTask.start_time,
            end_time: update.end_time || new Date().toISOString(),
            duration: currentTask.start_time ? Math.round((new Date(update.end_time || Date.now()) - new Date(currentTask.start_time)) / 1000) : 0,
            status: 'success',
            tracks: Array.isArray(currentTask.tracks) ? currentTask.tracks.map(t => ({
              title: t.title,
              artist: t.artist,
              status: t.status,
              path: t.path
            })) : []
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

  // Parse Playlist API (preview before starting an import)
  if (pathname === '/api/tasks/parse-playlist' && req.method === 'POST') {
    try {
      const { url } = await readRequestJson(req);
      if (!url || !String(url).trim()) {
        res.writeHead(400, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ ok: false, error: 'url is required' }));
        return;
      }
      const { stdout } = await execFileAsync('python3', ['-u', PLAYLIST_SYNC_SCRIPT, '--url', String(url).trim(), '--parse-only'], {
        env: { ...process.env, PYTHONUNBUFFERED: '1', THIRD_PARTY_COOKIE: process.env.THIRD_PARTY_COOKIE || '' },
        maxBuffer: 20 * 1024 * 1024
      });
      const lines = stdout.trim().split(/\r?\n/).filter(Boolean);
      const parsed = JSON.parse(lines[lines.length - 1]);
      let checkResults = [];
      try {
        checkResults = await callDbOps('batch_check', JSON.stringify((parsed.tracks || []).map(track => ({ title: track.title, artist: track.artist }))));
      } catch (e) { console.error('Playlist preview batch check error:', e.message); }
      const tracks = (parsed.tracks || []).map((track, index) => ({
        ...track,
        index,
        exists: Boolean(checkResults[index]?.exists),
        local_path: checkResults[index]?.path || ''
      }));
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: true, data: { ...parsed, tracks } }));
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: false, error: e.message || '歌单解析失败' }));
    }
    return;
  }

  // Start Playlist Task API
  if (pathname === '/api/tasks/start' && req.method === 'POST') {
    try {
      const { url, target = 'public', user = DEFAULT_USER, source = '', playlist_name = '', tracks = [], quality = 'flac', cover_url = '' } = await readRequestJson(req);
      const result = startPlaylistTask(url, target, user, '', '', source, { playlistName: playlist_name, tracks, quality, coverUrl: cover_url });
      res.writeHead(result.status, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify(result.ok ? { ok: true, message: result.message } : { ok: false, error: result.error, message: result.error }));
    } catch (err) {
      res.writeHead(400, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: false, error: err.message, message: err.message }));
    }
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
  let filePath = path.join(PUBLIC_DIR, pathname === '/' ? 'index.html' : pathname);
  if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
    const ext = path.extname(filePath).toLowerCase();
    const mimeTypes = {
      '.html': 'text/html; charset=utf-8',
      '.js': 'application/javascript; charset=utf-8',
      '.css': 'text/css; charset=utf-8',
      '.json': 'application/json',
      '.png': 'image/png',
      '.jpg': 'image/jpeg',
      '.svg': 'image/svg+xml',
      '.ico': 'image/x-icon'
    };
    res.writeHead(200, { 'Content-Type': mimeTypes[ext] || 'application/octet-stream' });
    fs.createReadStream(filePath).pipe(res);
    return;
  }

  res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
  res.end('404 Not Found');
});

server.listen(PORT, HOST, () => {
  console.log(`🎵 TRIM Music Hub running at http://${HOST}:${PORT}`);
  console.log(`📁 Music Root: ${MUSIC_DIR}`);
  console.log(`💽 fnOS DB: ${FNOS_DB_PATH}`);
});
