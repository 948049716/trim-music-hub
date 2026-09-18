<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue';
import type { LibraryTrack, DuplicateGroup } from '../../types';
import { api } from '../../api';
import { showToast } from '../../composables/useToast';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Popconfirm } from '@/components/ui/popconfirm';
import { Card } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Database,
  Disc3,
  Search,
  Loader2,
  Trash2,
  ArrowUp,
  CheckCircle2,
  Sparkles,
  Layers,
  HardDrive
} from 'lucide-vue-next';

// 视图切换：全部曲目 vs 查重管理
const activeSubTab = ref<'all' | 'duplicates'>('all');

// 1. 全部曲目状态
const searchKw = ref('');
const tracks = ref<LibraryTrack[]>([]);
const totalCount = ref(0);
const page = ref(1);
const limit = 50;
const isInitialLoading = ref(false);
const isLoadingMore = ref(false);
const selectedAllTrackIds = ref<Set<number>>(new Set());

// 2. 查重模式状态
const duplicateKw = ref('');
const duplicateGroups = ref<DuplicateGroup[]>([]);
const duplicateGroupsCount = ref(0);
const duplicateTotalTracks = ref(0);
const isLoadingDuplicates = ref(false);
const selectedDupTrackIds = ref<Set<number>>(new Set());

// 通用状态
const failedCoverGuids = ref<Set<string>>(new Set());
const deletingTrackId = ref<number | null>(null);
const isBatchDeleting = ref(false);

const scrollContainerRef = ref<HTMLElement | null>(null);
const dupScrollContainerRef = ref<HTMLElement | null>(null);
const sentinelRef = ref<HTMLElement | null>(null);
const showBackToTop = ref(false);
const hasActiveSelection = computed(() =>
  activeSubTab.value === 'all'
    ? selectedAllTrackIds.value.size > 0
    : selectedDupTrackIds.value.size > 0
);

const hasMore = computed(() => {
  return tracks.value.length < totalCount.value;
});

let observer: IntersectionObserver | null = null;

// ================= 全部曲目逻辑 =================
async function handleSearch(resetPage = true) {
  if (resetPage) {
    page.value = 1;
    tracks.value = [];
    selectedAllTrackIds.value = new Set();
  }
  isInitialLoading.value = true;
  try {
    const res = await api.searchLibraryTracks(searchKw.value.trim(), 1, limit);
    if (res.ok) {
      tracks.value = res.data.list || [];
      totalCount.value = res.data.total || 0;
      nextTick(() => {
        if (scrollContainerRef.value) {
          scrollContainerRef.value.scrollTop = 0;
        }
        setupObserver();
      });
    } else {
      showToast('曲库检索失败', 'error');
    }
  } catch (e: any) {
    showToast(`检索曲库失败：${e.message}`, 'error');
  } finally {
    isInitialLoading.value = false;
  }
}

async function loadMore() {
  if (isInitialLoading.value || isLoadingMore.value || !hasMore.value) return;

  isLoadingMore.value = true;
  const nextPage = page.value + 1;
  try {
    const res = await api.searchLibraryTracks(searchKw.value.trim(), nextPage, limit);
    if (res.ok && res.data.list?.length) {
      page.value = nextPage;
      tracks.value.push(...res.data.list);
      totalCount.value = res.data.total || totalCount.value;
    }
  } catch (e: any) {
    showToast(`加载更多失败: ${e.message}`, 'error');
  } finally {
    isLoadingMore.value = false;
  }
}

function toggleSelectAllTracks() {
  if (selectedAllTrackIds.value.size === tracks.value.length && tracks.value.length > 0) {
    selectedAllTrackIds.value = new Set();
  } else {
    selectedAllTrackIds.value = new Set(tracks.value.map(t => t.id));
  }
}

function toggleTrackSelect(id: number) {
  const next = new Set(selectedAllTrackIds.value);
  if (next.has(id)) {
    next.delete(id);
  } else {
    next.add(id);
  }
  selectedAllTrackIds.value = next;
}

// ================= 查重模式逻辑 =================
async function loadDuplicates() {
  isLoadingDuplicates.value = true;
  try {
    const res = await api.getDuplicateTracks(duplicateKw.value.trim());
    if (res.ok) {
      duplicateGroups.value = res.data.groups || [];
      duplicateGroupsCount.value = res.data.groups_count || 0;
      duplicateTotalTracks.value = res.data.total_tracks || 0;
    } else {
      showToast('获取查重数据失败', 'error');
    }
  } catch (e: any) {
    showToast(`查找重复歌曲失败：${e.message}`, 'error');
  } finally {
    isLoadingDuplicates.value = false;
  }
}

// 查找组内最高品质曲目（优先体积最大 / FLAC）
function getBestTrackInGroup(group: DuplicateGroup): LibraryTrack | null {
  if (!group.tracks || group.tracks.length === 0) return null;
  return [...group.tracks].sort((a, b) => {
    const sizeA = a.size || a.file_size || 0;
    const sizeB = b.size || b.file_size || 0;
    return sizeB - sizeA;
  })[0];
}

