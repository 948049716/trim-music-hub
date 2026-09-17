#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Third-party music account helper.

Credentials never leave the NAS: Node passes the decrypted cookie through stdin and
this helper only returns account metadata and playlist summaries as JSON.
"""
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
        return json.loads(resp.read().decode("utf-8", "ignore"))


def media_url(raw):
    value = str(raw or '')
    if value.startswith('//'):
        return 'https:' + value
    if value.startswith('http://'):
        return 'https://' + value[7:]
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
    if not cookie_map(cookie).get("MUSIC_U"):
        return {"connected": False, "error": "网易云 Cookie 缺少 MUSIC_U"}
    data = request_json("https://music.163.com/api/nuser/account/get", cookie, "https://music.163.com/")
    profile = data.get("profile") or {}
    account = data.get("account") or {}
    user_id = profile.get("userId") or account.get("id")
    if not user_id:
        return {"connected": False, "error": "网易云登录状态已失效，请重新连接"}
    return {
        "connected": True,
        "user_id": str(user_id),
        "nickname": profile.get("nickname") or "网易云用户",
        "avatar": media_url(profile.get("avatarUrl")),
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


def main():
    if len(sys.argv) < 3:
        raise ValueError("usage: music_account.py <provider> <status|playlists>")
    provider, action = sys.argv[1], sys.argv[2]
    payload = json.loads(sys.stdin.read() or "{}")
    cookie = str(payload.get("cookie") or "")
    if provider == "netease":
        result = netease_status(cookie) if action == "status" else netease_playlists(cookie)
    elif provider == "qq":
        result = qq_status(cookie) if action == "status" else qq_playlists(cookie)
    else:
        result = {"connected": False, "error": "该平台暂未开放账号连接"}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"connected": False, "error": str(exc)}, ensure_ascii=False))
        sys.exit(1)

