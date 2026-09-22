#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TRIM Music Hub - Music Downloader & Metadata Ingestion Engine
Features:
1. Online music search & album art scraping
2. Deduplication check against local fnOS / TRIM NAS library
3. Audio stream resolution with multi-source support (Kuwo, Kugou, QQ Music, NetEase, Auto) via lx_source.js
4. Automatic format conversion to 24-bit True FLAC if needed
5. Metadata & synchronized LRC lyrics injection
"""

import os
import sys
import re
import json
import argparse
import subprocess
import urllib.request
import urllib.parse
import time
import shutil
import tempfile
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DEFAULT_DB_OPS = "/app/db_ops.py" if os.path.exists("/app/db_ops.py") else "/vol1/1000/Project/trim-music-hub/db_ops.py"
DB_OPS_SCRIPT = os.path.join(PROJECT_DIR, "db_ops.py") if os.path.exists(os.path.join(PROJECT_DIR, "db_ops.py")) else DEFAULT_DB_OPS
SETTINGS_FILE = os.path.join(PROJECT_DIR, "data", "settings.json")

def load_force_transcode() -> bool:
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return bool(data.get("force_transcode", False))
        except Exception:
            pass
    return False

def probe_audio_format(file_path: str) -> dict:
    """Probe audio codec and container using ffprobe."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_name,bit_rate:format=format_name",
            "-of", "json",
            file_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=True)
        data = json.loads(res.stdout)
        stream = (data.get("streams") or [{}])[0]
        fmt = data.get("format") or {}
        codec = stream.get("codec_name", "").lower().strip()
        bit_rate = int(stream.get("bit_rate") or fmt.get("bit_rate") or 0)
        format_name = fmt.get("format_name", "").lower()
        return {"codec": codec, "bit_rate": bit_rate, "format_name": format_name}
    except Exception:
        return {"codec": "", "bit_rate": 0, "format_name": ""}

DEFAULT_MUSIC = "/media/music" if os.path.exists("/media/music") else "/vol2/1000/媒体/音乐"

def load_effective_music_dir() -> str:
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                d = (data.get("download_dir") or "").strip()
                if d and os.path.exists(d):
                    return d
        except Exception:
            pass
    return os.environ.get("MUSIC_DIR", DEFAULT_MUSIC)

MUSIC_ROOT = load_effective_music_dir()
LX_SOURCE = os.environ.get("LX_SOURCE_PATH", os.path.join(SCRIPT_DIR, "lx_source.js"))
PUID = os.environ.get("PUID", "1000")
PGID = os.environ.get("PGID", "1000")

BANNED_KEYWORDS = [
    "live", "现场", "演唱会", "伴奏", "instrumental", "karaoke", "消音",
    "acoustic", "不插电", "demo", "remix", "sped up", "slowed", "混音",
    "电台", "解说", "访谈", "铃声", "片段"
]

def safe_move(src: str, dst: str):
    """Safely move a file across filesystems/mounts without failing on copystat/utime permissions."""
    try:
        if os.path.exists(dst):
            try:
                os.remove(dst)
            except Exception:
                pass
        shutil.move(src, dst, copy_function=shutil.copyfile)
    except Exception:
        shutil.copyfile(src, dst)
        try:
            os.remove(src)
        except Exception:
            pass

def load_default_source() -> str:
    """Load default download source from data/settings.json or fallback to kw."""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                src = data.get("download_source", "kw")
                if src in ["kw", "kg", "tx", "wy", "auto"]:
                    return src
    except Exception:
        pass
    return "kw"

def sanitize_text(text: str) -> str:
    if not text:
        return ""
    s = text.replace("#", "").replace("\ufff4", "").replace("\ufffd", "").strip()
    clean_no_brackets = re.sub(r"【.*?】", "", s)
    clean_no_brackets = re.sub(r"\[.*?\]", "", clean_no_brackets)
    clean_no_brackets = re.sub(r"\s+", " ", clean_no_brackets).strip()
    if clean_no_brackets:
        return clean_no_brackets
    s = re.sub(r"\s+", " ", s).strip()
    return s if s else text.strip()

