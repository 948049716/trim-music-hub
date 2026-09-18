<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import type { PlaylistSummary, PlaylistTrack, HistoryItem } from '../../types';
import { api } from '../../api';
import { showToast } from '../../composables/useToast';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { Popconfirm } from '@/components/ui/popconfirm';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter
} from '@/components/ui/dialog';
import {
  ListMusic,
  Disc3,
  RefreshCw,
  Loader2,
  Trash2,
  Search,
  Check,
  X,
  Clock,
  Sparkles
} from 'lucide-vue-next';

interface Props {
  open: boolean;
  playlistName: string;
  playlistSummary?: PlaylistSummary | null;
  historyItem?: HistoryItem | null;
}

const props = withDefaults(defineProps<Props>(), {
  open: false,
  playlistName: '',
  playlistSummary: null,
  historyItem: null
});

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void;
  (e: 'tracks-changed', payload: { playlistName: string; remainingCount: number }): void;
}>();

const playlistTracks = ref<PlaylistTrack[]>([]);
const loadingTracks = ref(false);
const loadTracksError = ref('');
const trackSearchKw = ref('');
const selectedTrackIds = ref<Set<number>>(new Set());

const matchedSummary = ref<PlaylistSummary | null>(null);
const failedCoverKeys = ref<Set<string>>(new Set());

// 单曲与批量移出状态
const removingTrackId = ref<number | null>(null);
const removeTrackPhysicalMap = ref<Record<number, boolean>>({});
const isBatchRemoving = ref(false);
const batchRemovePhysical = ref(false);

const currentSummary = computed(() => {
  return props.playlistSummary || matchedSummary.value;
});

const playlistTotalSize = computed(() => {
  return playlistTracks.value.reduce((acc, t) => acc + (t.size || 0), 0);
});

const playlistTotalDurationMs = computed(() => {
  return playlistTracks.value.reduce(
    (acc, t) => acc + (t.duration_ms || (t.duration ? t.duration * 1000 : 0)),
    0
  );
});

const filteredPlaylistTracks = computed(() => {
  const kw = trackSearchKw.value.trim().toLowerCase();
  return playlistTracks.value.filter(t => {
    if (filterReusedOnly.value && !isTrackReused(t)) {
      return false;
    }
    if (!kw) return true;
    return (
      t.title.toLowerCase().includes(kw) ||
      t.artist.toLowerCase().includes(kw) ||
      (t.album && t.album.toLowerCase().includes(kw))
    );
  });
});

const filterReusedOnly = ref(false);

function isTrackReused(t: PlaylistTrack): boolean {
  if (typeof t.is_reused === 'boolean') return t.is_reused;

  // 1. 若历史记录中自带了任务时的 tracks 详情
  if (props.historyItem?.tracks && Array.isArray(props.historyItem.tracks)) {
    const normTitle = (t.title || '').trim().toLowerCase();
    const normArtist = (t.artist || '').trim().toLowerCase();
    const match = props.historyItem.tracks.find(ht => {
      const htTitle = (ht.title || '').trim().toLowerCase();
      const htArtist = (ht.artist || '').trim().toLowerCase();
      return (
        (htTitle === normTitle && htArtist === normArtist) ||
        htTitle === normTitle ||
        (normTitle.includes(htTitle) && normArtist.includes(htArtist))
      );
    });
    if (match) {
      return match.status === 'reused';
    }
  }

  // 2. 时间戳比对（曲库建档时间明显早于加入歌单或任务开始时间）
  if (t.created_at) {
    const trackCreatedTime = new Date(t.created_at).getTime();
    if (!isNaN(trackCreatedTime)) {
      // 优先与歌单添加时间 added_at 比对
      if (t.added_at) {
        const addedTime = new Date(t.added_at).getTime();
        if (!isNaN(addedTime) && addedTime - trackCreatedTime > 20000) {
          return true;
        }
      }
      // 其次与历史记录的开始时间 start_time 比对
      if (props.historyItem?.start_time) {
        const taskStartTime = new Date(props.historyItem.start_time).getTime();
        if (!isNaN(taskStartTime) && trackCreatedTime < taskStartTime - 5000) {
          return true;
        }
      }
    }
  }

  return false;
}

