import type { TaskState, QueueTask, SearchSong, PlaylistSummary, PlaylistPreview, PlaylistTrack, LibraryTrack, HistoryItem, SettingsData, AuthorizedDirectory, DuplicateResult, MusicAccount, MusicProviderId, RemotePlaylist, CurrentUser } from '../types';

async function fetchWithAuth(url: string, init?: RequestInit): Promise<Response> {
  const res = await fetch(url, {
    credentials: 'include',
    ...init,
  });
  if (res.status === 401 && !url.includes('/api/auth/')) {
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('auth:unauthorized'));
    }
  }
  return res;
}

export const api = {
  async getAuthMe(): Promise<{ ok: boolean; loggedIn: boolean; user?: CurrentUser }> {
    const res = await fetchWithAuth('/api/auth/me');
    return res.json();
  },

  async login(username: string, password: string): Promise<{ ok: boolean; user?: CurrentUser; error?: string }> {
    const res = await fetchWithAuth('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    return res.json();
  },

  async logout(): Promise<{ ok: boolean; message?: string }> {
    const res = await fetchWithAuth('/api/auth/logout', { method: 'POST' });
    return res.json();
  },

  async getMusicAccounts(): Promise<{ ok: boolean; data: MusicAccount[] }> {
    const res = await fetchWithAuth('/api/music-accounts');
    return res.json();
  },

  async createNeteaseQr(): Promise<{ ok: boolean; unikey?: string; qr_url?: string; qr_img?: string; error?: string }> {
    const res = await fetchWithAuth('/api/music-accounts/netease/qr/create', { method: 'POST' });
    return res.json();
  },

  async checkNeteaseQr(unikey: string): Promise<{ ok: boolean; status?: 'waiting' | 'scanned' | 'expired' | 'success' | 'unknown'; code?: number; message?: string; account?: MusicAccount; error?: string }> {
    const res = await fetchWithAuth('/api/music-accounts/netease/qr/check', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ unikey })
    });
    return res.json();
  },

  async connectMusicAccount(target: string, cookie: string): Promise<{ ok: boolean; data?: MusicAccount; error?: string }> {
    const res = await fetchWithAuth(`/api/music-accounts/${target}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cookie })
    });
    return res.json();
  },

  async disconnectMusicAccount(target: string): Promise<{ ok: boolean; error?: string }> {
    const res = await fetchWithAuth(`/api/music-accounts/${target}`, { method: 'DELETE' });
    return res.json();
  },

  async getMusicAccountPlaylists(target: string): Promise<{ ok: boolean; data?: RemotePlaylist[]; error?: string }> {
    const res = await fetchWithAuth(`/api/music-accounts/${target}/playlists`);
    return res.json();
  },

  async importMusicAccountPlaylist(target: string, payload: { urls: string[]; target: string; user: string }): Promise<{ ok: boolean; message?: string; error?: string }> {
    const res = await fetchWithAuth(`/api/music-accounts/${target}/import`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    return res.json();
  },

  async getStatus(): Promise<{ ok: boolean; data: TaskState; isRunning: boolean }> {
    const res = await fetchWithAuth('/api/status');
    return res.json();
  },

  async getSettings(): Promise<{ ok: boolean; data: SettingsData }> {
    const res = await fetchWithAuth('/api/settings');
    return res.json();
  },

  async updateSettings(
    download_source?: string,
    custom_source?: any,
    download_dir?: string,
    is_configured?: boolean
  ): Promise<{ ok: boolean; data: SettingsData }> {
    const res = await fetchWithAuth('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ download_source, custom_source, download_dir, is_configured })
    });
    return res.json();
  },

  async getAuthorizedDirectories(): Promise<{ ok: boolean; data: AuthorizedDirectory[] }> {
    const res = await fetchWithAuth('/api/settings/directories');
    return res.json();
  },

  async verifyDirectory(path: string): Promise<{
    ok: boolean;
    data: {
      ok: boolean;
      path: string;
      exists: boolean;
      writable: boolean;
      is_fnos_authorized: boolean;
      error: string | null;
    };
  }> {
    const res = await fetchWithAuth('/api/settings/verify-directory', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path })
    });
    return res.json();
  },

  async getUsers(): Promise<{ ok: boolean; data: Array<{ id: number; name: string; role?: string }> }> {
    const res = await fetchWithAuth('/api/users');
    return res.json();
  },

  async parsePlaylist(url: string, accountId?: string): Promise<{ ok: boolean; data?: PlaylistPreview; error?: string }> {
    const res = await fetchWithAuth('/api/tasks/parse-playlist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, account_id: accountId })
    });
    return res.json();
  },

  async startTask(payload: {
    url: string;
    target: string;
    user: string;
    playlist_name?: string;
    quality?: 'flac' | '320k' | '128k';
    tracks?: PlaylistPreview['tracks'];
    source?: string;
    cover_url?: string;
    account_id?: string;
  }): Promise<{ ok: boolean; message: string; error?: string }> {
    const res = await fetchWithAuth('/api/tasks/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    return res.json();
  },

  async stopTask(): Promise<{ ok: boolean; message: string }> {
    const res = await fetchWithAuth('/api/tasks/stop', { method: 'POST' });
    return res.json();
  },

  async getTaskQueue(): Promise<{ ok: boolean; data: QueueTask[]; isAdmin?: boolean; error?: string }> {
    const res = await fetchWithAuth('/api/tasks/queue');
    return res.json();
  },

  async reorderTasks(taskIds: string[]): Promise<{ ok: boolean; message?: string; error?: string }> {
    const res = await fetchWithAuth('/api/tasks/reorder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task_ids: taskIds })
    });
    return res.json();
  },

  async cancelTask(taskId: string): Promise<{ ok: boolean; message?: string; error?: string }> {
    const res = await fetchWithAuth('/api/tasks/cancel', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task_id: taskId })
    });
    return res.json();
  },

  async clearCompletedTasks(): Promise<{ ok: boolean; message?: string; error?: string }> {
    const res = await fetchWithAuth('/api/tasks/clear-completed', { method: 'POST' });
    return res.json();
  },

  async searchOnline(keyword: string, page = 1, pageSize = 20): Promise<{ ok: boolean; data: SearchSong[]; page: number; page_size: number; total: number; has_more: boolean; error?: string }> {
    const res = await fetchWithAuth(`/api/search/online?q=${encodeURIComponent(keyword)}&page=${page}&page_size=${pageSize}`);
    return res.json();
  },

  async downloadSingle(payload: {
    artist: string;
    song: string;
    album?: string;
    cover?: string;
    quality: 'flac' | '320k' | '128k';
    source?: 'kw' | 'kg' | 'tx' | 'wy' | 'auto' | 'custom';
  }): Promise<{ ok: boolean; message?: string; error?: string; path?: string }> {
    const res = await fetchWithAuth('/api/download/single', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    return res.json();
  },

  async getPlaylists(): Promise<{ ok: boolean; data: PlaylistSummary[]; error?: string }> {
    const res = await fetchWithAuth('/api/playlists');
    return res.json();
  },

  async getPlaylistTracks(name: string): Promise<{ ok: boolean; data: PlaylistTrack[]; error?: string }> {
    const res = await fetchWithAuth(`/api/playlists/tracks?name=${encodeURIComponent(name)}`);
    return res.json();
  },

  async renamePlaylist(oldName: string, newName: string): Promise<{ ok: boolean; error?: string }> {
    const res = await fetchWithAuth('/api/playlists/rename', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ old_name: oldName, new_name: newName })
    });
    return res.json();
  },

  async updatePlaylistUsers(name: string, userIds: number[]): Promise<{ ok: boolean; message?: string; error?: string }> {
    const res = await fetchWithAuth('/api/playlists/update-users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, user_ids: userIds })
    });
    return res.json();
  },

  async removePlaylistTracks(name: string, trackIds: number[], removePhysical = false): Promise<{ ok: boolean; message?: string; error?: string }> {
    const res = await fetchWithAuth('/api/playlists/remove-tracks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, track_ids: trackIds, remove_physical: removePhysical })
    });
    return res.json();
  },

  async deletePlaylist(name: string, deleteTracks: boolean): Promise<{ ok: boolean; error?: string; deleted_files?: number }> {
    const res = await fetchWithAuth('/api/playlists/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, delete_tracks: deleteTracks })
    });
    return res.json();
  },

  async searchLibraryTracks(query: string, page = 1, limit = 50): Promise<{ ok: boolean; data: { total: number; page: number; limit: number; list: LibraryTrack[] } }> {
    const res = await fetchWithAuth(`/api/tracks/search?q=${encodeURIComponent(query)}&page=${page}&limit=${limit}`);
    return res.json();
  },

  async getDuplicateTracks(query = ''): Promise<{ ok: boolean; data: DuplicateResult }> {
    const res = await fetchWithAuth(`/api/tracks/duplicates?q=${encodeURIComponent(query)}`);
    return res.json();
  },

  async deleteTrack(trackId: number, removePhysical = true): Promise<{ ok: boolean; error?: string }> {
    const res = await fetchWithAuth('/api/tracks/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ track_id: trackId, remove_physical: removePhysical })
    });
    return res.json();
  },

  async batchDeleteTracks(trackIds: number[], removePhysical = true): Promise<{ ok: boolean; message?: string; error?: string; deleted_count?: number; failed_count?: number }> {
    const res = await fetchWithAuth('/api/tracks/batch-delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ track_ids: trackIds, remove_physical: removePhysical })
    });
    return res.json();
  },

  async getHistory(): Promise<{ ok: boolean; data: HistoryItem[] }> {
    const res = await fetchWithAuth('/api/history');
    return res.json();
  },

  async deleteHistory(id: number): Promise<{ ok: boolean }> {
    const res = await fetchWithAuth('/api/history/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id })
    });
    return res.json();
  },

  async clearHistory(): Promise<{ ok: boolean }> {
    const res = await fetchWithAuth('/api/history/clear', { method: 'POST' });
    return res.json();
  }
};
