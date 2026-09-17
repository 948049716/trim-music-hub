<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue';
import { api } from '../../api';
import { showToast } from '../../composables/useToast';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter
} from '@/components/ui/dialog';
import {
  Settings,
  Check,
  Sparkles,
  Loader2,
  Sliders,
  Server,
  Key,
  Link2,
  FolderCheck,
  FolderOpen,
  AlertTriangle,
  RefreshCw,
  FolderPlus,
} from 'lucide-vue-next';
import type { SettingsData, AuthorizedDirectory } from '../../types';

const props = defineProps<{
  open: boolean;
  isFirstInstall?: boolean;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'update:open', val: boolean): void;
  (e: 'updated', source: string, dir: string): void;
}>();

const activeSubTab = ref<'directory' | 'source'>('directory');

const currentSource = ref<'kw' | 'kg' | 'tx' | 'wy' | 'auto' | 'custom'>('kw');
const downloadDir = ref<string>('');
const isConfigured = ref<boolean>(true);
const authorizedDirs = ref<AuthorizedDirectory[]>([]);
const isLoadingDirs = ref<boolean>(false);
const customDirInput = ref<string>('');
const dirVerifyResult = ref<{
  ok: boolean;
  exists: boolean;
  writable: boolean;
  is_fnos_authorized: boolean;
  error: string | null;
} | null>(null);
const isVerifyingDir = ref<boolean>(false);

const availableSources = ref<SettingsData['available_sources']>([
  { id: 'kw', name: '酷我音乐', desc: '高品质FLAC专线 · 推荐默认', default: true },
  { id: 'kg', name: '酷狗音乐', desc: '海棠/星海SVIP线路', default: false },
  { id: 'tx', name: 'QQ音乐', desc: '长青/溯音专线', default: false },
  { id: 'wy', name: '网易云音乐', desc: '163云音乐线路', default: false },
  { id: 'auto', name: '智能多源聚合', desc: '酷我优先，故障自动回退', default: false },
  { id: 'custom', name: '自定义音源', desc: '自建 API 端点 / 远程源脚本解析', default: false }
]);

const customConfig = ref({
  name: '自建音乐解析服务',
  api_url: '',
  api_key: '',
  script_url: ''
});

const isSaving = ref(false);

async function loadDirectories() {
  isLoadingDirs.value = true;
  try {
    const res = await api.getAuthorizedDirectories();
    if (res.ok && res.data) {
      authorizedDirs.value = res.data;
    }
  } catch (e) {
    console.error('Failed to load authorized directories:', e);
  } finally {
    isLoadingDirs.value = false;
  }
}

async function verifyCustomDirectory(targetPath: string) {
  if (!targetPath.trim()) {
    dirVerifyResult.value = null;
    return;
  }
  isVerifyingDir.value = true;
  try {
    const res = await api.verifyDirectory(targetPath.trim());
    if (res.ok && res.data) {
      dirVerifyResult.value = res.data;
      if (res.data.ok) {
        downloadDir.value = res.data.path;
      }
    } else {
      dirVerifyResult.value = {
        ok: false,
        exists: false,
        writable: false,
        is_fnos_authorized: false,
        error: '目录验证请求失败'
      };
    }
  } catch (e: any) {
    dirVerifyResult.value = {
      ok: false,
      exists: false,
      writable: false,
      is_fnos_authorized: false,
      error: e.message
    };
  } finally {
    isVerifyingDir.value = false;
  }
}

function selectDirectory(d: AuthorizedDirectory) {
  downloadDir.value = d.path;
  customDirInput.value = d.path;
  dirVerifyResult.value = {
    ok: d.writable,
    exists: d.exists,
    writable: d.writable,
    is_fnos_authorized: d.is_fnos_authorized,
    error: d.writable ? null : '该目录不可写'
  };
}

async function loadSettings() {
  try {
    await loadDirectories();
    const res = await api.getSettings();
    if (res.ok && res.data) {
      currentSource.value = res.data.download_source || 'kw';
      downloadDir.value = res.data.download_dir || res.data.effective_music_dir || '';
      customDirInput.value = downloadDir.value;
      isConfigured.value = res.data.is_configured ?? true;

      if (res.data.available_sources) {
        availableSources.value = res.data.available_sources;
      }
      if (res.data.custom_source) {
        customConfig.value = {
          name: res.data.custom_source.name || '自建音乐解析服务',
          api_url: res.data.custom_source.api_url || '',
          api_key: res.data.custom_source.api_key || '',
          script_url: res.data.custom_source.script_url || ''
        };
      }

      if (downloadDir.value) {
        verifyCustomDirectory(downloadDir.value);
      }
    }
  } catch (e) {}
}

