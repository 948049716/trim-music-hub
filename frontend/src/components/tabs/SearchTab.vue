<script setup lang="ts">
import { ref, onMounted } from 'vue';
import type { SearchSong, SettingsData } from '../../types';
import { api } from '../../api';
import { showToast } from '../../composables/useToast';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent
} from '@/components/ui/card';
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem
} from '@/components/ui/select';
import { Search, Loader2, Sparkles, CheckCircle, Ban, ArrowDownToLine, Music, Settings2 } from 'lucide-vue-next';

const searchKeyword = ref('');
const isSearching = ref(false);
const searchResults = ref<SearchSong[]>([]);
const downloadingMap = ref<Record<string, boolean>>({});
const selectedQualityMap = ref<Record<string, 'flac' | '320k' | '128k'>>({});

// Settings & Source
const currentSource = ref<'kw' | 'kg' | 'tx' | 'wy' | 'auto' | 'custom'>('kw');
const availableSources = ref<SettingsData['available_sources']>([
  { id: 'kw', name: '酷我音乐 (默认)', desc: '高品质FLAC专线', default: true },
  { id: 'kg', name: '酷狗音乐', desc: '海棠/星海SVIP', default: false },
  { id: 'tx', name: 'QQ音乐', desc: '长青/溯音专线', default: false },
  { id: 'wy', name: '网易云音乐', desc: '163云音乐', default: false },
  { id: 'auto', name: '智能多源聚合', desc: '故障自动回退', default: false },
  { id: 'custom', name: '自定义音源', desc: '私有API/自定义源', default: false }
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
      showToast(`当前下载音源已切换为：${availableSources.value.find(s => s.id === srcStr)?.name}`, 'success');
    }
  } catch (e: any) {
    showToast(`切换音源异常: ${e.message}`, 'error');
  }
}

async function handleSearch() {
  const kw = searchKeyword.value.trim();
  if (!kw) {
    showToast('请输入歌名或歌手名进行搜索', 'warning');
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
          selectedQualityMap.value[key] = 'flac';
        }
      });
      if (res.data.length === 0) {
        showToast('未找到匹配的音源', 'info');
      }
    } else {
      showToast('搜歌接口请求异常', 'error');
    }
  } catch (e: any) {
    showToast(`搜歌失败: ${e.message}`, 'error');
  } finally {
    isSearching.value = false;
  }
}

async function triggerDownload(song: SearchSong, idx: number) {
  const key = `${song.artist}-${song.title}-${idx}`;
  const quality = selectedQualityMap.value[key] || 'flac';

  if (song.exists) {
    showToast(`该歌曲在 NAS 曲库中已存在，禁止重复下载！`, 'warning');
    return;
  }

  downloadingMap.value[key] = true;
  showToast(`已发起【${song.artist} - ${song.title}】(${quality.toUpperCase()}) 下载任务`, 'info');

  try {
    const res = await api.downloadSingle({
      artist: song.artist,
      song: song.title,
      album: song.album,
      cover: song.cover,
      quality,
      source: currentSource.value
    } as any);
    if (res.ok) {
      showToast(`下载流水线已成功拉起，请在【任务监控】查看进度`, 'success');
      // Mark as existing locally to prevent duplicate click
      song.exists = true;
      song.local_path = '正在下载入库中...';
    } else {
      showToast(res.error || '下载任务启动失败', 'error');
    }
  } catch (e: any) {
    showToast(`下载请求失败: ${e.message}`, 'error');
  } finally {
    downloadingMap.value[key] = false;
  }
}

onMounted(() => {
  loadSourceSettings();
});
</script>

