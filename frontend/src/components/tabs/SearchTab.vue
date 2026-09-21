<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import type { SearchSong, SettingsData, CurrentUser } from "../../types";
import { api } from "../../api";
import { showToast } from "../../composables/useToast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import {
  Search,
  Loader2,
  CheckCircle,
  ArrowDownToLine,
  Music,
  Settings2,
  Radio,
  Download,
  ListPlus,
  CheckSquare,
  Square,
  Sparkles,
  Check,
} from "lucide-vue-next";
import { EmptyState, LoadingState } from "@/components/ui/state";
import { ListSentinel, PullRefreshList } from "@/components/ui/list";

const props = defineProps<{
  currentUser?: CurrentUser | null;
}>();

const searchKeyword = ref("");
const isSearching = ref(false);
const isLoadingMore = ref(false);
const searchResults = ref<SearchSong[]>([]);
const currentPage = ref(0);
const hasMore = ref(false);
const downloadingMap = ref<Record<string, boolean>>({});
const selectedQualityMap = ref<Record<string, "flac" | "320k" | "128k">>({});

// 多选与批量操作状态
const selectedSongKeys = ref<Set<string>>(new Set());
const selectedCount = computed(() => selectedSongKeys.value.size);
const isAllSelected = computed(
  () => searchResults.value.length > 0 && selectedCount.value === searchResults.value.length
);

const batchModalOpen = ref(false);
const batchCreatePlaylist = ref(true);
const batchPlaylistName = ref("");
const batchTargetType = ref<"public" | "user">("public");
const batchTargetUser = ref("admin");
const batchQuality = ref<"flac" | "320k" | "128k">("flac");
const batchSource = ref<"kw" | "kg" | "tx" | "wy" | "auto" | "custom">("kw");
const batchSubmitting = ref(false);
const userList = ref<Array<{ id: number; name: string }>>([]);

const selectedSongs = computed(() =>
  searchResults.value.filter((song, idx) =>
    selectedSongKeys.value.has(songKey(song, idx))
  )
);

const batchReusedCount = computed(() =>
  selectedSongs.value.filter((s) => s.exists).length
);

function toggleSelectSong(song: SearchSong, idx: number) {
  const key = songKey(song, idx);
  const next = new Set(selectedSongKeys.value);
  if (next.has(key)) {
    next.delete(key);
  } else {
    next.add(key);
  }
  selectedSongKeys.value = next;
}

function toggleSelectAll() {
  if (isAllSelected.value) {
    selectedSongKeys.value = new Set();
  } else {
    const next = new Set<string>();
    searchResults.value.forEach((s, i) => next.add(songKey(s, i)));
    selectedSongKeys.value = next;
  }
}

function clearSelection() {
  selectedSongKeys.value = new Set();
}

async function loadUsers() {
  try {
    const res = await api.getUsers();
    if (res.ok && Array.isArray(res.data)) {
      userList.value = res.data;
      if (props.currentUser?.username) {
        batchTargetUser.value = props.currentUser.username;
      } else if (res.data[0]) {
        batchTargetUser.value = res.data[0].name;
      }
    }
  } catch {}
}

function openBatchModal() {
  if (selectedCount.value === 0) return;
  const kw = searchKeyword.value.trim();
  batchPlaylistName.value = kw ? `${kw} - 精选` : `搜歌自建歌单_${new Date().toLocaleDateString()}`;
  batchSource.value = currentSource.value;
  if (props.currentUser?.username) {
    batchTargetType.value = "user";
    batchTargetUser.value = props.currentUser.username;
  }
  batchModalOpen.value = true;
  loadUsers();
}

