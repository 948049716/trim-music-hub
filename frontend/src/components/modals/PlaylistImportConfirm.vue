<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import type { PlaylistPreview, PlaylistPreviewTrack } from '@/types';
import { api } from '@/api';
import { showToast } from '@/composables/useToast';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select';
import { ArrowLeft, Check, Loader2, Music2, RefreshCw, AlertCircle } from 'lucide-vue-next';

type QualityType = 'flac' | '320k' | '128k' | string;
type SourceType = 'auto' | 'tx' | 'wy' | 'kw' | 'kg';

interface Props {
  url: string;
  accountId?: string;
  provider?: string;
  initialPlaylistName?: string;
  defaultTargetType?: 'public' | 'user';
  defaultTargetUser?: string;
  userList?: Array<{ id: number; name: string }>;
  initialPreview?: PlaylistPreview | null;
  showBackButton?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  accountId: '',
  provider: '',
  initialPlaylistName: '',
  defaultTargetType: undefined,
  defaultTargetUser: '',
  userList: () => [],
  initialPreview: null,
  showBackButton: true,
});

const emit = defineEmits<{
  (e: 'back'): void;
  (e: 'started'): void;
  (e: 'cancel'): void;
}>();

const preview = ref<PlaylistPreview | null>(props.initialPreview || null);
const selectedIndexes = ref<number[]>([]);
const playlistName = ref(props.initialPlaylistName || '');
const resolvedAccountUser = ref(props.defaultTargetUser || '');

// 优先读取云端账号绑定的飞牛用户
const boundUserName = computed(() => {
  return preview.value?.matched_account?.owner_user || props.defaultTargetUser || resolvedAccountUser.value || '';
});

const targetType = ref<'public' | 'user'>(
  props.defaultTargetType
    ? props.defaultTargetType
    : (props.defaultTargetUser || props.accountId ? 'user' : 'public')
);
const targetUser = ref(props.defaultTargetUser || '');
const parsing = ref(false);
const parseError = ref('');
const starting = ref(false);

const globalQuality = ref<string>('flac');
const trackQualityMap = ref<Record<number, string>>({});

function resolveDefaultSource(): SourceType {
  const p = (props.provider || '').toLowerCase();
  const plat = (preview.value?.platform || '').toLowerCase();
  const targetUrl = props.url.toLowerCase();
  if (p === 'qq' || plat.includes('qq') || targetUrl.includes('qq.com')) return 'tx';
  if (p === 'netease' || plat.includes('网易') || plat.includes('163') || targetUrl.includes('163.com')) return 'wy';
  return 'auto';
}

const selectedSource = ref<SourceType>(resolveDefaultSource());

const selectedCount = computed(() => selectedIndexes.value.length);
const allSelected = computed(() => !!preview.value && preview.value.tracks.length > 0 && selectedCount.value === preview.value.tracks.length);
const reusedCount = computed(() => preview.value?.tracks.filter(t => t.exists).length || 0);
const selectedTracks = computed(() => preview.value?.tracks.filter(track => selectedIndexes.value.includes(track.index)) || []);

function getTrackQualities(track: PlaylistPreviewTrack): Array<{ value: string; label: string }> {
  const raw = track.available_qualities && track.available_qualities.length > 0
    ? track.available_qualities
    : ['flac', '320k', '128k'];
  const map: Record<string, string> = {
    'flac24bit': 'Hi-Res',
    'flac': 'FLAC',
    '320k': '320K',
    '128k': '128K'
  };
  return raw.map(q => ({
    value: q,
    label: map[q] || q.toUpperCase()
  }));
}

function getTrackQuality(track: PlaylistPreviewTrack): string {
  if (trackQualityMap.value[track.index]) {
    return trackQualityMap.value[track.index];
  }
  const quals = track.available_qualities && track.available_qualities.length > 0
    ? track.available_qualities
    : ['flac', '320k', '128k'];
  if (quals.includes(globalQuality.value)) {
    return globalQuality.value;
  }
  if (globalQuality.value === 'flac') {
    return quals[0] || 'flac';
  }
  if (quals.includes('320k')) return '320k';
  if (quals.includes('128k')) return '128k';
  return quals[0] || 'flac';
}

function setTrackQuality(index: number, q: string) {
  trackQualityMap.value[index] = q;
}

