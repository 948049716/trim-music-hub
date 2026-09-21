<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import type { HistoryItem } from '../../types';
import { api } from '../../api';
import { showToast } from '../../composables/useToast';
import PlaylistTracksModal from '../modals/PlaylistTracksModal.vue';
import BatchActionBar from '@/components/ui/BatchActionBar.vue';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { SpringTabs, type SpringTabItem } from '@/components/ui/tabs';
import { Popconfirm } from '@/components/ui/popconfirm';
import { EmptyState, LoadingState } from '@/components/ui/state';
import { ListSentinel, PullRefreshList } from '@/components/ui/list';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent
} from '@/components/ui/card';
import {
  History,
  Trash2,
  Clock,
  Check,
  ArrowDownToLine,
  XCircle,
  RefreshCw,
  ListMusic,
  Disc3,
  Search,
  CheckCircle2,
  ChevronRight,
  Loader2
} from 'lucide-vue-next';

const history = ref<HistoryItem[]>([]);
const isLoading = ref(false);
const activeFilter = ref<'all' | 'playlist' | 'song'>('all');
const searchKw = ref('');

const historyFilterTabs = computed<SpringTabItem<'all' | 'playlist' | 'song'>[]>(() => [
  {
    value: 'all',
    label: '全部',
    badge: totalCount.value,
  },
  {
    value: 'playlist',
    label: '歌单',
    icon: ListMusic,
    badge: playlistCount.value,
  },
  {
    value: 'song',
    label: '歌曲',
    icon: Disc3,
    badge: songCount.value,
  },
]);

const failedCovers = ref<Set<number>>(new Set());

// 批量选择与操作状态（对齐曲库多选交互）
const selectedHistoryIds = ref<Set<number>>(new Set());
const isBatchDeleting = ref(false);

// 查看歌单曲目弹窗状态
const tracksModalOpen = ref(false);
const activePlaylistName = ref('');
const activeHistoryItem = ref<HistoryItem | null>(null);

function openPlaylistModal(h: HistoryItem) {
  if (isSongItem(h)) return;
  activePlaylistName.value = h.playlist_name;
  activeHistoryItem.value = h;
  tracksModalOpen.value = true;
}

function markCoverFailed(id: number) {
  const next = new Set(failedCovers.value);
  next.add(id);
  failedCovers.value = next;
}

const isPullRefreshing = ref(false);

async function onPullRefresh() {
  isPullRefreshing.value = true;
  try {
    await fetchHistory(true);
  } finally {
    isPullRefreshing.value = false;
  }
}

async function fetchHistory(silent = false) {
  if (!silent) isLoading.value = true;
  try {
    const res = await api.getHistory();
    if (res.ok) {
      history.value = res.data;
      const currentIds = new Set(history.value.map(h => h.id));
      selectedHistoryIds.value = new Set(
        Array.from(selectedHistoryIds.value).filter(id => currentIds.has(id))
      );
    } else {
      showToast('获取下载历史失败', 'error');
    }
  } catch (e: any) {
    showToast(`读取下载记录失败：${e.message}`, 'error');
  } finally {
    if (!silent) isLoading.value = false;
  }
}

function toggleSelectHistory(id: number) {
  const next = new Set(selectedHistoryIds.value);
  if (next.has(id)) {
    next.delete(id);
  } else {
    next.add(id);
  }
  selectedHistoryIds.value = next;
}

function toggleSelectAllHistory() {
  if (selectedHistoryIds.value.size === filteredHistory.value.length && filteredHistory.value.length > 0) {
    selectedHistoryIds.value = new Set();
  } else {
    selectedHistoryIds.value = new Set(filteredHistory.value.map(h => h.id));
  }
}

async function handleBatchDeleteHistory() {
  const targetIds = Array.from(selectedHistoryIds.value);
  if (targetIds.length === 0) return;

  isBatchDeleting.value = true;
  try {
    const results = await Promise.all(targetIds.map(id => api.deleteHistory(id)));
    const successCount = results.filter(r => r.ok).length;
    const targetSet = new Set(targetIds);
    history.value = history.value.filter(h => !targetSet.has(h.id));
    selectedHistoryIds.value = new Set();
    showToast(`已清除 ${successCount} 条下载记录。`, 'success');
  } catch (e: any) {
    showToast(`批量清除记录失败: ${e.message}`, 'error');
  } finally {
    isBatchDeleting.value = false;
  }
}