// 智能标记所有非最高品质副本
function smartSelectSuboptimalDuplicates() {
  const newSet = new Set<number>();
  for (const g of duplicateGroups.value) {
    const best = getBestTrackInGroup(g);
    for (const t of g.tracks) {
      if (best && t.id === best.id) {
        // 保留最高品质
        continue;
      }
      newSet.add(t.id);
    }
  }
  selectedDupTrackIds.value = newSet;
  showToast(`已选中 ${newSet.size} 首较差版本，每组保留音质最佳的一首。`, 'success');
}

// 智能标记历史旧版本（保留最新添加的版本）
function smartSelectOlderDuplicates() {
  const newSet = new Set<number>();
  for (const g of duplicateGroups.value) {
    if (!g.tracks || g.tracks.length <= 1) continue;
    const sorted = [...g.tracks].sort((a, b) => {
      const timeA = new Date(a.created_at || 0).getTime();
      const timeB = new Date(b.created_at || 0).getTime();
      return timeB - timeA;
    });
    // sorted[0] 是最新添加的，标记其余旧版本
    for (let i = 1; i < sorted.length; i++) {
      newSet.add(sorted[i].id);
    }
  }
  selectedDupTrackIds.value = newSet;
  showToast(`已选中 ${newSet.size} 首较早版本，每组保留最新的一首。`, 'success');
}

// 单组快捷：保留本组最高音质
function selectGroupSuboptimal(group: DuplicateGroup) {
  const best = getBestTrackInGroup(group);
  const next = new Set(selectedDupTrackIds.value);
  for (const t of group.tracks) {
    if (best && t.id === best.id) {
      next.delete(t.id);
    } else {
      next.add(t.id);
    }
  }
  selectedDupTrackIds.value = next;
}

// 单组快捷：切换全选本组
function toggleGroupAll(group: DuplicateGroup) {
  const next = new Set(selectedDupTrackIds.value);
  const allGroupSelected = group.tracks.every(t => next.has(t.id));
  for (const t of group.tracks) {
    if (allGroupSelected) {
      next.delete(t.id);
    } else {
      next.add(t.id);
    }
  }
  selectedDupTrackIds.value = next;
}

function toggleDupTrackSelect(id: number) {
  const next = new Set(selectedDupTrackIds.value);
  if (next.has(id)) {
    next.delete(id);
  } else {
    next.add(id);
  }
  selectedDupTrackIds.value = next;
}

function clearDupSelection() {
  selectedDupTrackIds.value = new Set();
}

// 估算选中的总容量
const selectedDupTotalBytes = computed(() => {
  let bytes = 0;
  const trackMap = new Map<number, LibraryTrack>();
  for (const g of duplicateGroups.value) {
    for (const t of g.tracks) {
      trackMap.set(t.id, t);
    }
  }
  for (const id of selectedDupTrackIds.value) {
    const t = trackMap.get(id);
    if (t) {
      bytes += t.size || t.file_size || 0;
    }
  }
  return bytes;
});

const selectedAllTotalBytes = computed(() => {
  let bytes = 0;
  for (const t of tracks.value) {
    if (selectedAllTrackIds.value.has(t.id)) {
      bytes += t.size || t.file_size || 0;
    }
  }
  return bytes;
});

// ================= 批量与单曲删除 =================
async function confirmDeleteTrack(t: LibraryTrack) {
  deletingTrackId.value = t.id;
  try {
    const res = await api.deleteTrack(t.id, true);
    if (res.ok) {
      showToast(`已删除“${t.title}”及本地文件。`, 'success');
      // 更新全部曲目
      tracks.value = tracks.value.filter(item => item.id !== t.id);
      totalCount.value = Math.max(0, totalCount.value - 1);
      selectedAllTrackIds.value.delete(t.id);

      // 更新查重曲目
      for (const g of duplicateGroups.value) {
        g.tracks = g.tracks.filter(item => item.id !== t.id);
        g.count = g.tracks.length;
      }
      duplicateGroups.value = duplicateGroups.value.filter(g => g.tracks.length > 1);
      duplicateGroupsCount.value = duplicateGroups.value.length;
      selectedDupTrackIds.value.delete(t.id);
    } else {
      showToast(res.error || '删除失败', 'error');
    }
  } catch (e: any) {
    showToast(`删除歌曲失败：${e.message}`, 'error');
  } finally {
    deletingTrackId.value = null;
  }
}

