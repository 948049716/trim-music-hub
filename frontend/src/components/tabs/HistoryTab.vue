<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import type { HistoryItem } from '../../types';
import { api } from '../../api';
import { showToast } from '../../composables/useToast';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Popconfirm } from '@/components/ui/popconfirm';
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
  CheckCircle2
} from 'lucide-vue-next';

const history = ref<HistoryItem[]>([]);
const isLoading = ref(false);
const activeFilter = ref<'all' | 'playlist' | 'song'>('all');
const searchKw = ref('');

const deletingId = ref<number | null>(null);
const isClearingAll = ref(false);
const failedCovers = ref<Set<number>>(new Set());

function markCoverFailed(id: number) {
  const next = new Set(failedCovers.value);
  next.add(id);
  failedCovers.value = next;
}

async function fetchHistory() {
  isLoading.value = true;
  try {
    const res = await api.getHistory();
    if (res.ok) {
      history.value = res.data;
    } else {
      showToast('获取下载历史失败', 'error');
    }
  } catch (e: any) {
    showToast(`读取下载记录失败：${e.message}`, 'error');
  } finally {
    isLoading.value = false;
  }
}

async function confirmDeleteItem(id: number) {
  deletingId.value = id;
  try {
    const res = await api.deleteHistory(id);
    if (res.ok) {
      history.value = history.value.filter(h => h.id !== id);
      showToast('这条记录已删除。', 'success');
    } else {
      showToast('删除记录失败', 'error');
    }
  } catch (e: any) {
    showToast(`删除失败: ${e.message}`, 'error');
  } finally {
    deletingId.value = null;
  }
}

async function confirmClearAll() {
  isClearingAll.value = true;
  try {
    const res = await api.clearHistory();
    if (res.ok) {
      history.value = [];
      showToast('下载记录已清空。', 'success');
    } else {
      showToast('清空历史失败', 'error');
    }
  } catch (e: any) {
    showToast(`清空记录失败：${e.message}`, 'error');
  } finally {
    isClearingAll.value = false;
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
const sentinelRef = ref<HTMLElement | null>(null);
let observer: IntersectionObserver | null = null;

function loadMore() {
  if (hasMore.value) {
    displayLimit.value += 20;
  }
}

watch([activeFilter, searchKw], () => {
  displayLimit.value = 20;
});

onMounted(() => {
  observer = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && hasMore.value) {
      loadMore();
    }
  }, { threshold: 0.1 });
  if (sentinelRef.value) observer.observe(sentinelRef.value);
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
  if (m < 60) return `${m} 分 ${s} 秒`;
  const h = Math.floor(m / 60);
  const remM = m % 60;
  return `${h} 小时 ${remM} 分`;
}

function formatDate(iso?: string) {
  if (!iso) return '--';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  });
}

onMounted(() => {
  fetchHistory();
});
</script>

