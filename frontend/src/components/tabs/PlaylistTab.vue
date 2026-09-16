<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import type { PlaylistSummary, PlaylistTrack } from '../../types';
import { api } from '../../api';
import { showToast } from '../../composables/useToast';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { Popconfirm } from '@/components/ui/popconfirm';
import { Card } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter
} from '@/components/ui/dialog';
import {
  ListMusic,
  Users,
  UserCheck,
  RefreshCw,
  Loader2,
  Trash2,
  Edit3,
  Eye,
  Music,
  Disc3,
  CalendarDays,
  FileCheck2,
  Search,
  CheckCircle2,
  Globe,
  FileAudio
} from 'lucide-vue-next';

const playlists = ref<PlaylistSummary[]>([]);
const systemUsers = ref<Array<{ id: number; name: string; role?: string }>>([]);
const isLoading = ref(false);
const searchKw = ref('');
const failedCoverKeys = ref<Set<string>>(new Set());

// 滚动分页控制
const displayLimit = ref(15);
const sentinelRef = ref<HTMLElement | null>(null);
let observer: IntersectionObserver | null = null;

const filteredPlaylists = computed(() => {
  const kw = searchKw.value.trim().toLowerCase();
  if (!kw) return playlists.value;
  return playlists.value.filter(p => {
    const nameMatch = p.name.toLowerCase().includes(kw);
    const userStr = typeof p.users === 'string' ? p.users : '';
    const userMatch = userStr.toLowerCase().includes(kw);
    return nameMatch || userMatch;
  });
});

const displayedPlaylists = computed(() => {
  return filteredPlaylists.value.slice(0, displayLimit.value);
});

const hasMore = computed(() => displayLimit.value < filteredPlaylists.value.length);

function loadMore() {
  if (hasMore.value) {
    displayLimit.value += 15;
  }
}

watch(searchKw, () => {
  displayLimit.value = 15;
});

// View & Edit Tracks Dialog
const tracksDialogOpen = ref(false);
const activePlaylistName = ref('');
const playlistTracks = ref<PlaylistTrack[]>([]);
const loadingTracks = ref(false);
const trackSearchKw = ref('');
const selectedTrackIds = ref<Set<number>>(new Set());

// 单曲与批量移出状态
const removingTrackId = ref<number | null>(null);
const removeTrackPhysicalMap = ref<Record<number, boolean>>({});
const isBatchRemoving = ref(false);
const batchRemovePhysical = ref(false);

const filteredPlaylistTracks = computed(() => {
  const kw = trackSearchKw.value.trim().toLowerCase();
  if (!kw) return playlistTracks.value;
  return playlistTracks.value.filter(t =>
    t.title.toLowerCase().includes(kw) ||
    t.artist.toLowerCase().includes(kw) ||
    (t.album && t.album.toLowerCase().includes(kw))
  );
});

function toggleSelectTrack(id: number) {
  const s = new Set(selectedTrackIds.value);
  if (s.has(id)) {
    s.delete(id);
  } else {
    s.add(id);
  }
  selectedTrackIds.value = s;
}

function toggleSelectAllTracks() {
  const visible = filteredPlaylistTracks.value;
  if (visible.length === 0) return;
  const allSelected = visible.every(t => selectedTrackIds.value.has(t.id));
  const s = new Set(selectedTrackIds.value);
  if (allSelected) {
    visible.forEach(t => s.delete(t.id));
  } else {
    visible.forEach(t => s.add(t.id));
  }
  selectedTrackIds.value = s;
}

