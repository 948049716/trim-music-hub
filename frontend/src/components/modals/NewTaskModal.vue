<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import type { PlaylistPreview, PlaylistPreviewTrack } from '@/types';
import { api } from '@/api';
import { showToast } from '@/composables/useToast';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select';
import { ArrowLeft, Check, Link2, Loader2, Music2, RefreshCw } from 'lucide-vue-next';

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{ (e: 'close'): void; (e: 'update:open', val: boolean): void; (e: 'started'): void }>();

const step = ref<1 | 2>(1);
const playlistUrl = ref('');
const preview = ref<PlaylistPreview | null>(null);
const selectedIndexes = ref<number[]>([]);
const playlistName = ref('');
const targetType = ref<'public' | 'user'>('public');
const targetUser = ref('');
const userList = ref<Array<{ id: number; name: string }>>([]);
const parsing = ref(false);
const starting = ref(false);

const selectedCount = computed(() => selectedIndexes.value.length);
const allSelected = computed(() => !!preview.value && preview.value.tracks.length > 0 && selectedCount.value === preview.value.tracks.length);
const selectedTracks = computed(() => preview.value?.tracks.filter(track => selectedIndexes.value.includes(track.index)) || []);

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
  preview.value = null;
  selectedIndexes.value = [];
  playlistName.value = '';
  targetType.value = 'public';
  targetUser.value = userList.value[0]?.name || '';
  parsing.value = false;
  starting.value = false;
}

