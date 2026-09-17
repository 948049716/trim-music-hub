#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TRIM Music Hub - fnOS SQLite Database Bridge
Connects to fnOS music.db to provide:
1. Fast local library deduplication (exact and fuzzy title/artist matches)
2. Playlist CRUD (list, rename, delete, track listing)
3. Local track management & physical file deletion
4. fnOS user resolution
"""

import os
import sys
import json
import sqlite3
import shutil
import re
import uuid
import datetime

# Resolve database and music paths with sensible fallbacks
DEFAULT_DB = "/app/db/music.db" if os.path.exists("/app/db/music.db") else "/usr/local/apps/@appdata/trim.music/db/music.db"
DB_PATH = os.environ.get("FNOS_DB_PATH", DEFAULT_DB)

DEFAULT_MUSIC = "/media/music" if os.path.exists("/media/music") else "/vol2/1000/媒体/音乐"
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "settings.json")

def load_effective_music_dir():
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

def get_db(required=True):
    try:
        if not os.path.exists(DB_PATH):
            if required:
                raise FileNotFoundError(f"fnOS database not found at {DB_PATH}. Please verify volume mapping.")
            return None
        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        if required:
            raise
        return None

def get_physically_deletable_paths(cursor, track_ids):
    """Return file paths not referenced by any active track outside track_ids."""
    ids = list(dict.fromkeys(track_ids))
    if not ids:
        return []

    placeholders = ",".join("?" for _ in ids)
    cursor.execute(f"""
    SELECT DISTINCT af.path
    FROM track selected
    JOIN audio_file af ON selected.audio_file_id = af.id
    WHERE selected.id IN ({placeholders})
      AND af.path IS NOT NULL
      AND TRIM(af.path) != ''
      AND NOT EXISTS (
          SELECT 1
          FROM track survivor
          LEFT JOIN audio_file survivor_af ON survivor.audio_file_id = survivor_af.id
          WHERE survivor.id NOT IN ({placeholders})
            AND survivor.is_admin_deleted = 0
            AND survivor.is_audio_file_deleted = 0
            AND (
                survivor.audio_file_id = selected.audio_file_id
                OR survivor_af.path = af.path
            )
      )
    """, ids + ids)
    return [row["path"] for row in cursor.fetchall()]


def list_playlists():
    conn = get_db()
    c = conn.cursor()
    query = """
    SELECT p.name, p.cover_guid, COUNT(DISTINCT pt.track_id) as track_count,
           GROUP_CONCAT(DISTINCT u.name) as users,
           GROUP_CONCAT(DISTINCT u.id) as user_ids,
           MIN(p.created_at) as created_at,
           GROUP_CONCAT(p.id) as playlist_ids
    FROM playlist p
    LEFT JOIN playlist_track pt ON p.id = pt.playlist_id
    LEFT JOIN user u ON p.user_id = u.id
    GROUP BY p.name
    ORDER BY MIN(p.id) DESC
    """
    c.execute(query)
    rows = c.fetchall()
    playlists = []
    for r in rows:
        m3u_exists = os.path.exists(os.path.join(PLAYLIST_DIR, f"{r['name']}.m3u8")) or os.path.exists(os.path.join(PLAYLIST_DIR, f"{r['name']}.m3u"))
        raw_uids = [int(x) for x in (r["user_ids"] or "").split(",") if x.isdigit()]
        playlists.append({
            "name": r["name"],
            "cover_guid": r["cover_guid"] or "",
            "track_count": r["track_count"],
            "users": r["users"] or "所有成员 (公共)",
            "user_ids": raw_uids,
            "created_at": r["created_at"] or "",
            "playlist_ids": r["playlist_ids"] or "",
            "m3u_exists": m3u_exists
        })
    conn.close()
    return playlists

def sync_playlist_m3u(name):
    m3u_file = None
    for ext in [".m3u8", ".m3u"]:
        target = os.path.join(PLAYLIST_DIR, f"{name}{ext}")
        if os.path.exists(target):
            m3u_file = target
            break
    if not m3u_file:
        return

    tracks = get_playlist_tracks(name)
    lines = ["#EXTM3U", f"#PLAYLIST:{name}", ""]
    for t in tracks:
        p = t.get("path")
        if p and os.path.exists(p):
            rel_p = os.path.relpath(p, PLAYLIST_DIR)
            lines.append(rel_p)
    try:
        with open(m3u_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except Exception:
        pass

def remove_playlist_tracks(name, track_ids, remove_physical=False):
    if not track_ids:
        return True, "未指定需移除的曲目"
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("SELECT id FROM playlist WHERE name = ?", (name,))
        p_rows = c.fetchall()
        p_ids = [r["id"] for r in p_rows]
        if not p_ids:
            conn.close()
            return False, "歌单不存在"

        placeholders_p = ','.join(['?'] * len(p_ids))
        placeholders_t = ','.join(['?'] * len(track_ids))

        track_paths = get_physically_deletable_paths(c, track_ids) if remove_physical else []

        c.execute(f"""
        DELETE FROM playlist_track
        WHERE playlist_id IN ({placeholders_p}) AND track_id IN ({placeholders_t})
        """, p_ids + track_ids)

        if remove_physical:
            c.execute(f"UPDATE track SET is_admin_deleted = 1, is_audio_file_deleted = 1 WHERE id IN ({placeholders_t})", track_ids)

        conn.commit()
    except Exception as e:
        conn.close()
        return False, str(e)
    conn.close()

    sync_playlist_m3u(name)

    if remove_physical and track_paths:
        for p in track_paths:
            if os.path.exists(p):
                try:
                    os.remove(p)
                    lrc_p = os.path.splitext(p)[0] + ".lrc"
                    if os.path.exists(lrc_p):
                        os.remove(lrc_p)
                    parent = os.path.dirname(p)
                    if os.path.exists(parent) and not os.listdir(parent):
                        os.rmdir(parent)
                except Exception:
                    pass

    return True, f"已成功从歌单【{name}】移出 {len(track_ids)} 首曲目"

def get_playlist_tracks(name):
    conn = get_db()
    c = conn.cursor()
    query = """
    SELECT t.id, t.title, a.name as artist, al.name as album, af.path, t.duration_ms, af.size, af.codec,
           COALESCE(NULLIF(t.cover_guid, ''), NULLIF(al.cover_guid, ''), NULLIF(a.cover_guid, ''), '') as cover_guid
    FROM playlist p
    JOIN playlist_track pt ON p.id = pt.playlist_id
    JOIN track t ON pt.track_id = t.id
    LEFT JOIN track_artist ta ON t.id = ta.track_id
    LEFT JOIN artist a ON ta.artist_id = a.id
    LEFT JOIN album al ON t.album_id = al.id
    LEFT JOIN audio_file af ON t.audio_file_id = af.id
    WHERE p.name = ? AND t.is_audio_file_deleted = 0 AND t.is_admin_deleted = 0
    ORDER BY pt.id ASC
    """
    c.execute(query, (name,))
    rows = c.fetchall()
    tracks = []
    seen = set()
    for r in rows:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        tracks.append({
            "id": r["id"],
            "title": r["title"],
            "artist": r["artist"] or "未知歌手",
            "album": r["album"] or "",
            "path": r["path"] or "",
            "duration_ms": r["duration_ms"] or 0,
            "size": r["size"] or 0,
            "codec": r["codec"] or "FLAC",
            "cover_guid": r["cover_guid"] or ""
        })
    conn.close()
    return tracks

def update_playlist_users(name, user_ids):
    conn = get_db()
    c = conn.cursor()
    try:
        # 获取当前歌单关联的所有曲目 ID
        c.execute("""
        SELECT DISTINCT pt.track_id
        FROM playlist p
        JOIN playlist_track pt ON p.id = pt.playlist_id
        WHERE p.name = ?
        """, (name,))
        track_ids = [r[0] for r in c.fetchall()]

        # 获取当前歌单封面 guid
        c.execute("SELECT cover_guid FROM playlist WHERE name = ? LIMIT 1", (name,))
        cov_row = c.fetchone()
        cover_guid = cov_row[0] if cov_row else ""

        # 获取现有该名称的所有歌单行
        c.execute("SELECT id, user_id FROM playlist WHERE name = ?", (name,))
        existing_p_rows = c.fetchall()
        existing_uids = {r["user_id"]: r["id"] for r in existing_p_rows}

        target_uids = set(user_ids)
        all_active_uids = set()
        c.execute("SELECT id FROM user WHERE status = 'active'")
        for r in c.fetchall():
            all_active_uids.add(r[0])

        # 如果 target_uids 包含了所有活跃用户，也可以理解为公共歌单
        # 1. 移除不在 target_uids 中的用户的歌单
        for uid, pid in list(existing_uids.items()):
            if uid not in target_uids:
                c.execute("DELETE FROM playlist_track WHERE playlist_id = ?", (pid,))
                c.execute("DELETE FROM playlist WHERE id = ?", (pid,))

        # 2. 为新勾选的 target_uids 补充创建歌单并关联曲目
        for uid in target_uids:
            if uid not in existing_uids:
                p_guid = uuid.uuid4().hex
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.000000000+08:00")
                c.execute("""
                INSERT INTO playlist (guid, name, cover_guid, user_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (p_guid, name, cover_guid, uid, now, now))
                new_pid = c.lastrowid
                for tid in track_ids:
                    c.execute("""
                    INSERT INTO playlist_track (user_id, playlist_id, track_id, added_at, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """, (uid, new_pid, tid, now, now, now))

        conn.commit()
    except Exception as e:
        conn.close()
        return False, str(e)

    conn.close()
    return True, f"成功更新歌单【{name}】的指定可见成员"