function isSongItem(item: HistoryItem): boolean {
  if (item.type) return item.type === 'song';
  return (
    item.total === 1 ||
    item.platform?.includes('单曲') ||
    item.playlist_name?.startsWith('单曲')
  );
}

function getSongDetails(item: HistoryItem) {
  if (item.title && item.artist) {
    return { title: item.title, artist: item.artist };
  }
  let raw = item.playlist_name || '';
  raw = raw.replace(/^单曲下载[:：]\s*/, '').replace(/^单曲[:：]\s*/, '').trim();
  const parts = raw.split(' - ');
  if (parts.length >= 2) {
    return { artist: parts[0].trim(), title: parts.slice(1).join(' - ').trim() };
  }
  return { artist: item.platform || '单曲', title: raw };
}

const totalCount = computed(() => history.value.length);

const playlistCount = computed(() => {
  return history.value.filter(h => !isSongItem(h)).length;
});

const songCount = computed(() => {
  return history.value.filter(h => isSongItem(h)).length;
});

// 滚动分页控制
const displayLimit = ref(20);
const displayedHistory = computed(() => filteredHistory.value.slice(0, displayLimit.value));
const hasMore = computed(() => displayLimit.value < filteredHistory.value.length);

function loadMore() {
  if (hasMore.value) {
    displayLimit.value += 20;
  }
}

watch([activeFilter, searchKw], () => {
  displayLimit.value = 20;
});

onMounted(() => {
  fetchHistory();
});

const filteredHistory = computed(() => {
  return history.value.filter(h => {
    const isSong = isSongItem(h);
    if (activeFilter.value === 'playlist' && isSong) return false;
    if (activeFilter.value === 'song' && !isSong) return false;

    if (searchKw.value.trim()) {
      const kw = searchKw.value.trim().toLowerCase();
      const matchName = (h.playlist_name || '').toLowerCase().includes(kw);
      const matchArtist = (h.artist || '').toLowerCase().includes(kw);
      const matchPlatform = (h.platform || '').toLowerCase().includes(kw);
      return matchName || matchArtist || matchPlatform;
    }
    return true;
  });
});

function formatDuration(sec?: number) {
  if (!sec || sec <= 0) return '不到 1 秒';
  if (sec < 60) return `${sec} 秒`;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  if (m < 60) return s > 0 ? `${m} 分 ${s} 秒` : `${m} 分钟`;
  const h = Math.floor(m / 60);
  const remM = m % 60;
  return `${h} 小时 ${remM} 分`;
}

function formatDate(iso?: string) {
  if (!iso) return '--';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  const now = new Date();
  const isSameYear = d.getFullYear() === now.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  const hour = String(d.getHours()).padStart(2, '0');
  const min = String(d.getMinutes()).padStart(2, '0');
  return isSameYear ? `${m}/${day} ${hour}:${min}` : `${d.getFullYear()}/${m}/${day} ${hour}:${min}`;
}

onMounted(() => {
  fetchHistory();
});
</script>

