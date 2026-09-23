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
import hashlib

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
                raise FileNotFoundError(f"fnOS database not found at {DB_PATH}. Please verify volume mapping or check permissions.")
            return None
        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA busy_timeout = 30000")
        except Exception:
            pass
        return conn
    except Exception as e:
        if required:
            raise
        return None


# ==================== 动态表结构自省与 OTA 升级兼容保护层 ====================
_TABLE_COLUMNS_CACHE = {}

def get_table_columns(cursor_or_conn, table_name: str) -> dict:
    """
    通过 PRAGMA table_info(table_name) 动态自省获取目标表真实列结构。
    返回格式: {col_name: {'name': str, 'type': str, 'notnull': bool, 'dflt_value': any, 'pk': bool}}
    """
    global _TABLE_COLUMNS_CACHE
    if table_name in _TABLE_COLUMNS_CACHE:
        return _TABLE_COLUMNS_CACHE[table_name]

    cols = {}
    try:
        cursor = cursor_or_conn.cursor() if hasattr(cursor_or_conn, "cursor") else cursor_or_conn
        cursor.execute(f'PRAGMA table_info("{table_name}");')
        for r in cursor.fetchall():
            c_name = r["name"] if isinstance(r, sqlite3.Row) else r[1]
            c_type = (r["type"] if isinstance(r, sqlite3.Row) else r[2]) or ""
            c_notnull = bool(r["notnull"] if isinstance(r, sqlite3.Row) else r[3])
            c_dflt = r["dflt_value"] if isinstance(r, sqlite3.Row) else r[4]
            c_pk = bool(r["pk"] if isinstance(r, sqlite3.Row) else r[5])
            cols[c_name] = {
                "name": c_name,
                "type": c_type.upper(),
                "notnull": c_notnull,
                "dflt_value": c_dflt,
                "pk": c_pk
            }
        if cols:
            _TABLE_COLUMNS_CACHE[table_name] = cols
    except Exception:
        pass
    return cols

def table_exists(cursor_or_conn, table_name: str) -> bool:
    """检测目标数据表在当前数据库中是否存在。"""
    try:
        cursor = cursor_or_conn.cursor() if hasattr(cursor_or_conn, "cursor") else cursor_or_conn
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name = ?;", (table_name,))
        return cursor.fetchone() is not None
    except Exception:
        return False

def check_schema_compatibility(cursor_or_conn=None) -> dict:
    """
    对飞牛音乐数据库执行结构完整性与版本指纹自检。
    若检测到飞牛 OTA 大版本重构导致核心表缺失，自动返回 safe_mode = True，
    通知上层业务停止对未知数据库直接写入，平滑退化为标准文件级（M3U8 + 内嵌标签）兜底。
    """
    close_when_done = False
    conn = None
    if cursor_or_conn is None:
        conn = get_db(required=False)
        if not conn:
            return {
                "compatible": False,
                "safe_mode": True,
                "schema_fingerprint": "",
                "tables_found": [],
                "missing_tables": ["all"],
                "reason": "无法连接或未配置飞牛音乐数据库 (music.db)"
            }
        cursor = conn.cursor()
        close_when_done = True
    else:
        cursor = cursor_or_conn.cursor() if hasattr(cursor_or_conn, "cursor") else cursor_or_conn

    try:
        critical_tables = ["track", "playlist", "playlist_track", "user", "audio_file"]
        found = []
        missing = []
        for tbl in critical_tables:
            if table_exists(cursor, tbl):
                found.append(tbl)
            else:
                missing.append(tbl)

        cursor.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND name IN (?, ?, ?, ?, ?) ORDER BY name;",
            ("track", "playlist", "playlist_track", "user", "audio_file")
        )
        rows = cursor.fetchall()
        raw_ddl = "".join([f"{r[0]}:{r[1] or ''};" for r in rows])
        fingerprint = hashlib.sha256(raw_ddl.encode("utf-8")).hexdigest()[:16] if raw_ddl else ""

        if missing:
            return {
                "compatible": False,
                "safe_mode": True,
                "schema_fingerprint": fingerprint,
                "tables_found": found,
                "missing_tables": missing,
                "reason": f"检测到关键表缺失 ({', '.join(missing)})，已自动进入安全防损模式 (Safe Mode)"
            }

        return {
            "compatible": True,
            "safe_mode": False,
            "schema_fingerprint": fingerprint,
            "tables_found": found,
            "missing_tables": [],
            "reason": "结构完全兼容"
        }
    except Exception as e:
        return {
            "compatible": False,
            "safe_mode": True,
            "schema_fingerprint": "",
            "tables_found": [],
            "missing_tables": ["error"],
            "reason": f"数据库结构自省异常: {e}"
        }
    finally:
        if close_when_done and conn:
            try:
                conn.close()
            except Exception:
                pass

