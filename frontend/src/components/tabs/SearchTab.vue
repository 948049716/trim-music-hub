<script setup lang="ts">
import { ref, onMounted } from "vue";
import type { SearchSong, SettingsData } from "../../types";
import { api } from "../../api";
import { showToast } from "../../composables/useToast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
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
  Sparkles,
  CheckCircle,
  Ban,
  ArrowDownToLine,
  Music,
  Settings2,
} from "lucide-vue-next";

const searchKeyword = ref("");
const isSearching = ref(false);
const searchResults = ref<SearchSong[]>([]);
const downloadingMap = ref<Record<string, boolean>>({});
const selectedQualityMap = ref<Record<string, "flac" | "320k" | "128k">>({});

// Settings & Source
const currentSource = ref<"kw" | "kg" | "tx" | "wy" | "auto" | "custom">("kw");
const availableSources = ref<SettingsData["available_sources"]>([
  { id: "kw", name: "酷我音乐 (默认)", desc: "高品质FLAC专线", default: true },
  { id: "kg", name: "酷狗音乐", desc: "海棠/星海SVIP", default: false },
  { id: "tx", name: "QQ音乐", desc: "长青/溯音专线", default: false },
  { id: "wy", name: "网易云音乐", desc: "163云音乐", default: false },
  { id: "auto", name: "智能多源聚合", desc: "故障自动回退", default: false },
  {
    id: "custom",
    name: "自定义音源",
    desc: "私有API/自定义源",
    default: false,
  },
]);

async function loadSourceSettings() {
  try {
    const res = await api.getSettings();
    if (res.ok && res.data) {
      currentSource.value = res.data.download_source;
      if (res.data.available_sources) {
        availableSources.value = res.data.available_sources;
      }
    }
  } catch (e) {}
}

async function handleSourceChange(newSrc: any) {
  if (!newSrc) return;
  const srcStr = String(newSrc);
  currentSource.value = srcStr as any;
  try {
    const res = await api.updateSettings(srcStr);
    if (res.ok) {
      showToast(
        `下载音源已切换为“${availableSources.value.find((s) => s.id === srcStr)?.name}”。`,
        "success",
      );
    }
  } catch (e: any) {
    showToast(`切换音源失败：${e.message}`, "error");
  }
}

async function handleSearch() {
  const kw = searchKeyword.value.trim();
  if (!kw) {
    showToast("先输入歌名、歌手或专辑。", "warning");
    return;
  }
  isSearching.value = true;
  try {
    const res = await api.searchOnline(kw);
    if (res.ok) {
      searchResults.value = res.data;
      // Initialize qualities
      res.data.forEach((s, idx) => {
        const key = `${s.artist}-${s.title}-${idx}`;
        if (!selectedQualityMap.value[key]) {
          selectedQualityMap.value[key] = "flac";
        }
      });
      if (res.data.length === 0) {
        showToast("没有找到匹配歌曲，试试其他关键词。", "info");
      }
    } else {
      showToast("暂时无法搜索歌曲，请稍后重试。", "error");
    }
  } catch (e: any) {
    showToast(`搜索失败：${e.message}`, "error");
  } finally {
    isSearching.value = false;
  }
}

