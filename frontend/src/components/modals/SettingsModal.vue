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
  Info,
  Server,
  Key,
  Link2,
  FolderCheck,
  FolderOpen,
  HardDrive,
  AlertTriangle,
  RefreshCw,
  FolderPlus,
  ShieldCheck
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
    showToast('请先选择或配置有效的音乐下载存储目录', 'warning');
    activeSubTab.value = 'directory';
    return;
  }

  if (dirVerifyResult.value && !dirVerifyResult.value.writable) {
    showToast('当前选中的下载目录无写入权限，请检查目录权限或选择其他目录', 'error');
    activeSubTab.value = 'directory';
    return;
  }

  if (currentSource.value === 'custom' && !customConfig.value.api_url.trim() && !customConfig.value.script_url.trim()) {
    showToast('使用自定义音源时，请至少填写自定义 API 地址或源脚本 URL', 'warning');
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
      showToast('系统设置已成功保存并立即生效', 'success');
      emit('updated', currentSource.value, downloadDir.value.trim());
      emit('close');
      emit('update:open', false);
    } else {
      showToast('设置保存失败', 'error');
    }
  } catch (e: any) {
    showToast(`保存异常: ${e.message}`, 'error');
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
</script>

<template>
  <Dialog :open="props.open" @update:open="handleOpenUpdate">
    <DialogContent class="sm:max-w-xl bg-[#0d1413] border border-white/[0.14] shadow-[0_30px_90px_rgba(0,0,0,0.95)] rounded-2xl p-6 opacity-100 max-h-[90vh] overflow-y-auto">
      <DialogHeader>
        <div class="flex items-center justify-between">
          <DialogTitle class="flex items-center gap-2 text-base font-bold text-white">
            <Settings class="w-4 h-4 text-brand-400" />
            <span>{{ props.isFirstInstall ? '首次安装配置 · 存储与音源初始化' : '系统设置与下载配置' }}</span>
          </DialogTitle>
          <Badge v-if="props.isFirstInstall" variant="brand" class="text-[10px] animate-pulse">
            首次初始化
          </Badge>
        </div>
        <DialogDescription class="text-xs text-slate-400 leading-relaxed pt-1">
          {{ props.isFirstInstall 
            ? '欢迎使用 TRIM Music Hub！请先指定飞牛 NAS 授权的音乐库下载目录，确保后续下载的音频与歌词可被官方飞牛音乐无缝刮削。'
            : '配置音乐下载存储路径、飞牛授权曲库与音频流解析服务。' }}
        </DialogDescription>
      </DialogHeader>

      <!-- 顶部导航切换：存储目录 / 下载音源 -->
      <div class="flex items-center gap-2 border-b border-white/[0.08] pb-3 pt-2">
        <button
          type="button"
          @click="activeSubTab = 'directory'"
          class="flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all"
          :class="activeSubTab === 'directory' 
            ? 'bg-brand-500/20 text-brand-300 border border-brand-500/40 shadow-sm' 
            : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]'"
        >
          <FolderCheck class="w-3.5 h-3.5" />
          <span>下载存储目录</span>
          <Badge v-if="downloadDir" variant="secondary" class="text-[9px] px-1 py-0 bg-white/[0.06]">已选定</Badge>
        </button>

        <button
          type="button"
          @click="activeSubTab = 'source'"
          class="flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all"
          :class="activeSubTab === 'source' 
            ? 'bg-brand-500/20 text-brand-300 border border-brand-500/40 shadow-sm' 
            : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]'"
        >
          <Sparkles class="w-3.5 h-3.5" />
          <span>解析音源配置</span>
          <Badge variant="secondary" class="text-[9px] px-1 py-0 uppercase">{{ currentSource }}</Badge>
        </button>
      </div>

      <!-- 选项卡 1：下载存储目录配置 -->
      <div v-show="activeSubTab === 'directory'" class="space-y-4 py-2">
        <div>
          <div class="flex items-center justify-between mb-2">
            <label class="block text-xs font-semibold text-slate-300 flex items-center gap-1.5">
              <HardDrive class="w-3.5 h-3.5 text-brand-400" />
              <span>飞牛 NAS 授权的音乐库目录</span>
            </label>
            <button
              type="button"
              @click="loadDirectories"
              class="text-[11px] text-slate-400 hover:text-brand-300 flex items-center gap-1 transition-colors"
              :disabled="isLoadingDirs"
            >
              <RefreshCw class="w-3 h-3" :class="isLoadingDirs ? 'animate-spin' : ''" />
              <span>刷新授权列表</span>
            </button>
          </div>

          <!-- 授权目录卡片选择列表 -->
          <div class="space-y-2">
            <div
              v-for="d in authorizedDirs"
              :key="d.path"
              @click="selectDirectory(d)"
              class="flex items-start justify-between p-3 rounded-xl border transition-all cursor-pointer select-none"
              :class="downloadDir === d.path
                ? 'bg-brand-500/10 border-brand-500/50 shadow-sm'
                : 'bg-background/60 border-white/[0.08] hover:border-slate-700 hover:bg-white/[0.03]'"
            >
              <div class="flex items-start gap-3">
                <div
                  class="w-8 h-8 rounded-lg flex items-center justify-center text-xs shrink-0 mt-0.5"
                  :class="downloadDir === d.path ? 'bg-brand-500 text-black shadow-md' : 'bg-secondary text-slate-400'"
                >
                  <FolderCheck v-if="d.is_fnos_authorized" class="w-4 h-4 stroke-[2.5]" />
                  <FolderOpen v-else class="w-4 h-4" />
                </div>
                <div>
                  <div class="flex items-center gap-2 flex-wrap">
                    <span class="text-xs font-bold text-white">{{ d.name }}</span>
                    <Badge v-if="d.is_fnos_authorized" variant="brand" class="text-[9px] px-1.5 py-0 flex items-center gap-1">
                      <ShieldCheck class="w-2.5 h-2.5" />
                      <span>飞牛官方音乐库授权</span>
                    </Badge>
                    <Badge v-if="d.writable" variant="secondary" class="text-[9px] px-1.5 py-0 text-emerald-400 border-emerald-500/30">可读写</Badge>
                    <Badge v-else variant="destructive" class="text-[9px] px-1.5 py-0">只读不可写</Badge>
                  </div>
                  <p class="text-[11px] text-slate-400 mt-1 font-mono break-all">{{ d.path }}</p>
                  <p class="text-[10px] text-slate-500 mt-0.5">
                    已收录音频文件约 {{ d.file_count }} 个
                  </p>
                </div>
              </div>

              <div
                class="w-5 h-5 rounded-full border flex items-center justify-center shrink-0 ml-2 mt-0.5"
                :class="downloadDir === d.path ? 'border-brand-500 bg-brand-500 text-black' : 'border-slate-600'"
              >
                <Check v-if="downloadDir === d.path" class="w-3 h-3 stroke-[3]" />
              </div>
            </div>

            <div v-if="!isLoadingDirs && authorizedDirs.length === 0" class="p-4 rounded-xl border border-white/[0.08] text-center text-xs text-slate-400">
              未检测到飞牛官方媒体库自动授权目录，请在下方手动指定存储路径。
            </div>
          </div>
        </div>

        <!-- 自定义路径输入与校验 -->
        <div class="space-y-2 pt-1 border-t border-white/[0.08]">
          <label class="block text-xs font-semibold text-slate-300 flex items-center justify-between">
            <span class="flex items-center gap-1.5">
              <FolderPlus class="w-3.5 h-3.5 text-slate-400" />
              <span>或手动指定/微调物理下载目录路径</span>
            </span>
            <span v-if="isVerifyingDir" class="text-[10px] text-slate-400 flex items-center gap-1">
              <Loader2 class="w-3 h-3 animate-spin" />
              <span>正在校验路径权限...</span>
            </span>
          </label>
          <div class="flex items-center gap-2">
            <Input
              v-model="customDirInput"
              placeholder="例如：/vol2/1000/媒体/音乐 或 /media/music"
              class="h-8 text-xs font-mono bg-background/80 flex-1"
              @blur="verifyCustomDirectory(customDirInput)"
              @keydown.enter="verifyCustomDirectory(customDirInput)"
            />
            <Button
              variant="secondary"
              size="sm"
              class="h-8 text-xs shrink-0"
              @click="verifyCustomDirectory(customDirInput)"
              :disabled="isVerifyingDir"
            >
              检测并选中
            </Button>
          </div>

          <!-- 目录检测结果指示条 -->
          <div
            v-if="dirVerifyResult"
            class="p-2.5 rounded-lg text-[11px] flex items-start gap-2 border leading-relaxed"
            :class="dirVerifyResult.ok
              ? 'bg-emerald-950/20 border-emerald-500/30 text-emerald-300'
              : 'bg-rose-950/20 border-rose-500/30 text-rose-300'"
          >
            <Check v-if="dirVerifyResult.ok" class="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
            <AlertTriangle v-else class="w-3.5 h-3.5 text-rose-400 shrink-0 mt-0.5" />
            <div>
              <p class="font-medium">
                {{ dirVerifyResult.ok ? '✅ 该存储目录校验通过，具备完整写入权限' : '❌ 目录校验异常' }}
              </p>
              <p v-if="dirVerifyResult.is_fnos_authorized" class="text-[10px] text-emerald-400/80">
                ★ 该目录是飞牛官方音乐库挂载路径，新下载的歌曲飞牛会自动入库！
              </p>
              <p v-if="dirVerifyResult.error" class="text-[10px] text-rose-400/80">
                原因：{{ dirVerifyResult.error }}
              </p>
            </div>
          </div>
        </div>

        <!-- 说明小贴士 -->
        <div class="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 text-[11px] text-slate-400 space-y-1.5 leading-relaxed">
          <div class="flex items-center gap-1.5 font-medium text-slate-300">
            <Info class="w-3.5 h-3.5 text-brand-400 shrink-0" />
            <span>为什么建议选择飞牛官方授权音乐库？</span>
          </div>
          <p>
            飞牛官方音乐 App 只会主动扫描它已授权的存储库（如 <code>/vol2/1000/媒体/音乐</code>）。选定该目录后，TRIM Music Hub 下载的 24-bit 无损单曲、歌词与原版封面将能<strong>秒级被飞牛音乐自动刮削并完美呈现在各端 App 中</strong>。
          </p>
        </div>
      </div>

      <!-- 选项卡 2：解析音源配置 -->
      <div v-show="activeSubTab === 'source'" class="space-y-4 py-2">
        <div class="space-y-2">
          <label class="block text-xs font-semibold text-slate-300">选择当前生效音源</label>

          <div class="space-y-2">
            <div
              v-for="src in availableSources"
              :key="src.id"
              @click="currentSource = src.id"
              class="flex items-center justify-between p-3 rounded-xl border transition-all cursor-pointer select-none"
              :class="currentSource === src.id
                ? 'bg-primary/10 border-primary/50 shadow-sm'
                : 'bg-background/60 border-white/[0.08] hover:border-slate-700 hover:bg-white/[0.03]'"
            >
              <div class="flex items-center gap-3">
                <div
                  class="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold"
                  :class="currentSource === src.id ? 'bg-primary text-primary-foreground shadow-md' : 'bg-secondary text-slate-400'"
                >
                  {{ src.id.toUpperCase() }}
                </div>
                <div>
                  <div class="flex items-center gap-2">
                    <span class="text-xs font-bold text-white">{{ src.name }}</span>
                    <Badge v-if="src.id === 'kw'" variant="brand" class="text-[9px] px-1.5 py-0">推荐默认</Badge>
                    <Badge v-else-if="src.id === 'auto'" variant="indigo" class="text-[9px] px-1.5 py-0">多源聚合</Badge>
                    <Badge v-else-if="src.id === 'custom'" variant="secondary" class="text-[9px] px-1.5 py-0 text-amber-400 border-amber-400/30">自定义扩展</Badge>
                  </div>
                  <p class="text-[11px] text-slate-400 mt-0.5">{{ src.desc }}</p>
                </div>
              </div>

              <div
                class="w-5 h-5 rounded-full border flex items-center justify-center shrink-0"
                :class="currentSource === src.id ? 'border-primary bg-primary text-primary-foreground' : 'border-slate-600'"
              >
                <Check v-if="currentSource === src.id" class="w-3 h-3 stroke-[3]" />
              </div>
            </div>
          </div>
        </div>

        <!-- 自定义音源配置面板 -->
        <div
          v-if="currentSource === 'custom'"
          class="rounded-xl border border-amber-500/20 bg-amber-500/[0.03] p-4 space-y-3 animate-in fade-in zoom-in-95 duration-150"
        >
          <div class="flex items-center gap-2 text-xs font-bold text-amber-400 pb-1 border-b border-white/[0.06]">
            <Sliders class="w-4 h-4" />
            <span>自定义音源连接参数</span>
          </div>

          <div class="space-y-1">
            <label class="block text-[11px] font-medium text-slate-300 flex items-center gap-1.5">
              <Server class="w-3.5 h-3.5 text-slate-400" />
              <span>自定义线路显示名称</span>
            </label>
            <Input
              v-model="customConfig.name"
              placeholder="例如：自建私有音频解析"
              class="h-8 text-xs bg-background/80"
            />
          </div>

          <div class="space-y-1">
            <label class="block text-[11px] font-medium text-slate-300 flex items-center gap-1.5">
              <Link2 class="w-3.5 h-3.5 text-slate-400" />
              <span>自定义 API 端点 URL</span>
            </label>
            <Input
              v-model="customConfig.api_url"
              placeholder="http://192.168.0.x:port/api/music/url 或 https://..."
              class="h-8 text-xs bg-background/80 font-mono"
            />
            <p class="text-[10px] text-slate-500 leading-tight">
              支持通用 RESTful 端点，调用时会自动附带 ?song=歌名&artist=歌手&quality=flac 等参数
            </p>
          </div>

          <div class="space-y-1">
            <label class="block text-[11px] font-medium text-slate-300 flex items-center gap-1.5">
              <Key class="w-3.5 h-3.5 text-slate-400" />
              <span>API 鉴权密钥 Token (可选)</span>
            </label>
            <Input
              v-model="customConfig.api_key"
              type="password"
              placeholder="若自建节点设置了 API Key / Token 请在此填写"
              class="h-8 text-xs bg-background/80 font-mono"
            />
          </div>

          <div class="space-y-1">
            <label class="block text-[11px] font-medium text-slate-300 flex items-center gap-1.5">
              <Sparkles class="w-3.5 h-3.5 text-slate-400" />
              <span>远程源脚本 URL (可选，兼容洛雪/LX Music 源脚本)</span>
            </label>
            <Input
              v-model="customConfig.script_url"
              placeholder="https://raw.githubusercontent.com/.../source.js"
              class="h-8 text-xs bg-background/80 font-mono"
            />
          </div>
        </div>

        <!-- 音源说明卡片 -->
        <div class="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 text-[11px] text-slate-400 space-y-1.5 leading-relaxed">
          <div class="flex items-center gap-1.5 font-medium text-slate-300">
            <Info class="w-3.5 h-3.5 text-brand-400 shrink-0" />
            <span>音源提供与技术说明</span>
          </div>
          <p>
            • <strong>内置音源来源</strong>：基于洛雪开源生态聚合音源协议（开源社区贡献者「全豆要」、「星海团队」、「溯音」、「长青」等公益节点），支持各平台 FLAC / 320K 直连。
          </p>
          <p>
            • <strong>故障自动兜底</strong>：当选择【智能多源聚合】或某个源下架时，系统将智能在其他源中自动重试，确保 100% 下载成功。
          </p>
        </div>
      </div>

      <DialogFooter class="pt-3 border-t border-white/[0.08] flex items-center justify-between gap-2">
        <div class="text-[11px] text-slate-400 font-mono truncate max-w-[260px]">
          <span class="text-slate-500">当前目录:</span> {{ downloadDir || '未配置' }}
        </div>
        <div class="flex items-center gap-2">
          <Button v-if="!props.isFirstInstall" variant="ghost" size="sm" @click="emit('close')">
            取消
          </Button>
          <Button
            variant="default"
            size="sm"
            @click="handleSave"
            :disabled="isSaving"
            class="gap-1.5 bg-brand-500 hover:bg-brand-600 text-black font-semibold"
          >
            <Loader2 v-if="isSaving" class="w-3.5 h-3.5 animate-spin" />
            <span>{{ isSaving ? '正在保存...' : (props.isFirstInstall ? '完成初始化配置' : '保存设置') }}</span>
          </Button>
        </div>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