def safe_insert(cursor, table_name: str, data: dict, or_ignore: bool = False) -> int:
    """
    基于动态列自省 (PRAGMA table_info) 执行安全的 INSERT：
    1. 自动剔除目标表中不存在的字段（防止 OTA 删除/改名字段导致崩溃）；
    2. 自动检测目标表新增的 NOT NULL 且无默认值的列，并填充类型安全默认值；
    3. 返回新插入行的 lastrowid。
    """
    cols = get_table_columns(cursor, table_name)
    if not cols:
        raise ValueError(f"Target table '{table_name}' does not exist or has no accessible schema.")

    filtered_data = {k: v for k, v in data.items() if k in cols}

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.000000000+08:00")
    for col_name, meta in cols.items():
        if meta["notnull"] and not meta["pk"] and meta["dflt_value"] is None and col_name not in filtered_data:
            c_type = meta["type"]
            if any(t in c_type for t in ["INT", "BOOL", "NUMERIC", "REAL", "FLOAT"]):
                filtered_data[col_name] = 0
            elif "TIME" in c_type or "DATE" in c_type or col_name.endswith("_at"):
                filtered_data[col_name] = now_str
            elif "guid" in col_name.lower():
                filtered_data[col_name] = uuid.uuid4().hex
            else:
                filtered_data[col_name] = ""

    if not filtered_data:
        raise ValueError(f"No valid columns matched for table '{table_name}'.")

    col_names = list(filtered_data.keys())
    placeholders = ", ".join(["?"] * len(col_names))
    quoted_cols = ", ".join([f'"{c}"' for c in col_names])
    verb = "INSERT OR IGNORE INTO" if or_ignore else "INSERT INTO"
    sql = f'{verb} "{table_name}" ({quoted_cols}) VALUES ({placeholders});'

    cursor.execute(sql, [filtered_data[c] for c in col_names])
    return cursor.lastrowid

def safe_update(cursor, table_name: str, data: dict, where_clause: str, where_params: list = None) -> int:
    """
    基于动态列自省执行安全的 UPDATE：
    仅更新当前数据库表中真实存在的列；若目标列均不存在则安全跳过，绝不抛出 SQL 语法或字段异常。
    """
    cols = get_table_columns(cursor, table_name)
    if not cols:
        return 0

    filtered_data = {k: v for k, v in data.items() if k in cols}
    if not filtered_data:
        return 0

    set_clause = ", ".join([f'"{k}" = ?' for k in filtered_data.keys()])
    sql = f'UPDATE "{table_name}" SET {set_clause} WHERE {where_clause};'
    params = list(filtered_data.values()) + (list(where_params) if where_params else [])
    cursor.execute(sql, params)
    return cursor.rowcount