async function triggerDownload(song: SearchSong, idx: number) {
  const key = `${song.artist}-${song.title}-${idx}`;
  const quality = selectedQualityMap.value[key] || "flac";

  if (song.exists) {
    showToast("这首歌已在曲库中，无需重复下载。", "warning");
    return;
  }

  downloadingMap.value[key] = true;
  showToast(
    `正在下载“${song.artist} - ${song.title}”（${quality.toUpperCase()}）。`,
    "info",
  );

  try {
    const res = await api.downloadSingle({
      artist: song.artist,
      song: song.title,
      album: song.album,
      cover: song.cover,
      quality,
      source: currentSource.value,
    } as any);
    if (res.ok) {
      showToast("已加入下载任务，可前往“任务”查看进度。", "success");
      // Mark as existing locally to prevent duplicate click
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

onMounted(() => {
  loadSourceSettings();
});
</script>

<template>
  <div class="space-y-5">
    <Card class="overflow-hidden p-0">
      <div class="grid lg:grid-cols-[minmax(0,1fr)_300px]">
        <form class="p-4 sm:p-5" @submit.prevent="handleSearch">
          <label class="mb-2 block text-xs font-semibold text-foreground"
            >想听什么？</label
          >
          <div class="flex gap-2">
            <div class="relative min-w-0 flex-1">
              <Search
                class="absolute left-3.5 top-1/2 z-10 h-4 w-4 -translate-y-1/2 text-muted-foreground"
              />
              <Input
                v-model="searchKeyword"
                type="search"
                placeholder="歌名、歌手或专辑"
                class="h-11 pl-10 text-sm"
              />
            </div>
            <Button
              type="submit"
              size="lg"
              :disabled="isSearching"
              class="h-11 shrink-0 px-4 sm:px-5"
            >
              <Loader2 v-if="isSearching" class="h-4 w-4 animate-spin" /><Search
                v-else
                class="h-4 w-4"
              /><span class="hidden sm:inline">搜索</span>
            </Button>
          </div>
          <p class="mt-2 text-[10px] text-muted-foreground">
            搜索时会同时检查飞牛曲库，已有歌曲不会重复下载。
          </p>
        </form>
        <div
          class="border-t border-border bg-[hsl(var(--surface-inset)/.55)] p-4 sm:p-5 lg:border-l lg:border-t-0"
        >
          <label
            class="mb-2 flex items-center gap-2 text-xs font-semibold text-foreground"
            ><Settings2 class="h-3.5 w-3.5 text-primary" />下载音源</label
          >
          <Select
            :model-value="currentSource"
            @update:model-value="handleSourceChange"
          >
            <SelectTrigger class="h-10 w-full"
              ><SelectValue placeholder="选择音源"
            /></SelectTrigger>
            <SelectContent
              ><SelectItem
                v-for="src in availableSources"
                :key="src.id"
                :value="src.id"
                >{{ src.name }}</SelectItem
              ></SelectContent
            >
          </Select>
          <p class="mt-2 truncate text-[10px] text-muted-foreground">
            {{
              availableSources.find((s) => s.id === currentSource)?.desc ||
              "用于搜索与下载"
            }}
          </p>
        </div>
      </div>
    </Card>

    <Card class="p-4 sm:p-5">
      <div
        class="mb-4 flex items-center justify-between border-b border-border pb-3"
      >
        <div class="flex items-center gap-2">
          <Music class="h-4 w-4 text-primary" />
          <h3 class="text-xs font-bold text-foreground">搜索结果</h3>
          <Badge v-if="searchResults.length" variant="outline"
            >{{ searchResults.length }} 首</Badge
          >
        </div>
        <span
          v-if="searchResults.length"
          class="hidden text-[10px] text-muted-foreground sm:inline"
          >选择音质后即可保存到 NAS</span
        >
      </div>

      <div
        v-if="!isSearching && searchResults.length === 0"
        class="flex min-h-[300px] flex-col items-center justify-center text-center"
      >
        <div
          class="grid h-14 w-14 place-items-center rounded-full border border-dashed border-border bg-muted"
        >
          <Search class="h-6 w-6 text-muted-foreground/60" />
        </div>
        <p class="mt-4 text-sm font-semibold text-foreground">从一首歌开始</p>
        <p class="mt-1.5 text-xs text-muted-foreground">
          输入歌名或歌手，找到合适的版本后保存到曲库。
        </p>
      </div>
      <div
        v-else-if="isSearching"
        class="flex min-h-[300px] flex-col items-center justify-center text-center"
      >
        <Loader2 class="h-7 w-7 animate-spin text-primary" />
        <p class="mt-3 text-xs text-muted-foreground">
          正在查找歌曲并核对本地曲库…
        </p>
      </div>

      <div v-else class="divide-y divide-border/70">
        <article
          v-for="(song, idx) in searchResults"
          :key="`${song.artist}-${song.title}-${idx}`"
          class="group flex items-center justify-between gap-3 py-3.5 first:pt-0 last:pb-0"
        >
          <div class="flex min-w-0 flex-1 items-center gap-3">
            <img
              :src="
                song.cover ||
                'https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=400&q=80'
              "
              class="h-12 w-12 shrink-0 rounded-xl border border-border/80 object-cover"
              :alt="`${song.title} 封面`"
              loading="lazy"
              decoding="async"
              referrerpolicy="no-referrer"
            />
            <div class="min-w-0 flex-1">
              <div class="flex min-w-0 items-center gap-2">
                <h4
                  class="truncate text-sm font-bold text-foreground"
                  :title="song.title"
                >
                  {{ song.title }}
                </h4>
                <Badge
                  :variant="song.exists ? 'success' : 'outline'"
                  class="shrink-0 px-1.5 py-0 text-[10px] h-4 leading-none font-medium"
                >
                  {{ song.exists ? "已在曲库" : "未收录" }}
                </Badge>
              </div>
              <p class="mt-0.5 truncate text-xs text-muted-foreground">
                {{ song.artist
                }}<span v-if="song.album"> · {{ song.album }}</span>
              </p>
              <p
                v-if="song.exists && song.local_path"
                class="mt-0.5 truncate font-mono text-[10px] text-muted-foreground/75"
                :title="song.local_path"
              >
                {{ song.local_path }}
              </p>
            </div>
          </div>

          <div class="shrink-0">
            <!-- Fused Split Button: [ ⬇ 下载 | FLAC ▾ ] -->
            <div
              v-if="!song.exists"
              class="inline-flex items-stretch overflow-hidden rounded-xl border border-primary/30 bg-primary text-primary-foreground shadow-sm transition-all hover:shadow"
            >
              <Button variant="ghost"
                type="button"
                class="inline-flex h-8 items-center gap-1.5 px-3 text-xs font-semibold text-primary-foreground hover:text-primary-foreground hover:bg-primary/90 active:scale-[0.98] transition-all disabled:cursor-not-allowed disabled:opacity-60"
                :disabled="
                  downloadingMap[`${song.artist}-${song.title}-${idx}`]
                "
                @click="triggerDownload(song, idx)"
              >
                <Loader2
                  v-if="downloadingMap[`${song.artist}-${song.title}-${idx}`]"
                  class="h-3.5 w-3.5 animate-spin"
                />
                <ArrowDownToLine v-else class="h-3.5 w-3.5" />
                <span>{{
                  downloadingMap[`${song.artist}-${song.title}-${idx}`]
                    ? "准备中"
                    : "下载"
                }}</span>
              </Button>

              <div
                class="w-px self-stretch bg-primary-foreground/25 my-1"
              ></div>

              <Select
                v-model="
                  selectedQualityMap[`${song.artist}-${song.title}-${idx}`]
                "
                :disabled="
                  downloadingMap[`${song.artist}-${song.title}-${idx}`]
                "
              >
                <SelectTrigger
                  class="h-8 border-0 bg-transparent px-2 text-[11px] font-bold tracking-tight text-primary-foreground hover:bg-white/10 dark:hover:bg-white/15 focus:ring-0 shadow-none rounded-none gap-1 [&>svg]:h-3 [&>svg]:w-3 [&>svg]:text-primary-foreground [&>svg]:opacity-85"
                >
                  <SelectValue placeholder="FLAC" />
                </SelectTrigger>
                <SelectContent align="end" class="min-w-[130px]">
                  <SelectItem value="flac">FLAC (无损)</SelectItem>
                  <SelectItem value="320k">320K (高品质)</SelectItem>
                  <SelectItem value="128k">128K (标准)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <Button
              v-else
              disabled
              variant="secondary"
              size="sm"
              class="h-8 shrink-0 rounded-xl px-2.5 text-xs font-medium opacity-75"
            >
              <CheckCircle class="mr-1 h-3.5 w-3.5 text-emerald-500" />已有
            </Button>
          </div>
        </article>
      </div>
    </Card>
  </div>
</template>