function handleGlobalQualityChange(val: any) {
  const q = String(val);
  globalQuality.value = q;
  if (preview.value?.tracks) {
    for (const track of preview.value.tracks) {
      const quals = track.available_qualities && track.available_qualities.length > 0
        ? track.available_qualities
        : ['flac', '320k', '128k'];
      if (quals.includes(q)) {
        trackQualityMap.value[track.index] = q;
      } else {
        trackQualityMap.value[track.index] = quals[0] || q;
      }
    }
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

async function doParse() {
  const targetUrl = props.url.trim();
  if (!targetUrl) {
    parseError.value = '缺少歌单解析地址';
    return;
  }
  parsing.value = true;
  parseError.value = '';
  try {
    const res = await api.parsePlaylist(targetUrl, props.accountId || undefined);
    if (!res.ok || !res.data) throw new Error(res.error || '无法解析这个歌单链接');
    preview.value = res.data;
    playlistName.value = res.data.playlist_name || props.initialPlaylistName || '未命名歌单';
    selectedIndexes.value = res.data.tracks.map(track => track.index);
    globalQuality.value = 'flac';
    selectedSource.value = resolveDefaultSource();
    trackQualityMap.value = {};
    for (const track of res.data.tracks) {
      trackQualityMap.value[track.index] = 'flac';
    }
    if (res.data.matched_account?.owner_user) {
      resolvedAccountUser.value = res.data.matched_account.owner_user;
      if (!props.defaultTargetUser) {
        targetUser.value = res.data.matched_account.owner_user;
        if (!props.defaultTargetType) targetType.value = 'user';
      }
    }
    if (!res.data.tracks.length) {
      showToast('歌单解析成功，但没有可导入的歌曲。', 'warning');
    }
  } catch (e: any) {
    parseError.value = e.message || '歌单解析失败';
  } finally {
    parsing.value = false;
  }
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
      quality: getTrackQuality(track)
    }));

    const finalUser = targetUser.value || boundUserName.value || (props.userList[0]?.name || 'admin');
    const res = await api.startTask({
      url: props.url.trim(),
      target: targetType.value,
      user: finalUser,
      playlist_name: playlistName.value.trim(),
      quality: globalQuality.value,
      source: selectedSource.value,
      tracks: tracksPayload,
      cover_url: preview.value?.cover_url || '',
      account_id: props.accountId || preview.value?.matched_account?.id || undefined
    });
    if (!res.ok) throw new Error(res.error || res.message || '歌单未能开始导入');
    showToast(`《${playlistName.value.trim()}》已开始导入，共 ${selectedTracks.value.length} 首歌曲。`, 'success');
    emit('started');
  } catch (e: any) {
    showToast(`导入失败：${e.message}`, 'error');
  } finally {
    starting.value = false;
  }
}

watch(() => props.defaultTargetUser, (newVal) => {
  if (newVal) {
    targetUser.value = newVal;
    resolvedAccountUser.value = newVal;
    if (!props.defaultTargetType) targetType.value = 'user';
  }
});

watch(() => props.defaultTargetType, (newVal) => {
  if (newVal) {
    targetType.value = newVal;
  }
});

watch(() => props.userList, (list) => {
  if (list && list.length > 0) {
    if (!targetUser.value || !list.some(u => u.name === targetUser.value)) {
      const preferred = boundUserName.value;
      if (preferred && list.some(u => u.name === preferred)) {
        targetUser.value = preferred;
      } else {
        targetUser.value = list[0].name;
      }
    }
  }
}, { immediate: true });

watch(() => preview.value, (newPreview) => {
  if (newPreview?.matched_account?.owner_user) {
    resolvedAccountUser.value = newPreview.matched_account.owner_user;
    if (!props.defaultTargetUser) {
      targetUser.value = newPreview.matched_account.owner_user;
      if (!props.defaultTargetType) targetType.value = 'user';
    }
  }
}, { immediate: true });

watch(() => props.url, (newUrl) => {
  if (newUrl && (!preview.value || preview.value.playlist_name !== props.initialPlaylistName)) {
    doParse();
  }
});

watch(() => props.initialPreview, (val) => {
  if (val) {
    preview.value = val;
    playlistName.value = val.playlist_name || props.initialPlaylistName || '未命名歌单';
    selectedIndexes.value = val.tracks.map(track => track.index);
    selectedSource.value = resolveDefaultSource();
    if (val.matched_account?.owner_user) {
      resolvedAccountUser.value = val.matched_account.owner_user;
      if (!props.defaultTargetUser) {
        targetUser.value = val.matched_account.owner_user;
        if (!props.defaultTargetType) targetType.value = 'user';
      }
    }
  }
}, { immediate: true });