def safe_mark_tracks_deleted(cursor, track_ids: list) -> int:
    """安全地将指定曲目 ID 列表标记为软删除，自适应字段变更。"""
    if not track_ids:
        return 0
    cols = get_table_columns(cursor, "track")
    update_data = {}
    if "is_admin_deleted" in cols:
        update_data["is_admin_deleted"] = 1
    if "is_audio_file_deleted" in cols:
        update_data["is_audio_file_deleted"] = 1
    if not update_data:
        return 0
    placeholders = ",".join(["?"] * len(track_ids))
    return safe_update(cursor, "track", update_data, f"id IN ({placeholders})", track_ids)

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
    try:
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
        return playlists
    finally:
        conn.close()

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
    track_paths = []
    try:
        c.execute("SELECT id FROM playlist WHERE name = ?", (name,))
        p_rows = c.fetchall()
        p_ids = [r["id"] for r in p_rows]
        if not p_ids:
            return False, "歌单不存在"

        placeholders_p = ','.join(['?'] * len(p_ids))
        placeholders_t = ','.join(['?'] * len(track_ids))

        if remove_physical:
            track_paths = get_physically_deletable_paths(c, track_ids)

        c.execute(f"""
        DELETE FROM playlist_track
        WHERE playlist_id IN ({placeholders_p}) AND track_id IN ({placeholders_t})
        """, p_ids + track_ids)

        if remove_physical:
            safe_mark_tracks_deleted(c, track_ids)

        conn.commit()
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return False, str(e)
    finally:
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
    try:
        query = """
        SELECT t.id, t.title, a.name as artist, al.name as album, af.path, t.duration_ms, af.size, af.codec,
               COALESCE(NULLIF(t.cover_guid, ''), NULLIF(al.cover_guid, ''), NULLIF(a.cover_guid, ''), '') as cover_guid,
               t.created_at as track_created_at, pt.created_at as added_at
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
                "cover_guid": r["cover_guid"] or "",
                "created_at": r["track_created_at"] or "",
                "added_at": r["added_at"] or ""
            })
        return tracks
    finally:
        conn.close()

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
                new_pid = safe_insert(c, "playlist", {
                    "guid": p_guid,
                    "name": name,
                    "cover_guid": cover_guid,
                    "user_id": uid,
                    "created_at": now,
                    "updated_at": now
                })
                for tid in track_ids:
                    safe_insert(c, "playlist_track", {
                        "user_id": uid,
                        "playlist_id": new_pid,
                        "track_id": tid,
                        "added_at": now,
                        "created_at": now,
                        "updated_at": now
                    }, or_ignore=True)

        conn.commit()
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return False, str(e)
    finally:
        conn.close()

    return True, f"成功更新歌单【{name}】的指定可见成员"

def rename_playlist(old_name, new_name):
    if not new_name.strip():
        return False, "新歌单名称不能为空"
    conn = get_db()
    c = conn.cursor()
    try:
        safe_update(c, "playlist", {"name": new_name.strip()}, "name = ?", [old_name])
        conn.commit()
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return False, str(e)
    finally:
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
            safe_mark_tracks_deleted(c, track_ids)
        conn.commit()
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return False, str(e), 0
    finally:
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
    file_path = None
    title = ""
    try:
        c.execute("""
        SELECT t.id, t.title, af.path
        FROM track t
        LEFT JOIN audio_file af ON t.audio_file_id = af.id
        WHERE t.id = ?
        """, (track_id,))
        row = c.fetchone()
        if not row:
            return False, "曲目不存在"

        title = row["title"]
        deletable_paths = get_physically_deletable_paths(c, [track_id]) if remove_physical else []
        file_path = deletable_paths[0] if deletable_paths else None

        c.execute("DELETE FROM playlist_track WHERE track_id = ?", (track_id,))
        safe_mark_tracks_deleted(c, [track_id])
        conn.commit()
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return False, str(e)
    finally:
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

    data_query += " ORDER BY t.id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    try:
        c.execute(count_query, params[:len(params)-2])
        total = c.fetchone()[0]

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
        return {"total": total, "page": page, "limit": limit, "list": tracks}
    finally:
        conn.close()

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
    try:
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
        return {
            "groups_count": len(valid_groups),
            "total_tracks": total_duplicate_tracks,
            "groups": valid_groups
        }
    finally:
        conn.close()

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
            safe_mark_tracks_deleted(c, found_ids)
            conn.commit()
            deleted_count = len(found_ids)
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return {"ok": False, "deleted_count": 0, "failed_count": len(track_ids), "error": str(e)}
    finally:
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

VERSION_KEYWORDS = [
    "dj", "remix", "live", "现场", "伴奏", "instrumental", "karaoke", "消音",
    "acoustic", "不插电", "piano", "钢琴", "demo", "sped up", "slowed", "混音",
    "ver", "version", "remaster"
]

def get_version_marker(title):
    if not title:
        return ""
    title = str(title).strip()
    parts = re.findall(r"[\(（\[【](.*?)[\)）\]】]", title)
    hyphen_parts = re.findall(r"\s*-\s*([^-\(\)（）\[\]【】]+)$", title)
    for p in parts + hyphen_parts:
        p_clean = p.strip().lower()
        if any(kw in p_clean for kw in VERSION_KEYWORDS):
            return re.sub(r"[\s\.\-_·]", "", p_clean)
    return ""

def clean_search_term(s):
    if not s:
        return ""
    cleaned = re.sub(r"[\(（\[【].*?[\)）\]】]", "", str(s)).strip()
    cleaned = re.sub(r"\s*-\s*(?:live|remaster|remastered|伴奏|instrumental|edit|version|ver).*$", "", cleaned, flags=re.I).strip()
    return cleaned if cleaned else str(s).strip()

def get_artist_variants(artist_str):
    if not artist_str:
        return []
    variants = set()
    raw_artists = [a.strip() for a in re.split(r'[/,、&|]|(?:\s+feat\.?\s+)|(?:\s+with\s+)|与', str(artist_str), flags=re.I) if a.strip()]
    if not raw_artists:
        raw_artists = [str(artist_str).strip()]
        
    for a in raw_artists:
        low = a.lower()
        variants.add(low)
        no_punc = re.sub(r"[\s\.\-_·'\"`]", "", low)
        if no_punc:
            variants.add(no_punc)
        cn_parts = re.findall(r'[\u4e00-\u9fa5]{2,}', a)
        for cp in cn_parts:
            variants.add(cp.lower())
        en_parts = re.findall(r'[a-zA-Z0-9]{2,}', a)
        for ep in en_parts:
            variants.add(ep.lower())
            variants.add(re.sub(r"[\s\.\-_]", "", ep).lower())
        sub_brackets = re.findall(r'[\(（](.*?)[\)）]', a)
        for sb in sub_brackets:
            if sb.strip():
                variants.add(sb.strip().lower())
        clean_base = re.sub(r'[\(（].*?[\)）]', '', a).strip().lower()
        if clean_base:
            variants.add(clean_base)
            
    return [v for v in variants if len(v) >= 2 or len(variants) == 1]

def _match_single_song_internal(c, title, artist):
    title = (title or "").strip()
    artist = (artist or "").strip()
    if not title:
        return {"exists": False, "path": "", "id": None}

    c_title = clean_search_term(title)
    variants = get_artist_variants(artist)
    audio_exts = (".flac", ".mp3", ".alac", ".wav", ".m4a", ".aac", ".ogg")

    candidates = []
    if c:
        try:
            c.execute("""
            SELECT t.id, t.title, a.name as artist, af.path, t.is_admin_deleted, t.is_audio_file_deleted
            FROM track t
            LEFT JOIN track_artist ta ON t.id = ta.track_id
            LEFT JOIN artist a ON ta.artist_id = a.id
            LEFT JOIN audio_file af ON t.audio_file_id = af.id
            WHERE (
                LOWER(t.title) = LOWER(?)
                OR LOWER(t.title) = LOWER(?)
                OR LOWER(t.title) LIKE LOWER(?)
                OR LOWER(af.path) LIKE LOWER(?)
            )
            AND t.is_admin_deleted = 0
            AND af.path IS NOT NULL
            """, (title, c_title, f"{c_title}%", f"%{c_title}%"))

            rows = c.fetchall()
            for r in rows:
                db_artist = (r["artist"] or "").lower().strip()
                db_clean = re.sub(r"[\s\.\-_·'\"`]", "", db_artist)
                db_path = (r["path"] or "").lower()

                artist_match = False
                if not variants:
                    artist_match = True
                else:
                    for v in variants:
                        if v == db_artist or v == db_clean:
                            artist_match = True
                            break
                        if len(v) >= 2 and (v in db_artist or v in db_clean or (len(db_clean) >= 2 and db_clean in v)):
                            artist_match = True
                            break
                        if len(v) >= 2 and v in db_path:
                            artist_match = True
                            break

                if not artist_match:
                    continue

                if r["is_audio_file_deleted"] != 0 or r["is_admin_deleted"] != 0:
                    continue

                file_exists = os.path.exists(r["path"]) if r["path"] else False
                if not file_exists:
                    continue

                # 严格区分特殊版本（如 DJ版、Remix、Live、伴奏 等），避免 DJ 版被原版吃掉
                target_ver = get_version_marker(title)
                db_ver = get_version_marker(r["title"]) or get_version_marker(os.path.splitext(os.path.basename(r["path"]))[0])
                if target_ver != db_ver:
                    continue

                score = 0
                score += 20  # 真实物理文件在盘
                score += 10  # 数据库无删除标记
                if r["title"].lower() == title.lower():
                    score += 10
                elif clean_search_term(r["title"]).lower() == c_title.lower():
                    score += 5

                path_lower = (r["path"] or "").lower()
                if path_lower.endswith((".flac", ".alac", ".wav")):
                    score += 3
                elif path_lower.endswith(".mp3"):
                    score += 1

                candidates.append((score, r))
        except Exception:
            pass

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        best = candidates[0][1]
        return {"exists": True, "path": best["path"], "id": best["id"]}

    # 磁盘兜底扫描
    if os.path.exists(MUSIC_ROOT):
        target_ver = get_version_marker(title)
        target_dirs = []
        for v in variants:
            target_dirs.extend([
                os.path.join(MUSIC_ROOT, v, f"{v} - {title}"),
                os.path.join(MUSIC_ROOT, v, f"{v} - {c_title}"),
                os.path.join(MUSIC_ROOT, v, title),
                os.path.join(MUSIC_ROOT, v, c_title),
                os.path.join(MUSIC_ROOT, f"{v} - {title}"),
                os.path.join(MUSIC_ROOT, f"{v} - {c_title}"),
                os.path.join(MUSIC_ROOT, v)
            ])

        for d in target_dirs:
            if os.path.isdir(d):
                try:
                    for item in os.listdir(d):
                        subpath = os.path.join(d, item)
                        if os.path.isfile(subpath) and subpath.lower().endswith(audio_exts):
                            item_ver = get_version_marker(os.path.splitext(item)[0])
                            if target_ver != item_ver:
                                continue
                            item_low = item.lower()
                            if title.lower() in item_low or (c_title and c_title.lower() in item_low):
                                return {"exists": True, "path": subpath, "id": None}
                        elif os.path.isdir(subpath):
                            for fname in os.listdir(subpath):
                                if fname.lower().endswith(audio_exts):
                                    fname_ver = get_version_marker(os.path.splitext(fname)[0])
                                    if target_ver != fname_ver:
                                        continue
                                    fname_low = fname.lower()
                                    if title.lower() in fname_low or (c_title and c_title.lower() in fname_low):
                                        return {"exists": True, "path": os.path.join(subpath, fname), "id": None}
                except Exception:
                    pass

    return {"exists": False, "path": "", "id": None}

def check_song_exists(title, artist):
    conn = get_db(required=False)
    c = conn.cursor() if conn else None
    try:
        return _match_single_song_internal(c, title, artist)
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

def batch_check_songs(songs):
    conn = get_db(required=False)
    c = conn.cursor() if conn else None
    res = []
    try:
        for s in songs:
            title = (s.get("title") or "").strip()
            artist = (s.get("artist") or "").strip()
            res.append(_match_single_song_internal(c, title, artist))
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
    try:
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
        return users
    finally:
        conn.close()

def list_authorized_directories():
    dirs = []
    seen = set()
    seen_inodes = set()

    def _get_inode_key(p):
        try:
            st = os.stat(p)
            return (st.st_dev, st.st_ino)
        except Exception:
            return None

    # 1. fnOS shared_library table from music.db
    try:
        conn = get_db(required=False)
        if conn:
            try:
                c = conn.cursor()
                c.execute("SELECT id, guid, path, created_at FROM shared_library")
                rows = c.fetchall()
                for r in rows:
                    p = r["path"]
                    if not p:
                        continue
                    norm_p = os.path.normpath(p)
                    inode_key = _get_inode_key(p)
                    if norm_p in seen or (inode_key and inode_key in seen_inodes):
                        continue
                    seen.add(norm_p)
                    if inode_key:
                        seen_inodes.add(inode_key)

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
            finally:
                conn.close()
    except Exception:
        pass

    # 2. If no fnOS authorized library found (e.g. offline dev or fresh setup), scan common media candidates on volumes
    if not dirs:
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
            norm_cand = os.path.normpath(cand)
            inode_key = _get_inode_key(cand)
            if norm_cand in seen or (inode_key and inode_key in seen_inodes):
                continue
            if os.path.exists(cand):
                seen.add(norm_cand)
                if inode_key:
                    seen_inodes.add(inode_key)
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

    # 3. If settings.json has a valid configured download_dir that's not yet in dirs, include it
    current_setting = load_effective_music_dir()
    if current_setting and os.path.exists(current_setting):
        norm_setting = os.path.normpath(current_setting)
        inode_key = _get_inode_key(current_setting)
        if norm_setting not in seen and (not inode_key or inode_key not in seen_inodes):
            seen.add(norm_setting)
            if inode_key:
                seen_inodes.add(inode_key)
            writable = False
            try:
                test_file = os.path.join(current_setting, f".trim_test_write_{os.getpid()}")
                with open(test_file, "w") as tf:
                    tf.write("ok")
                os.remove(test_file)
                writable = True
            except Exception:
                writable = False
            try:
                file_count = sum(1 for _, _, files in os.walk(current_setting) for f in files if f.lower().endswith(('.flac', '.mp3', '.m4a', '.wav', '.aac', '.alac', '.ogg')))
            except Exception:
                file_count = 0
            dirs.append({
                "path": current_setting,
                "name": os.path.basename(current_setting) or current_setting,
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
            try:
                puid = os.environ.get("PUID", "1000")
                pgid = os.environ.get("PGID", "1000")
                subprocess.run(["chown", "-R", f"{puid}:{pgid}", p], stderr=subprocess.DEVNULL)
                subprocess.run(["chmod", "-R", "777", p], stderr=subprocess.DEVNULL)
                subprocess.run(["setfacl", "-m", f"u:{puid}:rwx", p], stderr=subprocess.DEVNULL)
                subprocess.run(["setfacl", "-d", "-m", f"u:{puid}:rwx", p], stderr=subprocess.DEVNULL)
            except Exception:
                pass
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
    conn = get_db(required=False)
    if conn:
        try:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM shared_library WHERE path = ?", (p,))
            row = c.fetchone()
            if row and row[0] > 0:
                is_fnos_authorized = True
        except Exception:
            pass
        finally:
            conn.close()

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
    elif action == "check_schema":
        print(json.dumps(check_schema_compatibility(), ensure_ascii=False))