def rename_playlist(old_name, new_name):
    if not new_name.strip():
        return False, "新歌单名称不能为空"
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("UPDATE playlist SET name = ? WHERE name = ?", (new_name.strip(), old_name))
        conn.commit()
    except Exception as e:
        conn.close()
        return False, str(e)
    conn.close()

    # Rename .m3u8 file if exists
    for ext in [".m3u8", ".m3u"]:
        old_file = os.path.join(PLAYLIST_DIR, f"{old_name}{ext}")
        new_file = os.path.join(PLAYLIST_DIR, f"{new_name.strip()}{ext}")
        if os.path.exists(old_file):
            try:
                os.rename(old_file, new_file)
            except Exception:
                pass
    return True, f"成功将歌单【{old_name}】重命名为【{new_name.strip()}】"

def delete_playlist(name, delete_tracks=False):
    conn = get_db()
    c = conn.cursor()
    p_ids = []
    m3u_file_paths = []
    m3u_found = False

    # Check for m3u/m3u8 files on disk
    for ext in [".m3u8", ".m3u"]:
        m3u_path = os.path.join(PLAYLIST_DIR, f"{name}{ext}")
        if os.path.exists(m3u_path):
            m3u_found = True
            if delete_tracks:
                try:
                    with open(m3u_path, "r", encoding="utf-8", errors="ignore") as mf:
                        for line in mf:
                            line = line.strip()
                            if line and not line.startswith("#"):
                                p = line if os.path.isabs(line) else os.path.normpath(os.path.join(PLAYLIST_DIR, line))
                                if os.path.exists(p) and p not in m3u_file_paths:
                                    m3u_file_paths.append(p)
                except Exception:
                    pass

    try:
        c.execute("SELECT id FROM playlist WHERE name = ?", (name,))
        p_rows = c.fetchall()
        p_ids = [r["id"] for r in p_rows]

        if not p_ids and not m3u_found:
            conn.close()
            return False, "歌单不存在", 0

        track_paths = []
        track_ids = []
        if delete_tracks:
            if p_ids:
                c.execute(f"""
                SELECT DISTINCT t.id
                FROM playlist_track pt
                JOIN track t ON pt.track_id = t.id
                WHERE pt.playlist_id IN ({','.join(['?']*len(p_ids))})
                """, p_ids)
                track_ids = [r["id"] for r in c.fetchall()]
                track_paths = get_physically_deletable_paths(c, track_ids)

            # Check files from m3u if any
            for mp in m3u_file_paths:
                if mp not in track_paths:
                    c.execute("""
                    SELECT t.id FROM track t
                    JOIN audio_file af ON t.audio_file_id = af.id
                    WHERE af.path = ?
                    """, (mp,))
                    m_rows = c.fetchall()
                    if m_rows:
                        m_tids = [r["id"] for r in m_rows]
                        for mtid in m_tids:
                            if mtid not in track_ids:
                                track_ids.append(mtid)
                        deletable = get_physically_deletable_paths(c, m_tids)
                        for dp in deletable:
                            if dp not in track_paths:
                                track_paths.append(dp)
                    else:
                        # File on disk not registered in DB
                        track_paths.append(mp)

        if p_ids:
            c.execute(f"DELETE FROM playlist_track WHERE playlist_id IN ({','.join(['?']*len(p_ids))})", p_ids)
            c.execute(f"DELETE FROM playlist WHERE id IN ({','.join(['?']*len(p_ids))})", p_ids)

        if delete_tracks and track_ids:
            c.execute(f"UPDATE track SET is_admin_deleted = 1, is_audio_file_deleted = 1 WHERE id IN ({','.join(['?']*len(track_ids))})", track_ids)
        conn.commit()
    except Exception as e:
        conn.close()
        return False, str(e), 0
    conn.close()

    # Delete M3U8/M3U files
    for ext in [".m3u8", ".m3u"]:
        m3u_path = os.path.join(PLAYLIST_DIR, f"{name}{ext}")
        if os.path.exists(m3u_path):
            try:
                os.remove(m3u_path)
            except Exception:
                pass

    # Delete physical audio files, lyrics and empty parent dirs
    deleted_files_count = 0
    all_target_paths = list(dict.fromkeys(track_paths + m3u_file_paths))
    if delete_tracks and all_target_paths:
        for p in all_target_paths:
            if os.path.exists(p):
                try:
                    os.remove(p)
                    deleted_files_count += 1
                    lrc_p = os.path.splitext(p)[0] + ".lrc"
                    if os.path.exists(lrc_p):
                        try:
                            os.remove(lrc_p)
                        except Exception:
                            pass
                    parent = os.path.dirname(p)
                    if os.path.exists(parent) and not os.listdir(parent):
                        os.rmdir(parent)
                        grandparent = os.path.dirname(parent)
                        if os.path.exists(grandparent) and not os.listdir(grandparent):
                            os.rmdir(grandparent)
                except Exception:
                    pass

    msg = f"已成功删除歌单【{name}】"
    if delete_tracks:
        msg += f"，并彻底清理了 {deleted_files_count} 首本地物理歌曲"
    return True, msg, deleted_files_count