onMounted(async () => {
  selectedSource.value = resolveDefaultSource();
  if (props.accountId || props.url) {
    try {
      const accRes = await api.getMusicAccounts();
      if (accRes.ok && Array.isArray(accRes.data)) {
        let matched = null;
        if (props.accountId) {
          matched = accRes.data.find(a => a.id === props.accountId || a.provider === props.accountId);
        }
        if (!matched && props.url) {
          const urlLower = props.url.toLowerCase();
          if (urlLower.includes('qq.com')) matched = accRes.data.find(a => a.provider === 'qq' && a.connected);
          else if (urlLower.includes('163.com')) matched = accRes.data.find(a => a.provider === 'netease' && a.connected);
        }
        if (matched && matched.owner_user) {
          resolvedAccountUser.value = matched.owner_user;
          if (!targetUser.value || !props.defaultTargetUser) {
            targetUser.value = matched.owner_user;
            if (!props.defaultTargetType) targetType.value = 'user';
          }
        }
      }
    } catch {}
  }
  if (!preview.value && props.url) {
    doParse();
  }
});
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col overflow-hidden">
    <!-- 正在解析 Loading 状态 -->
    <div v-if="parsing" class="flex min-h-[360px] flex-1 flex-col items-center justify-center text-center p-6 space-y-3">
      <div class="relative grid h-14 w-14 place-items-center rounded-2xl bg-primary/10 text-primary shadow-inner">
        <Loader2 class="h-7 w-7 animate-spin" />
      </div>
      <div>
        <p class="text-sm font-bold text-foreground">正在解析歌单内容…</p>
        <p class="mt-1 text-xs text-muted-foreground max-w-sm">正在提取歌单曲目、歌曲元数据与 NAS 本地查重，请稍候</p>
      </div>
      <Button v-if="props.showBackButton" variant="ghost" size="sm" class="mt-2 text-xs text-muted-foreground" @click="emit('back')">
        <ArrowLeft class="h-3.5 w-3.5 mr-1" />返回歌单列表
      </Button>
    </div>

    <!-- 解析出错状态 -->
    <div v-else-if="parseError" class="flex min-h-[360px] flex-1 flex-col items-center justify-center text-center p-6 space-y-3">
      <div class="grid h-12 w-12 place-items-center rounded-2xl bg-destructive/10 text-destructive">
        <AlertCircle class="h-6 w-6" />
      </div>
      <div>
        <p class="text-sm font-bold text-foreground">歌单解析失败</p>
        <p class="mt-1 text-xs text-muted-foreground max-w-sm">{{ parseError }}</p>
      </div>
      <div class="flex items-center gap-2 pt-2">
        <Button v-if="props.showBackButton" variant="outline" size="sm" class="h-8 text-xs" @click="emit('back')">
          <ArrowLeft class="h-3.5 w-3.5 mr-1" />返回列表
        </Button>
        <Button variant="brand" size="sm" class="h-8 text-xs gap-1.5" @click="doParse">
          <RefreshCw class="h-3.5 w-3.5" />重试解析
        </Button>
      </div>
    </div>

    <!-- 解析成功：确认导入与选歌表单 -->
    <div v-else class="flex min-h-0 flex-1 flex-col overflow-hidden space-y-3">
      <!-- 歌单信息与基础配置栏 -->
      <div class="shrink-0 space-y-2.5 pt-1">
        <!-- 歌单封面与名称输入 -->
        <div class="flex items-center gap-3 rounded-xl border border-border bg-muted/20 p-2.5 sm:p-3">
          <div class="relative h-12 w-12 sm:h-14 sm:w-14 shrink-0 overflow-hidden rounded-lg bg-muted shadow-sm">
            <img v-if="preview?.cover_url" :src="preview.cover_url" alt="歌单封面" class="h-full w-full object-cover" loading="lazy" referrerpolicy="no-referrer" />
            <Music2 v-else class="absolute left-1/2 top-1/2 h-5 w-5 -translate-x-1/2 -translate-y-1/2 text-muted-foreground/50" />
          </div>
          <div class="min-w-0 flex-1 space-y-1">
            <div class="flex items-center justify-between gap-2">
              <span class="text-[10px] font-semibold text-primary/80 uppercase tracking-wider">{{ preview?.platform || '第三方平台' }}</span>
              <span class="text-[10px] text-muted-foreground font-mono">已选 {{ selectedCount }} / {{ preview?.tracks.length || 0 }} 首</span>
            </div>
            <Input v-model="playlistName" class="h-8 text-xs sm:h-9 sm:text-sm font-semibold" placeholder="歌单名称" />
          </div>
        </div>

        <!-- 导入设置网格：可见范围 + 统一品质 + 音源配置 -->
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
            <div class="flex items-center justify-between">
              <label class="block text-[11px] font-medium text-muted-foreground">所属成员</label>
              <span v-if="boundUserName && targetUser === boundUserName" class="text-[10px] text-primary font-medium">账号绑定成员</span>
            </div>
            <Select v-model="targetUser">
              <SelectTrigger class="h-8 sm:h-9 text-xs font-semibold">
                <SelectValue placeholder="选择成员" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem v-for="u in userList" :key="u.id" :value="u.name">
                  <div class="flex items-center justify-between w-full gap-2">
                    <span>{{ u.name }}</span>
                    <span v-if="u.name === boundUserName" class="text-[10px] text-primary font-semibold">(已绑定)</span>
                  </div>
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div class="space-y-1">
            <div class="flex items-center justify-between">
              <label class="block text-[11px] font-medium text-muted-foreground">统一音质</label>
              <span class="text-[10px] text-muted-foreground/75 hidden sm:inline">可单曲改</span>
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

          <div class="space-y-1" :class="targetType !== 'user' ? 'col-span-2 sm:col-span-1' : 'col-span-2 sm:col-span-1'">
            <div class="flex items-center justify-between">
              <label class="block text-[11px] font-medium text-muted-foreground">抓取音源</label>
              <span v-if="selectedSource === 'tx' || selectedSource === 'wy'" class="text-[10px] text-primary font-semibold">平台优先</span>
            </div>
            <Select v-model="selectedSource">
              <SelectTrigger class="h-8 sm:h-9 text-xs font-semibold">
                <SelectValue placeholder="选择音源" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="tx">QQ 音乐 (tx)</SelectItem>
                <SelectItem value="wy">网易云 (wy)</SelectItem>
                <SelectItem value="kw">酷我音乐 (kw)</SelectItem>
                <SelectItem value="kg">酷狗音乐 (kg)</SelectItem>
                <SelectItem value="auto">智能聚合 (auto)</SelectItem>
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
      <div class="min-h-0 flex-1 overflow-y-auto overscroll-contain rounded-xl border border-border bg-card divide-y divide-border/60 pr-0.5 custom-scrollbar">
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
                :model-value="getTrackQuality(track)"
                @update:model-value="(val: any) => setTrackQuality(track.index, val as string)"
              >
                <SelectTrigger class="h-7 min-w-[70px] sm:min-w-[78px] px-1.5 py-0 text-[10px] font-semibold tracking-tight">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent align="end">
                  <SelectItem
                    v-for="q in getTrackQualities(track)"
                    :key="q.value"
                    :value="q.value"
                  >
                    {{ q.label }}
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>
      </div>

      <!-- 底部操作按钮栏 -->
      <div class="shrink-0 border-t border-border pt-3 flex items-center justify-between gap-2">
        <Button v-if="props.showBackButton" variant="ghost" size="sm" class="h-8 px-2.5 text-xs text-muted-foreground" @click="emit('back')">
          <ArrowLeft class="h-3.5 w-3.5 mr-1" />返回列表
        </Button>
        <Button v-else variant="ghost" size="sm" class="h-8 px-2.5 text-xs text-muted-foreground" @click="emit('cancel')">
          取消
        </Button>

        <div class="flex items-center gap-2">
          <Button variant="outline" size="sm" class="h-8 px-2.5 text-xs" :disabled="parsing" @click="doParse">
            <RefreshCw class="h-3.5 w-3.5 mr-1" :class="parsing ? 'animate-spin' : ''" />重新解析
          </Button>
          <Button
            variant="brand"
            size="sm"
            class="h-8 px-4 text-xs font-semibold shadow-sm"
            :disabled="starting || !selectedTracks.length"
            @click="handleSubmit"
          >
            <Loader2 v-if="starting" class="h-3.5 w-3.5 animate-spin mr-1.5" />
            <span>{{ starting ? '正在启动…' : `开始导入 (${selectedCount})` }}</span>
          </Button>
        </div>
      </div>
    </div>
  </div>
</template>