def check_duplicate(title: str, artist: str = ""):
    if os.path.exists(DB_OPS_SCRIPT):
        try:
            res = subprocess.run([sys.executable, DB_OPS_SCRIPT, "check_song_exists", title, artist], capture_output=True, text=True, timeout=10)
            data = json.loads(res.stdout.strip())
            return data.get("exists", False), data.get("path", "")
        except Exception:
            pass
    return False, ""

def search_songs(keyword: str):
    """Direct search using Kugou official public filter API with zero external service dependency."""
    try:
        url = f"http://songsearch.kugou.com/song_search_v2?keyword={urllib.parse.quote(keyword)}&page=1&pagesize=15&platform=WebFilter&filter=2&iscorrection=1"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            lists = data.get("data", {}).get("lists", [])
            results = []
            default_cover = "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=400&q=80"
            for item in lists:
                s_name = item.get("SongName", "").replace("<em>", "").replace("</em>", "").replace("&nbsp;", " ").strip()
                a_name = item.get("SingerName", "").replace("<em>", "").replace("</em>", "").replace("&nbsp;", " ").strip()
                alb_name = item.get("AlbumName", "").replace("<em>", "").replace("</em>", "").replace("&nbsp;", " ").strip()
                img = item.get("Image", "").replace("{size}", "400")
                results.append({
                    "song_name": s_name,
                    "singer_name": a_name,
                    "album_name": alb_name,
                    "cover": img if img else default_cover,
                    "hash": item.get("FileHash", ""),
                    "sq_hash": item.get("SQFileHash", "")
                })
            return results
    except Exception as e:
        print(f"[Search API Error]: {e}", file=sys.stderr)
    return []

def get_kugou_hash(title: str, artist: str) -> str:
    """Fetch Kugou SQFileHash or FileHash for Kugou resolution."""
    try:
        kw = urllib.parse.quote(f"{title} {artist}")
        url = f"http://songsearch.kugou.com/song_search_v2?keyword={kw}&page=1&pagesize=5&platform=WebFilter&filter=2&iscorrection=1"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            lists = data.get("data", {}).get("lists", [])
            if lists:
                return lists[0].get("SQFileHash") or lists[0].get("FileHash") or ""
    except Exception:
        pass
    return ""

def get_qq_mid(title: str, artist: str) -> str:
    """Fetch QQ Music songmid for QQ resolution."""
    try:
        kw = urllib.parse.quote(f"{title} {artist}")
        url = f"https://c.y.qq.com/soso/fcgi-bin/client_search_cp?p=1&n=1&w={kw}&format=json"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://y.qq.com"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            songs = data.get("data", {}).get("song", {}).get("list", [])
            if songs:
                return str(songs[0].get("songmid", ""))
    except Exception:
        pass
    return ""

def get_netease_id(title: str, artist: str) -> str:
    """Fetch NetEase song ID for 163 resolution."""
    try:
        kw = urllib.parse.quote(f"{title} {artist}")
        url = f"https://music.163.com/api/search/get/web?csrf_token=hlpretag=&hlposttag=&s={kw}&type=1&offset=0&total=true&limit=1"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            songs = data.get("result", {}).get("songs", [])
            if songs:
                return str(songs[0].get("id", ""))
    except Exception:
        pass
    return ""

