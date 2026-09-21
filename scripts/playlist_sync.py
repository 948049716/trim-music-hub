#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TRIM Music Hub - Playlist Sync & Downloader
Parses third-party music playlists (NetEase Cloud Music, QQ Music, etc.),
performs fast deduplication against fnOS / TRIM NAS library, downloads missing tracks,
generates standard M3U8 files, and registers playlists into fnOS music.db.
"""

import os
import sys
import re
import json
import argparse
import subprocess
import urllib.request
import urllib.parse
from datetime import datetime
import uuid
import sqlite3
import shutil
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
MUSIC_MANAGER = os.path.join(SCRIPT_DIR, "music_manager.py")
SETTINGS_FILE = os.path.join(PROJECT_DIR, "data", "settings.json")

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
PLAYLIST_DIR = os.path.join(MUSIC_ROOT, "歌单")

DEFAULT_DB_DIR = "/app/db" if os.path.exists("/app/db") else "/usr/local/apps/@appdata/trim.music/db"
DB_DIR = os.environ.get("FNOS_DB_DIR", DEFAULT_DB_DIR)
DB_PATH = os.environ.get("FNOS_DB_PATH") or os.path.join(DB_DIR, "music.db")

DEFAULT_COVER_DIR = "/app/cover" if os.path.exists("/app/cover") else "/vol1/@appmeta/trim.music/cover"
COVER_DIR = os.environ.get("FNOS_COVER_DIR", DEFAULT_COVER_DIR)

MONITOR_PORT = os.environ.get("PORT", "4175")
MONITOR_URL = f"http://127.0.0.1:{MONITOR_PORT}/api/update-status"

PUID = os.environ.get("PUID", "1000")
PGID = os.environ.get("PGID", "1000")

USER_AGENTS = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
THIRD_PARTY_COOKIE = os.environ.get("THIRD_PARTY_COOKIE", "").strip()

def resolve_real_url(raw_text: str) -> str:
    """Extract and resolve short links or redirects."""
    m = re.search(r"https?://[^\s\"'>]+", raw_text)
    if not m:
        return ""
    url = m.group(0)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENTS})
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.geturl()
    except Exception:
        return url

def parse_netease_playlist(url: str):
    """Parse NetEase Cloud Music playlist."""
    m = re.search(r"[?&]id=(\d+)", url)
    if not m:
        m = re.search(r"/playlist/(\d+)", url)
    if not m:
        return None
    pid = m.group(1)
    api_url = f"https://music.163.com/api/v3/playlist/detail?id={pid}&n=1000&s=0"
    headers = {
        "User-Agent": USER_AGENTS,
        "Referer": "https://music.163.com/",
        "Cookie": THIRD_PARTY_COOKIE or "os=pc; osver=Microsoft-Windows-10-Professional-build-19042-64bit; appver=2.9.7;"
    }
    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("code") != 200:
                return None
            pl = data.get("playlist", {})
            name = pl.get("name", "").strip()
            cover = pl.get("coverImgUrl", "")
            tracks_raw = pl.get("tracks", [])
            tracks = []
            for t in tracks_raw:
                t_name = t.get("name", "").strip()
                artists = "/".join([a.get("name", "") for a in t.get("ar", []) if a.get("name")])
                album = t.get("al", {}).get("name", "").strip()
                t_cover = t.get("al", {}).get("picUrl", "")
                if t_name and artists:
                    tracks.append({
                        "title": t_name,
                        "artist": artists,
                        "album": album,
                        "cover": t_cover
                    })
            return {
                "platform": "网易云音乐",
                "playlist_name": name,
                "cover_url": cover,
                "tracks": tracks
            }
    except Exception as e:
        print(f"[NetEase Parse Error]: {e}", file=sys.stderr)
        return None

def parse_qq_playlist(url: str):
    """Parse QQ Music playlist."""
    tid = None
    m = re.search(r"[?&]id=(\d+)", url)
    if m:
        tid = m.group(1)
    else:
        m2 = re.search(r"/(?:playsquare|playlist)/([a-zA-Z0-9_-]+)", url)
        if m2:
            tid = m2.group(1)
    if not tid:
        return None

    api_url = f"https://c.y.qq.com/qzone/fcg-bin/fcg_ucc_getcdinfo_byids_cp.fcg?type=1&json=1&utf8=1&onlysong=0&disstid={tid}&g_tk=5381&loginUin=0&hostUin=0&format=json&inCharset=utf8&outCharset=utf-8&notice=0&platform=yqq.json&needNewCode=0"
    headers = {
        "User-Agent": USER_AGENTS,
        "Referer": "https://y.qq.com/",
        "Cookie": THIRD_PARTY_COOKIE
    }
    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("code") != 0:
                return None
            cdlist = data.get("cdlist", [])
            if not cdlist:
                return None
            pl = cdlist[0]
            name = pl.get("dissname", "").strip()
            cover = pl.get("logo", "")
            tracks_raw = pl.get("songlist", [])
            tracks = []
            for t in tracks_raw:
                t_name = t.get("songname", "").strip()
                singers = "/".join([s.get("name", "") for s in t.get("singer", []) if s.get("name")])
                album = t.get("albumname", "").strip()
                mid = t.get("albummid", "")
                t_cover = f"https://y.gtimg.cn/music/photo_new/T002R300x300M000{mid}.jpg" if mid else ""
                if t_name and singers:
                    tracks.append({
                        "title": t_name,
                        "artist": singers,
                        "album": album,
                        "cover": t_cover
                    })
            return {
                "platform": "QQ音乐",
                "playlist_name": name,
                "cover_url": cover,
                "tracks": tracks
            }
    except Exception as e:
        print(f"[QQ Music Parse Error]: {e}", file=sys.stderr)
        return None

def parse_playlist_url(raw_input: str):
    real_url = resolve_real_url(raw_input)
    if not real_url:
        return None
    if "163.com" in real_url:
        return parse_netease_playlist(real_url)
    elif "qq.com" in real_url:
        return parse_qq_playlist(real_url)
    return None

def build_local_library_index():
    """Scan local music directory once to build an in-memory index for fast matching."""
    index = set()
    files_map = {}
    if not os.path.exists(MUSIC_ROOT):
        return index, files_map

    try:
        for artist_entry in os.scandir(MUSIC_ROOT):
            if not artist_entry.is_dir() or artist_entry.name == "歌单":
                continue
            for song_entry in os.scandir(artist_entry.path):
                s_name = song_entry.name.lower().strip()
                if song_entry.is_dir():
                    for f in os.scandir(song_entry.path):
                        if f.name.endswith((".flac", ".mp3", ".alac", ".wav", ".m4a")):
                            files_map[s_name] = f.path
                            index.add(s_name)
                            parts = s_name.split(" - ")
                            if len(parts) > 1:
                                song_title_clean = parts[-1].strip()
                                index.add(song_title_clean)
                                files_map[song_title_clean] = f.path
                                combo = f"{parts[0].strip()} - {song_title_clean}"
                                index.add(combo)
                                files_map[combo] = f.path
                            break
                elif song_entry.is_file():
                    base = os.path.splitext(s_name)[0].strip()
                    index.add(base)
                    files_map[base] = song_entry.path
    except Exception as e:
        print(f"[Index Error]: {e}", file=sys.stderr)
    return index, files_map

LOCAL_INDEX, LOCAL_FILES = None, None

def check_track_exists(title: str, artist: str):
    global LOCAL_INDEX, LOCAL_FILES
    if LOCAL_INDEX is None:
        LOCAL_INDEX, LOCAL_FILES = build_local_library_index()

    t_clean = title.strip().lower()
    a_clean = artist.split("/")[0].strip().lower()

    combo = f"{a_clean} - {t_clean}"
    if combo in LOCAL_FILES:
        return {"exists": True, "path": LOCAL_FILES[combo]}

    for idx_key, fpath in LOCAL_FILES.items():
        if a_clean in idx_key and t_clean in idx_key:
            return {"exists": True, "path": fpath}

    direct_dir = os.path.join(MUSIC_ROOT, artist.split("/")[0].strip(), f"{artist.split('/')[0].strip()} - {title.strip()}")
    if os.path.exists(direct_dir):
        for f in os.listdir(direct_dir):
            if f.endswith((".flac", ".mp3", ".alac", ".wav", ".m4a")):
                return {"exists": True, "path": os.path.join(direct_dir, f)}

    return {"exists": False, "path": ""}

def download_single_track(artist: str, title: str, album: str = None, quality: str = "flac", source: str = ""):
    cmd = [
        sys.executable, MUSIC_MANAGER,
        "--artist", artist.split("/")[0].strip(),
        "--song", title,
        "--quality", quality
    ]
    if album:
        cmd.extend(["--album", album])
    if source:
        cmd.extend(["--source", source])
    res = subprocess.run(cmd, capture_output=True, text=True)
    
    stdout_text = (res.stdout or "").strip()
    if stdout_text:
        lines = stdout_text.splitlines()
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip().startswith("{"):
                try:
                    block = "\n".join(lines[i:])
                    data = json.loads(block)
                    if data.get("status") in ("success", "already_exists"):
                        p = data.get("path") or data.get("info") or ""
                        return True, p
                    elif data.get("status") == "error":
                        print(f"  -> Error: {data.get('message', '未知错误')}")
                        return False, ""
                except Exception:
                    continue

    if res.returncode != 0:
        err = (res.stderr or "").strip() or stdout_text[-200:]
        print(f"  -> Subprocess error ({res.returncode}): {err}")
    return False, ""

def generate_m3u8(playlist_name: str, tracks: list):
    os.makedirs(PLAYLIST_DIR, exist_ok=True)
    filename = f"{playlist_name}.m3u8"
    filepath = os.path.join(PLAYLIST_DIR, filename)

    lines = ["#EXTM3U\n"]
    for t in tracks:
        p = t.get("path")
        if p and os.path.exists(p):
            lines.append(f"#EXTINF:-1,{t.get('artist')} - {t.get('title')}\n")
            lines.append(f"{p}\n")

    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(lines)
    try:
        os.chmod(filepath, 0o777)
        subprocess.run(["chown", "-R", f"{PUID}:{PGID}", PLAYLIST_DIR], stderr=subprocess.DEVNULL)
    except Exception:
        pass
    return filepath

def import_playlist_cover(cover_url: str) -> str:
    """Download cover image from playlist URL and import into fnOS @appmeta structure."""
    if not cover_url:
        return ""
    cover_guid = uuid.uuid4().hex
    prefix = cover_guid[:2]
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        src_img = os.path.join(tmpdir, "src.jpg")
        out_webp = os.path.join(tmpdir, cover_guid)
        w120 = os.path.join(tmpdir, f"{cover_guid}_w120.jpg")
        w160 = os.path.join(tmpdir, f"{cover_guid}_w160.jpg")
        w400 = os.path.join(tmpdir, f"{cover_guid}_w400.jpg")
        w600 = os.path.join(tmpdir, f"{cover_guid}_w600.jpg")
        w800 = os.path.join(tmpdir, f"{cover_guid}_w800.jpg")
        try:
            req = urllib.request.Request(cover_url, headers={"User-Agent": USER_AGENTS})
            with urllib.request.urlopen(req, timeout=12) as resp, open(src_img, "wb") as f:
                f.write(resp.read())

            subprocess.run(["ffmpeg", "-y", "-i", src_img, "-c:v", "libwebp", "-f", "webp", out_webp], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            subprocess.run(["ffmpeg", "-y", "-i", src_img, "-vf", "scale=120:-1", w120], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            subprocess.run(["ffmpeg", "-y", "-i", src_img, "-vf", "scale=160:-1", w160], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            subprocess.run(["ffmpeg", "-y", "-i", src_img, "-vf", "scale=400:-1", w400], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            subprocess.run(["ffmpeg", "-y", "-i", src_img, "-vf", "scale=600:-1", w600], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            subprocess.run(["ffmpeg", "-y", "-i", src_img, "-vf", "scale=800:-1", w800], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

            target_dir = os.path.join(COVER_DIR, "playlist", prefix)
            try:
                os.makedirs(target_dir, exist_ok=True)
                for fname in [cover_guid, w120, w160, w400, w600, w800]:
                    base_name = os.path.basename(fname)
                    dst_path = os.path.join(target_dir, base_name)
                    shutil.copy(os.path.join(tmpdir, base_name), dst_path)
                    try:
                        os.chmod(dst_path, 0o644)
                    except Exception:
                        pass
            except PermissionError:
                cmd = f"sudo mkdir -p {target_dir} && sudo cp {tmpdir}/* {target_dir}/ && sudo chmod 644 {target_dir}/*"
                subprocess.run(cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            print(f"🖼️ [Cover Imported]: 成功导入歌单官方高清封面 [GUID: {cover_guid}]")
            return cover_guid
        except Exception as e:
            print(f"[Cover Import Error]: {e}", file=sys.stderr)
            return ""

def resolve_track_ids(conn, c, tracks: list, wait_seconds: int = 8) -> list:
    """
    Resolve track IDs from fnOS database for a list of track items.
    Polls up to wait_seconds for newly downloaded files to be detected by fnOS inotify file scanner.
    """
    matched_map = {}
    start_time = time.time()

    while True:
        try:
            conn.rollback()
        except Exception:
            pass

        unmatched = [t for t in tracks if id(t) not in matched_map]
        if not unmatched:
            break

        for t in unmatched:
            p = t.get("path")
            title = (t.get("title") or "").strip()
            artist = (t.get("artist") or "").split("/")[0].strip()

            tid = None
            if p:
                filename = os.path.basename(p)
                c.execute("SELECT t.id FROM track t JOIN audio_file af ON t.audio_file_id = af.id WHERE af.path = ? OR af.path LIKE ? LIMIT 1;", (p, '%' + filename))
                row = c.fetchone()
                if row:
                    tid = row[0]

            if not tid and title and artist:
                c.execute("""
                    SELECT t.id FROM track t
                    LEFT JOIN track_artist ta ON t.id = ta.track_id
                    LEFT JOIN artist a ON ta.artist_id = a.id
                    WHERE t.title = ? AND (a.name LIKE ? OR t.title_latin_full LIKE ?)
                    LIMIT 1;
                """, (title, f"%{artist}%", f"%{title}%"))
                row = c.fetchone()
                if row:
                    tid = row[0]

            if not tid and title:
                c.execute("SELECT id FROM track WHERE title = ? LIMIT 1;", (title,))
                row = c.fetchone()
                if row:
                    tid = row[0]

            if tid:
                matched_map[id(t)] = tid

        missing = len(tracks) - len(matched_map)
        if missing == 0 or (time.time() - start_time >= wait_seconds):
            break
        time.sleep(1.2)

    return [matched_map[id(t)] for t in tracks if id(t) in matched_map]

def sync_to_fnos_db(playlist_name: str, target_mode: str, target_user: str, all_synced: list, cover_guid: str = ""):
    if not os.path.exists(DB_PATH):
        print(f"[DB Sync Warning]: fnOS database not found at {DB_PATH}, skipping DB registration.")
        return 0

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        users = []
        if target_mode == 'public':
            c.execute("SELECT id, name FROM user WHERE status='active';")
            users = c.fetchall()
        else:
            c.execute("SELECT id, name FROM user WHERE name=? OR id=?;", (target_user, target_user))
            users = c.fetchall()
            if not users:
                c.execute("SELECT id, name FROM user WHERE id=1;")
                users = c.fetchall()

        matched_track_ids = resolve_track_ids(conn, c, all_synced, wait_seconds=8)

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S.000000000+08:00')

        created_count = 0
        total_tracks_added = 0
        for u_id, u_name in users:
            pl_guid = uuid.uuid4().hex
            c.execute("SELECT id, cover_guid FROM playlist WHERE name=? AND user_id=?;", (playlist_name, u_id))
            existing_pl = c.fetchone()
            if existing_pl:
                pl_id = existing_pl[0]
                if cover_guid:
                    c.execute("UPDATE playlist SET cover_guid=?, updated_at=? WHERE id=?;", (cover_guid, now, pl_id))
            else:
                c.execute("""
                    INSERT INTO playlist (guid, name, cover_guid, user_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?);
                """, (pl_guid, playlist_name, cover_guid or "", u_id, now, now))
                pl_id = c.lastrowid
                created_count += 1

            for tid in matched_track_ids:
                c.execute("SELECT id FROM playlist_track WHERE playlist_id=? AND track_id=?;", (pl_id, tid))
                if not c.fetchone():
                    c.execute("""
                        INSERT INTO playlist_track (user_id, playlist_id, track_id, added_at, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?);
                    """, (u_id, pl_id, tid, now, now, now))
                    total_tracks_added += 1

        conn.commit()
        conn.close()
        print(f"✅ fnOS 数据库已绑定: 歌单《{playlist_name}》关联用户数={len(users)}, 成功添加歌曲={len(matched_track_ids)}首, 封面GUID={cover_guid or '无'}")
        return created_count
    except Exception as e:
        print(f"[DB Sync Error]: {e}", file=sys.stderr)
        return 0

def push_monitor_update(task_data: dict):
    try:
        req = urllib.request.Request(
            MONITOR_URL,
            data=json.dumps(task_data).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            pass
    except Exception:
        pass

def main():
    parser = argparse.ArgumentParser(description="TRIM Music Hub Playlist Sync")
    parser.add_argument("--url", required=True, help="Playlist URL or share text")
    parser.add_argument("--parse-only", action="store_true", help="Only parse the playlist and print JSON")
    parser.add_argument("--tracks-file", default="", help="JSON file containing the selected tracks")
    parser.add_argument("--playlist-name", default="", help="Override playlist name")
    parser.add_argument("--cover-url", default="", help="Override cover image URL")
    parser.add_argument("--target", default="public", choices=["public", "user"], help="Target playlist type (public/user)")
    parser.add_argument("--user", default="admin", help="Target fnOS user if target=user")
    parser.add_argument("--quality", default="flac", choices=["flac", "320k", "128k"], help="Download quality")
    parser.add_argument("--source", default="", choices=["", "kw", "kg", "tx", "wy", "auto", "custom"], help="Download source")
    parser.add_argument("--check-only", action="store_true", help="Only analyze and deduplicate, do not download")
    args = parser.parse_args()

    print(f"=== [TRIM Music Hub] Starting Playlist Sync ===")
    parsed = parse_playlist_url(args.url)
    if not parsed:
        print("❌ Error: Unable to parse playlist URL. Please ensure it is a valid NetEase or QQ Music link.")
        sys.exit(1)

    if args.parse_only:
        print(json.dumps(parsed, ensure_ascii=False))
        return

    playlist_name = args.playlist_name.strip() or parsed["playlist_name"]
    platform = parsed["platform"]
    raw_tracks = parsed["tracks"]
    if args.tracks_file:
        try:
            with open(args.tracks_file, "r", encoding="utf-8") as f:
                selected_tracks = json.load(f)
            if isinstance(selected_tracks, list):
                raw_tracks = selected_tracks
        except Exception as e:
            print(f"[Selected Tracks Error]: {e}", file=sys.stderr)
    total = len(raw_tracks)
    cover_url = (args.cover_url or "").strip() or (parsed.get("cover_url") or "").strip() or (parsed.get("cover") or "").strip()
    if not cover_url and raw_tracks:
        for rt in raw_tracks:
            if rt.get("cover"):
                cover_url = rt["cover"].strip()
                break

    print(f"📋 Playlist: 《{playlist_name}》 [{platform}], Total: {total} tracks")

    # Fast duplicate check
    reused = []
    to_download = []
    for t in raw_tracks:
        chk = check_track_exists(t["title"], t["artist"])
        if chk["exists"]:
            t["status"] = "reused"
            t["path"] = chk["path"]
            reused.append(t)
        else:
            t["status"] = "pending"
            to_download.append(t)

    print(f"⚡ Deduplication Result: Local Reused {len(reused)} | Need Download {len(to_download)}")

    if args.check_only:
        m3u_file = generate_m3u8(playlist_name, reused)
        print(f"✅ Preview M3U8 generated: {m3u_file}")
        sys.exit(0)

    # Initial monitor task state
    task_state = {
        "status": "downloading",
        "playlist_name": playlist_name,
        "platform": platform,
        "target": args.target,
        "user": args.user,
        "total": total,
        "reused_count": len(reused),
        "downloaded_count": 0,
        "failed_count": 0,
        "cover": cover_url,
        "current_track": None,
        "start_time": datetime.now().isoformat(),
        "tracks": raw_tracks
    }
    push_monitor_update(task_state)

    downloaded = []
    failed = []

    for idx, t in enumerate(to_download):
        track_quality = str(t.get("quality") or args.quality or "flac").lower().strip()
        if track_quality not in ("flac", "320k", "128k"):
            track_quality = args.quality or "flac"
        t["status"] = "downloading"
        task_state["current_track"] = {
            "title": t["title"],
            "artist": t["artist"],
            "album": t.get("album", ""),
            "step": f"正在抓取音频流 ({track_quality.upper()})...",
            "cover": t.get("cover", "")
        }
        push_monitor_update(task_state)

        print(f"[{idx+1}/{len(to_download)}] Downloading: {t['artist']} - {t['title']} [{track_quality}]...")
        ok, p = download_single_track(t["artist"], t["title"], t.get("album"), quality=track_quality, source=args.source)
        if ok:
            t["status"] = "downloaded"
            t["path"] = p
            downloaded.append(t)
            task_state["downloaded_count"] += 1
            print(f"  -> ✅ Saved: {p}")
        else:
            t["status"] = "failed"
            failed.append(t)
            task_state["failed_count"] += 1
            print(f"  -> ⚠️ Failed or invalid stream")

        push_monitor_update(task_state)

    # Finalize M3U8 & fnOS Database
    task_state["status"] = "finalizing"
    task_state["current_track"] = {
        "title": "正在生成歌单与官方封面",
        "artist": "飞牛系统",
        "album": playlist_name,
        "step": "正在注入高品质封面与曲库关联...",
        "cover": cover_url
    }
    push_monitor_update(task_state)

    all_synced = reused + downloaded
    m3u_path = generate_m3u8(playlist_name, all_synced)
    print(f"✅ Generated M3U8 playlist: {m3u_path}")

    cover_guid = import_playlist_cover(cover_url)
    sync_to_fnos_db(playlist_name, args.target, args.user, all_synced, cover_guid)

    task_state["status"] = "success"
    task_state["end_time"] = datetime.now().isoformat()
    task_state["current_track"] = None
    push_monitor_update(task_state)

    print(f"🎉 Playlist 《{playlist_name}》 fully synchronized! Total: {total} (Reused {len(reused)}, Downloaded {len(downloaded)}, Failed {len(failed)})")

if __name__ == "__main__":
    main()