def delete_single_track(track_id, remove_physical=True):
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("""
        SELECT t.id, t.title, af.path
        FROM track t
        LEFT JOIN audio_file af ON t.audio_file_id = af.id
        WHERE t.id = ?
        """, (track_id,))
        row = c.fetchone()
        if not row:
            conn.close()
            return False, "曲目不存在"

        title = row["title"]
        deletable_paths = get_physically_deletable_paths(c, [track_id]) if remove_physical else []
        file_path = deletable_paths[0] if deletable_paths else None

        c.execute("DELETE FROM playlist_track WHERE track_id = ?", (track_id,))
        c.execute("UPDATE track SET is_admin_deleted = 1, is_audio_file_deleted = 1 WHERE id = ?", (track_id,))
        conn.commit()
    except Exception as e:
        conn.close()
        return False, str(e)
    conn.close()

    if remove_physical and file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
            lrc_p = os.path.splitext(file_path)[0] + ".lrc"
            if os.path.exists(lrc_p):
                os.remove(lrc_p)
            parent = os.path.dirname(file_path)
            if os.path.exists(parent) and not os.listdir(parent):
                os.rmdir(parent)
        except Exception as e:
            return True, f"已在曲库标记删除，但物理文件删除失败: {e}"

    return True, f"已彻底删除曲目【{title}】"