function formatBytes(bytes?: number): string {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

function formatDuration(ms?: number): string {
  if (!ms) return '0:00';
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

// Edit Playlist Dialog (Name + User Assignment)
const editDialogOpen = ref(false);
const editOldName = ref('');
const editNewName = ref('');
const editIsPublic = ref(true);
const editSelectedUserIds = ref<number[]>([]);
const isSavingEdit = ref(false);

// Delete state for Popconfirm
const deletingName = ref<string | null>(null);
const deletePhysicalMap = ref<Record<string, boolean>>({});

async function fetchUsers() {
  try {
    const res = await api.getUsers();
    if (res.ok && res.data) {
      systemUsers.value = res.data;
    }
  } catch (e) {}
}

async function fetchPlaylists() {
  isLoading.value = true;
  try {
    const res = await api.getPlaylists();
    if (res.ok) {
      playlists.value = res.data;
    } else {
      showToast('获取歌单列表失败', 'error');
    }
  } catch (e: any) {
    showToast(`歌单请求异常: ${e.message}`, 'error');
  } finally {
    isLoading.value = false;
  }
}

function getPlaylistMembers(users: PlaylistSummary['users']) {
  if (Array.isArray(users)) {
    return users.map(user => user.name).filter(Boolean);
  }
  return (users || '').split(',').map(user => user.trim()).filter(Boolean);
}

function isPublicPlaylist(pl: PlaylistSummary): boolean {
  if (systemUsers.value.length > 0 && pl.user_ids && pl.user_ids.length > 0) {
    const allUids = systemUsers.value.map(u => u.id);
    if (allUids.every(uid => pl.user_ids?.includes(uid))) {
      return true;
    }
  }
  const members = getPlaylistMembers(pl.users);
  return members.length === 0 || members.some(m => /公共|所有成员/.test(m));
}

function formatMemberSummary(pl: PlaylistSummary) {
  if (isPublicPlaylist(pl)) {
    return '公共歌单 (全部成员)';
  }
  const members = getPlaylistMembers(pl.users);
  return `专属 · ${members.join(', ')}`;
}

function formatPlaylistDate(value?: string) {
  if (!value) return '创建时间未知';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '创建时间未知';
  return date.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' });
}

type CoverType = 'playlist' | 'track';

function coverUrl(type: CoverType, guid?: string) {
  return guid ? `/api/covers/${type}/${encodeURIComponent(guid)}?size=160` : '';
}

function coverAvailable(type: CoverType, guid?: string) {
  return Boolean(guid) && !failedCoverKeys.value.has(`${type}:${guid}`);
}

function markCoverFailed(type: CoverType, guid?: string) {
  const next = new Set(failedCoverKeys.value);
  next.add(`${type}:${guid || ''}`);
  failedCoverKeys.value = next;
}

async function viewTracks(pl: PlaylistSummary) {
  activePlaylistName.value = pl.name;
  trackSearchKw.value = '';
  selectedTrackIds.value = new Set();
  tracksDialogOpen.value = true;
  loadingTracks.value = true;
  try {
    const res = await api.getPlaylistTracks(pl.name);
    if (res.ok) {
      playlistTracks.value = res.data;
    } else {
      showToast('获取曲目清单失败', 'error');
    }
  } catch (e: any) {
    showToast(`曲目异常: ${e.message}`, 'error');
  } finally {
    loadingTracks.value = false;
  }
}

async function handleRemoveTrack(t: PlaylistTrack) {
  removingTrackId.value = t.id;
  const physical = Boolean(removeTrackPhysicalMap.value[t.id]);
  try {
    const res = await api.removePlaylistTracks(activePlaylistName.value, [t.id], physical);
    if (res.ok) {
      showToast(`已从歌单移出《${t.title}》${physical ? '，并彻底删除了物理文件' : ''}`, 'success');
      playlistTracks.value = playlistTracks.value.filter(item => item.id !== t.id);
      selectedTrackIds.value.delete(t.id);
      delete removeTrackPhysicalMap.value[t.id];
      const pl = playlists.value.find(p => p.name === activePlaylistName.value);
      if (pl && pl.track_count > 0) {
        pl.track_count -= 1;
      }
    } else {
      showToast(res.error || '移出失败', 'error');
    }
  } catch (e: any) {
    showToast(`移出异常: ${e.message}`, 'error');
  } finally {
    removingTrackId.value = null;
  }
}

async function handleBatchRemoveTracks() {
  const ids = Array.from(selectedTrackIds.value);
  if (ids.length === 0) return;
  isBatchRemoving.value = true;
  try {
    const res = await api.removePlaylistTracks(activePlaylistName.value, ids, batchRemovePhysical.value);
    if (res.ok) {
      showToast(`已批量从歌单移出 ${ids.length} 首曲目${batchRemovePhysical.value ? '，并彻底删除了物理文件' : ''}`, 'success');
      playlistTracks.value = playlistTracks.value.filter(item => !selectedTrackIds.value.has(item.id));
      const pl = playlists.value.find(p => p.name === activePlaylistName.value);
      if (pl) {
        pl.track_count = Math.max(0, pl.track_count - ids.length);
      }
      selectedTrackIds.value = new Set();
      batchRemovePhysical.value = false;
    } else {
      showToast(res.error || '批量移出失败', 'error');
    }
  } catch (e: any) {
    showToast(`批量移出异常: ${e.message}`, 'error');
  } finally {
    isBatchRemoving.value = false;
  }
}

function openEdit(pl: PlaylistSummary) {
  editOldName.value = pl.name;
  editNewName.value = pl.name;

  const allUids = systemUsers.value.map(u => u.id);
  const currentUids = pl.user_ids || [];

  const isPublic = isPublicPlaylist(pl);
  editIsPublic.value = isPublic;

  if (isPublic) {
    editSelectedUserIds.value = [...allUids];
  } else {
    editSelectedUserIds.value = currentUids.length > 0 ? [...currentUids] : (allUids[0] ? [allUids[0]] : []);
  }

  editDialogOpen.value = true;
}

function toggleEditPublic(isPub: boolean) {
  editIsPublic.value = isPub;
  if (isPub) {
    editSelectedUserIds.value = systemUsers.value.map(u => u.id);
  } else if (editSelectedUserIds.value.length === 0 && systemUsers.value.length > 0) {
    editSelectedUserIds.value = [systemUsers.value[0].id];
  }
}

function toggleEditUserId(uid: number) {
  const s = new Set(editSelectedUserIds.value);
  if (s.has(uid)) {
    s.delete(uid);
  } else {
    s.add(uid);
  }
  editSelectedUserIds.value = Array.from(s);
  if (systemUsers.value.length > 0 && editSelectedUserIds.value.length === systemUsers.value.length) {
    editIsPublic.value = true;
  } else {
    editIsPublic.value = false;
  }
}

async function handleSaveEdit() {
  const newName = editNewName.value.trim();
  if (!newName) {
    showToast('歌单名称不能为空', 'error');
    return;
  }

  const targetUids = editIsPublic.value
    ? systemUsers.value.map(u => u.id)
    : editSelectedUserIds.value;

  if (targetUids.length === 0) {
    showToast('请至少选择一个可见成员', 'warning');
    return;
  }

  isSavingEdit.value = true;
  try {
    let effectiveName = editOldName.value;
    if (newName !== editOldName.value) {
      const resRename = await api.renamePlaylist(editOldName.value, newName);
      if (!resRename.ok) {
        showToast(resRename.error || '重命名失败', 'error');
        return;
      }
      effectiveName = newName;
    }

    const resUsers = await api.updatePlaylistUsers(effectiveName, targetUids);
    if (!resUsers.ok) {
      showToast(resUsers.error || '更新歌单可见成员失败', 'error');
      return;
    }

    showToast(`歌单《${effectiveName}》配置已更新`, 'success');
    editDialogOpen.value = false;
    await fetchPlaylists();
  } catch (e: any) {
    showToast(`保存异常: ${e.message}`, 'error');
  } finally {
    isSavingEdit.value = false;
  }
}

async function handleDelete(pl: PlaylistSummary) {
  deletingName.value = pl.name;
  const physical = Boolean(deletePhysicalMap.value[pl.name]);
  try {
    const res = await api.deletePlaylist(pl.name, physical);
    if (res.ok) {
      showToast(`歌单《${pl.name}》已删除${physical ? `，并清理了 ${res.deleted_files || 0} 个本地文件` : ''}`, 'success');
      playlists.value = playlists.value.filter(p => p.name !== pl.name);
      delete deletePhysicalMap.value[pl.name];
    } else {
      showToast(res.error || '删除失败', 'error');
    }
  } catch (e: any) {
    showToast(`删除异常: ${e.message}`, 'error');
  } finally {
    deletingName.value = null;
  }
}

onMounted(async () => {
  await fetchUsers();
  await fetchPlaylists();

  observer = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && hasMore.value) {
      loadMore();
    }
  }, { threshold: 0.1 });
  if (sentinelRef.value) observer.observe(sentinelRef.value);
});
</script>