async function handleSave() {
  if (!downloadDir.value.trim()) {
    showToast('请先选择一个可用的音乐保存目录。', 'warning');
    activeSubTab.value = 'directory';
    return;
  }

  if (dirVerifyResult.value && !dirVerifyResult.value.writable) {
    showToast('当前目录不可写，请检查权限或选择其他目录。', 'error');
    activeSubTab.value = 'directory';
    return;
  }

  if (currentSource.value === 'custom' && !customConfig.value.api_url.trim() && !customConfig.value.script_url.trim()) {
    showToast('使用自定义音源时，请填写 API 地址或源脚本地址。', 'warning');
    activeSubTab.value = 'source';
    return;
  }

  isSaving.value = true;
  try {
    const res = await api.updateSettings(
      currentSource.value,
      customConfig.value,
      downloadDir.value.trim(),
      true
    );
    if (res.ok) {
      showToast('设置已保存。', 'success');
      emit('updated', currentSource.value, downloadDir.value.trim());
      emit('close');
      emit('update:open', false);
    } else {
      showToast('设置保存失败', 'error');
    }
  } catch (e: any) {
    showToast(`保存失败： ${e.message}`, 'error');
  } finally {
    isSaving.value = false;
  }
}

function handleOpenUpdate(val: boolean) {
  emit('update:open', val);
  if (!val) emit('close');
}

watch(() => props.open, (val) => {
  if (val) {
    if (props.isFirstInstall) {
      activeSubTab.value = 'directory';
    }
    loadSettings();
  }
});

onMounted(() => {
  loadSettings();
});
const selectedSourceName = computed(() =>
  availableSources.value.find(source => source.id === currentSource.value)?.name || currentSource.value.toUpperCase()
);