def search_tracks(keyword="", page=1, limit=50):
    conn = get_db()
    c = conn.cursor()
    offset = max(0, (page - 1) * limit)

    count_query = """
    SELECT COUNT(DISTINCT t.id)
    FROM track t
    LEFT JOIN track_artist ta ON t.id = ta.track_id
    LEFT JOIN artist a ON ta.artist_id = a.id
    LEFT JOIN album al ON t.album_id = al.id
    WHERE t.is_admin_deleted = 0 AND t.is_audio_file_deleted = 0
    """
    data_query = """
    SELECT t.id, t.title, a.name as artist, al.name as album, af.path, t.duration_ms, af.size, af.codec,
           COALESCE(NULLIF(t.cover_guid, ''), NULLIF(al.cover_guid, ''), NULLIF(a.cover_guid, ''), '') as cover_guid,
           t.created_at
    FROM track t
    LEFT JOIN track_artist ta ON t.id = ta.track_id
    LEFT JOIN artist a ON ta.artist_id = a.id
    LEFT JOIN album al ON t.album_id = al.id
    LEFT JOIN audio_file af ON t.audio_file_id = af.id
    WHERE t.is_admin_deleted = 0 AND t.is_audio_file_deleted = 0
    """

    params = []
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        filter_clause = " AND (t.title LIKE ? OR a.name LIKE ? OR al.name LIKE ?)"
        count_query += filter_clause
        data_query += filter_clause
        params.extend([kw, kw, kw])

    c.execute(count_query, params)
    total = c.fetchone()[0]

    data_query += " ORDER BY t.id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    c.execute(data_query, params)
    rows = c.fetchall()

    tracks = []
    seen = set()
    for r in rows:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        tracks.append({
            "id": r["id"],
            "title": r["title"],
            "artist": r["artist"] or "未知歌手",
            "album": r["album"] or "",
            "path": r["path"] or "",
            "duration_ms": r["duration_ms"] or 0,
            "size": r["size"] or 0,
            "cover_guid": r["cover_guid"] or "",
            "codec": r["codec"] or "FLAC",
            "created_at": r["created_at"] or ""
        })
    conn.close()
    return {"total": total, "page": page, "limit": limit, "list": tracks}

