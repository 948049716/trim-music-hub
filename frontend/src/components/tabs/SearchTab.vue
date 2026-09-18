<script setup lang="ts">
import { ref, onMounted } from "vue";
import type { SearchSong, SettingsData } from "../../types";
import { api } from "../../api";
import { showToast } from "../../composables/useToast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
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
} from "lucide-vue-next";
import { EmptyState, LoadingState } from "@/components/ui/state";
import { ListSentinel } from "@/components/ui/list";

const searchKeyword = ref("");
const isSearching = ref(false);
const isLoadingMore = ref(false);
const searchResults = ref<SearchSong[]>([]);
const currentPage = ref(0);
const hasMore = ref(false);
const downloadingMap = ref<Record<string, boolean>>({});
const selectedQualityMap = ref<Record<string, "flac" | "320k" | "128k">>({});

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
  if (!searchKeyword.value.trim()) return;
  isPullRefreshing.value = true;
  try {
    await fetchSearchPage(1);
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
      <span class="text-[11px] text-muted-foreground">选择音质后即可保存到 NAS</span>
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
        v-else-if="isSearching"
        title="正在查找歌曲并核对本地曲库…"
        description="支持 FLAC 无损与高品质音源检索"
      />

      <div v-else class="space-y-2 select-text">
        <article v-for="(song, idx) in searchResults" :key="songKey(song, idx)" class="search-result-row group">
          <div class="search-result-row__art">
            <img :src="song.cover || 'https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=400&q=80'" :alt="`${song.title} 封面`" loading="lazy" decoding="async" referrerpolicy="no-referrer" />
          </div>
          <div class="search-result-row__content">
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
  </div>
</template>
