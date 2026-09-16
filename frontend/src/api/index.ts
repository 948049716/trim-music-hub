import type { TaskState, SearchSong, PlaylistSummary, PlaylistTrack, LibraryTrack, HistoryItem, SettingsData, AuthorizedDirectory, DuplicateResult } from '../types';

export const api = {
  async getStatus(): Promise<{ ok: boolean; data: TaskState; isRunning: boolean }> {
    const res = await fetch('/api/status');
    return res.json();
  },

  async getSettings(): Promise<{ ok: boolean; data: SettingsData }> {
    const res = await fetch('/api/settings');
    return res.json();
  },

  async updateSettings(
    download_source?: string,
    custom_source?: any,
    download_dir?: string,
    is_configured?: boolean
  ): Promise<{ ok: boolean; data: SettingsData }> {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ download_source, custom_source, download_dir, is_configured })
    });
    return res.json();
  },

  async getAuthorizedDirectories(): Promise<{ ok: boolean; data: AuthorizedDirectory[] }> {
    const res = await fetch('/api/settings/directories');
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
    const res = await fetch('/api/settings/verify-directory', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path })
    });
    return res.json();
  },

  async getUsers(): Promise<{ ok: boolean; data: Array<{ id: number; name: string; role?: string }> }> {
    const res = await fetch('/api/users');
    return res.json();
  },

  async startTask(payload: { url: string; target: string; user: string }): Promise<{ ok: boolean; message: string }> {
    const res = await fetch('/api/tasks/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    return res.json();
  },

  async stopTask(): Promise<{ ok: boolean; message: string }> {
    const res = await fetch('/api/tasks/stop', { method: 'POST' });
    return res.json();
  },

  async searchOnline(keyword: string): Promise<{ ok: boolean; data: SearchSong[] }> {
    const res = await fetch(`/api/search/online?q=${encodeURIComponent(keyword)}`);
    return res.json();
  },

  async downloadSingle(payload: {
    artist: string;
    song: string;
    album?: string;
    cover?: string;
    quality: 'flac' | '320k' | '128k';
  }): Promise<{ ok: boolean; message?: string; error?: string; path?: string }> {
    const res = await fetch('/api/download/single', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    return res.json();
  },

  async getPlaylists(): Promise<{ ok: boolean; data: PlaylistSummary[] }> {
    const res = await fetch('/api/playlists');
    return res.json();
  },

  async getPlaylistTracks(name: string): Promise<{ ok: boolean; data: PlaylistTrack[] }> {
    const res = await fetch(`/api/playlists/tracks?name=${encodeURIComponent(name)}`);
    return res.json();
  },

  async renamePlaylist(oldName: string, newName: string): Promise<{ ok: boolean; error?: string }> {
    const res = await fetch('/api/playlists/rename', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ old_name: oldName, new_name: newName })
    });
    return res.json();
  },

  async updatePlaylistUsers(name: string, userIds: number[]): Promise<{ ok: boolean; message?: string; error?: string }> {
    const res = await fetch('/api/playlists/update-users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, user_ids: userIds })
    });
    return res.json();
  },

  async removePlaylistTracks(name: string, trackIds: number[], removePhysical = false): Promise<{ ok: boolean; message?: string; error?: string }> {
    const res = await fetch('/api/playlists/remove-tracks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, track_ids: trackIds, remove_physical: removePhysical })
    });
    return res.json();
  },

  async deletePlaylist(name: string, deleteTracks: boolean): Promise<{ ok: boolean; error?: string; deleted_files?: number }> {
    const res = await fetch('/api/playlists/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, delete_tracks: deleteTracks })
    });
    return res.json();
  },

  async searchLibraryTracks(query: string, page = 1, limit = 50): Promise<{ ok: boolean; data: { total: number; page: number; limit: number; list: LibraryTrack[] } }> {
    const res = await fetch(`/api/tracks/search?q=${encodeURIComponent(query)}&page=${page}&limit=${limit}`);
    return res.json();
  },

  async getDuplicateTracks(query = ''): Promise<{ ok: boolean; data: DuplicateResult }> {
    const res = await fetch(`/api/tracks/duplicates?q=${encodeURIComponent(query)}`);
    return res.json();
  },

  async deleteTrack(trackId: number, removePhysical = true): Promise<{ ok: boolean; error?: string }> {
    const res = await fetch('/api/tracks/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ track_id: trackId, remove_physical: removePhysical })
    });
    return res.json();
  },

  async batchDeleteTracks(trackIds: number[], removePhysical = true): Promise<{ ok: boolean; message?: string; error?: string; deleted_count?: number; failed_count?: number }> {
    const res = await fetch('/api/tracks/batch-delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ track_ids: trackIds, remove_physical: removePhysical })
    });
    return res.json();
  },

  async getHistory(): Promise<{ ok: boolean; data: HistoryItem[] }> {
    const res = await fetch('/api/history');
    return res.json();
  },

  async deleteHistory(id: number): Promise<{ ok: boolean }> {
    const res = await fetch('/api/history/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id })
    });
    return res.json();
  },

  async clearHistory(): Promise<{ ok: boolean }> {
    const res = await fetch('/api/history/clear', { method: 'POST' });
    return res.json();
  }
};