def find_duplicate_tracks(keyword=""):
    conn = get_db()
    c = conn.cursor()
    kw = (keyword or "").strip().lower()
    where_kw = ""
    params = []
    if kw:
        where_kw = "AND (LOWER(t.title) LIKE ? OR LOWER(COALESCE(a.name, '')) LIKE ? OR LOWER(COALESCE(al.name, '')) LIKE ?)"
        params = [f"%{kw}%", f"%{kw}%", f"%{kw}%"]

    query = f"""
    WITH dup_keys AS (
        SELECT LOWER(TRIM(t.title)) as norm_title,
               LOWER(TRIM(COALESCE(a.name, ''))) as norm_artist,
               COUNT(DISTINCT t.id) as dup_count
        FROM track t
        LEFT JOIN track_artist ta ON t.id = ta.track_id
        LEFT JOIN artist a ON ta.artist_id = a.id
        LEFT JOIN album al ON t.album_id = al.id
        WHERE t.is_admin_deleted = 0 AND t.is_audio_file_deleted = 0 {where_kw}
        GROUP BY norm_title, norm_artist
        HAVING dup_count > 1
    )
    SELECT dk.norm_title, dk.norm_artist, dk.dup_count,
           t.id, t.title, a.name as artist, al.name as album, af.path, t.duration_ms, af.size, af.codec,
           COALESCE(NULLIF(t.cover_guid, ''), NULLIF(al.cover_guid, ''), NULLIF(a.cover_guid, ''), '') as cover_guid,
           t.created_at
    FROM dup_keys dk
    JOIN track t ON LOWER(TRIM(t.title)) = dk.norm_title
    LEFT JOIN track_artist ta ON t.id = ta.track_id
    LEFT JOIN artist a ON ta.artist_id = a.id
    LEFT JOIN album al ON t.album_id = al.id
    LEFT JOIN audio_file af ON t.audio_file_id = af.id
    WHERE t.is_admin_deleted = 0 AND t.is_audio_file_deleted = 0
      AND LOWER(TRIM(COALESCE(a.name, ''))) = dk.norm_artist
    ORDER BY dk.dup_count DESC, dk.norm_title ASC, af.size DESC
    """
    c.execute(query, params)
    rows = c.fetchall()

    groups = {}
    total_duplicate_tracks = 0
    for r in rows:
        key = f"{r['norm_title']}___{r['norm_artist']}"
        if key not in groups:
            groups[key] = {
                "key": key,
                "title": r["title"],
                "artist": r["artist"] or "未知歌手",
                "count": 0,
                "tracks": []
            }
        if not any(x["id"] == r["id"] for x in groups[key]["tracks"]):
            groups[key]["tracks"].append({
                "id": r["id"],
                "title": r["title"],
                "artist": r["artist"] or "未知歌手",
                "album": r["album"] or "",
                "path": r["path"] or "",
                "duration_ms": r["duration_ms"] or 0,
                "file_size": r["size"] or 0,
                "size": r["size"] or 0,
                "codec": r["codec"] or "FLAC",
                "cover_guid": r["cover_guid"] or "",
                "created_at": r["created_at"] or ""
            })
            groups[key]["count"] = len(groups[key]["tracks"])
            total_duplicate_tracks += 1

    valid_groups = [g for g in groups.values() if len(g["tracks"]) > 1]
    conn.close()
    return {
        "groups_count": len(valid_groups),
        "total_tracks": total_duplicate_tracks,
        "groups": valid_groups
    }

def batch_delete_tracks(track_ids, remove_physical=True):
    if not track_ids:
        return {"ok": True, "deleted_count": 0, "failed_count": 0, "message": "未指定曲目"}

    conn = get_db()
    c = conn.cursor()
    deleted_count = 0
    paths_to_delete = []

    try:
        placeholders = ",".join("?" for _ in track_ids)
        c.execute(f"""
        SELECT t.id, t.title, af.path
        FROM track t
        LEFT JOIN audio_file af ON t.audio_file_id = af.id
        WHERE t.id IN ({placeholders})
        """, track_ids)
        rows = c.fetchall()

        found_ids = [r["id"] for r in rows]
        if remove_physical:
            paths_to_delete = get_physically_deletable_paths(c, found_ids)

        if found_ids:
            found_placeholders = ",".join("?" for _ in found_ids)
            c.execute(f"DELETE FROM playlist_track WHERE track_id IN ({found_placeholders})", found_ids)
            c.execute(f"UPDATE track SET is_admin_deleted = 1, is_audio_file_deleted = 1 WHERE id IN ({found_placeholders})", found_ids)
            conn.commit()
            deleted_count = len(found_ids)
    except Exception as e:
        conn.close()
        return {"ok": False, "deleted_count": 0, "failed_count": len(track_ids), "error": str(e)}
    conn.close()

    if remove_physical:
        for p in paths_to_delete:
            if os.path.exists(p):
                try:
                    os.remove(p)
                    lrc_p = os.path.splitext(p)[0] + ".lrc"
                    if os.path.exists(lrc_p):
                        os.remove(lrc_p)
                    parent = os.path.dirname(p)
                    if os.path.exists(parent) and not os.listdir(parent):
                        os.rmdir(parent)
                except Exception:
                    pass

    return {
        "ok": True,
        "deleted_count": deleted_count,
        "failed_count": len(track_ids) - deleted_count,
        "message": f"成功删除 {deleted_count} 首曲目"
    }

def clean_search_term(s):
    if not s:
        return ""
    cleaned = re.sub(r"\(.*?\)|\[.*?\]|（.*?）|【.*?】", "", s).strip()
    return cleaned if cleaned else s.strip()