async function handleParse() {
  const url = playlistUrl.value.trim();
  if (!url) {
    showToast('粘贴歌单链接或分享文本后再解析。', 'warning');
    return;
  }
  parsing.value = true;
  try {
    const res = await api.parsePlaylist(url);
    if (!res.ok || !res.data) throw new Error(res.error || '无法解析这个歌单链接');
    preview.value = res.data;
    playlistName.value = res.data.playlist_name || '未命名歌单';
    selectedIndexes.value = res.data.tracks.map(track => track.index);
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
    const res = await api.startTask({
      url: playlistUrl.value.trim(),
      target: targetType.value,
      user: targetUser.value,
      playlist_name: playlistName.value.trim(),
      tracks: selectedTracks.value
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

onMounted(loadUsers);
</script>

<template>
  <Dialog :open="props.open" @update:open="handleOpenUpdate">
    <DialogContent class="sm:max-w-3xl">
      <DialogHeader class="pr-8">
        <div class="flex items-start gap-3">
          <Button v-if="step === 2" variant="ghost" size="icon" class="-ml-2 shrink-0" aria-label="返回修改链接" @click="backToInput">
            <ArrowLeft class="h-4 w-4" />
          </Button>
          <div v-else class="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary"><Link2 class="h-5 w-5" /></div>
          <div class="min-w-0">
            <DialogTitle class="text-lg font-bold tracking-[-0.02em] text-foreground">{{ step === 1 ? '导入歌单' : '确认导入内容' }}</DialogTitle>
            <DialogDescription class="pt-1 text-xs leading-relaxed text-muted-foreground">
              {{ step === 1 ? '先解析链接，确认歌曲后再开始下载。' : `已解析 ${preview?.tracks.length || 0} 首歌曲，可取消不需要的歌曲。` }}
            </DialogDescription>
          </div>
        </div>
      </DialogHeader>

      <div v-if="step === 1" class="space-y-4 py-1">
        <div class="space-y-2">
          <label class="block text-xs font-semibold text-foreground">歌单链接或分享文本</label>
          <Input v-model="playlistUrl" type="text" class="h-11" placeholder="粘贴网易云或 QQ 音乐歌单链接" @keyup.enter="handleParse" />
        </div>
        <div class="rounded-xl border border-dashed border-border bg-muted/25 p-3 text-[11px] leading-5 text-muted-foreground">
          <span class="font-semibold text-foreground">导入流程：</span>解析歌单 → 选择歌曲 → 修改歌单名称与可见范围 → 开始下载。
        </div>
      </div>

      <div v-else class="min-h-0 space-y-4 py-1">
        <div class="grid gap-3 sm:grid-cols-[minmax(0,1fr)_220px]">
          <div class="flex min-w-0 items-center gap-3 rounded-2xl border border-border bg-muted/25 p-3">
            <div class="relative h-14 w-14 shrink-0 overflow-hidden rounded-xl bg-muted">
              <img v-if="preview?.cover_url" :src="preview.cover_url" alt="歌单封面" class="h-full w-full object-cover" loading="lazy" referrerpolicy="no-referrer" />
              <Music2 v-else class="absolute left-1/2 top-1/2 h-5 w-5 -translate-x-1/2 -translate-y-1/2 text-muted-foreground/50" />
            </div>
            <div class="min-w-0">
              <p class="truncate text-sm font-bold">{{ preview?.playlist_name }}</p>
              <p class="mt-1 text-[10px] text-muted-foreground">{{ preview?.platform }} · 已选 {{ selectedCount }} / {{ preview?.tracks.length || 0 }} 首</p>
            </div>
          </div>
          <div class="space-y-2">
            <label class="block text-xs font-semibold text-foreground">导入后的歌单名</label>
            <Input v-model="playlistName" class="h-10" placeholder="输入歌单名称" />
          </div>
        </div>

        <div class="grid gap-3 sm:grid-cols-2">
          <div class="space-y-2">
            <label class="block text-xs font-semibold text-foreground">谁可以看到</label>
            <Select v-model="targetType"><SelectTrigger class="h-10"><SelectValue placeholder="选择可见范围" /></SelectTrigger><SelectContent><SelectItem value="public">所有家庭成员</SelectItem><SelectItem value="user">指定成员</SelectItem></SelectContent></Select>
          </div>
          <div v-if="targetType === 'user'" class="space-y-2">
            <label class="block text-xs font-semibold text-foreground">选择成员</label>
            <Select v-model="targetUser"><SelectTrigger class="h-10"><SelectValue placeholder="选择成员" /></SelectTrigger><SelectContent><SelectItem v-for="u in userList" :key="u.id" :value="u.name">{{ u.name }}</SelectItem></SelectContent></Select>
          </div>
        </div>

        <div class="flex items-center justify-between rounded-xl border border-border bg-muted/25 px-3 py-2.5">
          <label class="flex items-center gap-2 text-xs font-semibold text-foreground"><Checkbox :model-value="allSelected" @update:model-value="toggleAll" />全选歌曲</label>
          <span class="text-[10px] text-muted-foreground">已存在曲库的歌曲会复用，不会重复下载</span>
        </div>

        <div class="max-h-[45vh] overflow-y-auto rounded-2xl border border-border pr-1">
          <div v-if="!preview?.tracks.length" class="grid min-h-40 place-items-center text-xs text-muted-foreground">没有可导入的歌曲</div>
          <label v-for="track in preview?.tracks" :key="track.index" class="group flex cursor-pointer items-center gap-3 border-b border-border/70 px-3 py-2.5 last:border-b-0 hover:bg-muted/30">
            <Checkbox :model-value="selectedIndexes.includes(track.index)" @update:model-value="value => toggleTrack(track, value)" />
            <img v-if="track.cover" :src="track.cover" :alt="`${track.title}封面`" class="h-10 w-10 shrink-0 rounded-lg object-cover" loading="lazy" referrerpolicy="no-referrer" />
            <div v-else class="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-muted text-muted-foreground"><Music2 class="h-4 w-4" /></div>
            <div class="min-w-0 flex-1"><p class="truncate text-xs font-semibold">{{ track.title }}</p><p class="mt-0.5 truncate text-[10px] text-muted-foreground">{{ track.artist }}<span v-if="track.album"> · {{ track.album }}</span></p></div>
            <span v-if="track.exists" class="flex shrink-0 items-center gap-1 text-[10px] text-emerald-600 dark:text-emerald-400"><Check class="h-3 w-3" />已收录</span>
          </label>
        </div>
      </div>

      <DialogFooter class="flex-row justify-between gap-2 border-t border-border pt-4">
        <Button variant="ghost" @click="closeModal">取消</Button>
        <div class="flex gap-2">
          <Button v-if="step === 2" variant="outline" @click="backToInput"><RefreshCw class="h-4 w-4" />重新解析</Button>
          <Button v-if="step === 1" @click="handleParse" :disabled="parsing"><Loader2 v-if="parsing" class="h-4 w-4 animate-spin" /><span>{{ parsing ? '正在解析…' : '解析歌单' }}</span></Button>
          <Button v-else @click="handleSubmit" :disabled="starting || !selectedTracks.length"><Loader2 v-if="starting" class="h-4 w-4 animate-spin" /><span>{{ starting ? '正在启动…' : `开始导入（${selectedCount}）` }}</span></Button>
        </div>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
