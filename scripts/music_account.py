#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Third-party music account helper.

Credentials never leave the NAS: Node passes the decrypted cookie through stdin and
this helper only returns account metadata, playlist summaries, or daily recommended tracks as JSON.
"""
import gzip
import json
import re
import sys
import urllib.parse
import urllib.request

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"


def request_json(url, cookie="", referer=""):
    headers = {"User-Agent": USER_AGENT}
    if cookie:
        headers["Cookie"] = cookie
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        content = resp.read()
        if resp.info().get("Content-Encoding") == "gzip":
            content = gzip.decompress(content)
        return json.loads(content.decode("utf-8", "ignore"))


def media_url(raw):
    value = str(raw or "")
    if value.startswith("//"):
        return "https:" + value
    if value.startswith("http://"):
        return "https://" + value[7:]
    return value


def cookie_map(raw):
    result = {}
    for part in re.split(r"[;\n]+", raw or ""):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        if key:
            result[key] = value.strip()
    return result


def qq_uin(cookies):
    raw = cookies.get("wxuin") if cookies.get("login_type") == "2" else ""
    raw = raw or cookies.get("uin") or cookies.get("qqmusic_uin") or cookies.get("wxuin") or cookies.get("p_uin") or ""
    digits = re.sub(r"\D", "", raw)
    return digits.lstrip("0") or digits


def qq_music_key(cookies):
    for key in ("qm_keyst", "qqmusic_key", "music_key", "p_skey", "skey", "psrf_qqaccess_token", "psrf_qqrefresh_token", "wxrefresh_token", "wxskey"):
        if cookies.get(key):
            return cookies[key]
    return ""


def netease_status(cookie):
    cmap = cookie_map(cookie)
    if not cmap.get("MUSIC_U"):
        return {"connected": False, "error": "网易云 Cookie 缺少 MUSIC_U"}
    try:
        data = request_json("https://music.163.com/api/nuser/account/get", cookie, "https://music.163.com/")
        profile = data.get("profile") or {}
        account = data.get("account") or {}
        user_id = profile.get("userId") or account.get("id")
        if user_id:
            return {
                "connected": True,
                "user_id": str(user_id),
                "nickname": profile.get("nickname") or "网易云用户",
                "avatar": media_url(profile.get("avatarUrl")),
            }
    except Exception:
        pass

    # 兜底：若已获取到 MUSIC_U 凭据但获取详情接口波动，仍允许作为已连接
    return {
        "connected": True,
        "user_id": "",
        "nickname": "网易云用户",
        "avatar": "",
    }


def netease_playlists(cookie):
    status = netease_status(cookie)
    if not status.get("connected"):
        return {**status, "playlists": []}
    items = []
    offset = 0
    while offset < 2000:
        query = urllib.parse.urlencode({"uid": status["user_id"], "limit": 200, "offset": offset})
        data = request_json(f"https://music.163.com/api/user/playlist?{query}", cookie, "https://music.163.com/")
        page = data.get("playlist") or []
        for pl in page:
            pid = str(pl.get("id") or "")
            if not pid:
                continue
            creator = pl.get("creator") or {}
            items.append({
                "id": pid,
                "name": pl.get("name") or "未命名歌单",
                "cover": media_url(pl.get("coverImgUrl")),
                "track_count": int(pl.get("trackCount") or 0),
                "creator": creator.get("nickname") or status["nickname"],
                "subscribed": bool(pl.get("subscribed")),
                "import_url": f"https://music.163.com/playlist?id={pid}",
            })
        if not data.get("more") or not page:
            break
        offset += len(page)
    return {**status, "playlists": items}


def netease_daily_recommend(cookie):
    status = netease_status(cookie)
    if not status.get("connected"):
        return {**status, "playlist_id": "", "playlist_name": "每日推荐", "cover_url": "", "track_count": 0, "tracks": []}

    try:
        url = "https://music.163.com/api/v1/discovery/recommend/songs"
        headers = {
            "User-Agent": USER_AGENT,
            "Referer": "https://music.163.com/",
            "Cookie": cookie
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as resp:
            content = resp.read()
            if resp.info().get("Content-Encoding") == "gzip":
                content = gzip.decompress(content)
            data = json.loads(content.decode("utf-8", "ignore"))

        raw_tracks = data.get("recommend") or data.get("data", {}).get("dailySongs") or []
        if not raw_tracks and data.get("code") != 200:
            return {
                **status,
                "error": data.get("message") or "获取网易云每日推荐失败",
                "playlist_id": "",
                "playlist_name": "每日歌曲推荐",
                "cover_url": "",
                "track_count": 0,
                "tracks": []
            }

        tracks = []
        for s in raw_tracks:
            t_name = str(s.get("name") or "").strip()
            artists = "/".join([str(a.get("name") or "") for a in (s.get("artists") or s.get("ar") or []) if a.get("name")])
            album_obj = s.get("album") or s.get("al") or {}
            album_name = str(album_obj.get("name") or "").strip()
            cover = media_url(album_obj.get("picUrl") or "")
            sid = str(s.get("id") or "")
            qualities = []
            if s.get("hrMusic") or s.get("hr"):
                qualities.append("flac24bit")
            if s.get("sqMusic") or s.get("sq"):
                qualities.append("flac")
            if s.get("hMusic") or s.get("h"):
                qualities.append("320k")
            if s.get("mMusic") or s.get("lMusic") or s.get("m") or s.get("l"):
                qualities.append("128k")
            if not qualities:
                qualities = ["flac", "320k", "128k"]

            if t_name and artists:
                tracks.append({
                    "id": sid,
                    "title": t_name,
                    "artist": artists,
                    "album": album_name,
                    "cover": cover,
                    "duration": int((s.get("duration") or s.get("dt") or 0) / 1000),
                    "available_qualities": qualities,
                    "url": f"https://music.163.com/song?id={sid}" if sid else ""
                })

        return {
            "connected": True,
            "provider": "netease",
            "user_id": status.get("user_id", ""),
            "nickname": status.get("nickname", ""),
            "playlist_id": "netease_daily",
            "playlist_name": "每日歌曲推荐",
            "cover_url": tracks[0]["cover"] if tracks else "",
            "track_count": len(tracks),
            "import_url": "https://music.163.com/discover/recommend/taste",
            "tracks": tracks
        }
    except Exception as exc:
        return {
            **status,
            "error": f"获取网易云每日推荐异常: {exc}",
            "playlist_id": "",
            "playlist_name": "每日歌曲推荐",
            "cover_url": "",
            "track_count": 0,
            "tracks": []
        }


def qq_status(cookie):
    cookies = cookie_map(cookie)
    uin = qq_uin(cookies)
    if not uin or not qq_music_key(cookies):
        return {"connected": False, "error": "QQ 音乐 Cookie 缺少 uin 或登录票据"}
    nickname = cookies.get(f"ptnick_{uin}") or cookies.get(f"ptnick_0{uin}") or cookies.get("nick") or f"QQ {uin}"
    try:
        nickname = urllib.parse.unquote(nickname.replace("+", "%20"))
    except Exception:
        pass
    avatar = cookies.get(f"qqmusic_avatar_{uin}") or f"https://q1.qlogo.cn/g?b=qq&nk={uin}&s=100"
    return {"connected": True, "user_id": uin, "nickname": nickname, "avatar": media_url(avatar)}


def qq_get(url, cookie, params):
    return request_json(url + "?" + urllib.parse.urlencode(params), cookie, "https://y.qq.com/portal/profile.html")


def qq_playlist_item(pl, subscribed, fallback_creator):
    pid = str(pl.get("dissid") or pl.get("tid") or pl.get("dirid") or pl.get("id") or pl.get("diss_id") or "")
    if not pid:
        return None
    return {
        "id": pid,
        "name": pl.get("diss_name") or pl.get("dissname") or pl.get("name") or pl.get("title") or "未命名歌单",
        "cover": media_url(pl.get("diss_cover") or pl.get("logo") or pl.get("picurl") or pl.get("cover")),
        "track_count": int(pl.get("song_cnt") or pl.get("songnum") or pl.get("total_song_num") or pl.get("song_count") or 0),
        "creator": pl.get("hostname") or pl.get("nick") or pl.get("creator") or fallback_creator,
        "subscribed": subscribed,
        "import_url": f"https://y.qq.com/n/ryqq/playlist/{pid}",
    }


def qq_playlists(cookie):
    status = qq_status(cookie)
    if not status.get("connected"):
        return {**status, "playlists": []}
    uin = status["user_id"]
    created = qq_get("https://c.y.qq.com/rsc/fcgi-bin/fcg_user_created_diss", cookie, {
        "hostUin": 0, "hostuin": uin, "sin": 0, "size": 200, "g_tk": 5381,
        "loginUin": uin, "format": "json", "inCharset": "utf8", "outCharset": "utf-8",
        "notice": 0, "platform": "yqq.json", "needNewCode": 0,
    })
    collected = qq_get("https://c.y.qq.com/fav/fcgi-bin/fcg_get_profile_order_asset.fcg", cookie, {
        "ct": 20, "cid": 205360956, "userid": uin, "reqtype": 3, "sin": 0, "ein": 200,
    })
    raw_created = ((created.get("data") or {}).get("disslist") or [])
    raw_collected = ((collected.get("data") or {}).get("cdlist") or [])
    seen = set()
    items = []
    for raw, subscribed in [(pl, False) for pl in raw_created] + [(pl, True) for pl in raw_collected]:
        item = qq_playlist_item(raw, subscribed, status["nickname"])
        if item and item["id"] not in seen:
            seen.add(item["id"])
            items.append(item)
    return {**status, "playlists": items}


def fetch_qq_diss_tracks(dissid, cookie=""):
    u_api = "https://u.y.qq.com/cgi-bin/musicu.fcg"
    payload = {
        "comm": {"cv": 4747474, "ct": 24},
        "req_0": {
            "module": "music.srfDissInfo.aiDissInfo",
            "method": "uniform_get_Dissinfo",
            "param": {
                "disstid": int(dissid) if str(dissid).isdigit() else dissid,
                "enc_host_uin": "",
                "tag": 1,
                "userinfo": 1,
                "song_begin": 0,
                "song_num": 100,
                "orderlist": 1
            }
        }
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.48",
        "Referer": "https://i2.y.qq.com/n3/other/pages/details/playlist.html",
    }
    if cookie:
        headers["Cookie"] = cookie
    try:
        req = urllib.request.Request(u_api, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=12) as resp:
            content = resp.read()
            if resp.info().get("Content-Encoding") == "gzip":
                content = gzip.decompress(content)
            res = json.loads(content.decode("utf-8", "ignore"))
        req_0 = res.get("req_0", {})
        d = req_0.get("data", {})
        dirinfo = d.get("dirinfo") or {}
        raw_songs = d.get("songlist") or []
        tracks = []
        for s in raw_songs:
            t_name = str(s.get("title") or s.get("songname") or "").strip()
            singers = "/".join([str(sing.get("name") or "") for sing in (s.get("singer") or []) if sing.get("name")])
            album_obj = s.get("album") or {}
            album_name = str(album_obj.get("name") or s.get("albumname") or "").strip()
            mid = str(s.get("mid") or "")
            alb_mid = str(album_obj.get("mid") or "")
            cover = f"https://y.gtimg.cn/music/photo_new/T002R300x300M000{alb_mid}.jpg" if alb_mid else (dirinfo.get("picurl") or "")
            finfo = s.get("file") or {}
            qualities = []
            if finfo.get("size_hires") or finfo.get("size_flac"):
                qualities.append("flac")
            if finfo.get("size_320mp3"):
                qualities.append("320k")
            if finfo.get("size_128mp3"):
                qualities.append("128k")
            if not qualities:
                qualities = ["flac", "320k", "128k"]
            if t_name and singers:
                tracks.append({
                    "id": str(s.get("id") or mid),
                    "mid": mid,
                    "title": t_name,
                    "artist": singers,
                    "album": album_name,
                    "cover": cover,
                    "duration": int(s.get("interval") or 0),
                    "available_qualities": qualities,
                    "url": f"https://y.qq.com/n/ryqq/songDetail/{mid}" if mid else ""
                })
        return {
            "playlist_id": str(dissid),
            "playlist_name": str(dirinfo.get("title") or "今日私享"),
            "cover_url": dirinfo.get("picurl") or "",
            "track_count": len(tracks),
            "tracks": tracks
        }
    except Exception as e:
        return None


def fetch_qq_radar_songs(cookie=""):
    u_api = "https://u.y.qq.com/cgi-bin/musicu.fcg"
    tracks = []
    seen_ids = set()

    def fetch_page(page):
        payload = {
            "comm": {"ct": 24, "cv": 0},
            "req_0": {
                "module": "music.recommend.TrackRelationServer",
                "method": "GetRadarSong",
                "param": {"page": page, "num": 10}
            }
        }
        headers = {
            "User-Agent": USER_AGENT,
            "Referer": "https://y.qq.com/"
        }
        if cookie:
            headers["Cookie"] = cookie
        try:
            req = urllib.request.Request(u_api, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=8) as resp:
                content = resp.read()
                if resp.info().get("Content-Encoding") == "gzip":
                    content = gzip.decompress(content)
                res = json.loads(content.decode("utf-8", "ignore"))
                return res.get("req_0", {}).get("data", {}).get("VecSongs") or []
        except Exception:
            return []

    try:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=3) as executor:
            pages = list(executor.map(fetch_page, range(3)))
        all_vec = [item for page_items in pages for item in page_items]
        for item in all_vec:
            t = item.get("Track") or {}
            mid = str(t.get("mid") or "").strip()
            sid = str(t.get("id") or mid).strip()
            if not mid or mid in seen_ids:
                continue
            seen_ids.add(mid)
            t_name = str(t.get("title") or t.get("name") or "").strip()
            singers = "/".join([str(s.get("name") or "") for s in (t.get("singer") or []) if s.get("name")])
            alb = t.get("album") or {}
            alb_name = str(alb.get("title") or alb.get("name") or "").strip()
            alb_mid = str(alb.get("mid") or "").strip()
            cover = f"https://y.gtimg.cn/music/photo_new/T002R300x300M000{alb_mid}.jpg" if alb_mid else ""
            finfo = t.get("file") or {}
            qualities = []
            if finfo.get("size_hires") or finfo.get("size_flac"):
                qualities.append("flac")
            if finfo.get("size_320mp3"):
                qualities.append("320k")
            if finfo.get("size_128mp3"):
                qualities.append("128k")
            if not qualities:
                qualities = ["flac", "320k", "128k"]
            if t_name and singers:
                tracks.append({
                    "id": sid,
                    "mid": mid,
                    "title": t_name,
                    "artist": singers,
                    "album": alb_name,
                    "cover": cover,
                    "duration": int(t.get("interval") or 0),
                    "available_qualities": qualities,
                    "url": f"https://y.qq.com/n/ryqq/songDetail/{mid}" if mid else ""
                })
        return tracks
    except Exception:
        return []


def qq_daily_recommend(cookie):
    status = qq_status(cookie)
    if not status.get("connected"):
        return {**status, "playlist_id": "", "playlist_name": "每日推荐", "cover_url": "", "track_count": 0, "tracks": []}

    found_dissid = None
    playlist_title = "今日私享"

    # 1. 优先尝试从 musicmac/v6/index.html 查找明确带有日推关键词的专属歌单
    try:
        url = "https://c.y.qq.com/node/musicmac/v6/index.html"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) QQMusic/8.5.0",
            "Referer": "https://y.qq.com/",
            "Cookie": cookie,
            "Accept-Encoding": "gzip, deflate"
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            content = resp.read()
            if resp.info().get("Content-Encoding") == "gzip":
                content = gzip.decompress(content)
            html = content.decode("utf-8", "ignore")

            sections = re.findall(r'<section[^>]*class="[^"]*mod_for_u[^"]*"[^>]*>(.*?)</section>', html, re.S)
            for sec in sections:
                m_tit = re.search(r'<h[23][^>]*class="[^"]*mod_tit[^"]*"[^>]*>(.*?)</h[23]>', sec)
                tit = m_tit.group(1).strip() if m_tit else ""
                if any(kw in tit for kw in ["今日私享", "每日30首", "每日推荐", "今日推荐", "为你推荐", "私享"]):
                    rids = re.findall(r'data-rid="(\d+)"', sec)
                    if rids:
                        found_dissid = rids[0]
                        playlist_title = tit
                        break
    except Exception:
        pass

    if found_dissid:
        detail = fetch_qq_diss_tracks(found_dissid, cookie)
        if detail and detail.get("tracks"):
            return {
                "connected": True,
                "provider": "qq",
                "user_id": status.get("user_id", ""),
                "nickname": status.get("nickname", ""),
                "playlist_id": detail["playlist_id"],
                "playlist_name": detail["playlist_name"] or playlist_title,
                "cover_url": detail["cover_url"],
                "track_count": detail["track_count"],
                "import_url": f"daily://qq/{status.get('user_id', '')}",
                "tracks": detail["tracks"]
            }

    # 2. 调用 QQ 音乐官方个性化雷达推荐 API (TrackRelationServer.GetRadarSong)
    radar_tracks = fetch_qq_radar_songs(cookie)
    if radar_tracks:
        cover_url = radar_tracks[0].get("cover") or ""
        return {
            "connected": True,
            "provider": "qq",
            "user_id": status.get("user_id", ""),
            "nickname": status.get("nickname", ""),
            "playlist_id": "qq_daily_radar",
            "playlist_name": "今日私享",
            "cover_url": cover_url,
            "track_count": len(radar_tracks),
            "import_url": f"daily://qq/{status.get('user_id', '')}",
            "tracks": radar_tracks
        }

    return {
        **status,
        "error": "未能获取到 QQ 音乐今日推荐歌曲",
        "playlist_id": "",
        "playlist_name": "今日私享",
        "cover_url": "",
        "track_count": 0,
        "tracks": []
    }


def main():
    if len(sys.argv) < 3:
        raise ValueError("usage: music_account.py <provider> <status|playlists|daily_recommend>")
    provider, action = sys.argv[1], sys.argv[2]
    payload = json.loads(sys.stdin.read() or "{}")
    cookie = str(payload.get("cookie") or "")
    if provider == "netease":
        if action == "status":
            result = netease_status(cookie)
        elif action == "playlists":
            result = netease_playlists(cookie)
        elif action == "daily_recommend":
            result = netease_daily_recommend(cookie)
        else:
            result = {"connected": False, "error": f"未知动作: {action}"}
    elif provider == "qq":
        if action == "status":
            result = qq_status(cookie)
        elif action == "playlists":
            result = qq_playlists(cookie)
        elif action == "daily_recommend":
            result = qq_daily_recommend(cookie)
        else:
            result = {"connected": False, "error": f"未知动作: {action}"}
    else:
        result = {"connected": False, "error": "该平台暂未开放账号连接"}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"connected": False, "error": str(exc)}, ensure_ascii=False))
        sys.exit(1)