const reusedCount = computed(() => {
  return playlistTracks.value.filter(t => isTrackReused(t)).length;
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
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  }
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

function formatHistoryDuration(sec?: number) {
  if (!sec || sec <= 0) return '不到 1 秒';
  if (sec < 60) return `${sec} 秒`;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  if (m < 60) return `${m} 分 ${s} 秒`;
  const h = Math.floor(m / 60);
  const remM = m % 60;
  return `${h} 小时 ${remM} 分`;
}

function formatHistoryDate(iso?: string) {
  if (!iso) return '--';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  });
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

async function fetchPlaylistTracks(name: string) {
  if (!name) return;
  loadingTracks.value = true;
  loadTracksError.value = '';
  try {
    const res = await api.getPlaylistTracks(name);
    if (res.ok) {
      playlistTracks.value = res.data || [];
    } else {
      loadTracksError.value = res.error || '无法读取歌单歌曲，请稍后重试。';
      showToast('无法读取歌单歌曲，请稍后重试。', 'error');
    }
  } catch (e: any) {
    loadTracksError.value = e.message || '读取歌曲失败';
    showToast(`读取歌曲失败：${e.message}`, 'error');
  } finally {
    loadingTracks.value = false;
  }
}

async function fetchMatchedSummary(name: string) {
  if (props.playlistSummary || !name) return;
  try {
    const res = await api.getPlaylists();
    if (res.ok && Array.isArray(res.data)) {
      const found = res.data.find(p => p.name === name);
      if (found) {
        matchedSummary.value = found;
      }
    }
  } catch (e) {
    // 静默处理
  }
}

async function handleRemoveTrack(t: PlaylistTrack) {
  removingTrackId.value = t.id;
  const physical = Boolean(removeTrackPhysicalMap.value[t.id]);
  try {
    const res = await api.removePlaylistTracks(props.playlistName, [t.id], physical);
    if (res.ok) {
      showToast(`已将“${t.title}”移出歌单${physical ? '，并删除本地文件' : ''}。`, 'success');
      playlistTracks.value = playlistTracks.value.filter(item => item.id !== t.id);
      selectedTrackIds.value.delete(t.id);
      delete removeTrackPhysicalMap.value[t.id];
      emit('tracks-changed', {
        playlistName: props.playlistName,
        remainingCount: playlistTracks.value.length
      });
    } else {
      showToast(res.error || '移出失败', 'error');
    }
  } catch (e: any) {
    showToast(`移出歌曲失败：${e.message}`, 'error');
  } finally {
    removingTrackId.value = null;
  }
}

async function handleBatchRemoveTracks() {
  const ids = Array.from(selectedTrackIds.value);
  if (ids.length === 0) return;
  isBatchRemoving.value = true;
  try {
    const res = await api.removePlaylistTracks(
      props.playlistName,
      ids,
      batchRemovePhysical.value
    );
    if (res.ok) {
      showToast(
        `已移出 ${ids.length} 首歌曲${batchRemovePhysical.value ? '，并删除本地文件' : ''}。`,
        'success'
      );
      playlistTracks.value = playlistTracks.value.filter(
        item => !selectedTrackIds.value.has(item.id)
      );
      selectedTrackIds.value = new Set();
      batchRemovePhysical.value = false;
      emit('tracks-changed', {
        playlistName: props.playlistName,
        remainingCount: playlistTracks.value.length
      });
    } else {
      showToast(res.error || '批量移出失败', 'error');
    }
  } catch (e: any) {
    showToast(`批量移出失败：${e.message}`, 'error');
  } finally {
    isBatchRemoving.value = false;
  }
}