async function handleBatchDelete(mode: 'all' | 'duplicates') {
  const targetIds = mode === 'all'
    ? Array.from(selectedAllTrackIds.value)
    : Array.from(selectedDupTrackIds.value);

  if (targetIds.length === 0) return;

  isBatchDeleting.value = true;
  try {
    const res = await api.batchDeleteTracks(targetIds, true);
    if (res.ok) {
      showToast(`已删除 ${res.deleted_count || targetIds.length} 首歌曲及本地文件。`, 'success');
      const deletedSet = new Set(targetIds);

      // 同步本地曲库列表
      tracks.value = tracks.value.filter(t => !deletedSet.has(t.id));
      totalCount.value = Math.max(0, totalCount.value - (res.deleted_count || targetIds.length));
      selectedAllTrackIds.value = new Set();

      // 同步查重列表
      for (const g of duplicateGroups.value) {
        g.tracks = g.tracks.filter(t => !deletedSet.has(t.id));
        g.count = g.tracks.length;
      }
      duplicateGroups.value = duplicateGroups.value.filter(g => g.tracks.length > 1);
      duplicateGroupsCount.value = duplicateGroups.value.length;
      selectedDupTrackIds.value = new Set();
    } else {
      showToast(res.error || '批量删除失败', 'error');
    }
  } catch (e: any) {
    showToast(`批量删除失败：${e.message}`, 'error');
  } finally {
    isBatchDeleting.value = false;
  }
}

// ================= 辅助函数与生命周期 =================
function onScroll(e: Event) {
  const el = e.target as HTMLElement;
  if (!el) return;

  showBackToTop.value = el.scrollTop > 300;

  const distanceToBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
  if (distanceToBottom < 160 && hasMore.value && !isLoadingMore.value && !isInitialLoading.value) {
    loadMore();
  }
}

function onDuplicateScroll(e: Event) {
  const el = e.target as HTMLElement;
  showBackToTop.value = Boolean(el && el.scrollTop > 300);
}

function scrollToTop() {
  if (activeSubTab.value === 'all') {
    scrollContainerRef.value?.scrollTo({ top: 0, behavior: 'smooth' });
  } else {
    dupScrollContainerRef.value?.scrollTo({ top: 0, behavior: 'smooth' });
  }
}

function setupObserver() {
  if (observer) {
    observer.disconnect();
    observer = null;
  }

  if (!sentinelRef.value || !scrollContainerRef.value) return;

  observer = new IntersectionObserver(
    (entries) => {
      if (entries[0]?.isIntersecting) {
        loadMore();
      }
    },
    {
      root: scrollContainerRef.value,
      rootMargin: '120px',
      threshold: 0.05
    }
  );

  observer.observe(sentinelRef.value);
}

function formatBytes(bytes?: number) {
  if (!bytes) return '--';
  const mb = bytes / (1024 * 1024);
  if (mb >= 1024) {
    return `${(mb / 1024).toFixed(2)} GB`;
  }
  return `${mb.toFixed(1)} MB`;
}