const compactDownloadDir = computed(() => {
  const path = downloadDir.value.trim();
  if (!path) return '尚未选择';
  return path.split(/[\\/]/).filter(Boolean).at(-1) || path;
});
</script>
<template>
  <Dialog :open="props.open" @update:open="handleOpenUpdate">
    <DialogContent
      class="!inset-x-0 !bottom-0 !top-4 !h-[calc(100dvh-1rem)] !max-h-[calc(100dvh-1rem)] !grid-rows-[auto_auto_minmax(0,1fr)_auto] !gap-0 !overflow-hidden !rounded-b-none !rounded-t-[1.75rem] !border-b-0 !p-0 shadow-[0_-18px_70px_hsl(var(--shadow-color)/.3)] sm:!left-1/2 sm:!top-1/2 sm:!bottom-auto sm:!h-[min(88dvh,780px)] sm:!max-h-[min(88dvh,780px)] sm:!max-w-xl sm:!-translate-x-1/2 sm:!-translate-y-1/2 sm:!rounded-[1.4rem] sm:!border-b sm:shadow-[0_30px_90px_hsl(var(--shadow-color)/.3)]"
    >
      <DialogHeader class="shrink-0 border-b border-border/80 px-5 pb-4 pr-14 pt-5 text-left sm:px-6 sm:pb-5 sm:pt-6">
        <div class="flex items-start gap-3">
          <div class="grid h-10 w-10 shrink-0 place-items-center rounded-2xl bg-primary/10 text-primary">
            <Settings class="h-5 w-5" />
          </div>
          <div class="min-w-0 pt-0.5">
            <div class="flex flex-wrap items-center gap-2">
              <DialogTitle class="text-[17px] font-bold tracking-tight text-foreground">
                {{ props.isFirstInstall ? '开始前完成设置' : '下载设置' }}
              </DialogTitle>
              <Badge v-if="props.isFirstInstall" variant="brand" class="h-5 px-2 text-[9px]">首次使用</Badge>
            </div>
            <DialogDescription class="mt-1 text-[11px] leading-5 text-muted-foreground sm:text-xs">
              {{ props.isFirstInstall ? '选择飞牛音乐目录，再确认下载音源。' : '管理歌曲保存位置和下载音源。' }}
            </DialogDescription>
          </div>
        </div>
      </DialogHeader>

      <div class="shrink-0 border-b border-border/70 bg-muted/35 px-4 py-3 sm:px-6">
        <div class="grid grid-cols-2 gap-1 rounded-2xl bg-muted p-1">
          <Button variant="ghost"
            type="button"
            class="h-auto min-w-0 justify-start whitespace-normal rounded-xl px-3 py-2 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
            :class="activeSubTab === 'directory' ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'"
            @click="activeSubTab = 'directory'"
          >
            <span class="flex items-center gap-2 text-xs font-semibold">
              <FolderCheck class="h-3.5 w-3.5 shrink-0" />
              保存位置
            </span>
            <span class="mt-0.5 block truncate pl-[22px] text-[10px] font-normal opacity-70">{{ compactDownloadDir }}</span>
          </Button>
          <Button variant="ghost"
            type="button"
            class="h-auto min-w-0 justify-start whitespace-normal rounded-xl px-3 py-2 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
            :class="activeSubTab === 'source' ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'"
            @click="activeSubTab = 'source'"
          >
            <span class="flex items-center gap-2 text-xs font-semibold">
              <Sparkles class="h-3.5 w-3.5 shrink-0" />
              下载音源
            </span>
            <span class="mt-0.5 block truncate pl-[22px] text-[10px] font-normal opacity-70">{{ selectedSourceName }}</span>
          </Button>
        </div>
      </div>

      <div class="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-4 sm:px-6 sm:py-5">
        <section v-show="activeSubTab === 'directory'" class="space-y-5">
          <div>
            <div class="mb-3 flex items-center justify-between gap-3">
              <div>
                <h3 class="text-sm font-bold text-foreground">选择音乐目录</h3>
                <p class="mt-0.5 text-[10px] leading-4 text-muted-foreground">新歌曲、歌词和封面会保存到这里。</p>
              </div>
              <Button type="button" variant="outline" size="sm" class="h-8 shrink-0 gap-1.5 px-2.5 text-[11px]" :disabled="isLoadingDirs" @click="loadDirectories">
                <RefreshCw class="h-3 w-3" :class="isLoadingDirs ? 'animate-spin' : ''" />
                刷新
              </Button>
            </div>

            <div class="space-y-2">
              <Button variant="ghost"
                v-for="d in authorizedDirs"
                :key="d.path"
                type="button"
                class="flex h-auto w-full items-start justify-start gap-3 whitespace-normal rounded-2xl border p-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
                :class="downloadDir === d.path ? 'border-primary/55 bg-primary/10' : 'border-border bg-card hover:bg-muted/45'"
                @click="selectDirectory(d)"
              >
                <span
                  class="grid h-10 w-10 shrink-0 place-items-center rounded-xl"
                  :class="downloadDir === d.path ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'"
                >
                  <FolderCheck v-if="d.is_fnos_authorized" class="h-4 w-4" />
                  <FolderOpen v-else class="h-4 w-4" />
                </span>
                <span class="min-w-0 flex-1">
                  <span class="flex flex-wrap items-center gap-1.5">
                    <strong class="text-xs text-foreground">{{ d.name }}</strong>
                    <span v-if="d.is_fnos_authorized" class="rounded-full bg-primary/10 px-1.5 py-0.5 text-[9px] font-semibold text-primary">飞牛曲库</span>
                    <span v-if="d.writable" class="rounded-full bg-emerald-500/10 px-1.5 py-0.5 text-[9px] font-semibold text-emerald-700 dark:text-emerald-300">可写入</span>
                    <span v-else class="rounded-full bg-destructive/10 px-1.5 py-0.5 text-[9px] font-semibold text-destructive">不可写</span>
                  </span>
                  <span class="mt-1 block break-all font-mono text-[10px] leading-4 text-muted-foreground">{{ d.path }}</span>
                  <span class="mt-0.5 block text-[10px] text-muted-foreground">约 {{ d.file_count }} 个音频文件</span>
                </span>
                <span
                  class="mt-2 grid h-5 w-5 shrink-0 place-items-center rounded-full border"
                  :class="downloadDir === d.path ? 'border-primary bg-primary text-primary-foreground' : 'border-border'"
                >
                  <Check v-if="downloadDir === d.path" class="h-3 w-3 stroke-[3]" />
                </span>
              </Button>

              <div v-if="isLoadingDirs" class="flex min-h-20 items-center justify-center gap-2 rounded-2xl border border-dashed border-border text-xs text-muted-foreground">
                <Loader2 class="h-4 w-4 animate-spin text-primary" />正在读取飞牛授权目录…
              </div>
              <div v-else-if="authorizedDirs.length === 0" class="rounded-2xl border border-dashed border-border px-4 py-5 text-center">
                <p class="text-xs font-semibold text-foreground">没有发现授权目录</p>
                <p class="mt-1 text-[10px] leading-4 text-muted-foreground">可以在下方直接填写音乐目录。</p>
              </div>
            </div>
          </div>

          <div class="rounded-2xl border border-border bg-muted/30 p-3.5">
            <div class="mb-2 flex items-center justify-between gap-3">
              <label class="flex items-center gap-2 text-xs font-semibold text-foreground">
                <FolderPlus class="h-3.5 w-3.5 text-primary" />手动填写目录
              </label>
              <span v-if="isVerifyingDir" class="flex items-center gap-1 text-[10px] text-muted-foreground">
                <Loader2 class="h-3 w-3 animate-spin" />正在检查
              </span>
            </div>
            <div class="flex flex-col gap-2 sm:flex-row">
              <Input v-model="customDirInput" placeholder="例如：/vol2/1000/媒体/音乐" class="h-10 min-w-0 flex-1 bg-card font-mono text-[11px]" @keyup.enter="verifyCustomDirectory(customDirInput)" />
              <Button type="button" variant="secondary" class="h-10 shrink-0 gap-1.5 text-xs" :disabled="isVerifyingDir || !customDirInput.trim()" @click="verifyCustomDirectory(customDirInput)">
                <FolderCheck class="h-3.5 w-3.5" />检查并使用
              </Button>
            </div>

            <div
              v-if="dirVerifyResult"
              class="mt-3 flex items-start gap-2 rounded-xl border p-2.5 text-[11px] leading-4"
              :class="dirVerifyResult.ok ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300' : 'border-destructive/30 bg-destructive/10 text-destructive'"
            >
              <Check v-if="dirVerifyResult.ok" class="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <AlertTriangle v-else class="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <div>
                <p class="font-semibold">{{ dirVerifyResult.ok ? '目录可正常写入' : '这个目录无法使用' }}</p>
                <p v-if="dirVerifyResult.is_fnos_authorized" class="mt-0.5 opacity-80">这是飞牛音乐授权目录，下载后可自动入库。</p>
                <p v-if="dirVerifyResult.error" class="mt-0.5 opacity-80">{{ dirVerifyResult.error }}</p>
              </div>
            </div>
          </div>

          <details class="group rounded-2xl border border-border bg-card px-3.5 py-3 text-[11px] text-muted-foreground">
            <summary class="cursor-pointer list-none font-semibold text-foreground marker:hidden">为什么推荐飞牛授权目录？</summary>
            <p class="mt-2 leading-5">保存到飞牛音乐已授权的目录后，新下载的歌曲、歌词和封面可以被飞牛音乐自动扫描和整理。</p>
          </details>
        </section>

        <section v-show="activeSubTab === 'source'" class="space-y-5">
          <div>
            <div class="mb-3">
              <h3 class="text-sm font-bold text-foreground">选择下载音源</h3>
              <p class="mt-0.5 text-[10px] leading-4 text-muted-foreground">点击卡片切换；歌曲下载失败时可改用智能多源。</p>
            </div>

            <div class="grid grid-cols-2 gap-2.5">
              <Button variant="ghost"
                v-for="src in availableSources"
                :key="src.id"
                type="button"
                class="relative h-auto min-h-[112px] justify-start whitespace-normal rounded-2xl border p-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
                :class="currentSource === src.id ? 'border-primary/60 bg-primary/10' : 'border-border bg-card hover:bg-muted/45'"
                @click="currentSource = src.id"
              >
                <span class="flex items-start justify-between gap-2">
                  <span
                    class="grid h-8 min-w-8 place-items-center rounded-xl px-2 text-[10px] font-bold tracking-tight"
                    :class="currentSource === src.id ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'"
                  >{{ src.id.toUpperCase() }}</span>
                  <span
                    class="grid h-5 w-5 place-items-center rounded-full border"
                    :class="currentSource === src.id ? 'border-primary bg-primary text-primary-foreground' : 'border-border text-transparent'"
                  >
                    <Check class="h-3 w-3 stroke-[3]" />
                  </span>
                </span>
                <strong class="mt-3 block truncate text-xs text-foreground">{{ src.name }}</strong>
                <span class="mt-1 line-clamp-2 block text-[10px] leading-4 text-muted-foreground">{{ src.desc }}</span>
                <span v-if="src.id === 'kw'" class="absolute bottom-2.5 right-3 text-[9px] font-semibold text-primary">推荐</span>
                <span v-else-if="src.id === 'auto'" class="absolute bottom-2.5 right-3 text-[9px] font-semibold text-primary">自动切换</span>
              </Button>
            </div>
          </div>

          <div v-if="currentSource === 'custom'" class="space-y-3 rounded-2xl border border-amber-500/25 bg-amber-500/[0.04] p-4">
            <div class="flex items-center gap-2 border-b border-border pb-2 text-xs font-bold text-amber-700 dark:text-amber-300">
              <Sliders class="h-4 w-4" />自定义音源
            </div>
            <div class="space-y-1.5">
              <label class="flex items-center gap-1.5 text-[11px] font-medium text-foreground"><Server class="h-3.5 w-3.5 text-muted-foreground" />显示名称</label>
              <Input v-model="customConfig.name" placeholder="例如：自建音乐解析" class="h-10 bg-card text-xs" />
            </div>
            <div class="space-y-1.5">
              <label class="flex items-center gap-1.5 text-[11px] font-medium text-foreground"><Link2 class="h-3.5 w-3.5 text-muted-foreground" />API 地址</label>
              <Input v-model="customConfig.api_url" placeholder="https://example.com/api/music" class="h-10 bg-card font-mono text-[11px]" />
              <p class="text-[10px] leading-4 text-muted-foreground">请求时会自动附带歌曲、歌手和音质参数。</p>
            </div>
            <div class="space-y-1.5">
              <label class="flex items-center gap-1.5 text-[11px] font-medium text-foreground"><Key class="h-3.5 w-3.5 text-muted-foreground" />访问密钥（可选）</label>
              <Input v-model="customConfig.api_key" type="password" placeholder="API Key / Token" class="h-10 bg-card font-mono text-[11px]" />
            </div>
            <div class="space-y-1.5">
              <label class="flex items-center gap-1.5 text-[11px] font-medium text-foreground"><Sparkles class="h-3.5 w-3.5 text-muted-foreground" />洛雪源脚本（可选）</label>
              <Input v-model="customConfig.script_url" placeholder="https://example.com/source.js" class="h-10 bg-card font-mono text-[11px]" />
            </div>
          </div>

          <details class="group rounded-2xl border border-border bg-card px-3.5 py-3 text-[11px] text-muted-foreground">
            <summary class="cursor-pointer list-none font-semibold text-foreground marker:hidden">音源说明</summary>
            <div class="mt-2 space-y-2 leading-5">
              <p>内置音源来自洛雪开源生态，可获取 FLAC、320K 等音质。</p>
              <p>选择“智能多源”后，当前线路失败时会自动尝试其他线路。</p>
            </div>
          </details>
        </section>
      </div>

      <DialogFooter class="safe-bottom shrink-0 border-t border-border/80 bg-popover/95 px-4 py-3 backdrop-blur sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <div class="hidden min-w-0 max-w-[270px] sm:block">
          <p class="text-[9px] text-muted-foreground">当前保存位置</p>
          <p class="truncate font-mono text-[10px] text-foreground/75">{{ downloadDir || '尚未选择' }}</p>
        </div>
        <div class="grid w-full grid-cols-[0.8fr_1.2fr] gap-2 sm:flex sm:w-auto">
          <Button v-if="!props.isFirstInstall" variant="outline" class="h-10" @click="emit('close')">稍后再说</Button>
          <Button class="h-10 gap-1.5 font-semibold" :disabled="isSaving" @click="handleSave">
            <Loader2 v-if="isSaving" class="h-3.5 w-3.5 animate-spin" />
            <span>{{ isSaving ? '正在保存…' : (props.isFirstInstall ? '完成设置' : '保存更改') }}</span>
          </Button>
        </div>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>