<template>
  <div class="space-y-4">
    <!-- Top Control Bar (紧凑无冗余标题) -->
    <Card class="bg-card/80 border-border backdrop-blur-xl shadow-xl p-3 sm:p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shrink-0">
      <div class="flex items-center gap-2.5 text-xs">
        <span class="text-slate-300 font-medium flex items-center gap-1.5">
          <ListMusic class="w-4 h-4 text-brand-400" />
          <span>歌单资产:</span>
          <strong class="text-white font-mono text-sm">{{ playlists.length }}</strong> 个
        </span>
        <span class="text-slate-600">|</span>
        <span class="flex items-center gap-1.5 text-[11px] text-slate-500">
          <span class="h-1.5 w-1.5 rounded-full bg-emerald-400" />
          直通飞牛底座 SQLite
        </span>
      </div>

      <div class="flex items-center gap-2 w-full sm:w-auto">
        <div class="relative flex-1 sm:w-64">
          <Search class="w-3.5 h-3.5 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2 z-10" />
          <Input
            v-model="searchKw"
            type="text"
            placeholder="搜索歌单名称或成员..."
            class="pl-9 h-9 text-xs"
          />
        </div>

        <Button
          variant="outline"
          size="icon"
          @click="fetchPlaylists"
          title="刷新歌单列表"
          class="h-9 w-9 rounded-xl shrink-0"
        >
          <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': isLoading }" />
        </Button>
      </div>
    </Card>

    <!-- Playlist Assets List -->
    <Card class="relative bg-card/80 border-border backdrop-blur-xl shadow-2xl p-4 sm:p-5 flex flex-col h-[calc(100vh-220px)] min-h-[500px]">
      <div v-if="isLoading" class="py-20 text-center text-slate-400 my-auto">
        <Loader2 class="mx-auto h-7 w-7 animate-spin text-primary" />
        <p class="mt-3 text-xs">正在读取飞牛歌单资产...</p>
      </div>

      <div v-else-if="playlists.length === 0" class="py-20 text-center text-slate-500 my-auto">
        <div class="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-dashed border-white/[0.09] bg-white/[0.02]">
          <ListMusic class="h-6 w-6 text-slate-700" />
        </div>
        <p class="mt-4 text-xs">飞牛数据库中暂无歌单数据</p>
      </div>

      <div v-else-if="filteredPlaylists.length === 0" class="py-20 text-center text-slate-500 my-auto">
        <p class="text-xs">未找到与 "{{ searchKw }}" 匹配的歌单</p>
      </div>

      <!-- 可滚动歌单列表 -->
      <div
        v-else
        class="flex-1 overflow-y-auto pr-1 space-y-2 select-text scrollbar-thin"
      >
        <div
          v-for="(pl, index) in displayedPlaylists"
          :key="pl.name"
          class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3.5 rounded-xl bg-white/[0.02] hover:bg-white/[0.05] border border-transparent transition-all group"
        >
          <!-- 左侧：封面与信息 -->
          <div class="flex items-center gap-3.5 overflow-hidden flex-1 min-w-0">
            <!-- 歌单封面 -->
            <div class="relative flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-white/[0.08] bg-black/25 shadow-md">
              <Disc3 class="h-6 w-6 text-primary/70 transition-transform duration-500 group-hover:rotate-12" />
              <img
                v-if="coverAvailable('playlist', pl.cover_guid)"
                :src="coverUrl('playlist', pl.cover_guid)"
                :alt="`${pl.name} 封面`"
                loading="lazy"
                decoding="async"
                class="absolute inset-0 h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                @error="markCoverFailed('playlist', pl.cover_guid)"
              />
              <span class="absolute bottom-1 right-1 rounded-md border border-white/[0.09] bg-black/70 px-1 py-0.2 font-mono text-[8px] text-slate-300">
                {{ String(index + 1).padStart(2, '0') }}
              </span>
            </div>

            <!-- 歌单详情 -->
            <div class="space-y-1 overflow-hidden min-w-0 flex-1">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="text-sm font-semibold text-white truncate max-w-sm">
                  {{ pl.name }}
                </span>

                <!-- M3U 状态 -->
                <Badge :variant="pl.m3u_exists ? 'success' : 'outline'" class="text-[9px] px-1.5 py-0">
                  <FileCheck2 class="mr-1 h-3 w-3" />
                  {{ pl.m3u_exists ? 'M3U 同步' : '仅数据库' }}
                </Badge>

                <!-- 归属成员展示徽章 -->
                <Badge
                  v-if="isPublicPlaylist(pl)"
                  variant="outline"
                  class="border-emerald-500/30 text-emerald-400 bg-emerald-950/25 text-[10px] px-1.5 py-0 flex items-center gap-1"
                >
                  <Globe class="w-3 h-3" />
                  <span>公共歌单</span>
                </Badge>
                <Badge
                  v-else
                  variant="outline"
                  class="border-indigo-500/30 text-indigo-400 bg-indigo-950/25 text-[10px] px-1.5 py-0 flex items-center gap-1"
                  :title="formatMemberSummary(pl)"
                >
                  <UserCheck class="w-3 h-3" />
                  <span class="truncate max-w-[140px]">{{ typeof pl.users === 'string' ? pl.users : pl.users.map(u => u.name).join(', ') }}</span>
                </Badge>
              </div>

              <div class="flex items-center gap-3 text-slate-400 text-[11px] flex-wrap">
                <span class="text-slate-300 font-mono">
                  曲目: <strong class="text-primary font-bold">{{ pl.track_count }}</strong> 首
                </span>
                <span class="text-slate-600">·</span>
                <span class="flex items-center gap-1 text-slate-500">
                  <CalendarDays class="h-3 w-3" />
                  <span>{{ formatPlaylistDate(pl.updated_at || pl.created_at) }}</span>
                </span>
                <span class="text-slate-600">·</span>
                <span class="text-slate-500 truncate max-w-[200px]" :title="formatMemberSummary(pl)">
                  {{ formatMemberSummary(pl) }}
                </span>
              </div>
            </div>
          </div>

          <!-- 右侧：快捷操作按钮 -->
          <div class="flex items-center justify-end gap-1.5 shrink-0 pt-2 sm:pt-0">
            <Button
              variant="secondary"
              size="sm"
              class="h-8 gap-1.5 text-xs text-slate-300 hover:text-white"
              @click="viewTracks(pl)"
            >
              <Eye class="h-3.5 w-3.5 text-primary" />
              <span>查看曲目</span>
            </Button>

            <Button
              variant="ghost"
              size="sm"
              title="编辑歌单及指定用户"
              class="h-8 px-2.5 text-xs text-slate-400 hover:bg-primary/[0.07] hover:text-primary gap-1"
              @click="openEdit(pl)"
            >
              <Edit3 class="h-3.5 w-3.5" />
              <span class="hidden sm:inline">编辑</span>
            </Button>

            <Popconfirm
              :title="`删除歌单《${pl.name}》？`"
              description="将从飞牛官方曲库注销该歌单记录。"
              confirmText="确认删除"
              :danger="true"
              :loading="deletingName === pl.name"
              side="top"
              align="end"
              widthClass="w-80"
              @confirm="handleDelete(pl)"
            >
              <template #extra>
                <label class="flex cursor-pointer select-none items-center gap-2.5 rounded-xl border border-destructive/25 bg-destructive/10 p-2 text-[11px] text-rose-300 mt-2">
                  <Checkbox
                    :checked="deletePhysicalMap[pl.name]"
                    @update:checked="(val: boolean) => deletePhysicalMap[pl.name] = Boolean(val)"
                  />
                  <span>同时从 NAS 物理删除音频与歌词文件</span>
                </label>
              </template>

              <Button
                variant="ghost"
                size="sm"
                title="删除歌单"
                class="h-8 px-2.5 text-xs text-slate-500 hover:bg-destructive/10 hover:text-rose-400"
              >
                <Trash2 class="h-3.5 w-3.5" />
              </Button>
            </Popconfirm>
          </div>
        </div>

        <!-- 滚动触底 Sentinel 哨兵元素 -->
        <div ref="sentinelRef" class="py-3 text-center">
          <div v-if="hasMore" class="flex items-center justify-center gap-2 text-xs text-slate-400 py-2">
            <RefreshCw class="w-4 h-4 animate-spin text-brand-400" />
            <span>向下滚动自动加载更多歌单...</span>
          </div>
          <div v-else-if="filteredPlaylists.length > 0" class="py-2 text-center text-[11px] text-slate-600">
            — 已显示全部 {{ filteredPlaylists.length }} 个歌单 —
          </div>
        </div>
      </div>
    </Card>

    <!-- Dialog: View & Edit Tracks (查看与管理歌单内曲目) -->
    <Dialog :open="tracksDialogOpen" @update:open="(val: boolean) => tracksDialogOpen = val">
      <DialogContent class="sm:max-w-4xl max-h-[88vh] flex flex-col bg-[#0d1413]/98 border border-white/[0.14] backdrop-blur-2xl shadow-2xl rounded-2xl p-0 overflow-hidden">
        <DialogHeader class="p-4 sm:p-5 border-b border-white/[0.08] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div class="space-y-1">
            <DialogTitle class="flex items-center gap-2 text-base font-bold text-white">
              <Music class="w-5 h-5 text-brand-400" />
              <span>《{{ activePlaylistName }}》曲目管理</span>
              <Badge variant="secondary" class="font-mono text-[11px] text-brand-400 px-1.5 py-0">
                {{ playlistTracks.length }} 首
              </Badge>
            </DialogTitle>
            <DialogDescription class="text-xs text-slate-400">
              管理该歌单在飞牛官方曲库内关联的音乐，支持搜索与移出曲目
            </DialogDescription>
          </div>

          <div class="relative w-full sm:w-64">
            <Search class="w-3.5 h-3.5 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2 z-10" />
            <Input
              v-model="trackSearchKw"
              type="text"
              placeholder="搜索歌单内曲目或歌手..."
              class="pl-9 h-8 text-xs bg-black/40"
            />
          </div>
        </DialogHeader>

        <!-- 工具条：全选 / 统计 -->
        <div class="flex items-center justify-between px-5 py-2.5 bg-black/25 border-b border-white/[0.06] text-xs text-slate-400 shrink-0">
          <label class="flex items-center gap-2 cursor-pointer select-none hover:text-white">
            <Checkbox
              :checked="filteredPlaylistTracks.length > 0 && filteredPlaylistTracks.every(t => selectedTrackIds.has(t.id))"
              @update:checked="toggleSelectAllTracks"
            />
            <span>全选列表 ({{ filteredPlaylistTracks.length }})</span>
          </label>
          <span v-if="selectedTrackIds.size > 0" class="text-brand-400 font-medium">
            已选中 {{ selectedTrackIds.size }} 首
          </span>
          <span v-else class="text-slate-500 text-[11px]">
            点击单曲右侧可从歌单移出
          </span>
        </div>

        <div class="p-4 overflow-y-auto space-y-1 flex-1 scrollbar-thin select-text relative min-h-[260px]">
          <div v-if="loadingTracks" class="py-16 text-center text-slate-400">
            <Loader2 class="w-7 h-7 mx-auto animate-spin text-brand-400 mb-2" />
            <span class="text-xs">加载曲目列表中...</span>
          </div>

          <div v-else-if="playlistTracks.length === 0" class="py-16 text-center text-slate-500 text-xs">
            该歌单内暂无曲目
          </div>

          <div v-else-if="filteredPlaylistTracks.length === 0" class="py-16 text-center text-slate-500 text-xs">
            未找到匹配 "{{ trackSearchKw }}" 的歌曲
          </div>

          <!-- 曲目行（无边框，干净排版，支持勾选与单曲移出） -->
          <div
            v-else
            v-for="(t, idx) in filteredPlaylistTracks"
            :key="t.id"
            :class="[
              'flex items-center justify-between gap-3 p-2.5 rounded-xl transition-all text-xs border border-transparent',
              selectedTrackIds.has(t.id)
                ? 'bg-brand-500/15 !border-brand-500/40 text-white'
                : 'bg-white/[0.02] hover:bg-white/[0.05]'
            ]"
          >
            <div class="flex items-center gap-3 overflow-hidden flex-1 min-w-0">
              <Checkbox
                :checked="selectedTrackIds.has(t.id)"
                @update:checked="() => toggleSelectTrack(t.id)"
                class="shrink-0"
              />

              <span class="text-slate-500 font-mono w-6 text-right shrink-0">{{ idx + 1 }}</span>

              <div class="relative flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-white/[0.07] bg-white/[0.025]">
                <FileAudio class="h-4 w-4 text-primary/70" />
                <img
                  v-if="coverAvailable('track', t.cover_guid)"
                  :src="coverUrl('track', t.cover_guid)"
                  :alt="`${t.title} 封面`"
                  loading="lazy"
                  decoding="async"
                  class="absolute inset-0 h-full w-full object-cover"
                  @error="markCoverFailed('track', t.cover_guid)"
                />
              </div>

              <div class="overflow-hidden min-w-0 flex-1">
                <div class="font-semibold text-white truncate flex items-center gap-2">
                  <span>{{ t.title }}</span>
                  <Badge variant="secondary" class="text-[9px] uppercase font-mono px-1.5 py-0">
                    {{ t.codec || 'FLAC' }}
                  </Badge>
                  <span v-if="t.size" class="text-[10px] text-slate-500 font-mono">
                    {{ formatBytes(t.size) }}
                  </span>
                  <span v-if="t.duration_ms" class="text-[10px] text-slate-500 font-mono">
                    {{ formatDuration(t.duration_ms) }}
                  </span>
                </div>
                <div class="text-slate-400 truncate mt-0.5 text-[11px]">{{ t.artist }} · 《{{ t.album || '未命名专辑' }}》</div>
                <div class="text-[10px] text-slate-500 font-mono truncate mt-0.5">{{ t.path }}</div>
              </div>
            </div>

            <!-- 单曲移出按钮 -->
            <div class="shrink-0">
              <Popconfirm
                :title="`从歌单《${activePlaylistName}》中移出《${t.title}》？`"
                description="将该歌曲从当前歌单解绑。默认不会删除本地音频文件。"
                confirmText="移出歌单"
                :danger="true"
                :loading="removingTrackId === t.id"
                side="left"
                align="center"
                widthClass="w-80"
                @confirm="handleRemoveTrack(t)"
              >
                <template #extra>
                  <label class="flex cursor-pointer select-none items-center gap-2 rounded-xl border border-destructive/25 bg-destructive/10 p-2 text-[11px] text-rose-300 mt-2">
                    <Checkbox
                      :checked="removeTrackPhysicalMap[t.id]"
                      @update:checked="(val: boolean) => removeTrackPhysicalMap[t.id] = Boolean(val)"
                    />
                    <span>同时从 NAS 硬盘物理彻底删除文件</span>
                  </label>
                </template>

                <Button
                  variant="ghost"
                  size="icon"
                  title="从歌单移出"
                  class="h-8 w-8 text-slate-500 hover:text-rose-400 hover:bg-destructive/10"
                >
                  <Trash2 class="w-3.5 h-3.5" />
                </Button>
              </Popconfirm>
            </div>
          </div>
        </div>

        <!-- 浮动批量操作条（当选中曲目时出现） -->
        <transition
          enter-active-class="transition duration-200 ease-out"
          enter-from-class="opacity-0 translate-y-4 scale-95"
          enter-to-class="opacity-100 translate-y-0 scale-100"
          leave-active-class="transition duration-150 ease-in"
          leave-from-class="opacity-100 translate-y-0 scale-100"
          leave-to-class="opacity-0 translate-y-4 scale-95"
        >
          <div
            v-if="selectedTrackIds.size > 0"
            class="absolute bottom-16 left-1/2 -translate-x-1/2 z-30 bg-[#0d1413]/95 border border-brand-500/40 backdrop-blur-xl px-5 py-2.5 rounded-2xl shadow-2xl flex items-center gap-4 text-xs"
          >
            <span class="text-white font-medium">
              已选中 <strong class="text-brand-400 font-mono text-sm">{{ selectedTrackIds.size }}</strong> 首曲目
            </span>
            <span class="text-slate-600">|</span>
            <Button
              variant="ghost"
              size="sm"
              @click="selectedTrackIds = new Set()"
              class="h-7 text-xs text-slate-400 hover:text-white"
            >
              取消选择
            </Button>
            <Popconfirm
              :title="`确认将选中的 ${selectedTrackIds.size} 首曲目从歌单《${activePlaylistName}》移出？`"
              description="曲目将从当前歌单解绑。默认不会删除本地音频文件。"
              confirmText="确认移出"
              :danger="true"
              :loading="isBatchRemoving"
              side="top"
              align="end"
              widthClass="w-84 sm:w-[380px]"
              @confirm="handleBatchRemoveTracks"
            >
              <template #extra>
                <label class="flex cursor-pointer select-none items-center gap-2 rounded-xl border border-destructive/25 bg-destructive/10 p-2 text-[11px] text-rose-300 mt-2">
                  <Checkbox
                    :checked="batchRemovePhysical"
                    @update:checked="(val: boolean) => batchRemovePhysical = Boolean(val)"
                  />
                  <span>同时从 NAS 物理彻底删除音频与歌词文件</span>
                </label>
              </template>
              <Button
                variant="destructive"
                size="sm"
                :disabled="isBatchRemoving"
                class="h-7 text-xs flex items-center gap-1.5"
              >
                <Loader2 v-if="isBatchRemoving" class="w-3 h-3 animate-spin" />
                <Trash2 v-else class="w-3 h-3" />
                <span>批量移出歌单 ({{ selectedTrackIds.size }})</span>
              </Button>
            </Popconfirm>
          </div>
        </transition>

        <DialogFooter class="p-3 border-t border-white/[0.08] bg-black/30 flex justify-end">
          <Button
            variant="secondary"
            size="sm"
            @click="tracksDialogOpen = false"
          >
            完成并关闭
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- Dialog: Edit Playlist (支持修改歌单名与指定用户分配) -->
    <Dialog :open="editDialogOpen" @update:open="(val: boolean) => editDialogOpen = val">
      <DialogContent class="sm:max-w-md bg-[#0d1413]/98 border border-white/[0.14] backdrop-blur-2xl shadow-2xl rounded-2xl p-6 space-y-4">
        <DialogHeader>
          <DialogTitle class="text-base font-bold text-white flex items-center gap-2">
            <Edit3 class="w-4 h-4 text-brand-400" />
            <span>编辑歌单</span>
          </DialogTitle>
          <DialogDescription class="text-xs text-slate-400">
            修改歌单在飞牛曲库中的名称与指定可见成员
          </DialogDescription>
        </DialogHeader>

        <!-- 歌单名称 -->
        <div class="space-y-1.5">
          <label class="text-xs font-medium text-slate-300">歌单名称</label>
          <Input
            v-model="editNewName"
            placeholder="输入歌单名称..."
            class="h-9 text-xs"
          />
        </div>

        <!-- 可见成员分配模式 -->
        <div class="space-y-2 pt-1">
          <label class="text-xs font-medium text-slate-300">可见范围与成员分配</label>
          
          <div class="grid grid-cols-2 gap-2">
            <button
              type="button"
              @click="toggleEditPublic(true)"
              class="p-2.5 rounded-xl border text-left text-xs transition-all flex items-center gap-2"
              :class="editIsPublic
                ? 'border-emerald-500/50 bg-emerald-950/20 text-emerald-300'
                : 'border-white/[0.08] bg-black/20 text-slate-400 hover:text-white'"
            >
              <Globe class="w-4 h-4" />
              <div>
                <div class="font-semibold">公共歌单</div>
                <div class="text-[10px] text-slate-400">所有家庭成员可见</div>
              </div>
            </button>

            <button
              type="button"
              @click="toggleEditPublic(false)"
              class="p-2.5 rounded-xl border text-left text-xs transition-all flex items-center gap-2"
              :class="!editIsPublic
                ? 'border-indigo-500/50 bg-indigo-950/20 text-indigo-300'
                : 'border-white/[0.08] bg-black/20 text-slate-400 hover:text-white'"
            >
              <UserCheck class="w-4 h-4" />
              <div>
                <div class="font-semibold">指定成员专属</div>
                <div class="text-[10px] text-slate-400">仅勾选的用户可见</div>
              </div>
            </button>
          </div>

          <!-- 指定用户勾选列表 -->
          <div v-if="!editIsPublic" class="space-y-1.5 pt-1.5">
            <div class="text-[11px] text-slate-400">请勾选允许访问此歌单的飞牛用户：</div>
            <div class="rounded-xl border border-white/[0.08] bg-black/30 p-2.5 space-y-2 max-h-40 overflow-y-auto scrollbar-thin">
              <label
                v-for="u in systemUsers"
                :key="u.id"
                class="flex items-center justify-between p-1.5 rounded-lg hover:bg-white/[0.04] cursor-pointer select-none text-xs"
              >
                <div class="flex items-center gap-2">
                  <Checkbox
                    :checked="editSelectedUserIds.includes(u.id)"
                    @update:checked="() => toggleEditUserId(u.id)"
                  />
                  <span class="text-white font-medium">{{ u.name }}</span>
                </div>
                <Badge v-if="u.role === 'admin'" variant="secondary" class="text-[9px] px-1 py-0 text-slate-400">
                  管理员
                </Badge>
              </label>
            </div>
          </div>
        </div>

        <DialogFooter class="flex justify-end gap-2 pt-2">
          <Button variant="ghost" size="sm" @click="editDialogOpen = false">取消</Button>
          <Button
            variant="default"
            size="sm"
            @click="handleSaveEdit"
            :disabled="isSavingEdit"
            class="flex items-center gap-1.5"
          >
            <Loader2 v-if="isSavingEdit" class="w-3.5 h-3.5 animate-spin" />
            <span>{{ isSavingEdit ? '保存中...' : '保存修改' }}</span>
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