def check_song_exists(title, artist):
    title = (title or "").strip()
    artist = (artist or "").strip()
    if not title:
        return {"exists": False}

    main_artist = re.split(r"[/,、&]", artist)[0].strip() if artist else ""
    c_title = clean_search_term(title)

    conn = get_db(required=False)
    row = None
    if conn:
        try:
            c = conn.cursor()
            query1 = """
            SELECT t.id, t.title, a.name as artist, af.path
            FROM track t
            LEFT JOIN track_artist ta ON t.id = ta.track_id
            LEFT JOIN artist a ON ta.artist_id = a.id
            LEFT JOIN audio_file af ON t.audio_file_id = af.id
            WHERE t.title = ? AND (a.name = ? OR a.name LIKE ?) AND t.is_admin_deleted = 0 AND af.path IS NOT NULL
            LIMIT 1
            """
            c.execute(query1, (title, artist, f"%{main_artist}%" if main_artist else "%"))
            row = c.fetchone()

            if not row and c_title and c_title != title:
                query2 = """
                SELECT t.id, t.title, a.name as artist, af.path
                FROM track t
                LEFT JOIN track_artist ta ON t.id = ta.track_id
                LEFT JOIN artist a ON ta.artist_id = a.id
                LEFT JOIN audio_file af ON t.audio_file_id = af.id
                WHERE (t.title = ? OR t.title LIKE ?) AND (a.name = ? OR a.name LIKE ?) AND t.is_admin_deleted = 0 AND af.path IS NOT NULL
                LIMIT 1
                """
                c.execute(query2, (c_title, f"{c_title}%", main_artist, f"%{main_artist}%"))
                row = c.fetchone()

            if not row and main_artist:
                query3 = """
                SELECT t.id, t.title, a.name as artist, af.path
                FROM track t
                LEFT JOIN track_artist ta ON t.id = ta.track_id
                LEFT JOIN artist a ON ta.artist_id = a.id
                JOIN audio_file af ON t.audio_file_id = af.id
                WHERE af.path LIKE ? AND t.is_admin_deleted = 0
                LIMIT 1
                """
                c.execute(query3, (f"%{main_artist}%{c_title}%",))
                row = c.fetchone()
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    if row:
        return {"exists": True, "path": row["path"], "id": row["id"]}

    audio_exts = (".flac", ".mp3", ".alac", ".wav", ".m4a", ".aac", ".ogg")
    if main_artist and os.path.exists(MUSIC_ROOT):
        target_dirs = [
            os.path.join(MUSIC_ROOT, main_artist, f"{main_artist} - {title}"),
            os.path.join(MUSIC_ROOT, main_artist, f"{main_artist} - {c_title}"),
            os.path.join(MUSIC_ROOT, main_artist, title),
            os.path.join(MUSIC_ROOT, main_artist, c_title),
            os.path.join(MUSIC_ROOT, f"{main_artist} - {title}"),
            os.path.join(MUSIC_ROOT, f"{main_artist} - {c_title}")
        ]
        for d in target_dirs:
            if os.path.isdir(d):
                try:
                    for fname in os.listdir(d):
                        if fname.lower().endswith(audio_exts):
                            return {"exists": True, "path": os.path.join(d, fname), "id": None}
                except Exception:
                    pass
        artist_dir = os.path.join(MUSIC_ROOT, main_artist)
        if os.path.isdir(artist_dir):
            try:
                for item in os.listdir(artist_dir):
                    subpath = os.path.join(artist_dir, item)
                    if os.path.isfile(subpath) and subpath.lower().endswith(audio_exts):
                        if title.lower() in item.lower() or (c_title and c_title.lower() in item.lower()):
                            return {"exists": True, "path": subpath, "id": None}
            except Exception:
                pass

    return {"exists": False}