async function handleBatchSubmit() {
  if (selectedCount.value === 0) return;
  batchSubmitting.value = true;
  try {
    if (batchCreatePlaylist.value) {
      if (!batchPlaylistName.value.trim()) {
        showToast("请填写歌单名称", "warning");
        return;
      }
      const tracksPayload = selectedSongs.value.map((song, i) => ({
        index: i,
        title: song.title,
        artist: song.artist,
        album: song.album || song.title,
        cover: song.cover || "",
        quality: batchQuality.value,
      }));

      const res = await api.startTask({
        url: "custom://search-batch",
        target: batchTargetType.value,
        user: batchTargetUser.value || "admin",
        playlist_name: batchPlaylistName.value.trim(),
        quality: batchQuality.value,
        source: batchSource.value,
        tracks: tracksPayload,
        cover_url: selectedSongs.value[0]?.cover || "",
      });

      if (res.ok) {
        showToast(`《${batchPlaylistName.value.trim()}》已加入同步任务，共 ${selectedCount.value} 首歌曲！`, "success");
        clearSelection();
        batchModalOpen.value = false;
      } else {
        showToast(res.error || "创建歌单失败", "error");
      }
    } else {
      const toDownload = selectedSongs.value.filter((s) => !s.exists);
      if (toDownload.length === 0) {
        showToast("所选歌曲已全部在曲库中，无需重复下载。", "info");
        clearSelection();
        batchModalOpen.value = false;
        return;
      }
      let addedCount = 0;
      for (const song of toDownload) {
        try {
          await api.downloadSingle({
            artist: song.artist,
            song: song.title,
            album: song.album,
            cover: song.cover,
            quality: batchQuality.value,
            source: batchSource.value,
          });
          song.exists = true;
          song.local_path = "正在下载入库中...";
          addedCount++;
        } catch {}
      }
      showToast(`已成功将 ${addedCount} 首歌曲加入下载队列！`, "success");
      clearSelection();
      batchModalOpen.value = false;
    }
  } catch (e: any) {
    showToast(`批量操作失败：${e.message}`, "error");
  } finally {
    batchSubmitting.value = false;
  }
}

const currentSource = ref<"kw" | "kg" | "tx" | "wy" | "auto" | "custom">("kw");
const availableSources = ref<SettingsData["available_sources"]>([
  { id: "kw", name: "酷我音乐 (默认)", desc: "高品质FLAC专线", default: true },
  { id: "kg", name: "酷狗音乐", desc: "海棠/星海SVIP", default: false },
  { id: "tx", name: "QQ音乐", desc: "长青/溯音专线", default: false },
  { id: "wy", name: "网易云音乐", desc: "163云音乐", default: false },
  { id: "auto", name: "智能多源聚合", desc: "故障自动回退", default: false },
  { id: "custom", name: "自定义音源", desc: "私有API/自定义源", default: false },
]);

function songKey(song: SearchSong, idx: number) {
  return `${song.artist}-${song.title}-${idx}`;
}

function initializeQuality(song: SearchSong, idx: number) {
  const key = songKey(song, idx);
  if (!selectedQualityMap.value[key]) selectedQualityMap.value[key] = "flac";
}

async function loadSourceSettings() {
  try {
    const res = await api.getSettings();
    if (res.ok && res.data) {
      currentSource.value = res.data.download_source;
      if (res.data.available_sources) availableSources.value = res.data.available_sources;
    }
  } catch {}
}

async function handleSourceChange(newSrc: unknown) {
  if (!newSrc) return;
  const srcStr = String(newSrc) as typeof currentSource.value;
  currentSource.value = srcStr;
  try {
    const res = await api.updateSettings(srcStr);
    if (res.ok) {
      showToast(`下载音源已切换为“${availableSources.value.find((s) => s.id === srcStr)?.name}”。`, "success");
    }
  } catch (e: any) {
    showToast(`切换音源失败：${e.message}`, "error");
  }
}

async function fetchSearchPage(page: number, append = false) {
  const kw = searchKeyword.value.trim();
  if (!kw) return;
  if (append) isLoadingMore.value = true;
  else isSearching.value = true;

  try {
    const res = await api.searchOnline(kw, page, 20);
    if (!res.ok) {
      showToast("暂时无法搜索歌曲，请稍后重试。", "error");
      return;
    }

    const incoming = res.data || [];
    if (append) searchResults.value.push(...incoming);
    else searchResults.value = incoming;
    incoming.forEach((song, index) => initializeQuality(song, append ? searchResults.value.length - incoming.length + index : index));
    currentPage.value = res.page || page;
    hasMore.value = Boolean(res.has_more);

    if (!append && incoming.length === 0) showToast("没有找到匹配歌曲，试试其他关键词。", "info");
  } catch (e: any) {
    showToast(`${append ? "加载更多" : "搜索"}失败：${e.message}`, "error");
  } finally {
    if (append) isLoadingMore.value = false;
    else isSearching.value = false;
  }
}

