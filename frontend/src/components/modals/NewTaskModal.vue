<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import type { PlaylistPreview, PlaylistPreviewTrack } from '@/types';
import { api } from '@/api';
import { showToast } from '@/composables/useToast';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select';
import { ArrowLeft, Check, Link2, Loader2, Music2, RefreshCw } from 'lucide-vue-next';

type QualityType = 'flac' | '320k' | '128k';

interface Props {
  open: boolean;
  initialUrl?: string;
  initialAccountId?: string;
  initialPlaylistName?: string;
}

const props = withDefaults(defineProps<Props>(), {
  open: false,
  initialUrl: '',
  initialAccountId: '',
  initialPlaylistName: ''
});
const emit = defineEmits<{ (e: 'close'): void; (e: 'update:open', val: boolean): void; (e: 'started'): void }>();

const step = ref<1 | 2>(1);
const playlistUrl = ref('');
const accountId = ref('');
const preview = ref<PlaylistPreview | null>(null);
const selectedIndexes = ref<number[]>([]);
const playlistName = ref('');
const targetType = ref<'public' | 'user'>('public');
const targetUser = ref('');
const userList = ref<Array<{ id: number; name: string }>>([]);
const parsing = ref(false);
const starting = ref(false);

const globalQuality = ref<QualityType>('flac');
const trackQualityMap = ref<Record<number, QualityType>>({});

const selectedCount = computed(() => selectedIndexes.value.length);
const allSelected = computed(() => !!preview.value && preview.value.tracks.length > 0 && selectedCount.value === preview.value.tracks.length);
const reusedCount = computed(() => preview.value?.tracks.filter(t => t.exists).length || 0);
const selectedTracks = computed(() => preview.value?.tracks.filter(track => selectedIndexes.value.includes(track.index)) || []);

function getTrackQuality(index: number): QualityType {
  return trackQualityMap.value[index] || globalQuality.value;
}

function setTrackQuality(index: number, q: QualityType) {
  trackQualityMap.value[index] = q;
}

function handleGlobalQualityChange(val: any) {
  const q = val as QualityType;
  globalQuality.value = q;
  if (preview.value?.tracks) {
    for (const track of preview.value.tracks) {
      trackQualityMap.value[track.index] = q;
    }
  }
}

async function loadUsers() {
  try {
    const res = await api.getUsers();
    if (res.ok && res.data.length) {
      userList.value = res.data;
      targetUser.value = res.data[0].name;
    }
  } catch {}
}

function reset() {
  step.value = 1;
  playlistUrl.value = '';
  accountId.value = '';
  preview.value = null;
  selectedIndexes.value = [];
  playlistName.value = '';
  targetType.value = 'public';
  targetUser.value = userList.value[0]?.name || '';
  globalQuality.value = 'flac';
  trackQualityMap.value = {};
  parsing.value = false;
  starting.value = false;
}

async function handleParse(customUrl?: string, customAccountId?: string) {
  const url = (customUrl || playlistUrl.value).trim();
  if (!url) {
    showToast('粘贴歌单链接或分享文本后再解析。', 'warning');
    return;
  }
  const accId = customAccountId || accountId.value || props.initialAccountId;
  parsing.value = true;
  try {
    const res = await api.parsePlaylist(url, accId);
    if (!res.ok || !res.data) throw new Error(res.error || '无法解析这个歌单链接');
    preview.value = res.data;
    playlistName.value = res.data.playlist_name || props.initialPlaylistName || '未命名歌单';
    selectedIndexes.value = res.data.tracks.map(track => track.index);
    globalQuality.value = 'flac';
    trackQualityMap.value = {};
    for (const track of res.data.tracks) {
      trackQualityMap.value[track.index] = 'flac';
    }
    step.value = 2;
    if (!res.data.tracks.length) showToast('歌单解析成功，但没有可导入的歌曲。', 'warning');
  } catch (e: any) {
    showToast(`解析失败：${e.message}`, 'error');
  } finally {
    parsing.value = false;
  }
}

function toggleTrack(track: PlaylistPreviewTrack, checked: boolean | 'indeterminate') {
  const next = new Set(selectedIndexes.value);
  if (checked === true) next.add(track.index);
  else next.delete(track.index);
  selectedIndexes.value = [...next];
}

