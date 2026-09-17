
export type MusicProviderId = 'netease' | 'qq' | 'bodian';

export interface MusicAccount {
  id: MusicProviderId;
  name: string;
  available: boolean;
  login_method: 'cookie' | 'unavailable';
  hint: string;
  connected: boolean;
  nickname: string;
  avatar: string;
  user_id: string;
  connected_at: string | null;
}

export interface RemotePlaylist {
  id: string;
  name: string;
  cover: string;
  track_count: number;
  creator: string;
  subscribed: boolean;
  import_url: string;
}

export interface AuthorizedDirectory {
  path: string;
  name: string;
  is_fnos_authorized: boolean;
  exists: boolean;
  writable: boolean;
  file_count: number;
  guid?: string;
}

export interface SettingsData {
  download_source: 'kw' | 'kg' | 'tx' | 'wy' | 'auto' | 'custom';
  download_dir?: string;
  is_configured?: boolean;
  effective_music_dir?: string;
  available_sources: Array<{
    id: 'kw' | 'kg' | 'tx' | 'wy' | 'auto' | 'custom';
    name: string;
    desc: string;
    default: boolean;
  }>;
  custom_source?: {
    name: string;
    api_url: string;
    api_key: string;
    script_url: string;
  };
}

export interface CurrentTrack {
  title: string;
  artist: string;
  album?: string;
  step?: string;
  cover?: string;
}

export interface TaskTrack {
  title: string;
  artist: string;
  album?: string;
  status: 'pending' | 'reused' | 'downloading' | 'downloaded' | 'failed';
  path?: string;
}

export interface TaskState {
  status: 'idle' | 'parsing' | 'downloading' | 'finalizing' | 'success' | 'failed' | 'stopped';
  playlist_name: string;
  platform: string;
  target: 'public' | 'user';
  user: string;
  total: number;
  processed_count: number;
  reused_count: number;
  downloaded_count: number;
  failed_count: number;
  current_track: CurrentTrack | null;
  start_time: string | null;
  end_time: string | null;
  tracks: TaskTrack[];
  updated_at: string;
}

export interface SearchSong {
  title: string;
  artist: string;
  album: string;
  cover: string;
  has_sq: boolean;
  hash: string;
  exists?: boolean;
  local_path?: string;
  local_id?: number | null;
}

export interface PlaylistSummary {
  name: string;
  cover_guid?: string;
  created_at?: string;
  updated_at?: string;
  m3u_exists?: boolean;
  users: string | Array<{ id: number; name: string }>;
  user_ids?: number[];
  track_count: number;
}

export interface PlaylistTrack {
  id: number;
  title: string;
  artist: string;
  album: string;
  duration?: number;
  duration_ms?: number;
  size?: number;
  codec?: string;
  cover_guid?: string;
  path: string;
}

export interface LibraryTrack {
  id: number;
  title: string;
  artist: string;
  album: string;
  path: string;
  file_type?: string;
  bitrate?: number;
  file_size?: number;
  duration_ms?: number;
  size?: number;
  codec?: string;
  cover_guid?: string;
  created_at?: string;
}

export interface DuplicateGroup {
  key: string;
  title: string;
  artist: string;
  count: number;
  tracks: LibraryTrack[];
}

export interface DuplicateResult {
  groups_count: number;
  total_tracks: number;
  groups: DuplicateGroup[];
}

export interface HistoryItem {
  id: number;
  type?: 'song' | 'playlist';
  playlist_name: string;
  title?: string;
  artist?: string;
  album?: string;
  quality?: string;
  cover?: string;
  platform: string;
  target: string;
  user: string;
  total: number;
  reused_count: number;
  downloaded_count: number;
  failed_count: number;
  start_time: string;
  end_time: string;
  duration: number;
  status?: string;
  operator?: string;
}