const isPullRefreshing = ref(false);

async function onPullRefresh() {
  const kw = searchKeyword.value.trim();
  if (!kw) return;
  isPullRefreshing.value = true;
  try {
    const res = await api.searchOnline(kw, 1, 20);
    if (res.ok) {
      const incoming = res.data || [];
      searchResults.value = incoming;
      incoming.forEach((song, index) => initializeQuality(song, index));
      currentPage.value = res.page || 1;
      hasMore.value = Boolean(res.has_more);
    } else {
      showToast("暂时无法刷新搜索结果，请稍后重试。", "error");
    }
  } catch (e: any) {
    showToast(`刷新失败：${e.message}`, "error");
  } finally {
    isPullRefreshing.value = false;
  }
}

async function handleSearch() {
  const kw = searchKeyword.value.trim();
  if (!kw) {
    showToast("先输入歌名、歌手或专辑。", "warning");
    return;
  }
  if (isSearching.value || isLoadingMore.value) return;
  searchResults.value = [];
  currentPage.value = 0;
  hasMore.value = false;
  await fetchSearchPage(1);
}

async function loadMore() {
  if (isSearching.value || isLoadingMore.value || !hasMore.value || currentPage.value < 1) return;
  await fetchSearchPage(currentPage.value + 1, true);
}

async function triggerDownload(song: SearchSong, idx: number) {
  const key = songKey(song, idx);
  const quality = selectedQualityMap.value[key] || "flac";
  if (song.exists) {
    showToast("这首歌已在曲库中，无需重复下载。", "warning");
    return;
  }

  downloadingMap.value[key] = true;
  showToast(`正在下载“${song.artist} - ${song.title}”（${quality.toUpperCase()}）。`, "info");
  try {
    const res = await api.downloadSingle({
      artist: song.artist,
      song: song.title,
      album: song.album,
      cover: song.cover,
      quality,
      source: currentSource.value,
    });
    if (res.ok) {
      showToast("已加入下载任务，可前往“任务”查看进度。", "success");
      song.exists = true;
      song.local_path = "正在下载入库中...";
    } else {
      showToast(res.error || "无法开始下载，请稍后重试。", "error");
    }
  } catch (e: any) {
    showToast(`下载失败：${e.message}`, "error");
  } finally {
    downloadingMap.value[key] = false;
  }
}

onMounted(loadSourceSettings);
</script>