def batch_check_songs(songs):
    conn = get_db(required=False)
    c = conn.cursor() if conn else None
    res = []
    audio_exts = (".flac", ".mp3", ".alac", ".wav", ".m4a", ".aac", ".ogg")

    try:
        for s in songs:
            title = (s.get("title") or "").strip()
            artist = (s.get("artist") or "").strip()
            if not title:
                res.append({"exists": False, "id": None, "path": ""})
                continue

            main_artist = re.split(r"[/,、&]", artist)[0].strip() if artist else ""
            c_title = clean_search_term(title)

            row = None
            if c:
                try:
                    query1 = """
                    SELECT t.id, af.path
                    FROM track t
                    LEFT JOIN track_artist ta ON t.id = ta.track_id
                    LEFT JOIN artist a ON ta.artist_id = a.id
                    LEFT JOIN audio_file af ON t.audio_file_id = af.id
                    WHERE t.title = ? AND (a.name = ? OR a.name LIKE ?) AND t.is_admin_deleted = 0 AND af.path IS NOT NULL
                    LIMIT 1
                    """
                    c.execute(query1, (title, artist, f"%{main_artist}%" if main_artist else "%"))
                    row = c.fetchone()

                    if not row and c_title and c_title != title:
                        query2 = """
                        SELECT t.id, af.path
                        FROM track t
                        LEFT JOIN track_artist ta ON t.id = ta.track_id
                        LEFT JOIN artist a ON ta.artist_id = a.id
                        LEFT JOIN audio_file af ON t.audio_file_id = af.id
                        WHERE (t.title = ? OR t.title LIKE ?) AND (a.name = ? OR a.name LIKE ?) AND t.is_admin_deleted = 0 AND af.path IS NOT NULL
                        LIMIT 1
                        """
                        c.execute(query2, (c_title, f"{c_title}%", main_artist, f"%{main_artist}%"))
                        row = c.fetchone()

                    if not row and main_artist:
                        query3 = """
                        SELECT t.id, af.path
                        FROM track t
                        JOIN audio_file af ON t.audio_file_id = af.id
                        WHERE af.path LIKE ? AND t.is_admin_deleted = 0
                        LIMIT 1
                        """
                        c.execute(query3, (f"%{main_artist}%{c_title}%",))
                        row = c.fetchone()
                except Exception:
                    pass

            found = bool(row)
            path = row["path"] if row else ""
            tid = row["id"] if row else None

            if not found and main_artist and os.path.exists(MUSIC_ROOT):
                for d in [
                    os.path.join(MUSIC_ROOT, main_artist, f"{main_artist} - {title}"),
                    os.path.join(MUSIC_ROOT, main_artist, f"{main_artist} - {c_title}"),
                    os.path.join(MUSIC_ROOT, main_artist, title),
                    os.path.join(MUSIC_ROOT, main_artist, c_title),
                    os.path.join(MUSIC_ROOT, f"{main_artist} - {title}"),
                    os.path.join(MUSIC_ROOT, f"{main_artist} - {c_title}")
                ]:
                    if os.path.isdir(d):
                        try:
                            for fname in os.listdir(d):
                                if fname.lower().endswith(audio_exts):
                                    found = True
                                    path = os.path.join(d, fname)
                                    break
                        except Exception:
                            pass
                    if found:
                        break

                if not found:
                    artist_dir = os.path.join(MUSIC_ROOT, main_artist)
                    if os.path.isdir(artist_dir):
                        try:
                            for item in os.listdir(artist_dir):
                                subpath = os.path.join(artist_dir, item)
                                if os.path.isfile(subpath) and subpath.lower().endswith(audio_exts):
                                    if title.lower() in item.lower() or (c_title and c_title.lower() in item.lower()):
                                        found = True
                                        path = subpath
                                        break
                        except Exception:
                            pass

            res.append({
                "exists": found,
                "id": tid,
                "path": path
            })
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

    return res

def list_users():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, guid, name, role, status FROM user ORDER BY id ASC")
    rows = c.fetchall()
    users = []
    for r in rows:
        users.append({
            "id": r["id"],
            "guid": r["guid"] or "",
            "name": r["name"],
            "role": r["role"] or "member",
            "status": r["status"] or "active"
        })
    conn.close()
    return users

def list_authorized_directories():
    dirs = []
    seen = set()

    # 1. fnOS shared_library table from music.db
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, guid, path, created_at FROM shared_library")
        rows = c.fetchall()
        for r in rows:
            p = r["path"]
            if p and p not in seen:
                seen.add(p)
                exists = os.path.exists(p)
                writable = False
                file_count = 0
                if exists:
                    try:
                        test_file = os.path.join(p, f".trim_test_write_{os.getpid()}")
                        with open(test_file, "w") as tf:
                            tf.write("ok")
                        os.remove(test_file)
                        writable = True
                    except Exception:
                        writable = False
                    try:
                        c.execute("SELECT COUNT(*) FROM track WHERE shared_library_id = ? AND is_audio_file_deleted = 0 AND is_admin_deleted = 0", (r["id"],))
                        row_cnt = c.fetchone()
                        file_count = row_cnt[0] if row_cnt else 0
                    except Exception:
                        file_count = 0
                    if file_count == 0:
                        try:
                            file_count = sum(1 for _, _, files in os.walk(p) for f in files if f.lower().endswith(('.flac', '.mp3', '.m4a', '.wav', '.aac', '.alac', '.ogg')))
                        except Exception:
                            file_count = 0
                dirs.append({
                    "path": p,
                    "name": "飞牛官方授权音乐库",
                    "is_fnos_authorized": True,
                    "exists": exists,
                    "writable": writable,
                    "file_count": file_count,
                    "guid": r["guid"]
                })
        conn.close()
    except Exception:
        pass

    # 2. Common media candidates on volumes
    candidates = [
        "/vol2/1000/媒体/音乐",
        "/vol1/1000/媒体/音乐",
        "/vol3/1000/媒体/音乐",
        "/vol2/1000/Music",
        "/vol1/1000/Music",
        "/media/music"
    ]
    for base in ["/vol1/1000", "/vol2/1000", "/vol3/1000"]:
        if os.path.isdir(base):
            for sub in ["媒体/音乐", "音乐", "Music", "media/music"]:
                p = os.path.join(base, sub)
                if p not in candidates:
                    candidates.append(p)

    for cand in candidates:
        if cand not in seen and os.path.exists(cand):
            seen.add(cand)
            writable = False
            try:
                test_file = os.path.join(cand, f".trim_test_write_{os.getpid()}")
                with open(test_file, "w") as tf:
                    tf.write("ok")
                os.remove(test_file)
                writable = True
            except Exception:
                writable = False
            try:
                file_count = sum(1 for _, _, files in os.walk(cand) for f in files if f.lower().endswith(('.flac', '.mp3', '.m4a', '.wav', '.aac', '.alac', '.ogg')))
            except Exception:
                file_count = 0
            dirs.append({
                "path": cand,
                "name": os.path.basename(cand) or cand,
                "is_fnos_authorized": False,
                "exists": True,
                "writable": writable,
                "file_count": file_count,
                "guid": ""
            })

    return dirs