<template>
  <div class="space-y-4">
    <!-- Filter, Search & Actions Bar (无冗余标题) -->
    <Card class="bg-card/80 border-border backdrop-blur-xl shadow-xl p-3 sm:p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
      <!-- Category Tabs (全部 / 歌单 / 歌曲) via shadcn-vue Tabs -->
      <Tabs :model-value="activeFilter" @update:model-value="(val) => activeFilter = val as any" class="self-start sm:self-auto">
        <TabsList class="bg-background/80 border border-border/80 p-1 rounded-xl h-auto">
          <TabsTrigger value="all" class="gap-1.5">
            <span>全部</span>
            <Badge
              variant="outline"
              class="px-1.5 py-0 text-[10px] font-mono font-bold border-0 bg-secondary text-muted-foreground"
            >
              {{ totalCount }}
            </Badge>
          </TabsTrigger>

          <TabsTrigger value="playlist" class="gap-1.5">
            <ListMusic class="w-3.5 h-3.5" />
            <span>歌单</span>
            <Badge
              variant="outline"
              class="px-1.5 py-0 text-[10px] font-mono font-bold border-0 bg-secondary text-muted-foreground"
            >
              {{ playlistCount }}
            </Badge>
          </TabsTrigger>

          <TabsTrigger value="song" class="gap-1.5">
            <Disc3 class="w-3.5 h-3.5" />
            <span>歌曲</span>
            <Badge
              variant="outline"
              class="px-1.5 py-0 text-[10px] font-mono font-bold border-0 bg-secondary text-muted-foreground"
            >
              {{ songCount }}
            </Badge>
          </TabsTrigger>
        </TabsList>
      </Tabs>

      <!-- Actions: Search, Refresh & Clear All -->
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

        <Popconfirm
          v-if="history.length > 0"
          title="清空全部历史？"
          description="将移除所有下载记录条目。操作不可撤销，但 NAS 硬盘上的所有音乐文件均完好无损。"
          confirmText="彻底清空"
          :danger="true"
          :loading="isClearingAll"
          side="bottom"
          align="end"
          @confirm="confirmClearAll"
        >
          <Button
            variant="destructiveOutline"
            size="sm"
            class="rounded-xl flex items-center gap-1.5 font-semibold h-9 shrink-0 text-xs"
          >
            <Trash2 class="w-3.5 h-3.5" />
            <span class="hidden sm:inline">清空历史</span>
          </Button>
        </Popconfirm>
      </div>
    </Card>

    <!-- Download History Items List -->
    <Card class="bg-card/80 border-border backdrop-blur-xl shadow-2xl p-3 sm:p-4">
      <!-- Loading State -->
      <div v-if="isLoading" class="py-16 text-center text-muted-foreground space-y-2">
        <RefreshCw class="w-8 h-8 mx-auto animate-spin text-primary" />
        <p class="text-xs">正在读取记录…</p>
      </div>

      <!-- Empty State -->
      <div v-else-if="filteredHistory.length === 0" class="py-16 text-center text-muted-foreground space-y-2">
        <History class="w-12 h-12 mx-auto stroke-1 text-muted-foreground/55" />
        <p class="text-xs">
          <span v-if="searchKw">未找到与 "{{ searchKw }}" 匹配的下载记录</span>
          <span v-else-if="activeFilter === 'playlist'">暂无歌单同步历史</span>
          <span v-else-if="activeFilter === 'song'">暂无单曲下载历史</span>
          <span v-else>还没有下载或导入记录。</span>
        </p>
      </div>

      <!-- List of Items -->
      <div v-else class="space-y-2">
        <div
          v-for="h in displayedHistory"
          :key="h.id"
          class="swipe-list-item"
        >
          <article class="media-list-row media-list-row--history">
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
                  {{ isSongItem(h) ? '单曲下载' : '歌单同步' }}
                </Badge>
                <Badge
                  v-if="isSongItem(h) && (h.quality || 'FLAC')"
                  variant="secondary"
                  class="shrink-0 px-1.5 py-0 text-[9px] uppercase font-mono"
                >
                  {{ h.quality || 'FLAC' }}
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
                <span v-if="h.operator" class="hidden sm:inline">操作人 {{ h.operator }}</span>
                <template v-if="!isSongItem(h)">
                  <span class="text-emerald-600 dark:text-emerald-400 font-semibold">新下 {{ h.downloaded_count }}</span>
                  <span class="text-blue-600 dark:text-blue-400 font-semibold">复用 {{ h.reused_count }}</span>
                  <span v-if="h.failed_count > 0" class="text-destructive font-semibold">失败 {{ h.failed_count }}</span>
                </template>
                <template v-else-if="h.failed_count === 0">
                  <span class="text-emerald-600 dark:text-emerald-400 font-semibold">已入库</span>
                </template>
              </div>
            </div>

            <!-- Desktop Delete Action -->
            <div class="media-list-row__desktop-action" @click.stop>
              <Popconfirm
                :title="`清除记录【${isSongItem(h) ? getSongDetails(h).title : h.playlist_name}】？`"
                description="仅从下载历史列表中移除该记录条目，不会删除 NAS 硬盘中的实际音频文件。"
                confirmText="清除"
                :danger="true"
                :loading="deletingId === h.id"
                side="left"
                align="center"
                @confirm="confirmDeleteItem(h.id)"
              >
                <Button
                  variant="ghost"
                  size="iconSm"
                  title="清除记录"
                  class="text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                >
                  <Trash2 class="h-3.5 w-3.5" />
                </Button>
              </Popconfirm>
            </div>
          </article>

          <!-- Mobile Swipe Delete Action -->
          <div class="swipe-list-item__action md:hidden">
            <Popconfirm
              :title="`清除记录【${isSongItem(h) ? getSongDetails(h).title : h.playlist_name}】？`"
              description="仅从下载历史列表中移除该记录条目，不会删除 NAS 硬盘中的实际音频文件。"
              confirmText="清除"
              :danger="true"
              :loading="deletingId === h.id"
              side="top"
              align="end"
              @confirm="confirmDeleteItem(h.id)"
            >
              <Button
                variant="destructive"
                class="swipe-list-item__delete"
                :disabled="deletingId === h.id"
              >
                <Trash2 class="h-4 w-4" />
                <span>清除</span>
              </Button>
            </Popconfirm>
          </div>
        </div>

        <!-- 滚动触底 Sentinel 哨兵元素 -->
        <div ref="sentinelRef" class="py-3 text-center">
          <div v-if="hasMore" class="flex items-center justify-center gap-2 text-xs text-muted-foreground py-2">
            <RefreshCw class="w-4 h-4 animate-spin text-primary" />
            <span>正在加载更多…</span>
          </div>
          <div v-else-if="filteredHistory.length > 0" class="py-2 text-center text-[11px] text-muted-foreground/75">
            已显示全部 {{ filteredHistory.length }} 条记录 —
          </div>
        </div>
      </div>
    </Card>
  </div>
</template>