<template>
  <div class="tab-content-container space-y-3">
    <!-- 顶部搜索与音源控制面板 (固定在顶部，不随列表滚动) -->
    <Card class="overflow-hidden p-3.5 sm:p-5 shrink-0 bg-card/85 border-border backdrop-blur-xl shadow-xl z-10">
      <form @submit.prevent="handleSearch" class="space-y-3">
        <!-- 标题与音源切换胶囊 -->
        <div class="flex items-center justify-between gap-2">
          <label class="text-xs font-semibold text-foreground flex items-center gap-1.5">
            <Music class="h-3.5 w-3.5 text-primary" />
            <span>全网搜歌</span>
          </label>

          <!-- 紧凑精致的音源选择胶囊 -->
          <div class="flex items-center gap-1.5">
            <Select :model-value="currentSource" @update:model-value="handleSourceChange">
              <SelectTrigger class="h-7 gap-1.5 rounded-full border border-border/80 bg-muted/50 hover:bg-muted/80 px-2.5 text-xs font-medium text-foreground transition-colors shadow-none focus:ring-1 focus:ring-primary/40 [&>svg]:h-3.5 [&>svg]:w-3.5 [&>svg]:text-muted-foreground">
                <Radio class="h-3 w-3 text-primary shrink-0" />
                <span class="truncate max-w-[120px]">{{ availableSources.find(s => s.id === currentSource)?.name || "选择音源" }}</span>
              </SelectTrigger>
              <SelectContent align="end" class="min-w-[160px]">
                <SelectItem v-for="src in availableSources" :key="src.id" :value="src.id">
                  <div class="flex flex-col py-0.5">
                    <span class="font-medium text-xs">{{ src.name }}</span>
                    <span class="text-[10px] text-muted-foreground">{{ src.desc }}</span>
                  </div>
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <!-- 搜索输入框与搜索按钮 -->
        <div class="flex gap-2">
          <div class="relative min-w-0 flex-1">
            <Search class="absolute left-3.5 top-1/2 z-10 h-4 w-4 -translate-y-1/2 text-muted-foreground pointer-events-none" />
            <Input
              v-model="searchKeyword"
              type="search"
              placeholder="搜索歌名、歌手或专辑..."
              class="h-10 sm:h-11 pl-10 text-sm bg-background/50 focus:bg-background transition-colors"
            />
          </div>
          <Button
            type="submit"
            size="lg"
            :disabled="isSearching || isLoadingMore"
            class="h-10 sm:h-11 shrink-0 px-4 sm:px-6 font-semibold gap-1.5 active:scale-95 transition-transform"
          >
            <Loader2 v-if="isSearching" class="h-4 w-4 animate-spin" />
            <Search v-else class="h-4 w-4" />
            <span class="hidden sm:inline">搜索</span>
          </Button>
        </div>

        <!-- 辅助提示 -->
        <div class="flex items-center justify-between text-[11px] text-muted-foreground pt-0.5">
          <p class="truncate flex items-center gap-1">
            <span class="inline-block h-1.5 w-1.5 rounded-full bg-primary/70"></span>
            搜索时自动对照飞牛曲库双轨查重，无需担心重复下载
          </p>
          <span class="hidden sm:inline text-muted-foreground/75 font-mono text-[10px]">
            {{ availableSources.find(s => s.id === currentSource)?.desc }}
          </span>
        </div>
      </form>
    </Card>

    <!-- 固定的搜索结果状态信息栏 -->
    <div v-if="searchResults.length" class="flex items-center justify-between px-1 text-xs shrink-0">
      <div class="flex items-center gap-2">
        <Music class="h-4 w-4 text-primary" />
        <h3 class="text-xs font-bold text-foreground">搜索结果</h3>
        <Badge variant="outline">{{ searchResults.length }} 首</Badge>
      </div>
      <div class="flex items-center gap-2">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          class="h-7 px-2 text-xs text-muted-foreground hover:text-foreground gap-1.5"
          @click="toggleSelectAll"
        >
          <CheckSquare v-if="isAllSelected" class="h-3.5 w-3.5 text-primary" />
          <Square v-else class="h-3.5 w-3.5" />
          <span>{{ isAllSelected ? '取消全选' : '全选' }}</span>
        </Button>
        <span class="hidden sm:inline text-[11px] text-muted-foreground">选择音质后即可保存到 NAS</span>
      </div>
    </div>

    <!-- 只有列表滚动，内置下拉刷新 -->
    <PullRefreshList
      :refreshing="isPullRefreshing"
      :disabled="!searchKeyword.trim()"
      @refresh="onPullRefresh"
      class="custom-scrollbar pr-0.5"
    >
      <section class="space-y-3 pb-6">

      <EmptyState
        v-if="!isSearching && searchResults.length === 0"
        :icon="Search"
        title="从一首歌开始"
        description="输入歌名或歌手，找到合适的版本后保存到曲库。"
      />
      <LoadingState
        v-else-if="isSearching && searchResults.length === 0"
        title="正在查找歌曲并核对本地曲库…"
        description="支持 FLAC 无损与高品质音源检索"
      />

      <div v-else class="space-y-2 select-text">
        <article
          v-for="(song, idx) in searchResults"
          :key="songKey(song, idx)"
          class="search-result-row group"
          :class="selectedSongKeys.has(songKey(song, idx)) ? 'media-list-row--selected' : ''"
        >
          <!-- 多选框 -->
          <button
            type="button"
            class="flex h-5 w-5 shrink-0 items-center justify-center rounded-md border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            :class="selectedSongKeys.has(songKey(song, idx)) ? 'border-primary bg-primary text-primary-foreground shadow-sm' : 'border-border/80 bg-background/60 hover:border-primary/50'"
            :aria-label="selectedSongKeys.has(songKey(song, idx)) ? '取消勾选' : '勾选此歌曲'"
            @click.stop="toggleSelectSong(song, idx)"
          >
            <Check v-if="selectedSongKeys.has(songKey(song, idx))" class="h-3.5 w-3.5 stroke-[3]" />
          </button>

          <div class="search-result-row__art" @click="toggleSelectSong(song, idx)">
            <img :src="song.cover || 'https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=400&q=80'" :alt="`${song.title} 封面`" loading="lazy" decoding="async" referrerpolicy="no-referrer" />
          </div>
          <div class="search-result-row__content" @click="toggleSelectSong(song, idx)">
            <div class="flex min-w-0 items-center gap-2">
              <h4 class="min-w-0 truncate text-sm sm:text-base font-semibold text-foreground" :title="song.title">{{ song.title }}</h4>
              <Badge :variant="song.exists ? 'success' : 'outline'" class="h-4 shrink-0 px-1.5 py-0 text-[10px] font-medium leading-none">{{ song.exists ? "已在曲库" : "未收录" }}</Badge>
            </div>
            <p class="truncate text-xs text-muted-foreground">{{ song.artist }}<span v-if="song.album"> · {{ song.album }}</span></p>
            <p v-if="song.exists && song.local_path" class="truncate font-mono text-[10px] text-muted-foreground/75" :title="song.local_path">{{ song.local_path }}</p>
          </div>

          <div v-if="!song.exists" class="search-result-row__action">
            <div class="inline-flex items-center h-8 rounded-xl border border-primary/35 bg-primary/10 backdrop-blur-sm p-0.5 shadow-sm transition-all hover:bg-primary/15 hover:border-primary/55">
              <button
                type="button"
                class="flex items-center gap-1.5 h-7 px-2.5 sm:px-3 text-xs font-semibold text-primary hover:text-foreground active:scale-95 transition-all disabled:opacity-50 disabled:pointer-events-none"
                :disabled="downloadingMap[songKey(song, idx)]"
                @click="triggerDownload(song, idx)"
              >
                <Loader2 v-if="downloadingMap[songKey(song, idx)]" class="h-3.5 w-3.5 animate-spin text-primary" />
                <ArrowDownToLine v-else class="h-3.5 w-3.5 text-primary" />
                <span>{{ downloadingMap[songKey(song, idx)] ? "准备中" : "下载" }}</span>
              </button>
              <div class="h-3.5 w-px bg-primary/25"></div>
              <Select v-model="selectedQualityMap[songKey(song, idx)]" :disabled="downloadingMap[songKey(song, idx)]">
                <SelectTrigger class="h-7 w-[54px] gap-0.5 rounded-lg border-0 bg-primary/15 hover:bg-primary/25 px-1.5 text-[10px] font-bold font-mono text-primary shadow-none focus:ring-0 transition-colors [&>svg]:h-3 [&>svg]:w-3 [&>svg]:text-primary/80">
                  <SelectValue placeholder="FLAC" />
                </SelectTrigger>
                <SelectContent align="end" class="min-w-[130px]">
                  <SelectItem value="flac">FLAC (无损)</SelectItem>
                  <SelectItem value="320k">320K (高品质)</SelectItem>
                  <SelectItem value="128k">128K (标准)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div v-else class="search-result-row__action">
            <div class="inline-flex items-center gap-1.5 h-8 px-2.5 rounded-xl border border-success/30 bg-success/10 text-success text-xs font-medium">
              <CheckCircle class="h-3.5 w-3.5" />
              <span>已在曲库</span>
            </div>
          </div>
        </article>

        <ListSentinel
          :has-more="hasMore"
          :loading="isLoadingMore"
          :total="searchResults.length"
          unit="首歌曲"
          @load-more="loadMore"
        />
      </div>
      </section>
    </PullRefreshList>

    <!-- 底部悬浮批量操作栏 -->
    <transition
      enter-active-class="transition duration-200 ease-out transform"
      enter-from-class="translate-y-8 opacity-0 scale-95"
      enter-to-class="translate-y-0 opacity-100 scale-100"
      leave-active-class="transition duration-150 ease-in transform"
      leave-from-class="translate-y-0 opacity-100 scale-100"
      leave-to-class="translate-y-8 opacity-0 scale-95"
    >
      <div
        v-if="selectedCount > 0"
        class="selection-action-bar selection-action-bar--page"
      >
        <div class="selection-action-bar__summary">
          <span class="selection-action-bar__pulse" aria-hidden="true" />
          <span class="text-foreground font-medium whitespace-nowrap text-xs sm:text-sm">
            已选 <strong class="text-primary font-mono text-sm">{{ selectedCount }}</strong> 首
            <span v-if="batchReusedCount > 0" class="text-[11px] text-muted-foreground ml-1.5 hidden sm:inline">
              ({{ batchReusedCount }} 首已在曲库)
            </span>
          </span>
        </div>
        <div class="selection-action-bar__controls">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            class="selection-action-bar__button h-8 text-xs text-muted-foreground hover:text-foreground"
            @click="clearSelection"
          >
            取消
          </Button>
          <Button
            type="button"
            variant="default"
            size="sm"
            class="selection-action-bar__button h-8 text-xs gap-1.5 font-medium shadow-sm"
            @click="openBatchModal"
          >
            <Download class="h-3.5 w-3.5" />
            <span>批量处理 ({{ selectedCount }})</span>
          </Button>
        </div>
      </div>
    </transition>

    <!-- 批量下载 / 批量创建歌单 Dialog -->
    <Dialog :open="batchModalOpen" @update:open="batchModalOpen = $event">
      <DialogContent class="sm:max-w-[460px] p-5 sm:p-6">
        <DialogHeader>
          <DialogTitle class="text-base font-bold flex items-center gap-2">
            <Sparkles class="h-4 w-4 text-primary" />批量处理已选歌曲 ({{ selectedCount }} 首)
          </DialogTitle>
          <DialogDescription class="text-xs text-muted-foreground">
            可批量将选中的歌曲下载保存到 NAS 曲库，或直接创建为飞牛歌单。
          </DialogDescription>
        </DialogHeader>

        <div class="space-y-4 py-2">
          <!-- 模式选择：创建歌单 vs 仅批量下载 -->
          <div class="space-y-2">
            <label class="text-xs font-semibold text-foreground">处理方式</label>
            <div class="grid grid-cols-2 gap-2">
              <button
                type="button"
                class="flex flex-col items-start gap-1 p-3 rounded-xl border text-left transition-all"
                :class="batchCreatePlaylist ? 'border-primary bg-primary/10 text-primary' : 'border-border bg-card text-muted-foreground hover:bg-muted/40'"
                @click="batchCreatePlaylist = true"
              >
                <div class="flex items-center gap-1.5 font-semibold text-xs text-foreground">
                  <ListPlus class="h-3.5 w-3.5 text-primary" />
                  <span>创建飞牛歌单并同步</span>
                </div>
                <span class="text-[10px] text-muted-foreground leading-4">创建歌单并自动下载未收录曲目</span>
              </button>

              <button
                type="button"
                class="flex flex-col items-start gap-1 p-3 rounded-xl border text-left transition-all"
                :class="!batchCreatePlaylist ? 'border-primary bg-primary/10 text-primary' : 'border-border bg-card text-muted-foreground hover:bg-muted/40'"
                @click="batchCreatePlaylist = false"
              >
                <div class="flex items-center gap-1.5 font-semibold text-xs text-foreground">
                  <Download class="h-3.5 w-3.5 text-primary" />
                  <span>仅批量下载到曲库</span>
                </div>
                <span class="text-[10px] text-muted-foreground leading-4">自动跳过已存在的曲目</span>
              </button>
            </div>
          </div>

          <!-- 歌单信息 (当创建歌单时展示) -->
          <div v-if="batchCreatePlaylist" class="space-y-3.5 rounded-xl border border-border/80 bg-muted/20 p-3.5">
            <div class="space-y-1.5">
              <label class="text-xs font-medium text-foreground">歌单名称</label>
              <Input
                v-model="batchPlaylistName"
                placeholder="例如：周杰伦精选集"
                class="h-9 text-xs bg-card"
              />
            </div>

            <div class="space-y-1.5">
              <label class="text-xs font-medium text-foreground">可见范围与归属</label>
              <div class="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  class="flex items-center justify-center gap-1.5 h-8 rounded-lg border text-xs font-medium transition-all"
                  :class="batchTargetType === 'public' ? 'border-primary bg-primary/10 text-primary font-semibold' : 'border-border bg-card text-muted-foreground'"
                  @click="batchTargetType = 'public'"
                >
                  公共歌单
                </button>
                <button
                  type="button"
                  class="flex items-center justify-center gap-1.5 h-8 rounded-lg border text-xs font-medium transition-all"
                  :class="batchTargetType === 'user' ? 'border-primary bg-primary/10 text-primary font-semibold' : 'border-border bg-card text-muted-foreground'"
                  @click="batchTargetType = 'user'"
                >
                  专属个人歌单
                </button>
              </div>
            </div>

            <div v-if="batchTargetType === 'user'" class="space-y-1.5">
              <label class="text-xs font-medium text-foreground">所属飞牛用户</label>
              <Select v-model="batchTargetUser">
                <SelectTrigger class="h-9 text-xs bg-card">
                  <SelectValue placeholder="选择飞牛用户" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem v-for="u in userList" :key="u.id" :value="u.name">
                    {{ u.name }}
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <!-- 音质选择 -->
          <div class="space-y-1.5">
            <label class="text-xs font-semibold text-foreground">下载音质</label>
            <div class="grid grid-cols-3 gap-2">
              <button
                v-for="q in [
                  { id: 'flac', label: 'FLAC 无损' },
                  { id: '320k', label: '320K 高品' },
                  { id: '128k', label: '128K 标准' },
                ]"
                :key="q.id"
                type="button"
                class="flex items-center justify-center h-8 rounded-lg border text-xs font-medium transition-all"
                :class="batchQuality === q.id ? 'border-primary bg-primary/10 text-primary font-semibold' : 'border-border bg-card text-muted-foreground'"
                @click="batchQuality = q.id as any"
              >
                {{ q.label }}
              </button>
            </div>
          </div>

          <!-- 提示说明 -->
          <div class="rounded-lg bg-muted/40 p-2.5 text-[11px] text-muted-foreground leading-relaxed">
            <span v-if="batchCreatePlaylist">
              已选 {{ selectedCount }} 首歌曲（其中 {{ batchReusedCount }} 首已在曲库将直接关联，{{ selectedCount - batchReusedCount }} 首将发起下载）。
            </span>
            <span v-else>
              已选 {{ selectedCount }} 首歌曲（其中 {{ batchReusedCount }} 首已存在将跳过，预计新增下载 {{ selectedCount - batchReusedCount }} 首）。
            </span>
          </div>
        </div>

        <DialogFooter class="gap-2 sm:gap-0">
          <Button
            type="button"
            variant="outline"
            size="sm"
            class="h-9 text-xs"
            :disabled="batchSubmitting"
            @click="batchModalOpen = false"
          >
            取消
          </Button>
          <Button
            type="button"
            size="sm"
            class="h-9 text-xs gap-1.5 font-semibold"
            :disabled="batchSubmitting || selectedCount === 0"
            @click="handleBatchSubmit"
          >
            <Loader2 v-if="batchSubmitting" class="h-3.5 w-3.5 animate-spin" />
            <span v-else>{{ batchCreatePlaylist ? '立即创建并同步' : '开始批量下载' }}</span>
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