<template>
  <div class="tab-content-container space-y-3">
    <!-- Filter & Search Bar (固定在顶部，不随列表滚动) -->
    <Card class="bg-card/80 border-border backdrop-blur-xl shadow-xl p-3 sm:p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shrink-0 z-10">
      <!-- Category Tabs (全部 / 歌单 / 歌曲 - 物理惯性弹簧切换器) -->
      <SpringTabs
        v-model="activeFilter"
        :items="historyFilterTabs"
        class="self-start sm:self-auto shrink-0"
      />

      <!-- Actions: Search & Refresh (已移除清空历史按钮) -->
      <div class="flex items-center gap-2 w-full sm:w-auto">
        <div class="relative flex-1 sm:w-64">
          <Search class="w-3.5 h-3.5 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2 z-10" />
          <Input
            v-model="searchKw"
            type="text"
            placeholder="搜索记录"
            class="pl-9 h-9 text-xs"
          />
        </div>

        <Button
          variant="outline"
          size="icon"
          @click="fetchHistory"
          title="刷新列表"
          class="h-9 w-9 rounded-xl shrink-0"
        >
          <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': isLoading }" />
        </Button>
      </div>
    </Card>

    <!-- 固定的列表头部栏（全选 / 统计，固定于列表上方不随列表滚动） -->
    <div v-if="filteredHistory.length > 0" class="flex items-center justify-between px-1 text-xs shrink-0">
      <div class="flex items-center gap-2">
        <Button
          variant="ghost"
          size="sm"
          class="h-7 px-2 text-muted-foreground text-[11px] sm:text-xs"
          @click="toggleSelectAllHistory"
        >
          {{ selectedHistoryIds.size === filteredHistory.length && filteredHistory.length > 0 ? '取消全选' : '全选' }}
        </Button>
        <span class="text-muted-foreground/50">|</span>
        <span class="text-muted-foreground text-[11px] sm:text-xs">
          共 <strong class="text-foreground font-mono">{{ filteredHistory.length }}</strong> 条
        </span>
        <span v-if="selectedHistoryIds.size > 0" class="text-warning font-medium text-[11px] sm:text-xs">
          · 已选 {{ selectedHistoryIds.size }} 条
        </span>
      </div>
    </div>

    <!-- 只有列表滚动，内置下拉刷新组件 -->
    <PullRefreshList
      :refreshing="isPullRefreshing"
      @refresh="onPullRefresh"
      class="custom-scrollbar pr-0.5"
    >
      <section class="space-y-3 pb-6">

      <!-- Loading State -->
      <LoadingState
        v-if="isLoading && history.length === 0"
        title="正在读取记录…"
        description="检索近期导入与下载任务记录"
      />

      <!-- Empty State -->
      <EmptyState
        v-else-if="filteredHistory.length === 0"
        :icon="History"
        :title="searchKw ? `未找到与 “${searchKw}” 匹配的下载记录` : activeFilter === 'playlist' ? '暂无歌单同步历史' : activeFilter === 'song' ? '暂无单曲下载历史' : '还没有下载或导入记录'"
        :description="searchKw ? '尝试更换搜索词或重置筛选' : '在搜歌页面下载单曲或在右上角导入歌单后，历史记录将自动保存于此。'"
        :action-text="searchKw ? '清空搜索' : ''"
        @action="searchKw = ''"
      />

      <!-- List of Items (平铺展示) -->
      <div v-else class="space-y-2 select-text">
        <article
          v-for="h in displayedHistory"
          :key="h.id"
          :class="[
            'media-list-row media-list-row--history transition-all',
            { 'media-list-row--selected': selectedHistoryIds.has(h.id) }
          ]"
          role="button"
          tabindex="0"
          :aria-pressed="selectedHistoryIds.has(h.id)"
          :aria-label="`${selectedHistoryIds.has(h.id) ? '取消选择' : '选择'}记录 ${isSongItem(h) ? getSongDetails(h).title : h.playlist_name}`"
          @click="toggleSelectHistory(h.id)"
          @keydown.enter.prevent="toggleSelectHistory(h.id)"
          @keydown.space.prevent="toggleSelectHistory(h.id)"
        >
          <!-- Cover Art with smooth gradient fade -->
          <div class="media-list-row__art" aria-hidden="true">
            <img
              v-if="h.cover && !failedCovers.has(h.id)"
              :src="h.cover"
              :alt="`${isSongItem(h) ? getSongDetails(h).title : h.playlist_name} 封面`"
              loading="lazy"
              decoding="async"
              referrerpolicy="no-referrer"
              @error="markCoverFailed(h.id)"
            />
            <div v-else class="media-list-row__art-fallback">
              <Disc3 v-if="isSongItem(h)" class="h-6 w-6 text-primary/35" />
              <ListMusic v-else class="h-6 w-6 text-primary/35" />
            </div>
          </div>

          <!-- Content Area -->
          <div class="media-list-row__content">
            <!-- Title Line -->
            <div class="media-list-row__title-line">
              <strong class="media-list-row__title">
                {{ isSongItem(h) ? getSongDetails(h).title : h.playlist_name }}
              </strong>
              <Badge
                :variant="isSongItem(h) ? 'default' : 'secondary'"
                class="shrink-0 px-1.5 py-0 text-[9.5px] font-medium"
              >
                {{ isSongItem(h) ? '单曲' : '歌单' }}
              </Badge>
              <Badge
                v-if="isSongItem(h) && (h.quality || 'FLAC')"
                variant="secondary"
                class="shrink-0 px-1.5 py-0 text-[9px] uppercase font-mono"
              >
                <template v-if="h.actual_quality && h.actual_quality.toLowerCase() !== (h.quality || '').toLowerCase()">
                  {{ h.quality }} → {{ h.actual_quality }}
                </template>
                <template v-else>
                  {{ h.quality || 'FLAC' }}
                </template>
              </Badge>
              <Badge
                v-if="isSongItem(h) && h.adjusted"
                variant="outline"
                class="shrink-0 px-1.5 py-0 text-[9px] font-semibold bg-amber-500/15 text-amber-500 border-amber-500/35"
                :title="h.adjustment_note || '音源或音质已按实际可用情况自动调整'"
              >
                有调整
              </Badge>
              <Badge
                v-if="!isSongItem(h) && (h.adjusted_count && h.adjusted_count > 0)"
                variant="outline"
                class="shrink-0 px-1.5 py-0 text-[9px] font-semibold bg-amber-500/15 text-amber-500 border-amber-500/35"
                :title="`歌单内有 ${h.adjusted_count} 首曲目音源或音质已调整`"
              >
                调整 {{ h.adjusted_count }} 首
              </Badge>
              <Badge
                v-if="h.failed_count > 0"
                variant="destructive"
                class="shrink-0 px-1.5 py-0 text-[9px]"
              >
                失败
              </Badge>
            </div>

            <!-- Subtitle Line -->
            <p class="media-list-row__subtitle">
              <span v-if="isSongItem(h)">
                {{ getSongDetails(h).artist }}<span v-if="h.album"> · 《{{ h.album }}》</span>
              </span>
              <span v-else>
                {{ h.platform }} · 共 {{ h.total }} 首
              </span>
            </p>

            <!-- Meta Line -->
            <div class="media-list-row__meta">
              <span>{{ formatDate(h.end_time || h.start_time) }}</span>
              <span>耗时 {{ formatDuration(h.duration) }}</span>
              <span>归属 {{ h.target === 'public' ? '公共' : h.user }}</span>
              <template v-if="!isSongItem(h)">
                <span class="text-success font-semibold">新 {{ h.downloaded_count }}</span>
                <span class="text-info font-semibold">复 {{ h.reused_count }}</span>
                <span v-if="h.adjusted_count && h.adjusted_count > 0" class="text-amber-500 font-semibold">调 {{ h.adjusted_count }}</span>
                <span v-if="h.failed_count > 0" class="text-destructive font-semibold">失败 {{ h.failed_count }}</span>
              </template>
              <template v-else-if="h.failed_count === 0">
                <span class="text-success font-semibold">已入库</span>
                <span v-if="h.adjustment_note" class="text-amber-500/90 font-medium truncate max-w-[240px]" :title="h.adjustment_note">
                  · {{ h.adjustment_note }}
                </span>
              </template>
            </div>
          </div>

          <!-- 末尾操作工具栏：仅歌单显示展开详情 icon，已去掉删除 icon -->
          <div
            v-if="!isSongItem(h)"
            class="media-list-row__history-tools"
            @click.stop
          >
            <Button
              variant="ghost"
              size="iconSm"
              title="查看歌单曲目与详情"
              class="text-muted-foreground hover:text-primary hover:bg-primary/10 transition-colors"
              @click="openPlaylistModal(h)"
            >
              <ListMusic class="h-4 w-4" />
            </Button>
          </div>
        </article>

        <!-- 滚动触底 Sentinel 哨兵组件 -->
        <ListSentinel
          :has-more="hasMore"
          :loading="isLoading"
          :total="filteredHistory.length"
          unit="条记录"
          loading-text="正在加载更多记录…"
          @load-more="loadMore"
        />
      </div>
    </section>
    </PullRefreshList>

    <!-- 底部浮动批量操作栏（下载记录） -->
    <!-- 批量操作悬浮条 (通用组件复用) -->
    <BatchActionBar
      :show="selectedHistoryIds.size > 0"
      :count="selectedHistoryIds.size"
      unit="条记录"
      action-text="清除"
      confirm-title="清除选中的历史记录？"
      confirm-desc="仅从下载历史列表中移除选中的记录，不会删除 NAS 硬盘中的实际音频文件。"
      confirm-btn-text="确认清除"
      :loading="isBatchDeleting"
      @cancel="selectedHistoryIds = new Set()"
      @confirm="handleBatchDeleteHistory"
    />

    <!-- Dialog: View & Edit Tracks from History (复用通用歌单曲目管理组件) -->
    <PlaylistTracksModal
      v-model:open="tracksModalOpen"
      :playlist-name="activePlaylistName"
      :history-item="activeHistoryItem"
    />
  </div>
</template>