function toggleAll(checked: boolean | 'indeterminate') {
  selectedIndexes.value = checked === true ? (preview.value?.tracks.map(track => track.index) || []) : [];
}

async function handleSubmit() {
  if (!preview.value) return;
  if (!playlistName.value.trim()) {
    showToast('请填写歌单名称。', 'warning');
    return;
  }
  if (!selectedTracks.value.length) {
    showToast('至少选择一首歌曲后再开始导入。', 'warning');
    return;
  }
  starting.value = true;
  try {
    const tracksPayload = selectedTracks.value.map(track => ({
      ...track,
      quality: getTrackQuality(track.index)
    }));

    const res = await api.startTask({
      url: playlistUrl.value.trim(),
      target: targetType.value,
      user: targetUser.value,
      playlist_name: playlistName.value.trim(),
      quality: globalQuality.value,
      tracks: tracksPayload,
      cover_url: preview.value?.cover_url || '',
      account_id: accountId.value || props.initialAccountId || undefined
    });
    if (!res.ok) throw new Error(res.error || res.message || '歌单未能开始导入');
    showToast(`《${playlistName.value.trim()}》已开始导入，共 ${selectedTracks.value.length} 首歌曲。`, 'success');
    emit('started');
    closeModal();
  } catch (e: any) {
    showToast(`导入失败：${e.message}`, 'error');
  } finally {
    starting.value = false;
  }
}

function closeModal() {
  reset();
  emit('close');
  emit('update:open', false);
}
function handleOpenUpdate(val: boolean) { if (!val) closeModal(); }
function backToInput() { step.value = 1; }

watch(() => props.open, async (val) => {
  if (val) {
    await loadUsers();
    if (props.initialUrl) {
      playlistUrl.value = props.initialUrl;
      accountId.value = props.initialAccountId || '';
      if (props.initialPlaylistName) {
        playlistName.value = props.initialPlaylistName;
      }
      await handleParse(props.initialUrl, props.initialAccountId);
    }
  } else {
    reset();
  }
});

onMounted(loadUsers);
</script>