def verify_directory(target_path):
    p = os.path.abspath(target_path.strip()) if target_path else ""
    if not p:
        return {"ok": False, "error": "路径不能为空"}

    exists = os.path.exists(p)
    is_dir = os.path.isdir(p) if exists else False
    writable = False
    error = None

    if exists and not is_dir:
        return {"ok": False, "error": "指定路径是一个文件而非目录"}

    if not exists:
        try:
            os.makedirs(p, exist_ok=True)
            exists = True
            is_dir = True
        except Exception as e:
            return {"ok": False, "error": f"创建目录失败: {e}"}

    try:
        test_file = os.path.join(p, f".trim_test_write_{os.getpid()}")
        with open(test_file, "w") as tf:
            tf.write("ok")
        os.remove(test_file)
        writable = True
    except Exception as e:
        writable = False
        error = f"目录无写入权限: {e}"

    is_fnos_authorized = False
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM shared_library WHERE path = ?", (p,))
        if c.fetchone()[0] > 0:
            is_fnos_authorized = True
        conn.close()
    except Exception:
        pass

    return {
        "ok": writable,
        "path": p,
        "exists": exists,
        "writable": writable,
        "is_fnos_authorized": is_fnos_authorized,
        "error": error
    }

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "list_playlists"
    if action == "list_playlists":
        print(json.dumps(list_playlists(), ensure_ascii=False))
    elif action == "list_users":
        print(json.dumps(list_users(), ensure_ascii=False))
    elif action == "get_playlist_tracks":
        name = sys.argv[2]
        print(json.dumps(get_playlist_tracks(name), ensure_ascii=False))
    elif action == "rename_playlist":
        old_name = sys.argv[2]
        new_name = sys.argv[3]
        ok, msg = rename_playlist(old_name, new_name)
        print(json.dumps({"ok": ok, "message": msg}, ensure_ascii=False))
    elif action == "delete_playlist":
        name = sys.argv[2]
        delete_tracks = sys.argv[3].lower() == "true" if len(sys.argv) > 3 else False
        ok, msg, count = delete_playlist(name, delete_tracks)
        print(json.dumps({"ok": ok, "message": msg, "deleted_files": count}, ensure_ascii=False))
    elif action == "check_song_exists":
        title = sys.argv[2]
        artist = sys.argv[3]
        print(json.dumps(check_song_exists(title, artist), ensure_ascii=False))
    elif action == "batch_check":
        songs_json = sys.argv[2]
        songs = json.loads(songs_json)
        print(json.dumps(batch_check_songs(songs), ensure_ascii=False))
    elif action == "delete_track":
        tid = int(sys.argv[2])
        remove_physical = sys.argv[3].lower() == "true" if len(sys.argv) > 3 else True
        ok, msg = delete_single_track(tid, remove_physical)
        print(json.dumps({"ok": ok, "message": msg}, ensure_ascii=False))
    elif action == "search_tracks":
        q = sys.argv[2] if len(sys.argv) > 2 else ""
        page = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        limit = int(sys.argv[4]) if len(sys.argv) > 4 else 50
        print(json.dumps(search_tracks(q, page, limit), ensure_ascii=False))
    elif action == "list_authorized_directories":
        print(json.dumps(list_authorized_directories(), ensure_ascii=False))
    elif action == "verify_directory":
        p = sys.argv[2] if len(sys.argv) > 2 else ""
        print(json.dumps(verify_directory(p), ensure_ascii=False))
    elif action == "find_duplicates":
        q = sys.argv[2] if len(sys.argv) > 2 else ""
        print(json.dumps(find_duplicate_tracks(q), ensure_ascii=False))
    elif action == "batch_delete_tracks":
        ids_json = sys.argv[2]
        track_ids = json.loads(ids_json)
        remove_physical = sys.argv[3].lower() == "true" if len(sys.argv) > 3 else True
        print(json.dumps(batch_delete_tracks(track_ids, remove_physical), ensure_ascii=False))
    elif action == "update_playlist_users":
        name = sys.argv[2]
        user_ids = json.loads(sys.argv[3])
        ok, msg = update_playlist_users(name, user_ids)
        print(json.dumps({"ok": ok, "message": msg}, ensure_ascii=False))
    elif action == "remove_playlist_tracks":
        name = sys.argv[2]
        track_ids = json.loads(sys.argv[3])
        remove_physical = sys.argv[4].lower() == "true" if len(sys.argv) > 4 else False
        ok, msg = remove_playlist_tracks(name, track_ids, remove_physical)
        print(json.dumps({"ok": ok, "message": msg}, ensure_ascii=False))