def resolve_stream_url_from_source(title: str, artist: str, source: str, quality_type: str) -> str:
    """Resolve streaming URL via a specific platform source."""
    kg_hash = get_kugou_hash(title, artist) if source == "kg" else ""
    qq_mid = get_qq_mid(title, artist) if source == "tx" else ""
    wy_id = get_netease_id(title, artist) if source == "wy" else ""
    lx_source_json = json.dumps(os.path.abspath(LX_SOURCE))

    node_script = f"""
    const fs = require('fs');
    const vm = require('vm');
    const crypto = require('crypto');
    const code = fs.readFileSync({lx_source_json}, 'utf8');
    let handlers = [];
    const lx = {{
      EVENT_NAMES: {{ request: 'request', inited: 'inited', updateAlert: 'updateAlert' }},
      env: 'desktop', version: '2.0.0',
      utils: {{ buffer: {{ from: (...a) => Buffer.from(...a) }}, crypto: {{ md5: (s) => crypto.createHash('md5').update(s).digest('hex') }} }},
      request(url, opts, cb) {{
        if (typeof opts === 'function') {{ cb = opts; opts = {{}}; }}
        fetch(url, opts).then(async r => {{
          let body;
          const ct = r.headers.get('content-type') || '';
          if (ct.includes('json')) body = await r.json().catch(() => r.text());
          else body = await r.text();
          cb(null, {{ statusCode: r.status, body, headers: Object.fromEntries(r.headers.entries()) }}, body);
        }}).catch(err => cb(err));
      }},
      on(name, fn) {{ if (name === 'request') handlers.push(fn); }},
      send() {{}}
    }};
    const sandbox = {{
      console: {{ log(){{}}, warn(){{}}, error(){{}}, group(){{}}, groupEnd(){{}} }},
      setTimeout, clearTimeout, setInterval, clearInterval,
      Buffer, URL, module: {{ exports: {{}} }}, exports: {{}},
      lx, globalThis: {{}}, global: {{}}
    }};
    sandbox.globalThis = sandbox; sandbox.global = sandbox; sandbox.globalThis.lx = lx;
    vm.createContext(sandbox);
    vm.runInContext(code, sandbox);
    const sourceHandler = handlers[0];

    async function run() {{
      try {{
        let musicInfo = {{ name: {json.dumps(title)}, singer: {json.dumps(artist)} }};
        const src = '{source}';
        if (src === 'kg' && '{kg_hash}') musicInfo.hash = '{kg_hash}';
        if (src === 'tx' && '{qq_mid}') musicInfo.songmid = '{qq_mid}';
        if (src === 'wy' && '{wy_id}') musicInfo.id = '{wy_id}';

        const ret = await sourceHandler({{
          action: 'musicUrl',
          source: src,
          info: {{ type: '{quality_type}', musicInfo }}
        }});
        const u = typeof ret === 'string' ? ret : ret?.url;
        if (u) console.log(JSON.stringify({{ url: u, quality: '{quality_type}', source: src }}));
        else console.log(JSON.stringify({{ error: 'no_url' }}));
      }} catch(e) {{
        console.log(JSON.stringify({{ error: e.message }}));
      }}
    }}
    run();
    """
    try:
        res = subprocess.run(["node", "-e", node_script], capture_output=True, text=True, timeout=20)
        output = res.stdout.strip().splitlines()[-1] if res.stdout.strip() else "{}"
        data = json.loads(output)
        if data.get("url"):
            return data["url"]
    except Exception:
        pass
    return None

def resolve_custom_source_stream(title: str, artist: str, quality: str = "flac") -> str:
    """Resolve stream URL using user-configured custom API or custom script."""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                settings = json.load(f)
                custom = settings.get("custom_source", {})
                api_url = custom.get("api_url", "").strip()
                api_key = custom.get("api_key", "").strip()
                if api_url:
                    params = {
                        "song": title,
                        "artist": artist,
                        "quality": quality,
                        "key": api_key
                    }
                    req_url = api_url + ("&" if "?" in api_url else "?") + urllib.parse.urlencode({k: v for k, v in params.items() if v})
                    req = urllib.request.Request(req_url, headers={
                        "User-Agent": "TRIM-Music-Hub/1.0",
                        "X-API-Key": api_key
                    })
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        res_data = json.loads(resp.read().decode("utf-8"))
                        url = res_data.get("url") or res_data.get("data", {}).get("url")
                        if url and str(url).startswith("http"):
                            print(f"  -> Successfully resolved from Custom API: {url[:60]}...")
                            return url
    except Exception as e:
        print(f"  -> Custom source resolve failed: {e}")
    return None

SOURCE_NAMES = {
    "kw": "酷我音乐",
    "kg": "酷狗音乐",
    "tx": "QQ音乐",
    "wy": "网易云音乐",
    "custom": "自建音源",
    "auto": "智能聚合"
}

