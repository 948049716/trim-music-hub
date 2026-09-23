-- table: app_state
CREATE TABLE "app_state"
(
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    k          TEXT     NOT NULL UNIQUE, -- 键，如：initialized
    v          TEXT     NOT NULL,        -- 值，如：true
    payload    TEXT,                     -- 存储额外信息的字段，如：{"user_id": 1, "initialized_at": "xxx"}
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- table: sqlite_sequence
CREATE TABLE sqlite_sequence(name,seq);

-- table: user
CREATE TABLE "user"
(
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    guid            TEXT     NOT NULL UNIQUE, -- 不可被遍历的全局唯一id
    name            TEXT     NOT NULL,
    name_latin_full TEXT     NOT NULL DEFAULT '',
    password        TEXT,                     -- 密码是可以没有的
    role            TEXT     NOT NULL,        -- 角色：管理员admin、普通用户member
    created_by      TEXT     NOT NULL,        -- 创建来源：oauth、手动创建manual
    status          TEXT     NOT NULL,        -- 状态：正常使用active、已被删除deleted
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
, shared_library_access_mode TEXT NOT NULL DEFAULT 'none', last_accessed_at DATETIME);

-- table: user_oauth
CREATE TABLE "user_oauth"
(
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER  NOT NULL,           -- 关联到 user 表的 id
    user_deleted    INTEGER  NOT NULL DEFAULT 0, -- 冗余字段：user是否已删除
    oauth_provider  TEXT     NOT NULL,           -- 授权登录的提供方：nas授权trim-nas
    oauth_user_id   TEXT,                        -- 授权平台的用户ID
    oauth_user_name TEXT,                        -- 授权平台上的用户名
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_user_id_oauth_provider UNIQUE (user_id, oauth_provider)
);

-- index: idx_user_oauth_provider_user_deleted
CREATE INDEX idx_user_oauth_provider_user_deleted ON user_oauth (oauth_provider, oauth_user_id, user_deleted);

-- table: user_token
CREATE TABLE "user_token"
(
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER  NOT NULL,        -- 关联到 user 表的 id
    token         TEXT     NOT NULL UNIQUE, -- 生成的token
    device_id     TEXT     NOT NULL,        -- 端侧设备ID，用于独立登录态管理
    expired_at    DATETIME NOT NULL,
    is_auth_login INTEGER  NOT NULL DEFAULT 0,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_user_id_device_id UNIQUE (user_id, device_id)
);

-- index: idx_user_token_user_expired
CREATE INDEX idx_user_token_user_expired ON user_token (user_id, expired_at);

-- table: shared_library
CREATE TABLE "shared_library"
(
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    guid                    TEXT     NOT NULL UNIQUE,                    -- 不可被遍历的全局唯一id
    path                    TEXT     NOT NULL UNIQUE,                    -- 存储路径
    metadata_preference     TEXT     NOT NULL,                           -- 元数据偏好
    auto_download_lyric     INTEGER  NOT NULL DEFAULT 1,                 -- 是否自动下载歌词
    content_last_changed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, -- 内容最后更新时间
    created_at              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- table: shared_library_member
CREATE TABLE "shared_library_member"
(
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    shared_library_id INTEGER  NOT NULL, -- 关联到 shared_library 表的 id
    user_id           INTEGER  NOT NULL, -- 关联到 user 表的 id
    created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_shared_library_id_user_id UNIQUE (shared_library_id, user_id)
);

-- index: idx_shared_library_member_user_library
CREATE INDEX idx_shared_library_member_user_library ON shared_library_member (user_id, shared_library_id);

-- table: audio_file
CREATE TABLE "audio_file"
(
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    shared_library_id INTEGER  NOT NULL,           -- 关联到 shared_library 表的 id
    path              TEXT     NOT NULL UNIQUE,    -- 文件路径
    name              TEXT     NOT NULL,           -- 文件名
    suffix            TEXT     NOT NULL,           -- 文件后缀
    size              INTEGER  NOT NULL,           -- 文件大小，单位byte
    hash              TEXT,                        -- 文件哈希值
    -- tech params
    duration_ms       INTEGER,                     -- 音频时长, 单位毫秒
    bitrate           INTEGER,                     -- 比特率
    sample_rate       INTEGER,                     -- 采样率
    bit_depth         INTEGER,                     -- 位深度
    channel           INTEGER,                     -- 声道数
    container         TEXT,                        -- 封装容器
    codec             TEXT,                        -- 编码方式
    stream_index      INTEGER  NOT NULL DEFAULT 0, -- 音频流在容器中的第一个位置
    fingerprint       TEXT,                        -- 音频指纹
    -- end of tech params
    tag_payload       TEXT,                        -- 移除大字段后的raw tag
    cue_path          TEXT,                        -- cue文件路径
    created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
, is_physical_file_deleted INTEGER NOT NULL DEFAULT 0);

-- index: idx_audio_file_shared_library_id
CREATE INDEX idx_audio_file_shared_library_id ON audio_file (shared_library_id);

-- table: artist
CREATE TABLE "artist"
(
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    guid                    TEXT     NOT NULL UNIQUE, -- 不可被遍历的全局唯一id
    name                    TEXT     NOT NULL,        -- 艺术家名称
    name_latin_full         TEXT     NOT NULL DEFAULT '',
    cover_guid              TEXT,                     -- 封面在本地文件系统存储的guid
    metadata_mode           INTEGER  NOT NULL,        -- 处理模式：1=local, 2=cloud
    metadata_cloud_provider INTEGER,                  -- 数据提供方：1=official
    metadata_cloud_ref_id   TEXT,                     -- cloud provider 下的实体标识
    created_at              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- index: idx_artist_name_metadata_mode
CREATE INDEX idx_artist_name_metadata_mode ON artist (name, metadata_mode);

-- index: idx_artist_cloud_ref
CREATE INDEX idx_artist_cloud_ref ON artist (metadata_cloud_provider, metadata_cloud_ref_id);

-- table: album
CREATE TABLE "album"
(
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    guid                    TEXT     NOT NULL UNIQUE, -- 不可被遍历的全局唯一id
    name                    TEXT     NOT NULL,        -- 专辑名称
    name_latin_full         TEXT     NOT NULL DEFAULT '',
    cover_guid              TEXT,                     -- 封面在本地文件系统存储的guid
    release_date            TEXT,                     -- 发布日期，如：2026-02-02
--     original_release_date   TEXT,                     -- 原始发行日期，如：2026、2026-02-02
    total_track             INTEGER,                  -- 曲目数量
    barcode                 TEXT,                     -- 专辑条码：UPC/EAN
    metadata_mode           INTEGER  NOT NULL,        -- 处理模式：1=local, 2=cloud
    metadata_cloud_provider INTEGER,                  -- 数据提供方：1=official
    metadata_cloud_ref_id   TEXT,                     -- cloud provider 下的实体标识
    created_at              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- index: idx_album_name_mode_release_date
CREATE INDEX idx_album_name_mode_release_date ON album (name, metadata_mode, release_date);

-- index: idx_album_cloud_ref
CREATE INDEX idx_album_cloud_ref ON album (metadata_cloud_provider, metadata_cloud_ref_id);

-- table: track
CREATE TABLE "track"
(
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    guid                    TEXT     NOT NULL UNIQUE,    -- 不可被遍历的全局唯一id
    audio_file_id           INTEGER  NOT NULL,           -- 关联到 audio_file 表的 id
    shared_library_id       INTEGER  NOT NULL,           -- 关联到 shared_library 表的 id
    title                   TEXT     NOT NULL,           -- 曲目标题
    title_latin_full        TEXT     NOT NULL DEFAULT '',
    album_id                INTEGER,                     -- 关联到 album 表的 id
    cover_guid              TEXT,                        -- 封面在本地文件系统存储的guid
    year                    INTEGER,                     -- 年份
    disc_no                 INTEGER,                     -- 光盘编号
    track_no                INTEGER,                     -- 曲目编号
    isrc                    TEXT,                        -- 国际标准录音编码
    duration_ms             INTEGER  NOT NULL,           -- 曲目时长，单位毫秒
    -- cue support
    is_cue                  INTEGER  NOT NULL DEFAULT 0, -- 是否来自CUE整轨音频（0/1）
    start_offset            TEXT,                        -- 开始偏移，时间格式mm:ss:ff，便于观察
    end_offset              TEXT,                        -- 结束偏移，时间格式mm:ss
    start_offset_ms         INTEGER,                     -- 开始偏移，单位毫秒
    end_offset_ms           INTEGER,                     -- 结束偏移，单位毫秒
    -- end of cue support
    metadata_mode           INTEGER  NOT NULL,           -- 处理模式：1=local, 2=cloud
    metadata_cloud_provider INTEGER,                     -- 数据提供方：1=official
    metadata_cloud_ref_id   TEXT,                        -- cloud provider 下的实体标识
    cloud_scrape_status     INTEGER  NOT NULL DEFAULT 0, -- 云端刮削状态：0=none, 1=pending, 2=success, 3=failed, 4=not_found
    created_at              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
, is_audio_file_deleted INTEGER NOT NULL DEFAULT 0, is_admin_deleted INTEGER NOT NULL DEFAULT 0);

-- index: idx_track_shared_library_id
CREATE INDEX idx_track_shared_library_id ON track (shared_library_id);

-- index: idx_track_album_id
CREATE INDEX idx_track_album_id ON track (album_id);

-- index: idx_track_audio_file_id
CREATE INDEX idx_track_audio_file_id ON track (audio_file_id);

-- table: album_artist
CREATE TABLE "album_artist"
(
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    album_id     INTEGER  NOT NULL,           -- 关联到 album 表的 id
    artist_id    INTEGER  NOT NULL,           -- 关联到 artist 表的 id
    artist_order INTEGER  NOT NULL DEFAULT 0, -- 艺术家顺序
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_album_id_artist_id UNIQUE (album_id, artist_id)
);

-- index: idx_album_artist_artist_id_album_id
CREATE INDEX idx_album_artist_artist_id_album_id ON album_artist (artist_id, album_id);

-- index: idx_album_artist_album_id_artist_id
CREATE INDEX idx_album_artist_album_id_artist_id ON album_artist (album_id, artist_id);

-- table: track_artist
CREATE TABLE "track_artist"
(
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id     INTEGER  NOT NULL,           -- 关联到 track 表的 id
    artist_id    INTEGER  NOT NULL,           -- 关联到 artist 表的 id
    artist_order INTEGER  NOT NULL DEFAULT 0, -- 艺术家顺序
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_track_id_artist_id UNIQUE (track_id, artist_id)
);

-- index: idx_track_artist_artist_id_track_id
CREATE INDEX idx_track_artist_artist_id_track_id ON track_artist (artist_id, track_id);

-- index: idx_track_artist_track_id_artist_id
CREATE INDEX idx_track_artist_track_id_artist_id ON track_artist (track_id, artist_id);

-- table: genre
CREATE TABLE "genre"
(
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    guid                    TEXT     NOT NULL UNIQUE, -- 不可被遍历的全局唯一id
    name                    TEXT     NOT NULL,        -- 风格名称
    name_latin_full         TEXT     NOT NULL DEFAULT '',
    cover_guid              TEXT,                     -- 封面在本地文件系统存储的guid
    metadata_mode           INTEGER  NOT NULL,        -- 处理模式：1=local, 2=cloud
    metadata_cloud_provider INTEGER,                  -- 数据提供方：1=official
    metadata_cloud_ref_id   TEXT,                     -- cloud provider 下的实体标识
    created_at              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- index: idx_genre_name
CREATE INDEX idx_genre_name ON genre (name);

-- table: track_genre
CREATE TABLE "track_genre"
(
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id   INTEGER  NOT NULL, -- 关联到 track 表的 id
    genre_id   INTEGER  NOT NULL, -- 关联到 genre 表的 id
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_track_id_genre_id UNIQUE (track_id, genre_id)
);

-- index: idx_track_genre_genre_id_track_id
CREATE INDEX idx_track_genre_genre_id_track_id ON track_genre (genre_id, track_id);

-- index: idx_track_genre_track_id_genre_id
CREATE INDEX idx_track_genre_track_id_genre_id ON track_genre (track_id, genre_id);

-- table: lyric
CREATE TABLE "lyric"
(
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    guid        TEXT     NOT NULL UNIQUE, -- 不可被遍历的全局唯一id
    track_id    INTEGER  NOT NULL,        -- 关联到 track 表的 id
    source      INTEGER  NOT NULL,        -- 歌词来源：1=文件内嵌embedded；2=同目录伴随文件：sidecar；3=刮削来的：scraped；4=用户手动搜索并关联：user_linked
    stored_guid TEXT,                     -- 歌词提取后，在本地的存储guid
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- index: idx_lyric_track_id
CREATE INDEX idx_lyric_track_id ON lyric (track_id);

-- table: favorite_track
CREATE TABLE "favorite_track"
(
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER  NOT NULL, -- 关联到 user 表的 id
    track_id   INTEGER  NOT NULL, -- 关联到 track 表的 id
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_favorite_track_user_track UNIQUE (user_id, track_id)
);

-- index: idx_favorite_track_user_created
CREATE INDEX idx_favorite_track_user_created ON favorite_track (user_id, created_at DESC);

-- index: idx_favorite_track_track_id
CREATE INDEX idx_favorite_track_track_id ON favorite_track (track_id);

-- table: play_history
CREATE TABLE "play_history"
(
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER  NOT NULL,
    track_id   INTEGER  NOT NULL,
    play_count INTEGER  NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_play_history_user_track UNIQUE (user_id, track_id)
);

-- index: idx_play_history_track_id
CREATE INDEX idx_play_history_track_id ON play_history (track_id);

-- index: idx_play_history_user_updated_track
CREATE INDEX idx_play_history_user_updated_track ON play_history (user_id, updated_at DESC, track_id);

-- table: user_track_lyric_preference
CREATE TABLE "user_track_lyric_preference"
(
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER  NOT NULL, -- 关联到 user 表的 id
    track_id   INTEGER  NOT NULL, -- 关联到 track 表的 id
    lyric_id   INTEGER  NOT NULL, -- 关联到 lyric 表的 id，用户最近一次使用的歌词
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_user_track_lyric_preference_user_id_track_id UNIQUE (user_id, track_id)
);

-- index: idx_user_track_lyric_preference_track_id
CREATE INDEX idx_user_track_lyric_preference_track_id ON user_track_lyric_preference (track_id);

-- index: idx_user_track_lyric_preference_lyric_id
CREATE INDEX idx_user_track_lyric_preference_lyric_id ON user_track_lyric_preference (lyric_id);

-- table: app_hook
CREATE TABLE `app_hook` (`id` integer PRIMARY KEY AUTOINCREMENT,`key` text,`value` text,`created_at` datetime,`updated_at` datetime);

-- table: playlist
CREATE TABLE "playlist"
(
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    guid       TEXT     NOT NULL UNIQUE, -- 不可被遍历的全局唯一id
    name       TEXT     NOT NULL,
    cover_guid TEXT,
    user_id    INTEGER  NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- index: idx_playlist_user_id_created_at
CREATE INDEX idx_playlist_user_id_created_at ON playlist (user_id, created_at DESC);

-- table: playlist_track
CREATE TABLE "playlist_track"
(
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER  NOT NULL,                           -- 冗余字段
    playlist_id INTEGER  NOT NULL,
    track_id    INTEGER  NOT NULL,
    added_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, -- 加入/再次加入的时间，排序依据
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_playlist_track_playlist_id_track_id UNIQUE (playlist_id, track_id)
);

-- index: idx_playlist_track_playlist_added
CREATE INDEX idx_playlist_track_playlist_added ON playlist_track (playlist_id, added_at DESC);

-- index: idx_playlist_track_track_id
CREATE INDEX idx_playlist_track_track_id ON playlist_track (track_id);

-- table: user_track_lyric_offset
CREATE TABLE "user_track_lyric_offset"
(
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER  NOT NULL,
    track_id   INTEGER  NOT NULL,
    lyric_id   INTEGER  NOT NULL,
    offset_ms  INTEGER  NOT NULL DEFAULT 0, -- 毫秒；正=提前，负=延后
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_user_track_lyric_offset UNIQUE (user_id, track_id, lyric_id)
);

-- index: idx_user_track_lyric_offset_user_id_track_id
CREATE INDEX idx_user_track_lyric_offset_user_id_track_id ON user_track_lyric_offset (user_id, track_id);

-- index: idx_user_track_lyric_offset_track_id
CREATE INDEX idx_user_track_lyric_offset_track_id ON user_track_lyric_offset (track_id);

-- index: idx_user_track_lyric_offset_lyric_id
CREATE INDEX idx_user_track_lyric_offset_lyric_id ON user_track_lyric_offset (lyric_id);

-- table: user_sorting_preference
CREATE TABLE "user_sorting_preference"
(
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER  NOT NULL,
    sort_id    TEXT     NOT NULL,
    sorting    TEXT     NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_user_sorting_preference UNIQUE (user_id, sort_id)
);

-- index: idx_user_sorting_preference_user_id
CREATE INDEX idx_user_sorting_preference_user_id ON user_sorting_preference (user_id);