function formatDuration(ms?: number) {
  if (!ms) return '00:00';
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

function trackCoverUrl(guid?: string) {
  return guid ? `/api/covers/track/${encodeURIComponent(guid)}?size=160` : '';
}

function trackCoverAvailable(guid?: string) {
  return Boolean(guid) && !failedCoverGuids.value.has(guid || '');
}

function markTrackCoverFailed(guid?: string) {
  if (!guid) return;
  const next = new Set(failedCoverGuids.value);
  next.add(guid);
  failedCoverGuids.value = next;
}

// 监听 Tab 切换
watch(activeSubTab, (val) => {
  showBackToTop.value = false;
  if (val === 'duplicates' && duplicateGroups.value.length === 0 && !isLoadingDuplicates.value) {
    loadDuplicates();
  }
});

onMounted(() => {
  handleSearch(true);
  // 预取查重统计
  api.getDuplicateTracks('').then(res => {
    if (res.ok) {
      duplicateGroupsCount.value = res.data.groups_count || 0;
      duplicateTotalTracks.value = res.data.total_tracks || 0;
    }
  }).catch(() => {});
});

onUnmounted(() => {
  if (observer) {
    observer.disconnect();
    observer = null;
  }
});
</script>

<template>
  <div class="space-y-4">
    <!-- Top Control Bar Card (固定顶部) -->
    <Card class="bg-card/80 border-border backdrop-blur-xl shadow-xl p-3 sm:p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shrink-0">
      <!-- Sub-Tabs Switch -->
      <div class="flex items-center gap-1.5 p-1 bg-background/60 border border-border/80 rounded-lg w-fit">
        <Button variant="ghost"
          type="button"
          @click="activeSubTab = 'all'"
          :class="[
            'h-auto px-3 py-1.5 rounded-md text-xs font-medium transition-all flex items-center gap-1.5',
            activeSubTab === 'all'
              ? 'bg-primary text-primary-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground hover:bg-muted'
          ]"
        >
          <Database class="w-3.5 h-3.5" />
          <span>全部曲目</span>
          <span class="text-[10px] px-1.5 py-0.2 rounded-full bg-muted/60 font-mono">
            {{ totalCount }}
          </span>
        </Button>

        <Button variant="ghost"
          type="button"
          @click="activeSubTab = 'duplicates'"
          :class="[
            'h-auto px-3 py-1.5 rounded-md text-xs font-medium transition-all flex items-center gap-1.5',
            activeSubTab === 'duplicates'
              ? 'bg-primary text-primary-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground hover:bg-muted'
          ]"
        >
          <Layers class="w-3.5 h-3.5" />
          <span>重复歌曲</span>
          <span
            v-if="duplicateGroupsCount > 0"
            class="text-[10px] px-1.5 py-0.2 rounded-full font-mono bg-amber-500/20 text-amber-700 dark:text-amber-300 border border-amber-500/30"
          >
            {{ duplicateGroupsCount }} 组
          </span>
        </Button>
      </div>

      <!-- Search Box (Contextual based on Active Tab) -->
      <div class="flex items-center gap-2 max-w-md w-full sm:w-auto">
        <!-- Tab 1: All Tracks Search -->
        <form
          v-if="activeSubTab === 'all'"
          @submit.prevent="handleSearch(true)"
          class="flex items-center gap-2 w-full sm:w-auto"
        >
          <div class="relative flex-1 sm:w-72">
            <Search class="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2 z-10" />
            <Input
              v-model="searchKw"
              type="text"
              placeholder="搜索歌名、歌手或专辑"
              class="pl-9 h-9 text-xs"
            />
          </div>
          <Button
            type="submit"
            variant="default"
            size="sm"
            :disabled="isInitialLoading"
            class="shrink-0 flex items-center gap-1.5 h-9"
          >
            <Loader2 v-if="isInitialLoading" class="w-3.5 h-3.5 animate-spin" />
            <Search v-else class="w-3.5 h-3.5" />
            <span>检索</span>
          </Button>
        </form>

        <!-- Tab 2: Duplicate Search -->
        <form
          v-else
          @submit.prevent="loadDuplicates"
          class="flex items-center gap-2 w-full sm:w-auto"
        >
          <div class="relative flex-1 sm:w-72">
            <Search class="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2 z-10" />
            <Input
              v-model="duplicateKw"
              type="text"
              placeholder="搜索重复歌曲"
              class="pl-9 h-9 text-xs"
            />
          </div>
          <Button
            type="submit"
            variant="default"
            size="sm"
            :disabled="isLoadingDuplicates"
            class="shrink-0 flex items-center gap-1.5 h-9"
          >
            <Loader2 v-if="isLoadingDuplicates" class="w-3.5 h-3.5 animate-spin" />
            <Search v-else class="w-3.5 h-3.5" />
            <span>查重</span>
          </Button>
        </form>
      </div>
    </Card>

    <!-- ==================== VIEW 1: 全部曲目 ==================== -->
    <Card
      v-if="activeSubTab === 'all'"
      class="relative bg-card/80 border-border backdrop-blur-xl shadow-2xl p-2.5 sm:p-4 md:p-5 flex flex-col h-[calc(100vh-270px)] min-h-[500px]"
    >
      <!-- 固定的列表头部信息栏 (移动端自适应紧凑) -->
      <div class="flex items-center justify-between pb-2.5 sm:pb-3 border-b border-border/80 mb-2.5 sm:mb-3 text-xs shrink-0 gap-2">
        <div class="flex items-center gap-2 sm:gap-3 flex-wrap min-w-0">
          <Button
            variant="ghost"
            size="sm"
            class="h-7 px-2 text-muted-foreground text-[11px] sm:text-xs"
            :disabled="tracks.length === 0"
            @click="toggleSelectAllTracks"
          >
            {{ selectedAllTrackIds.size === tracks.length && tracks.length > 0 ? '取消全选' : '全选' }}
          </Button>
          <span class="text-muted-foreground/50">|</span>
          <span class="text-muted-foreground hidden sm:inline">
            匹配总数: <strong class="text-foreground font-mono text-sm">{{ totalCount }}</strong> 首
          </span>
          <span class="text-muted-foreground sm:hidden text-[11px]">
            共 <strong class="text-foreground font-mono">{{ totalCount }}</strong> 首
          </span>
          <span class="text-muted-foreground/50 hidden sm:inline">|</span>
          <span class="text-muted-foreground hidden sm:inline">
            已载入: <strong class="text-primary font-mono">{{ tracks.length }}</strong> 首
          </span>
          <span v-if="selectedAllTrackIds.size > 0" class="text-amber-600 dark:text-amber-400 font-medium text-[11px] sm:text-xs">
            已选 {{ selectedAllTrackIds.size }} 首 <span class="hidden sm:inline">({{ formatBytes(selectedAllTotalBytes) }})</span>
          </span>
        </div>
        <div v-if="!hasMore && tracks.length > 0" class="flex items-center gap-1.5 text-[10px] sm:text-[11px] shrink-0">
          <span class="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
            <CheckCircle2 class="w-3.5 h-3.5" />
            <span class="hidden sm:inline">已全部载入</span>
          </span>
        </div>
      </div>

      <!-- 首次加载骨架/等待状态 -->
      <div v-if="isInitialLoading" class="flex-1 flex flex-col items-center justify-center py-16 text-muted-foreground space-y-2">
        <Loader2 class="w-8 h-8 animate-spin text-primary" />
        <p class="text-xs">正在从飞牛曲库检索曲目...</p>
      </div>

      <!-- 无结果状态 -->
      <div v-else-if="tracks.length === 0" class="flex-1 flex flex-col items-center justify-center py-16 text-muted-foreground space-y-2">
        <Database class="w-12 h-12 stroke-1 text-muted-foreground/55" />
        <p class="text-xs">未找到符合条件的音乐</p>
      </div>

      <!-- 独立可滚动曲目列表容器 -->
      <div
        v-else
        ref="scrollContainerRef"
        @scroll="onScroll"
        class="flex-1 overflow-y-auto overflow-x-hidden pr-2 space-y-2 select-text"
      >
        <div
          v-for="t in tracks"
          :key="t.id"
          class="swipe-list-item"
        >
          <article
            :class="[
              'media-list-row media-list-row--track',
              { 'media-list-row--selected': selectedAllTrackIds.has(t.id) }
            ]"
            role="button"
            tabindex="0"
            :aria-pressed="selectedAllTrackIds.has(t.id)"
            :aria-label="`${selectedAllTrackIds.has(t.id) ? '取消选择' : '选择'}歌曲 ${t.title}`"
            @click="toggleTrackSelect(t.id)"
            @keydown.enter.prevent="toggleTrackSelect(t.id)"
            @keydown.space.prevent="toggleTrackSelect(t.id)"
          >
            <div class="media-list-row__art" aria-hidden="true">
              <img
                v-if="trackCoverAvailable(t.cover_guid)"
                :src="trackCoverUrl(t.cover_guid)"
                :alt="`${t.title} 封面`"
                loading="lazy"
                decoding="async"
                @error="markTrackCoverFailed(t.cover_guid)"
              />
              <div v-else class="media-list-row__art-fallback">
                <Disc3 class="h-6 w-6 text-primary/35" />
              </div>
            </div>

            <div class="media-list-row__content">
              <div class="media-list-row__title-line">
                <strong class="media-list-row__title">{{ t.title }}</strong>
                <Badge variant="secondary" class="shrink-0 px-1.5 py-0 text-[9px] uppercase font-mono">
                  {{ t.codec || t.file_type || 'FLAC' }}
                </Badge>
              </div>
              <p class="media-list-row__subtitle">{{ t.artist }} · 《{{ t.album || '未命名专辑' }}》</p>
              <div class="media-list-row__meta">
                <span v-if="t.file_size || t.size">{{ formatBytes(t.file_size || t.size) }}</span>
                <span v-if="t.duration_ms">{{ formatDuration(t.duration_ms) }}</span>
                <span class="media-list-row__path" :title="t.path">{{ t.path }}</span>
              </div>
            </div>

            <div class="media-list-row__desktop-action" @click.stop>
              <Popconfirm
                :title="`彻底删除《${t.title}》？`"
                description="将同时从飞牛曲库与 NAS 硬盘物理彻底删除此音频文件。"
                :detail="`路径: ${t.path}`"
                confirmText="彻底删除"
                :danger="true"
                :loading="deletingTrackId === t.id"
                side="left"
                align="center"
                @confirm="confirmDeleteTrack(t)"
              >
                <Button variant="ghost" size="iconSm" title="删除歌曲" class="hover:bg-destructive/10 hover:text-destructive">
                  <Trash2 class="h-4 w-4" />
                </Button>
              </Popconfirm>
            </div>
          </article>

          <div class="swipe-list-item__action md:hidden">
            <Popconfirm
              :title="`彻底删除《${t.title}》？`"
              description="将同时从飞牛曲库与 NAS 硬盘物理彻底删除此音频文件。"
              :detail="`路径: ${t.path}`"
              confirmText="彻底删除"
              :danger="true"
              :loading="deletingTrackId === t.id"
              side="left"
              align="center"
              @confirm="confirmDeleteTrack(t)"
            >
              <Button variant="destructive" class="swipe-list-item__delete" title="删除歌曲">
                <Trash2 class="h-4 w-4" />
                <span>删除</span>
              </Button>
            </Popconfirm>
          </div>
        </div>

        <!-- 滚动触底 Sentinel 哨兵元素 -->
        <div ref="sentinelRef" class="py-3 text-center">
          <div v-if="isLoadingMore" class="flex items-center justify-center gap-2 text-xs text-muted-foreground py-2">
            <Loader2 class="w-4 h-4 animate-spin text-primary" />
            <span>正在加载更多曲目...</span>
          </div>
          <div v-else-if="!hasMore && tracks.length > 0" class="py-3 text-center text-[11px] text-muted-foreground/75">
            — 已加载全部 {{ totalCount }} 首曲目 —
          </div>
        </div>
      </div>

      <!-- 底部浮动批量操作栏（全部曲目） -->
      <transition
        enter-active-class="transition duration-200 ease-out"
        enter-from-class="opacity-0 translate-y-4 scale-95"
        enter-to-class="opacity-100 translate-y-0 scale-100"
        leave-active-class="transition duration-150 ease-in"
        leave-from-class="opacity-100 translate-y-0 scale-100"
        leave-to-class="opacity-0 translate-y-4 scale-95"
      >
        <div
          v-if="selectedAllTrackIds.size > 0"
          class="selection-action-bar selection-action-bar--page"
        >
          <div class="selection-action-bar__summary">
            <span class="selection-action-bar__pulse" aria-hidden="true" />
            <span class="text-foreground font-medium whitespace-nowrap">
              已选 <strong class="text-primary font-mono text-sm">{{ selectedAllTrackIds.size }}</strong> 首
            </span>
            <span class="selection-action-bar__size">{{ formatBytes(selectedAllTotalBytes) }}</span>
          </div>

          <div class="selection-action-bar__controls">
            <Button
              variant="ghost"
              size="sm"
              @click="selectedAllTrackIds = new Set()"
              class="selection-action-bar__button h-8 text-xs text-muted-foreground hover:text-foreground"
            >
              取消
            </Button>

            <Popconfirm
              :title="`批量彻底删除选中的 ${selectedAllTrackIds.size} 首曲目？`"
              description="将同时从飞牛曲库与 NAS 硬盘物理删除选中的所有音频文件及歌词，此操作不可恢复。"
              :detail="`预计释放空间: ${formatBytes(selectedAllTotalBytes)}`"
              confirmText="确认彻底批量删除"
              :danger="true"
              :loading="isBatchDeleting"
              side="top"
              align="end"
              widthClass="w-84 sm:w-[380px]"
              @confirm="handleBatchDelete('all')"
            >
              <Button
                variant="destructive"
                size="sm"
                :disabled="isBatchDeleting"
                class="selection-action-bar__button h-8 text-xs flex items-center justify-center gap-1.5 shadow-lg shadow-rose-950/40"
              >
                <Loader2 v-if="isBatchDeleting" class="w-3.5 h-3.5 animate-spin" />
                <Trash2 v-else class="w-3.5 h-3.5" />
                <span>删除 {{ selectedAllTrackIds.size }} 首</span>
              </Button>
            </Popconfirm>
          </div>
        </div>
      </transition>
    </Card>

    <!-- ==================== VIEW 2: 查重与多版本管理 ==================== -->
    <Card
      v-else
      class="relative bg-card/80 border-border backdrop-blur-xl shadow-2xl p-2.5 sm:p-4 md:p-5 flex flex-col h-[calc(100vh-270px)] min-h-[500px]"
    >
      <!-- 查重工具控制面板 -->
      <div class="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-border/80 mb-3 text-xs gap-3 shrink-0">
        <div class="flex flex-wrap items-center gap-2.5">
          <span class="text-foreground/85 font-medium flex items-center gap-1.5">
            <Layers class="w-4 h-4 text-amber-600 dark:text-amber-400" />
            <span>检测到重复曲目:</span>
            <strong class="text-amber-600 dark:text-amber-400 font-mono text-sm">{{ duplicateGroupsCount }}</strong> 组
            <span class="text-muted-foreground font-normal font-mono">({{ duplicateTotalTracks }} 首文件)</span>
          </span>

          <span class="text-muted-foreground/75 hidden sm:inline">|</span>

          <!-- 智能一键工具 -->
          <div class="flex items-center gap-1.5">
            <Button
              variant="secondary"
              size="sm"
              @click="smartSelectSuboptimalDuplicates"
              class="h-7 text-[11px] px-2.5 bg-amber-500/10 hover:bg-amber-500/20 text-amber-700 dark:text-amber-300 border border-amber-500/30 flex items-center gap-1"
              title="为每组曲目自动保留最高品质/最大体积版本，勾选其余副本待删除"
            >
              <Sparkles class="w-3 h-3 text-amber-600 dark:text-amber-400" />
              <span>选中较差版本</span>
            </Button>

            <Button
              variant="ghost"
              size="sm"
              @click="smartSelectOlderDuplicates"
              class="h-7 text-[11px] px-2 text-muted-foreground hover:text-foreground"
              title="保留每组最新添加的曲目，勾选旧版本待删除"
            >
              <span>保留最新</span>
            </Button>

            <Button
              v-if="selectedDupTrackIds.size > 0"
              variant="ghost"
              size="sm"
              @click="clearDupSelection"
              class="h-7 text-[11px] px-2 text-muted-foreground hover:text-destructive"
            >
              <span>清空勾选</span>
            </Button>
          </div>
        </div>

        <div class="flex items-center gap-2 text-muted-foreground text-[11px]">
          <span v-if="selectedDupTrackIds.size > 0" class="text-destructive font-medium">
            已勾选待清理: {{ selectedDupTrackIds.size }} 首 ({{ formatBytes(selectedDupTotalBytes) }})
          </span>
          <span v-else class="text-muted-foreground">
            勾选待清理副本，系统将保留未勾选项
          </span>
        </div>
      </div>

      <!-- 加载中 -->
      <div v-if="isLoadingDuplicates" class="flex-1 flex flex-col items-center justify-center py-16 text-muted-foreground space-y-2">
        <Loader2 class="w-8 h-8 animate-spin text-primary" />
        <p class="text-xs">正在检查重复歌曲…</p>
      </div>

      <!-- 无重复状态 -->
      <div v-else-if="duplicateGroups.length === 0" class="flex-1 flex flex-col items-center justify-center py-16 text-muted-foreground space-y-2">
        <CheckCircle2 class="w-12 h-12 stroke-1 text-emerald-500" />
        <p class="text-sm text-foreground/85 font-medium">没有发现重复歌曲</p>
        <p class="text-xs text-muted-foreground">当前范围内的歌曲都只有一个版本。</p>
      </div>

      <!-- 重复曲目分组列表 -->
      <div
        v-else
        ref="dupScrollContainerRef"
        @scroll="onDuplicateScroll"
        class="flex-1 overflow-y-auto pr-2 space-y-4 select-text"
      >
        <div
          v-for="g in duplicateGroups"
          :key="g.key"
          class="rounded-xl border border-border/80 bg-background/40 overflow-hidden shadow-sm"
        >
          <!-- 分组卡片头部 -->
          <div class="flex flex-col sm:flex-row sm:items-center justify-between px-4 py-2.5 bg-card/90 border-b border-border/60 gap-2">
            <div class="flex items-center gap-2.5 overflow-hidden">
              <Badge variant="outline" class="text-[11px] font-mono border-amber-500/40 text-amber-700 dark:text-amber-300 bg-amber-500/10 px-2 py-0.5">
                {{ g.count }} 个副本
              </Badge>
              <div class="font-bold text-foreground truncate text-sm flex items-center gap-2">
                <span>{{ g.title }}</span>
                <span class="text-xs text-muted-foreground font-normal">— {{ g.artist }}</span>
              </div>
            </div>

            <!-- 本组快捷操作 -->
            <div class="flex items-center gap-1.5 shrink-0">
              <Button
                variant="ghost"
                size="sm"
                @click="selectGroupSuboptimal(g)"
                class="h-6 px-2 text-[10px] text-amber-700 dark:text-amber-300 hover:text-amber-200 hover:bg-amber-500/10"
                title="保留本组音质最高版本，标记其余版本待删除"
              >
                <Sparkles class="w-3 h-3 mr-1" />
                <span>保留最佳</span>
              </Button>
              <Button
                variant="ghost"
                size="sm"
                @click="toggleGroupAll(g)"
                class="h-6 px-2 text-[10px] text-muted-foreground hover:text-foreground"
              >
                <span>{{ g.tracks.every(t => selectedDupTrackIds.has(t.id)) ? '取消勾选' : '全选此组' }}</span>
              </Button>
            </div>
          </div>

          <!-- 分组内版本列表 -->
          <div class="p-2 space-y-1">
            <div
              v-for="t in g.tracks"
              :key="t.id"
              :class="[
                'flex items-center justify-between gap-3 p-2.5 rounded-lg transition-all text-xs border border-transparent',
                selectedDupTrackIds.has(t.id)
                  ? 'bg-rose-500/15 !border-rose-500/40'
                  : 'bg-muted/40 hover:bg-muted/70'
              ]"
            >
              <div class="flex items-center gap-3 overflow-hidden flex-1">
                <!-- 勾选框：勾选代表标记待删除 -->
                <Checkbox
                  :checked="selectedDupTrackIds.has(t.id)"
                  @update:checked="toggleDupTrackSelect(t.id)"
                  class="shrink-0"
                />

                <!-- 封面小图 -->
                <div class="relative h-10 w-10 shrink-0 overflow-hidden rounded-lg border border-border bg-muted/70 flex items-center justify-center">
                  <img
                    v-if="trackCoverAvailable(t.cover_guid)"
                    :src="trackCoverUrl(t.cover_guid)"
                    :alt="`${t.title} 封面`"
                    loading="lazy"
                    decoding="async"
                    class="absolute inset-0 h-full w-full object-cover"
                    @error="markTrackCoverFailed(t.cover_guid)"
                  />
                                  <Disc3 v-else class="h-5 w-5 text-primary/35" />
                </div>

                <!-- 详细信息 -->
                <div class="overflow-hidden flex-1">
                  <div class="flex items-center gap-2 truncate">
                    <span class="font-medium text-foreground">{{ t.title }}</span>
                    <Badge variant="secondary" class="text-[10px] uppercase font-mono px-1.5 py-0">
                      {{ t.codec || 'FLAC' }}
                    </Badge>
                    <span class="text-[10px] text-primary font-mono">
                      {{ formatBytes(t.file_size || t.size) }}
                    </span>
                    <span v-if="t.duration_ms" class="text-[10px] text-muted-foreground font-mono">
                      {{ formatDuration(t.duration_ms) }}
                    </span>

                    <!-- 状态徽章 -->
                    <Badge
                      v-if="selectedDupTrackIds.has(t.id)"
                      variant="destructive"
                      class="text-[9px] px-1.5 py-0 font-normal"
                    >
                      待清理副本
                    </Badge>
                    <Badge
                      v-else-if="t.id === getBestTrackInGroup(g)?.id"
                      variant="secondary"
                      class="text-[9px] px-1.5 py-0 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 bg-emerald-500/10"
                    >
                      ★ 推荐保留 (最佳)
                    </Badge>
                    <Badge
                      v-else
                      variant="secondary"
                      class="text-[9px] px-1.5 py-0 text-muted-foreground"
                    >
                      保留
                    </Badge>
                  </div>

                  <div class="text-muted-foreground truncate mt-0.5 text-[11px]">
                    所属专辑: 《{{ t.album || '未命名专辑' }}》
                    <span v-if="t.created_at" class="text-muted-foreground ml-2 font-mono text-[10px]">
                      录入时间: {{ t.created_at.slice(0, 10) }}
                    </span>
                  </div>
                  <div class="text-[10px] text-muted-foreground font-mono truncate mt-0.5">
                    {{ t.path }}
                  </div>
                </div>
              </div>

              <!-- 单曲立即删除 -->
              <Popconfirm
                :title="`彻底删除此副本？`"
                description="将从飞牛曲库和 NAS 硬盘物理彻底删除此副本音频文件。"
                :detail="`路径: ${t.path}`"
                confirmText="删除此副本"
                :danger="true"
                :loading="deletingTrackId === t.id"
                side="left"
                align="center"
                @confirm="confirmDeleteTrack(t)"
              >
                <Button
                  variant="ghost"
                  size="icon"
                  title="删除此副本"
                  class="text-muted-foreground hover:text-destructive hover:bg-destructive/10 shrink-0 h-8 w-8"
                >
                  <Trash2 class="w-3.5 h-3.5" />
                </Button>
              </Popconfirm>
            </div>
          </div>
        </div>
      </div>

      <!-- 底部浮动批量操作栏（查重模式） -->
      <transition
        enter-active-class="transition duration-200 ease-out"
        enter-from-class="opacity-0 translate-y-4 scale-95"
        enter-to-class="opacity-100 translate-y-0 scale-100"
        leave-active-class="transition duration-150 ease-in"
        leave-from-class="opacity-100 translate-y-0 scale-100"
        leave-to-class="opacity-0 translate-y-4 scale-95"
      >
        <div
          v-if="selectedDupTrackIds.size > 0"
          class="selection-action-bar selection-action-bar--page selection-action-bar--danger"
        >
          <div class="selection-action-bar__summary">
            <span class="selection-action-bar__pulse" aria-hidden="true" />
            <span class="text-foreground font-medium whitespace-nowrap">
              已选 <strong class="text-destructive font-mono text-sm">{{ selectedDupTrackIds.size }}</strong> 个副本
            </span>
            <span class="selection-action-bar__size text-amber-700 dark:text-amber-300">
              {{ formatBytes(selectedDupTotalBytes) }}
            </span>
          </div>

          <div class="selection-action-bar__controls">
            <Button
              variant="ghost"
              size="sm"
              @click="clearDupSelection"
              class="selection-action-bar__button h-8 text-xs text-muted-foreground hover:text-foreground"
            >
              取消
            </Button>

            <Popconfirm
              :title="`彻底清理选中的 ${selectedDupTrackIds.size} 首冗余副本？`"
              description="将同时从飞牛官方曲库与 NAS 硬盘物理彻底删除选中的所有副本文件与歌词，此操作不可恢复。"
              :detail="`预计释放磁盘空间: ${formatBytes(selectedDupTotalBytes)}`"
              confirmText="立即彻底清理"
              :danger="true"
              :loading="isBatchDeleting"
              side="top"
              align="end"
              widthClass="w-84 sm:w-[380px]"
              @confirm="handleBatchDelete('duplicates')"
            >
              <Button
                variant="destructive"
                size="sm"
                :disabled="isBatchDeleting"
                class="selection-action-bar__button h-8 text-xs flex items-center justify-center gap-1.5 shadow-lg shadow-rose-950/50 bg-rose-600 hover:bg-rose-500"
              >
                <Loader2 v-if="isBatchDeleting" class="w-3.5 h-3.5 animate-spin" />
                <Trash2 v-else class="w-3.5 h-3.5" />
                <span>清理 {{ selectedDupTrackIds.size }} 个</span>
              </Button>
            </Popconfirm>
          </div>
        </div>
      </transition>
    </Card>

    <!-- 回到顶部悬浮按钮 -->
    <transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0 scale-95 translate-y-2"
      enter-to-class="opacity-100 scale-100 translate-y-0"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="opacity-100 scale-100 translate-y-0"
      leave-to-class="opacity-0 scale-95 translate-y-2"
    >
      <Button
        v-if="showBackToTop"
        @click="scrollToTop"
        variant="secondary"
        size="icon"
        :class="[
          'library-back-to-top shadow-xl rounded-full border border-border/80 bg-card/90 backdrop-blur text-foreground/85 hover:text-foreground h-10 w-10',
          { 'library-back-to-top--with-selection': hasActiveSelection }
        ]"
        title="回到顶部"
      >
        <ArrowUp class="w-4 h-4" />
      </Button>
    </transition>
  </div>
</template>