def resolve_audio_stream(title: str, artist: str, quality: str = "flac", source: str = None, force_transcode: bool = False) -> dict:
    """Resolve audio stream with fallback detection and quality downgrade handling."""
    quality_type = quality.lower().strip() if quality else "flac"
    if quality_type not in ["flac", "320k", "128k"]:
        quality_type = "flac"

    if not source:
        source = load_default_source()
    requested_source = source
    effective_source = requested_source

    if effective_source == "custom":
        url = resolve_custom_source_stream(title, artist, quality_type)
        if url:
            return {
                "url": url,
                "actual_quality": quality_type,
                "target_quality": quality_type,
                "source_used": "custom",
                "source_requested": requested_source,
                "source_fallback": False,
                "quality_adjusted": False,
                "adjustment_note": ""
            }
        print("  -> Custom source did not return URL, falling back to multi-source aggregation...")
        effective_source = "auto"

    source_plan = []
    if effective_source == "auto":
        source_plan = ["kw", "kg", "tx", "wy"]
    elif effective_source in ["kw", "kg", "tx", "wy"]:
        source_plan = [effective_source, "kw", "kg", "tx", "wy"]
        seen = set()
        source_plan = [x for x in source_plan if not (x in seen or seen.add(x))]
    else:
        source_plan = ["kw", "kg", "tx", "wy"]

    def probe_stream(test_url: str) -> bool:
        try:
            chk_req = urllib.request.Request(test_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(chk_req, timeout=10) as test_resp:
                ct = (test_resp.headers.get("Content-Type") or "").lower()
                if test_resp.status == 200 and not ("application/json" in ct or "text/html" in ct):
                    return True
                else:
                    return False
        except Exception:
            return False

    # 1. 尝试直接获取目标音质
    for src in source_plan:
        url = resolve_stream_url_from_source(title, artist, src, quality_type)
        if url and probe_stream(url):
            is_source_fallback = bool(requested_source and requested_source not in ("auto", "custom") and src != requested_source)
            note = ""
            if is_source_fallback:
                req_name = SOURCE_NAMES.get(requested_source, requested_source.upper())
                used_name = SOURCE_NAMES.get(src, src.upper())
                note = f"音源由{req_name}回退至{used_name}"
                print(f"  -> [音源调整] {note}")
            print(f"  -> Stream verified & successfully resolved from source: [{src.upper()}] ({quality_type.upper()})")
            return {
                "url": url,
                "actual_quality": quality_type,
                "target_quality": quality_type,
                "source_used": src,
                "source_requested": requested_source,
                "source_fallback": is_source_fallback,
                "quality_adjusted": False,
                "adjustment_note": note
            }
        elif url:
            print(f"  -> Source [{src.upper()}] stream probe failed, trying next fallback...")

    # 2. 如果目标是 128k 或 320k，未能直链解析到对应音质，向上寻找 320k 或 FLAC 音源
    if quality_type != "flac":
        fallback_qualities = ["320k", "flac"] if quality_type == "128k" else ["flac"]
        for fq in fallback_qualities:
            for src in source_plan:
                url = resolve_stream_url_from_source(title, artist, src, fq)
                if url and probe_stream(url):
                    is_source_fallback = bool(requested_source and requested_source not in ("auto", "custom") and src != requested_source)
                    notes = []
                    if is_source_fallback:
                        req_name = SOURCE_NAMES.get(requested_source, requested_source.upper())
                        used_name = SOURCE_NAMES.get(src, src.upper())
                        notes.append(f"音源由{req_name}回退至{used_name}")
                    
                    if not force_transcode:
                        # 优化 2：未开启强制转码时，没有目标品质直接向上选真实品质下载，不进行 CPU 转码！
                        notes.append(f"源站无{quality_type.upper()}，向上直通{fq.upper()}（免转码）")
                        note = " · ".join(notes)
                        print(f"  -> Stream verified from [{src.upper()}] ({fq.upper()}), direct download without transcoding: {note}")
                        return {
                            "url": url,
                            "actual_quality": fq,
                            "target_quality": fq,
                            "source_used": src,
                            "source_requested": requested_source,
                            "source_fallback": is_source_fallback,
                            "quality_adjusted": True,
                            "adjustment_note": note
                        }
                    else:
                        # 开启了强制转码：转码为目标品质
                        notes.append(f"由{fq.upper()}转码至{quality_type.upper()}")
                        note = " · ".join(notes)
                        print(f"  -> Stream verified from [{src.upper()}] ({fq.upper()}), will transcode down to requested {quality_type.upper()}")
                        if note:
                            print(f"  -> [音源/转码调整] {note}")
                        return {
                            "url": url,
                            "actual_quality": fq,
                            "target_quality": quality_type,
                            "source_used": src,
                            "source_requested": requested_source,
                            "source_fallback": is_source_fallback,
                            "quality_adjusted": True,
                            "adjustment_note": note
                        }

    # 3. 如果目标是 flac，但所有源都没有无损 FLAC（只有更低音源），向下寻找 320k 或 128k 降级保存
    if quality_type == "flac":
        lower_qualities = ["320k", "128k"]
        for lq in lower_qualities:
            for src in source_plan:
                url = resolve_stream_url_from_source(title, artist, src, lq)
                if url and probe_stream(url):
                    is_source_fallback = bool(requested_source and requested_source not in ("auto", "custom") and src != requested_source)
                    notes = []
                    if is_source_fallback:
                        req_name = SOURCE_NAMES.get(requested_source, requested_source.upper())
                        used_name = SOURCE_NAMES.get(src, src.upper())
                        notes.append(f"音源由{req_name}回退至{used_name}")
                    notes.append(f"无损未收录，降级为{lq.upper()}")
                    note = " · ".join(notes)
                    print(f"  -> [只有更低音源] {note}")
                    print(f"  -> Stream verified & successfully resolved from source: [{src.upper()}] ({lq.upper()})")
                    return {
                        "url": url,
                        "actual_quality": lq,
                        "target_quality": lq,
                        "source_used": src,
                        "source_requested": requested_source,
                        "source_fallback": is_source_fallback,
                        "quality_adjusted": True,
                        "adjustment_note": note
                    }

    return None

def get_flac_url(title: str, artist: str, quality: str = "flac", source: str = None) -> str:
    """Resolve audio streaming/download URL with specified quality and source."""
    info = resolve_audio_stream(title, artist, quality=quality, source=source)
    return info.get("url") if info else None

def download_file(url: str, dest_path: str):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req, timeout=30) as resp, open(dest_path, "wb") as f:
        chunk_size = 131072  # 128 KB
        downloaded = 0
        last_time = time.time()
        interval_bytes = 0

        while True:
            chunk = resp.read(chunk_size)
            if not chunk:
                break
            f.write(chunk)
            downloaded += len(chunk)
            interval_bytes += len(chunk)

            now = time.time()
            elapsed = now - last_time
            if elapsed >= 0.35:
                speed_mb = (interval_bytes / elapsed) / (1024 * 1024)
                speed_str = f"{speed_mb:.2f} MB/s" if speed_mb >= 0.1 else f"{int(speed_mb * 1024)} KB/s"
                print(f"[PROGRESS_SPEED] {speed_str}", flush=True)
                last_time = now
                interval_bytes = 0
        print(f"[PROGRESS_SPEED] 0 KB/s", flush=True)