watch(
  () => [props.open, props.playlistName],
  ([newOpen, newName]) => {
    if (newOpen && newName) {
      trackSearchKw.value = '';
      filterReusedOnly.value = false;
      selectedTrackIds.value = new Set();
      removeTrackPhysicalMap.value = {};
      batchRemovePhysical.value = false;
      if (!props.playlistSummary) {
        matchedSummary.value = null;
        fetchMatchedSummary(newName as string);
      }
      fetchPlaylistTracks(newName as string);
    }
  },
  { immediate: true }
);
</script>

<template>
  <Dialog :open="props.open" @update:open="(val: boolean) => emit('update:open', val)">
    <DialogContent class="sm:max-w-4xl max-h-[92vh] max-sm:fixed max-sm:inset-x-0 max-sm:bottom-0 max-sm:top-auto max-sm:h-[92dvh] max-sm:translate-y-0 max-sm:rounded-t-3xl max-sm:rounded-b-none flex flex-col bg-popover border border-border backdrop-blur-2xl shadow-2xl rounded-2xl p-0 overflow-hidden">
      <!-- 移动端顶部手势微条 -->
      <div class="pt-2.5 pb-1 flex justify-center sm:hidden shrink-0">
        <div class="w-10 h-1 rounded-full bg-muted-foreground/30" />
      </div>

      <!-- 对话框 Header -->
      <DialogHeader class="p-3.5 sm:p-5 border-b border-border flex flex-col gap-3 shrink-0">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div class="flex items-center gap-3 min-w-0">
            <!-- 歌单封面小图 -->
            <div class="relative w-12 h-12 sm:w-14 sm:h-14 rounded-xl overflow-hidden border border-border/80 bg-muted/60 shrink-0 shadow-sm">
              <!-- 优先使用飞牛官方缓存 cover_guid -->
              <img
                v-if="currentSummary?.cover_guid && coverAvailable('playlist', currentSummary.cover_guid)"
                :src="coverUrl('playlist', currentSummary.cover_guid)"
                :alt="`${props.playlistName} 封面`"
                class="w-full h-full object-cover"
                loading="lazy"
                @error="markCoverFailed('playlist', currentSummary?.cover_guid)"
              />
              <!-- 兜底使用历史导入记录自带的网络封面 -->
              <img
                v-else-if="props.historyItem?.cover && !failedCoverKeys.has(`history:${props.historyItem.id}`)"
                :src="props.historyItem.cover"
                :alt="`${props.playlistName} 封面`"
                class="w-full h-full object-cover"
                loading="lazy"
                referrerpolicy="no-referrer"
                @error="failedCoverKeys.add(`history:${props.historyItem.id}`)"
              />
              <div v-else class="w-full h-full flex items-center justify-center bg-primary/10 text-primary">
                <ListMusic class="w-6 h-6" />
              </div>
            </div>

            <div class="space-y-1 min-w-0 flex-1">
              <DialogTitle class="flex items-center gap-2 text-sm sm:text-base font-bold text-foreground">
                <span class="truncate">《{{ props.playlistName }}》</span>
                <Badge variant="secondary" class="font-mono text-[10px] sm:text-[11px] text-primary px-1.5 py-0 shrink-0">
                  {{ playlistTracks.length }} 首
                </Badge>
              </DialogTitle>
              <div class="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[11px] text-muted-foreground">
                <span v-if="playlistTotalDurationMs" class="flex items-center gap-1 font-mono">
                  <Clock class="w-3 h-3 text-muted-foreground/70" />
                  {{ formatDuration(playlistTotalDurationMs) }}
                </span>
                <span v-if="playlistTotalSize" class="font-mono">
                  {{ formatBytes(playlistTotalSize) }}
                </span>
                <Badge
                  v-if="currentSummary"
                  :variant="currentSummary.m3u_exists ? 'success' : 'outline'"
                  class="text-[9px] px-1.5 py-0"
                >
                  {{ currentSummary.m3u_exists ? '已同步 M3U' : '待同步 M3U' }}
                </Badge>
              </div>
            </div>
          </div>

          <!-- 搜索框 -->
          <div class="relative w-full sm:w-64 shrink-0">
            <Search class="w-3.5 h-3.5 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2 z-10" />
            <Input
              v-model="trackSearchKw"
              type="text"
              placeholder="搜索歌单内曲目或歌手..."
              class="pl-9 pr-8 h-8 text-xs bg-muted/80"
            />
            <button
              v-if="trackSearchKw"
              type="button"
              @click="trackSearchKw = ''"
              class="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground p-0.5 rounded-full"
              title="清空"
            >
              <X class="w-3 h-3" />
            </button>
          </div>
        </div>

        <!-- 如果存在 historyItem，展示导入记录的详细元数据与统计指标 -->
        <div
          v-if="props.historyItem"
          class="mt-1 pt-2.5 border-t border-border/70 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[11px] text-muted-foreground bg-muted/30 -mx-3.5 sm:-mx-5 px-3.5 sm:px-5 py-2 rounded-lg"
        >
          <div class="flex items-center gap-1.5 font-medium text-foreground">
            <Sparkles class="w-3 h-3 text-primary" />
            <span>导入来源：{{ props.historyItem.platform || '第三方歌单' }}</span>
          </div>
          <span>时间：{{ formatHistoryDate(props.historyItem.end_time || props.historyItem.start_time) }}</span>
          <span>耗时：{{ formatHistoryDuration(props.historyItem.duration) }}</span>
          <span>归属：{{ props.historyItem.target === 'public' ? '公共歌单' : props.historyItem.user }}</span>
          <div class="flex items-center gap-1.5 ml-auto">
            <span class="text-emerald-600 dark:text-emerald-400 font-medium">新下 {{ props.historyItem.downloaded_count }} 首</span>
            <span class="text-blue-600 dark:text-blue-400 font-medium">复用 {{ props.historyItem.reused_count }} 首</span>
            <span v-if="props.historyItem.failed_count > 0" class="text-destructive font-medium">失败 {{ props.historyItem.failed_count }} 首</span>
          </div>
        </div>
      </DialogHeader>

      <!-- 工具条：全选 / 统计 / 快速复用过滤 -->
      <div class="flex items-center justify-between px-5 py-2.5 bg-muted/65 border-b border-border text-xs text-muted-foreground shrink-0">
        <div class="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            class="h-7 px-2 text-muted-foreground"
            :disabled="filteredPlaylistTracks.length === 0"
            @click="toggleSelectAllTracks"
          >
            {{ filteredPlaylistTracks.length > 0 && filteredPlaylistTracks.every(t => selectedTrackIds.has(t.id)) ? '取消全选' : '全选' }}
          </Button>

          <Button
            v-if="reusedCount > 0"
            variant="ghost"
            size="sm"
            class="h-7 px-2 text-[11px] gap-1 transition-all rounded-lg"
            :class="filterReusedOnly ? 'bg-blue-500/15 text-blue-600 dark:text-blue-400 font-semibold border border-blue-500/30' : 'text-muted-foreground hover:text-foreground'"
            @click="filterReusedOnly = !filterReusedOnly"
          >
            <span class="w-1.5 h-1.5 rounded-full bg-blue-500" />
            <span>仅看复用 ({{ reusedCount }})</span>
          </Button>
        </div>

        <span v-if="selectedTrackIds.size > 0" class="text-primary font-medium">
          已选中 {{ selectedTrackIds.size }} 首
        </span>
        <span v-else class="text-muted-foreground text-[11px]">
          点按歌曲选择，向左滑动可移出
        </span>
      </div>

      <!-- 歌曲列表主体 -->
      <div
        class="p-4 overflow-y-auto overflow-x-hidden space-y-1 flex-1 scrollbar-thin select-text relative min-h-[260px]"
        :class="selectedTrackIds.size > 0 ? 'pb-24' : 'pb-6'"
      >
        <div v-if="loadingTracks" class="py-16 text-center text-muted-foreground">
          <Loader2 class="w-7 h-7 mx-auto animate-spin text-primary mb-2" />
          <span class="text-xs">加载曲目列表中...</span>
        </div>

        <div v-else-if="loadTracksError" class="py-16 text-center text-muted-foreground space-y-2">
          <p class="text-xs text-destructive">{{ loadTracksError }}</p>
          <Button variant="outline" size="sm" class="h-7 text-xs" @click="fetchPlaylistTracks(props.playlistName)">
            <RefreshCw class="w-3.5 h-3.5 mr-1" /> 重试
          </Button>
        </div>

        <div v-else-if="playlistTracks.length === 0" class="py-16 text-center text-muted-foreground text-xs space-y-2">
          <ListMusic class="w-10 h-10 mx-auto stroke-1 text-muted-foreground/50 mb-2" />
          <p>该歌单内暂无曲目</p>
          <p v-if="props.historyItem" class="text-[11px] text-muted-foreground/75">
            （导入记录显示当时收录了 {{ props.historyItem.total }} 首，若歌单此前已在飞牛中删除，曲目已解绑）
          </p>
        </div>

        <div v-else-if="filteredPlaylistTracks.length === 0" class="py-16 text-center text-muted-foreground text-xs space-y-2">
          <p>未找到匹配 "{{ trackSearchKw }}" 的歌曲</p>
          <Button variant="outline" size="sm" class="h-7 text-xs" @click="trackSearchKw = ''">清空搜索</Button>
        </div>

        <!-- 点按整行选择；移动端向左滑动显示移出操作 -->
        <div
          v-else
          v-for="(t, idx) in filteredPlaylistTracks"
          :key="t.id"
          class="swipe-list-item"
        >
          <article
            :class="[
              'media-list-row media-list-row--track',
              { 'media-list-row--selected': selectedTrackIds.has(t.id) }
            ]"
            role="button"
            tabindex="0"
            :aria-pressed="selectedTrackIds.has(t.id)"
            :aria-label="`${selectedTrackIds.has(t.id) ? '取消选择' : '选择'}歌曲 ${t.title}`"
            @click="toggleSelectTrack(t.id)"
            @keydown.enter.prevent="toggleSelectTrack(t.id)"
            @keydown.space.prevent="toggleSelectTrack(t.id)"
          >
            <div class="media-list-row__art" aria-hidden="true">
              <div
                v-if="selectedTrackIds.has(t.id)"
                class="absolute top-1 left-1 z-20 w-4 h-4 rounded-full bg-primary text-primary-foreground flex items-center justify-center shadow-md ring-1 ring-background"
              >
                <Check class="w-2.5 h-2.5 stroke-[3]" />
              </div>
              <img
                v-if="coverAvailable('track', t.cover_guid)"
                :src="coverUrl('track', t.cover_guid)"
                :alt="`${t.title} 封面`"
                loading="lazy"
                decoding="async"
                @error="markCoverFailed('track', t.cover_guid)"
              />
              <div v-else class="media-list-row__art-fallback">
                <Disc3 class="h-6 w-6 text-primary/35" />
              </div>
            </div>

            <div class="media-list-row__content">
              <div class="media-list-row__title-line">
                <strong class="media-list-row__title">{{ t.title }}</strong>
                <Badge
                  v-if="isTrackReused(t)"
                  variant="outline"
                  class="shrink-0 px-1.5 py-0 text-[9px] font-medium border-blue-500/35 text-blue-600 dark:text-blue-400 bg-blue-500/10 gap-1"
                >
                  <span class="w-1.5 h-1.5 rounded-full bg-blue-500 inline-block" />
                  <span>复用</span>
                </Badge>
                <Badge variant="secondary" class="shrink-0 px-1.5 py-0 text-[9px] uppercase font-mono">
                  {{ t.codec || 'FLAC' }}
                </Badge>
              </div>
              <p class="media-list-row__subtitle">{{ t.artist }} · 《{{ t.album || '未命名专辑' }}》</p>
              <div class="media-list-row__meta">
                <span>#{{ idx + 1 }}</span>
                <span v-if="t.size">{{ formatBytes(t.size) }}</span>
                <span v-if="t.duration_ms">{{ formatDuration(t.duration_ms) }}</span>
                <span class="media-list-row__path" :title="t.path">{{ t.path }}</span>
              </div>
            </div>

            <div class="media-list-row__desktop-action" @click.stop>
              <Popconfirm
                :title="`从歌单《${props.playlistName}》中移出《${t.title}》？`"
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
                  <label class="mt-2 flex cursor-pointer select-none items-center gap-2 rounded-xl border border-destructive/25 bg-destructive/10 p-2 text-[11px] text-destructive">
                    <Checkbox v-model="removeTrackPhysicalMap[t.id]" />
                    <span>同时从 NAS 硬盘物理彻底删除文件</span>
                  </label>
                </template>
                <Button variant="ghost" size="iconSm" title="从歌单移出" class="hover:bg-destructive/10 hover:text-destructive">
                  <Trash2 class="h-3.5 w-3.5" />
                </Button>
              </Popconfirm>
            </div>
          </article>

          <div class="swipe-list-item__action md:hidden">
            <Popconfirm
              :title="`从歌单《${props.playlistName}》中移出《${t.title}》？`"
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
                <label class="mt-2 flex cursor-pointer select-none items-center gap-2 rounded-xl border border-destructive/25 bg-destructive/10 p-2 text-[11px] text-destructive">
                  <Checkbox v-model="removeTrackPhysicalMap[t.id]" />
                  <span>同时彻底删除本地文件</span>
                </label>
              </template>
              <Button variant="destructive" class="swipe-list-item__delete" title="移出歌单">
                <Trash2 class="h-4 w-4" />
                <span>移出</span>
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
          class="selection-action-bar selection-action-bar--dialog"
        >
          <div class="selection-action-bar__summary">
            <span class="selection-action-bar__pulse" aria-hidden="true" />
            <span class="text-foreground font-medium whitespace-nowrap">
              已选 <strong class="text-primary font-mono text-sm">{{ selectedTrackIds.size }}</strong> 首
            </span>
          </div>
          <div class="selection-action-bar__controls">
            <Button
              variant="ghost"
              size="sm"
              @click="selectedTrackIds = new Set()"
              class="selection-action-bar__button h-8 text-xs text-muted-foreground hover:text-foreground"
            >
              取消
            </Button>
            <Popconfirm
              :title="`确认将选中的 ${selectedTrackIds.size} 首曲目从歌单《${props.playlistName}》移出？`"
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
                <label class="flex cursor-pointer select-none items-center gap-2 rounded-xl border border-destructive/25 bg-destructive/10 p-2 text-[11px] text-destructive mt-2">
                  <Checkbox v-model="batchRemovePhysical" />
                  <span>同时从 NAS 物理彻底删除音频与歌词文件</span>
                </label>
              </template>
              <Button
                variant="destructive"
                size="sm"
                :disabled="isBatchRemoving"
                class="selection-action-bar__button h-8 text-xs flex items-center justify-center gap-1.5"
              >
                <Loader2 v-if="isBatchRemoving" class="w-3 h-3 animate-spin" />
                <Trash2 v-else class="w-3 h-3" />
                <span>移出 {{ selectedTrackIds.size }} 首</span>
              </Button>
            </Popconfirm>
          </div>
        </div>
      </transition>

      <DialogFooter class="p-3 border-t border-border bg-muted/70 flex justify-end">
        <Button
          variant="secondary"
          size="sm"
          @click="emit('update:open', false)"
        >
          完成
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