<template>
  <Dialog :open="props.open" @update:open="handleOpenUpdate">
    <DialogContent
      :class="step === 2
        ? 'inset-x-0 bottom-0 top-auto h-[94dvh] max-h-[94dvh] w-full max-w-full rounded-b-none rounded-t-[1.5rem] p-0 gap-0 flex flex-col overflow-hidden sm:inset-auto sm:left-[50%] sm:top-[50%] sm:bottom-auto sm:h-auto sm:max-h-[88dvh] sm:w-full sm:max-w-3xl sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-[1.5rem] sm:p-6 sm:gap-4'
        : 'w-[calc(100vw-1.5rem)] max-w-[calc(100vw-1.5rem)] max-h-[calc(100dvh-1.5rem)] gap-3 p-4 sm:w-full sm:max-w-lg sm:p-6 sm:gap-4'"
    >
      <!-- 对话框 Header -->
      <DialogHeader class="shrink-0 border-b border-border/80 px-4 py-3.5 pr-12 sm:px-0 sm:pt-0 sm:pb-3 sm:border-0">
        <div class="flex items-start gap-3">
          <Button v-if="step === 2" variant="ghost" size="icon" class="-ml-2 shrink-0 h-9 w-9 rounded-lg" aria-label="返回修改链接" @click="backToInput">
            <ArrowLeft class="h-4 w-4" />
          </Button>
          <div v-else class="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
            <Link2 class="h-5 w-5" />
          </div>
          <div class="min-w-0">
            <DialogTitle class="text-base sm:text-lg font-bold tracking-[-0.02em] text-foreground">
              {{ step === 1 ? '导入歌单' : '确认导入内容' }}
            </DialogTitle>
            <DialogDescription class="pt-0.5 text-xs leading-relaxed text-muted-foreground truncate sm:text-clip">
              {{ step === 1 ? '先解析链接，确认歌曲与音质后再开始下载。' : `已解析 ${preview?.tracks.length || 0} 首歌曲，可指定曲目与音质。` }}
            </DialogDescription>
          </div>
        </div>
      </DialogHeader>

      <!-- Step 1: 粘贴链接 -->
      <div v-if="step === 1" class="space-y-4 py-1">
        <div class="space-y-2">
          <label class="block text-xs font-semibold text-foreground">歌单链接或分享文本</label>
          <Input v-model="playlistUrl" type="text" class="h-11" placeholder="粘贴网易云或 QQ 音乐歌单链接" @keyup.enter="handleParse" />
        </div>
        <div class="rounded-xl border border-dashed border-border bg-muted/25 p-3 text-[11px] leading-5 text-muted-foreground">
          <span class="font-semibold text-foreground">导入流程：</span>解析歌单 → 自选歌曲与品质 → 修改歌单名与归属 → 开始同步。
        </div>
      </div>

      <!-- Step 2: 确认导入与品质配置 -->
      <div v-else class="flex min-h-0 flex-1 flex-col overflow-hidden px-4 py-3 sm:px-0 sm:py-0 space-y-3">
        <!-- 歌单信息与基础配置栏 -->
        <div class="shrink-0 space-y-2.5">
          <!-- 歌单封面与名称输入 -->
          <div class="flex items-center gap-3 rounded-xl border border-border bg-muted/20 p-2.5 sm:p-3">
            <div class="relative h-12 w-12 sm:h-14 sm:w-14 shrink-0 overflow-hidden rounded-lg bg-muted shadow-sm">
              <img v-if="preview?.cover_url" :src="preview.cover_url" alt="歌单封面" class="h-full w-full object-cover" loading="lazy" referrerpolicy="no-referrer" />
              <Music2 v-else class="absolute left-1/2 top-1/2 h-5 w-5 -translate-x-1/2 -translate-y-1/2 text-muted-foreground/50" />
            </div>
            <div class="min-w-0 flex-1 space-y-1">
              <div class="flex items-center justify-between gap-2">
                <span class="text-[10px] font-semibold text-primary/80 uppercase tracking-wider">{{ preview?.platform || '第三方平台' }}</span>
                <span class="text-[10px] text-muted-foreground">已选 {{ selectedCount }} / {{ preview?.tracks.length || 0 }} 首</span>
              </div>
              <Input v-model="playlistName" class="h-8 text-xs sm:h-9 sm:text-sm font-semibold" placeholder="歌单名称" />
            </div>
          </div>

          <!-- 导入设置网格：可见范围 + 统一品质 -->
          <div class="grid grid-cols-2 gap-2 sm:grid-cols-3 sm:gap-3">
            <div class="space-y-1">
              <label class="block text-[11px] font-medium text-muted-foreground">可见范围</label>
              <Select v-model="targetType">
                <SelectTrigger class="h-8 sm:h-9 text-xs">
                  <SelectValue placeholder="选择可见范围" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="public">所有家庭成员</SelectItem>
                  <SelectItem value="user">指定成员</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div v-if="targetType === 'user'" class="space-y-1">
              <label class="block text-[11px] font-medium text-muted-foreground">所属成员</label>
              <Select v-model="targetUser">
                <SelectTrigger class="h-8 sm:h-9 text-xs">
                  <SelectValue placeholder="选择成员" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem v-for="u in userList" :key="u.id" :value="u.name">{{ u.name }}</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div class="space-y-1" :class="targetType !== 'user' ? 'col-span-1 sm:col-span-2' : ''">
              <div class="flex items-center justify-between">
                <label class="block text-[11px] font-medium text-muted-foreground">统一音质</label>
                <span class="text-[10px] text-muted-foreground/75 hidden sm:inline">可单独指定单曲</span>
              </div>
              <Select :model-value="globalQuality" @update:model-value="handleGlobalQualityChange">
                <SelectTrigger class="h-8 sm:h-9 text-xs font-semibold">
                  <SelectValue placeholder="选择音质" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="flac">FLAC (无损音质)</SelectItem>
                  <SelectItem value="320k">320K (高品质 MP3)</SelectItem>
                  <SelectItem value="128k">128K (标准品质)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>

        <!-- 列表控制条：全选 + 统计提示 -->
        <div class="shrink-0 flex items-center justify-between rounded-lg bg-muted/40 px-3 py-1.5 text-xs">
          <label class="flex items-center gap-2 font-medium text-foreground cursor-pointer select-none">
            <Checkbox :model-value="allSelected" @update:model-value="toggleAll" />
            <span class="text-xs">全选 ({{ selectedCount }})</span>
          </label>
          <span class="text-[10px] text-muted-foreground">
            <span v-if="reusedCount > 0" class="text-success font-medium">{{ reusedCount }} 首已在库 · </span>未收录单曲可改音质
          </span>
        </div>

        <!-- 歌曲列表滚动区 -->
        <div class="min-h-0 flex-1 overflow-y-auto overscroll-contain rounded-xl border border-border bg-card divide-y divide-border/60 pr-0.5">
          <div v-if="!preview?.tracks.length" class="grid min-h-32 place-items-center text-xs text-muted-foreground">
            没有可导入的歌曲
          </div>
          <div
            v-for="track in preview?.tracks"
            :key="track.index"
            class="group flex items-center gap-2.5 px-2.5 py-2 transition-colors hover:bg-muted/30"
          >
            <!-- 复选框 -->
            <Checkbox
              :model-value="selectedIndexes.includes(track.index)"
              class="shrink-0"
              @update:model-value="value => toggleTrack(track, value)"
            />

            <!-- 封面缩略图 -->
            <div class="relative h-9 w-9 shrink-0 overflow-hidden rounded-lg bg-muted">
              <img v-if="track.cover" :src="track.cover" :alt="`${track.title}封面`" class="h-full w-full object-cover" loading="lazy" referrerpolicy="no-referrer" />
              <Music2 v-else class="absolute left-1/2 top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 text-muted-foreground" />
            </div>

            <!-- 歌曲标题与歌手 -->
            <div class="min-w-0 flex-1 pr-1 cursor-pointer select-none" @click="toggleTrack(track, !selectedIndexes.includes(track.index))">
              <p class="truncate text-xs font-semibold text-foreground leading-tight">{{ track.title }}</p>
              <p class="mt-0.5 truncate text-[10px] text-muted-foreground leading-tight">
                {{ track.artist }}<span v-if="track.album"> · {{ track.album }}</span>
              </p>
            </div>

            <!-- 状态或单曲音质选择器 -->
            <div class="shrink-0 flex items-center">
              <span
                v-if="track.exists"
                class="inline-flex items-center gap-1 rounded-md bg-success/15 px-2 py-0.5 text-[10px] font-semibold text-success"
              >
                <Check class="h-3 w-3" />已收录
              </span>
              <div v-else class="flex items-center gap-1">
                <Select
                  :model-value="getTrackQuality(track.index)"
                  @update:model-value="(val: any) => setTrackQuality(track.index, val as QualityType)"
                >
                  <SelectTrigger class="h-7 w-[78px] sm:w-[84px] px-1.5 py-0 text-[10px] font-semibold tracking-tight">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent align="end">
                    <SelectItem value="flac">FLAC</SelectItem>
                    <SelectItem value="320k">320K</SelectItem>
                    <SelectItem value="128k">128K</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 对话框 Footer -->
      <DialogFooter class="shrink-0 border-t border-border bg-card/85 backdrop-blur px-4 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:px-0 sm:pt-4 sm:pb-0 sm:bg-transparent flex flex-row items-center justify-between gap-2">
        <Button variant="ghost" size="sm" class="h-9 px-3 text-xs" @click="closeModal">取消</Button>
        <div class="flex items-center gap-2">
          <Button v-if="step === 2" variant="outline" size="sm" class="h-9 px-3 text-xs" @click="backToInput">
            <RefreshCw class="h-3.5 w-3.5 mr-1" />重新解析
          </Button>
          <Button v-if="step === 1" size="sm" class="h-9 px-4 text-xs" @click="handleParse" :disabled="parsing">
            <Loader2 v-if="parsing" class="h-3.5 w-3.5 animate-spin mr-1" />
            <span>{{ parsing ? '正在解析…' : '解析歌单' }}</span>
          </Button>
          <Button v-else size="sm" class="h-9 px-4 text-xs font-semibold" @click="handleSubmit" :disabled="starting || !selectedTracks.length">
            <Loader2 v-if="starting" class="h-3.5 w-3.5 animate-spin mr-1" />
            <span>{{ starting ? '正在启动…' : `开始导入 (${selectedCount})` }}</span>
          </Button>
        </div>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