def get_artist_photo_fallback(artist: str) -> str:
    """Find high-res photo for the artist as cover fallback."""
    try:
        items = search_songs(artist)
        for item in items:
            c = item.get("cover")
            if c and "unsplash" not in c and "http" in c:
                return c
    except Exception:
        pass
    return "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=400&q=80"

def fetch_lyrics(title: str, artist: str) -> str:
    """Scrape synchronized LRC lyrics via NetEase official lyrics API."""
    try:
        kw = urllib.parse.quote(f"{title} {artist}")
        search_url = f"https://music.163.com/api/search/get/web?csrf_token=hlpretag=&hlposttag=&s={kw}&type=1&offset=0&total=true&limit=3"
        req = urllib.request.Request(search_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://music.163.com"
        })
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            songs = data.get("result", {}).get("songs", [])
            if not songs:
                return ""
            song_id = songs[0]["id"]

        lyric_url = f"https://music.163.com/api/song/lyric?os=pc&id={song_id}&lv=-1&kv=-1&tv=-1"
        req_lyric = urllib.request.Request(lyric_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req_lyric, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            lrc = data.get("lrc", {}).get("lyric", "")
            return lrc if "[" in lrc else ""
    except Exception:
        return ""

def ensure_true_flac(audio_path: str, title: str, artist: str, album: str):
    """Verify audio file format using ffprobe; convert if it is Ogg/Vorbis masquerading as FLAC."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=codec_name",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        codec = res.stdout.strip().lower()
        if codec != "flac":
            print(f"  -> File detected as [{codec}], converting to standard 24-bit FLAC via ffmpeg...")
            tmp_conv = audio_path + ".conv.flac"
            conv_cmd = [
                "ffmpeg", "-y", "-i", audio_path,
                "-c:a", "flac", "-sample_fmt", "s32",
                "-ar", "48000",
                tmp_conv
            ]
            subprocess.run(conv_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            safe_move(tmp_conv, audio_path)
    except Exception as e:
        print(f"  -> Format check error: {e}")

def embed_flac_metadata(filepath: str, title: str, artist: str, album: str, date: str, cover_path: str = None, lyrics: str = None):
    """Write FLAC Vorbis comments and optional embedded artwork."""
    cmd = [
        "metaflac",
        "--remove-all-tags",
        f"--set-tag=TITLE={title}",
        f"--set-tag=ARTIST={artist}",
        f"--set-tag=ALBUMARTIST={artist}",
        f"--set-tag=ALBUM={album}",
    ]
    if date:
        cmd.append(f"--set-tag=DATE={date}")
    if lyrics:
        cmd.append(f"--set-tag=LYRICS={lyrics}")

    if cover_path and os.path.exists(cover_path):
        cmd.append(f"--import-picture-from={cover_path}")

    cmd.append(filepath)
    env = dict(os.environ)
    env["LC_ALL"] = "C.UTF-8"
    env["LANG"] = "C.UTF-8"
    subprocess.run(cmd, env=env, check=True)


def embed_mp3_metadata(filepath: str, title: str, artist: str, album: str, date: str, cover_path: str = None, lyrics: str = None):
    """Write ID3 metadata for MP3 without re-encoding the audio stream."""
    fd, tagged_path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
        cmd = ["ffmpeg", "-y", "-i", filepath]
        if cover_path and os.path.exists(cover_path):
            cmd.extend(["-i", cover_path])
        cmd.extend([
            "-map", "0:a:0",
            "-c:a", "copy",
            "-id3v2_version", "3",
            "-metadata", f"title={title}",
            "-metadata", f"artist={artist}",
            "-metadata", f"album_artist={artist}",
            "-metadata", f"album={album}",
        ])
        if date:
            cmd.extend(["-metadata", f"date={date}"])
        if lyrics:
            cmd.extend(["-metadata", f"lyrics={lyrics}"])
        if cover_path and os.path.exists(cover_path):
            cmd.extend([
                "-map", "1:0",
                "-c:v", "mjpeg",
                "-disposition:v:0", "attached_pic",
                "-metadata:s:v", "title=Album cover",
                "-metadata:s:v", "comment=Cover (front)",
            ])
        cmd.append(tagged_path)
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        safe_move(tagged_path, filepath)
    finally:
        if os.path.exists(tagged_path):
            os.remove(tagged_path)

def convert_to_mp3(audio_path: str, bitrate: str):
    """Convert the resolved stream to a real MP3 at the requested bitrate.
    Optimization 1: Stream-copy pass-through if already MP3 (0 CPU).
    Optimization 3: Limit CPU threads to 1 (-threads 1) to prevent CPU hogging.
    """
    probe = probe_audio_format(audio_path)
    if probe.get("codec") == "mp3":
        print(f"  -> [智能嗅探直通] 音频流已为标准 MP3，0 CPU 损耗直接复用！")
        return

    fd, converted_path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
        cmd = [
            "ffmpeg", "-y", "-i", audio_path,
            "-threads", "1",
            "-map", "0:a:0",
            "-vn",
            "-c:a", "libmp3lame",
            "-b:a", bitrate,
            converted_path,
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        safe_move(converted_path, audio_path)
    finally:
        if os.path.exists(converted_path):
            os.remove(converted_path)

def process_song_download(artist: str, title: str, album: str = None, force: bool = False, quality: str = "flac", source: str = None, force_transcode: bool = None):
    if force_transcode is None:
        force_transcode = load_force_transcode()

    quality = (quality or "flac").lower().strip()
    if quality not in {"flac", "320k", "128k"}:
        quality = "flac"
    artist = sanitize_text(artist)
    title = sanitize_text(title)
    if not album:
        album = title
    else:
        album = sanitize_text(album)

    used_source = source or load_default_source()
    print(f"=== [TRIM Music Hub] Processing: {artist} - {title} (Quality: {quality.upper()}, Source: {used_source.upper()}, ForceTranscode: {force_transcode}) ===")

    # 1. Deduplication check
    is_dup, dup_path = check_duplicate(title, artist)
    if is_dup and not force:
        print(f"⚠️ [DEDUPLICATE] Target already in library: {dup_path}")
        return {"status": "already_exists", "info": dup_path}

    # 2. Search song & metadata
    search_res = search_songs(f"{artist} {title}")
    target_item = None
    for item in search_res:
        name = item.get("song_name", "")
        name_lower = name.lower()
        if any(bw in name_lower for bw in BANNED_KEYWORDS):
            continue
        target_item = item
        break

    if not target_item and search_res:
        target_item = search_res[0]

    cover_url = target_item.get("cover") if target_item else None
    if target_item and (not album or album == title):
        if target_item.get("album_name"):
            album = sanitize_text(target_item["album_name"])
    if not cover_url or "http" not in cover_url:
        print("  -> Album cover missing. Falling back to high-res artist photo...")
        cover_url = get_artist_photo_fallback(artist)

    # 3. Resolve audio stream url
    print(f"  -> Resolving {quality.upper()} audio stream via lx_source (Source: {used_source})...")
    stream_info = resolve_audio_stream(title, artist, quality=quality, source=used_source, force_transcode=force_transcode)
    if not stream_info or not stream_info.get("url"):
        return {"status": "error", "message": f"Could not find audio source ({quality}) for {artist} - {title}"}

    audio_url = stream_info["url"]
    actual_quality = stream_info.get("actual_quality", quality)
    target_quality = stream_info.get("target_quality", quality)
    source_used = stream_info.get("source_used", used_source)
    source_fallback = stream_info.get("source_fallback", False)
    quality_adjusted = stream_info.get("quality_adjusted", False)
    adjusted = source_fallback or quality_adjusted
    adjustment_note = stream_info.get("adjustment_note", "")

    # 4. Prepare directories and preserve the requested output format.
    effective_save_quality = target_quality if target_quality in ["320k", "128k"] else ("flac" if target_quality in ["flac", "flac24bit"] else quality)
    artist_dir = os.path.join(MUSIC_ROOT, artist)
    song_dir = os.path.join(artist_dir, f"{artist} - {title}")
    os.makedirs(song_dir, exist_ok=True)
    output_ext = "flac" if effective_save_quality == "flac" else "mp3"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_music = os.path.join(tmpdir, "download.input")
        tmp_cover = os.path.join(tmpdir, "cover.jpg")

        print(f"  -> Downloading audio stream from source...")
        download_file(audio_url, tmp_music)

        probed = probe_audio_format(tmp_music)
        real_codec = probed.get("codec", "")

        if effective_save_quality in ["flac", "flac24bit"]:
            ensure_true_flac(tmp_music, title, artist, album)
            output_ext = "flac"
        else:
            if real_codec == "mp3":
                print(f"  -> [智能嗅探直通] 下载音频已为标准 MP3，免重新编码直接复用！")
                output_ext = "mp3"
            elif not force_transcode:
                if real_codec == "flac":
                    print(f"  -> [未开启强制转码] 音源为原生 FLAC，直接无损封装入库！")
                    ensure_true_flac(tmp_music, title, artist, album)
                    output_ext = "flac"
                    effective_save_quality = "flac"
                else:
                    print(f"  -> [未开启强制转码] 音源为 {real_codec}，保持原生音频流！")
                    output_ext = "mp3"
                    convert_to_mp3(tmp_music, effective_save_quality)
            else:
                print(f"  -> [已开启强制转码] 将音源重新编码为 MP3 ({effective_save_quality})...")
                convert_to_mp3(tmp_music, effective_save_quality)
                output_ext = "mp3"

        final_audio_path = os.path.join(song_dir, f"{artist} - {title}.{output_ext}")

        # Download cover
        has_cover = False
        if cover_url:
            try:
                print(f"  -> Downloading cover art: {cover_url[:60]}...")
                download_file(cover_url, tmp_cover)
                if os.path.getsize(tmp_cover) > 1024:
                    has_cover = True
            except Exception as e:
                print(f"  -> Cover download failed: {e}")

        # Fetch lyrics
        lyrics_text = fetch_lyrics(title, artist)
        if lyrics_text:
            print("  -> Scraped timestamped LRC lyrics successfully")

        # Inject metadata & cover & lyrics using the container matching the output format.
        print(f"  -> Injecting metadata tags, cover art & lyrics into {output_ext.upper()}...")
        metadata_fn = embed_flac_metadata if output_ext == "flac" else embed_mp3_metadata
        metadata_fn(
            tmp_music,
            title=title,
            artist=artist,
            album=album,
            date="",
            cover_path=tmp_cover if has_cover else None,
            lyrics=lyrics_text if lyrics_text else None
        )

        safe_move(tmp_music, final_audio_path)

    # Save .lrc file if lyrics found
    if lyrics_text:
        lrc_path = os.path.join(song_dir, f"{artist} - {title}.lrc")
        try:
            with open(lrc_path, "w", encoding="utf-8") as f:
                f.write(lyrics_text)
            os.chmod(lrc_path, 0o777)
            print(f"  -> Saved sibling LRC lyrics file: {lrc_path}")
        except Exception as e:
            print(f"  -> Error saving LRC file: {e}")

    # Set permissions
    try:
        subprocess.run(["chown", "-R", f"{PUID}:{PGID}", artist_dir], stderr=subprocess.DEVNULL)
        subprocess.run(["chmod", "-R", "777", artist_dir], stderr=subprocess.DEVNULL)
    except Exception:
        pass

    if adjusted:
        print(f"ℹ️ [调整提示] 本曲目音源/音质有调整: {adjustment_note}")
    print(f"✅ Successfully archived: {final_audio_path}")
    return {
        "status": "success",
        "path": final_audio_path,
        "quality": quality,
        "actual_quality": actual_quality,
        "target_quality": effective_save_quality,
        "source_used": source_used,
        "source_requested": used_source,
        "source_fallback": source_fallback,
        "quality_adjusted": quality_adjusted,
        "adjusted": adjusted,
        "adjustment_note": adjustment_note,
        "format": output_ext,
        "artist": artist,
        "title": title,
        "album": album,
        "cover_embedded": has_cover
    }

def main():
    parser = argparse.ArgumentParser(description="TRIM Music Hub Downloader")
    parser.add_argument("--artist", required=True, help="Artist name")
    parser.add_argument("--song", required=True, help="Song title")
    parser.add_argument("--album", default="", help="Album title (optional)")
    parser.add_argument("--quality", default="flac", choices=["flac", "320k", "128k"], help="Audio quality (default: flac)")
    parser.add_argument("--source", default="", choices=["", "kw", "kg", "tx", "wy", "auto", "custom"], help="Download source")
    parser.add_argument("--force", action="store_true", help="Force download even if duplicate exists")
    parser.add_argument("--force-transcode", action="store_true", help="Force audio transcoding via CPU if format differs")
    parser.add_argument("--check-only", action="store_true", help="Check duplicate only")
    args = parser.parse_args()

    if args.check_only:
        is_dup, dup_path = check_duplicate(args.song, args.artist)
        if is_dup:
            print(f"【已收录】{dup_path}")
        else:
            print("未检测到重复")
        return

    force_transcode = args.force_transcode or load_force_transcode()
    ret = process_song_download(args.artist, args.song, args.album, args.force, quality=args.quality, source=args.source or None, force_transcode=force_transcode)
    print(json.dumps(ret, ensure_ascii=False, indent=2))
    if isinstance(ret, dict) and ret.get("status") != "success":
        sys.exit(1)

if __name__ == "__main__":
    main()