<template>
  <div class="space-y-6">
    <!-- Search Bar & Source Selector Card -->
    <Card class="bg-card/80 border-border backdrop-blur-xl shadow-xl p-4 sm:p-5">

      <div class="max-w-3xl mx-auto space-y-3">
        <!-- Search Input with Search Button -->
        <form @submit.prevent="handleSearch" class="flex items-center gap-2">
          <div class="relative flex-1">
            <Search class="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2 z-10" />
            <Input
              v-model="searchKeyword"
              type="text"
              placeholder="输入歌曲名、歌手名搜索（例如：周杰伦 晴天）..."
              class="pl-10 h-10 text-sm"
            />
          </div>
          <Button
            type="submit"
            variant="default"
            size="lg"
            :disabled="isSearching"
            class="gap-2 shrink-0 h-10"
          >
            <Loader2 v-if="isSearching" class="w-4 h-4 animate-spin" />
            <Search v-else class="w-4 h-4" />
            <span>{{ isSearching ? '正在检索...' : '搜索歌曲' }}</span>
          </Button>
        </form>

        <!-- Quick Source Switcher Strip -->
        <div class="flex items-center justify-between pt-1 px-1 text-xs text-slate-400">
          <div class="flex items-center gap-2">
            <Settings2 class="w-3.5 h-3.5 text-brand-400" />
            <span>当前下载音源：</span>
            <Select :model-value="currentSource" @update:model-value="handleSourceChange">
              <SelectTrigger class="h-7 w-44 rounded-lg bg-background/90 border-border text-xs">
                <SelectValue placeholder="选择解析源" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem v-for="src in availableSources" :key="src.id" :value="src.id">
                  {{ src.name }}
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
          <span class="hidden sm:inline text-[11px] text-slate-500">
            酷我专线为默认，支持 FLAC 24-bit 无损直出
          </span>
        </div>
      </div>
    </Card>

    <!-- Search Results Grid / List -->
    <Card class="bg-card/80 border-border backdrop-blur-xl shadow-2xl p-6">
      <div class="flex items-center justify-between pb-3 border-b border-border/80 mb-3 text-xs">
        <div class="flex items-center gap-2 text-slate-300">
          <Music class="w-4 h-4 text-brand-400" />
          <span>搜索结果</span>
          <span v-if="searchResults.length > 0" class="text-xs text-brand-400 font-mono font-medium">({{ searchResults.length }} 首)</span>
        </div>
        <span class="text-[11px] text-slate-500">双轨秒级比对飞牛官方曲库与物理目录</span>
      </div>

      <!-- Empty State -->
      <div v-if="!isSearching && searchResults.length === 0" class="py-16 text-center text-slate-500 space-y-2">
        <Search class="w-12 h-12 mx-auto stroke-1 text-slate-700" />
        <p class="text-xs">暂无检索结果，请在上方输入歌名或歌手名</p>
      </div>

      <!-- Loading State -->
      <div v-if="isSearching" class="py-16 text-center text-slate-400 space-y-3">
        <Loader2 class="w-8 h-8 mx-auto animate-spin text-brand-400" />
        <p class="text-xs">正在全网检索音源并比对飞牛本地曲库...</p>
      </div>

      <!-- Song List -->
      <div v-if="!isSearching && searchResults.length > 0" class="space-y-2.5">
        <div
          v-for="(song, idx) in searchResults"
          :key="`${song.artist}-${song.title}-${idx}`"
          class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 rounded-xl bg-white/[0.02] hover:bg-white/[0.05] border border-transparent transition-all"
        >
          <!-- Song Info -->
          <div class="flex items-center gap-3.5 overflow-hidden">
            <img
              :src="song.cover || 'https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=400&q=80'"
              class="w-12 h-12 rounded-lg object-cover border border-border shrink-0"
              alt="Cover"
            />
            <div class="overflow-hidden space-y-1">
              <div class="flex items-center gap-2">
                <span class="text-sm font-semibold text-white truncate">{{ song.title }}</span>

                <!-- Existing Badge -->
                <Badge
                  v-if="song.exists"
                  variant="success"
                  class="gap-1 text-[11px]"
                >
                  <CheckCircle class="w-3 h-3" />
                  <span>NAS已存在</span>
                </Badge>
                <Badge
                  v-else
                  variant="outline"
                  class="text-[11px]"
                >
                  未收录
                </Badge>
              </div>

              <div class="text-xs text-slate-400 truncate flex items-center gap-2">
                <span>{{ song.artist }}</span>
                <span v-if="song.album" class="text-slate-600">·</span>
                <span v-if="song.album" class="text-slate-500 truncate">《{{ song.album }}》</span>
              </div>

              <div v-if="song.exists && song.local_path" class="text-[11px] text-slate-500 font-mono truncate">
                路径: {{ song.local_path }}
              </div>
            </div>
          </div>

          <!-- Split Button Quality Selector & Download -->
          <div class="flex items-center gap-2 self-end sm:self-center shrink-0">
            <!-- Radix / Shadcn-vue Quality Select -->
            <Select
              v-model="selectedQualityMap[`${song.artist}-${song.title}-${idx}`]"
              :disabled="song.exists || downloadingMap[`${song.artist}-${song.title}-${idx}`]"
            >
              <SelectTrigger class="w-28 h-8 rounded-lg bg-background border-border text-xs">
                <SelectValue placeholder="音质" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="flac">FLAC 无损</SelectItem>
                <SelectItem value="320k">320K 高品</SelectItem>
                <SelectItem value="128k">128K 标准</SelectItem>
              </SelectContent>
            </Select>

            <!-- Download Button -->
            <Button
              v-if="!song.exists"
              variant="default"
              size="sm"
              @click="triggerDownload(song, idx)"
              :disabled="downloadingMap[`${song.artist}-${song.title}-${idx}`]"
              class="gap-1.5 h-8"
            >
              <Loader2 v-if="downloadingMap[`${song.artist}-${song.title}-${idx}`]" class="w-3.5 h-3.5 animate-spin" />
              <ArrowDownToLine v-else class="w-3.5 h-3.5" />
              <span>{{ downloadingMap[`${song.artist}-${song.title}-${idx}`] ? '正在拉起...' : '下载' }}</span>
            </Button>

            <!-- Disabled Lock Button -->
            <Button
              v-else
              disabled
              variant="secondary"
              size="sm"
              class="opacity-60 cursor-not-allowed gap-1 text-slate-500 h-8"
            >
              <Ban class="w-3 h-3 text-rose-400" />
              <span>禁止重复下载</span>
            </Button>
          </div>
        </div>
      </div>
    </Card>
  </div>
</template>
