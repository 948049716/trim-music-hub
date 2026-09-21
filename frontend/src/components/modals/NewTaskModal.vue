<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';
import type { PlaylistPreview } from '@/types';
import { api } from '@/api';
import { showToast } from '@/composables/useToast';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { ArrowLeft, Link2, Loader2 } from 'lucide-vue-next';
import PlaylistImportConfirm from './PlaylistImportConfirm.vue';

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
const playlistName = ref('');
const preview = ref<PlaylistPreview | null>(null);
const userList = ref<Array<{ id: number; name: string }>>([]);
const parsing = ref(false);

async function loadUsers() {
  try {
    const res = await api.getUsers();
    if (res.ok && res.data.length) {
      userList.value = res.data;
    }
  } catch {}
}

function reset() {
  step.value = 1;
  playlistUrl.value = '';
  accountId.value = '';
  preview.value = null;
  playlistName.value = '';
  parsing.value = false;
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
    step.value = 2;
    if (!res.data.tracks.length) showToast('歌单解析成功，但没有可导入的歌曲。', 'warning');
  } catch (e: any) {
    showToast(`解析失败：${e.message}`, 'error');
  } finally {
    parsing.value = false;
  }
}

function closeModal() {
  reset();
  emit('close');
  emit('update:open', false);
}

function handleOpenUpdate(val: boolean) {
  if (!val) closeModal();
}

function backToInput() {
  step.value = 1;
}

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

        <DialogFooter class="pt-2 flex flex-row items-center justify-between gap-2">
          <Button variant="ghost" size="sm" class="h-9 px-3 text-xs" @click="closeModal">取消</Button>
          <Button size="sm" class="h-9 px-4 text-xs font-semibold" :disabled="parsing || !playlistUrl.trim()" @click="() => handleParse()">
            <Loader2 v-if="parsing" class="h-3.5 w-3.5 animate-spin mr-1" />
            <span>{{ parsing ? '正在解析…' : '解析歌单' }}</span>
          </Button>
        </DialogFooter>
      </div>

      <!-- Step 2: 复用歌单确认与选歌组件 -->
      <div v-else class="flex min-h-0 flex-1 flex-col overflow-hidden px-4 py-3 sm:px-0 sm:py-0">
        <PlaylistImportConfirm
          :url="playlistUrl"
          :account-id="accountId"
          :initial-playlist-name="playlistName"
          :user-list="userList"
          :initial-preview="preview"
          :show-back-button="true"
          @back="backToInput"
          @started="() => { emit('started'); closeModal(); }"
          @cancel="closeModal"
        />
      </div>
    </DialogContent>
  </Dialog>
</template>
