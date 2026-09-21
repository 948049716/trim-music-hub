<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import type { MusicAccount, MusicProviderId, RemotePlaylist, CurrentUser } from '@/types';
import { api } from '@/api';
import { showToast } from '@/composables/useToast';
import PlaylistImportConfirm from './PlaylistImportConfirm.vue';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Popconfirm } from '@/components/ui/popconfirm';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  ArrowLeft, Check, Cloud, Download, KeyRound, LibraryBig, Loader2,
  LockKeyhole, Music2, RefreshCw, Unplug, UserRound,
  QrCode, Smartphone, ListMusic, CheckCircle2, AlertCircle
} from 'lucide-vue-next';

interface Props {
  open: boolean;
  currentUser?: CurrentUser | null;
}

const props = withDefaults(defineProps<Props>(), {
  open: false,
  currentUser: null
});

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'update:open', value: boolean): void;
  (e: 'started'): void;
  (e: 'open-import', payload: { url: string; accountId?: string; playlistName?: string }): void;
}>();

const accounts = ref<MusicAccount[]>([]);
const activeAccount = ref<MusicAccount | null>(null);
const selectedPlaylistForImport = ref<RemotePlaylist | null>(null);
const playlists = ref<RemotePlaylist[]>([]);
const cookieInput = ref('');
const loadingAccounts = ref(false);
const loadingPlaylists = ref(false);
const connecting = ref(false);
const disconnecting = ref(false);
const importingId = ref('');
const targetType = ref<'public' | 'user'>('public');
const targetUser = ref('admin');
const userList = ref<Array<{ id: number; name: string }>>([]);

// 管理员多账号视图切换 (全部 / 我的)
const accountFilterTab = ref<'all' | 'my'>('all');

// 登录方式与扫码状态
const loginMode = ref<'qr' | 'cookie'>('qr');
const qrLoading = ref(false);
const qrImg = ref('');
const qrUnikey = ref('');
const qrStatus = ref<'idle' | 'waiting' | 'scanned' | 'expired' | 'success'>('idle');
const qrMessage = ref('');
let qrPollTimer: ReturnType<typeof setInterval> | null = null;

const displayedAccounts = computed(() => {
  if (!props.currentUser?.isAdmin) {
    return accounts.value;
  }
  if (accountFilterTab.value === 'my') {
    return accounts.value.filter(a => a.is_self);
  }
  return accounts.value;
});

const providerBadge = (id: MusicProviderId) => ({ netease: '163', qq: 'QQ', bodian: 'BD' }[id] || id.toUpperCase());
const providerTone = (id: MusicProviderId) => ({
  netease: 'bg-red-500/15 text-red-600 dark:text-red-400 border-red-500/20',
  qq: 'bg-sky-500/15 text-sky-600 dark:text-sky-400 border-sky-500/20',
  bodian: 'bg-violet-500/15 text-violet-600 dark:text-violet-400 border-violet-500/20'
}[id] || 'bg-primary/10 text-primary border-primary/20');

async function loadAccounts() {
  loadingAccounts.value = true;
  try {
    const result = await api.getMusicAccounts();
    if (result.ok) accounts.value = result.data;
  } catch (error: any) {
    showToast(`账号列表加载失败：${error.message}`, 'error');
  } finally {
    loadingAccounts.value = false;
  }
}

async function loadUsers() {
  try {
    const result = await api.getUsers();
    if (result.ok && result.data.length) {
      userList.value = result.data;
      if (props.currentUser?.username) {
        const found = result.data.find(u => u.name === props.currentUser?.username);
        targetUser.value = found ? found.name : result.data[0].name;
      } else {
        targetUser.value = result.data[0].name;
      }
    }
  } catch {}
}

async function chooseAccount(account: MusicAccount) {
  activeAccount.value = account;
  playlists.value = [];
  cookieInput.value = '';
  stopQrPoll();

  // 默认可见范围联动绑定账号的飞牛音乐账号
  if (account.owner_user) {
    targetType.value = 'user';
    targetUser.value = account.owner_user;
  } else if (props.currentUser?.username) {
    targetType.value = 'user';
    targetUser.value = props.currentUser.username;
  }

  if (account.connected) {
    await loadPlaylists();
  } else {
    if (account.provider === 'netease') {
      loginMode.value = 'qr';
      await fetchNeteaseQr();
    } else {
      loginMode.value = 'cookie';
    }
  }
}

async function fetchNeteaseQr() {
  qrLoading.value = true;
  qrStatus.value = 'waiting';
  qrMessage.value = '正在获取网易云登录二维码…';
  qrImg.value = '';
  qrUnikey.value = '';
  stopQrPoll();

  try {
    const res = await api.createNeteaseQr();
    if (!res.ok || !res.unikey || !res.qr_img) {
      throw new Error(res.error || '获取二维码失败');
    }
    qrUnikey.value = res.unikey;
    qrImg.value = res.qr_img;
    qrStatus.value = 'waiting';
    qrMessage.value = '请打开网易云音乐手机 App 扫码';
    startQrPoll();
  } catch (e: any) {
    qrStatus.value = 'expired';
    qrMessage.value = e.message || '二维码生成失败，请点击重试';
    showToast(qrMessage.value, 'error');
  } finally {
    qrLoading.value = false;
  }
}

function startQrPoll() {
  stopQrPoll();
  qrPollTimer = setInterval(async () => {
    if (!qrUnikey.value || qrStatus.value === 'expired' || qrStatus.value === 'success') {
      stopQrPoll();
      return;
    }
    try {
      const res = await api.checkNeteaseQr(qrUnikey.value);
      if (!res.ok) {
        qrStatus.value = 'expired';
        qrMessage.value = res.error || '扫码验证失败，请刷新重试';
        stopQrPoll();
        showToast(qrMessage.value, 'error');
        return;
      }

      if (res.status === 'waiting') {
        qrStatus.value = 'waiting';
        qrMessage.value = '请打开网易云音乐手机 App 扫码';
      } else if (res.status === 'scanned') {
        qrStatus.value = 'scanned';
        qrMessage.value = '已扫描，请在手机上点击确认授权';
      } else if (res.status === 'expired') {
        qrStatus.value = 'expired';
        qrMessage.value = '二维码已失效，请点击刷新';
        stopQrPoll();
      } else if (res.status === 'success') {
        qrStatus.value = 'success';
        qrMessage.value = '授权成功！正在加载账号信息…';
        stopQrPoll();
        showToast('网易云音乐账号连接成功！', 'success');
        await loadAccounts();
        if (res.account) {
          activeAccount.value = res.account;
        } else {
          activeAccount.value = accounts.value.find(a => a.provider === 'netease' && a.is_self) || null;
        }
        await loadPlaylists();
      }
    } catch {
      // 忽略单次网络波动
    }
  }, 1500);
}

function stopQrPoll() {
  if (qrPollTimer) {
    clearInterval(qrPollTimer);
    qrPollTimer = null;
  }
}

async function connectAccountByCookie() {
  if (!activeAccount.value || !cookieInput.value.trim()) {
    showToast('请粘贴该平台网页端的登录 Cookie。', 'warning');
    return;
  }
  connecting.value = true;
  try {
    const targetId = activeAccount.value.id || activeAccount.value.provider;
    const result = await api.connectMusicAccount(targetId, cookieInput.value.trim());
    if (!result.ok || !result.data) throw new Error(result.error || '连接失败');
    cookieInput.value = '';
    showToast(`已连接 ${result.data.nickname || result.data.name}`, 'success');
    await loadAccounts();
    const updated = accounts.value.find(item => item.id === result.data?.id);
    if (updated) activeAccount.value = updated;
    await loadPlaylists();
  } catch (error: any) {
    showToast(error.message || '账号连接失败', 'error');
  } finally {
    connecting.value = false;
  }
}

async function disconnectAccount() {
  if (!activeAccount.value) return;
  disconnecting.value = true;
  try {
    const targetId = activeAccount.value.id || activeAccount.value.provider;
    const result = await api.disconnectMusicAccount(targetId);
    if (!result.ok) throw new Error(result.error || '断开失败');
    showToast('账号凭据已从 NAS 删除。', 'success');
    activeAccount.value = null;
    playlists.value = [];
    await loadAccounts();
  } catch (error: any) {
    showToast(error.message || '断开账号失败', 'error');
  } finally {
    disconnecting.value = false;
  }
}

async function loadPlaylists() {
  if (!activeAccount.value) return;
  loadingPlaylists.value = true;
  try {
    const targetId = activeAccount.value.id || activeAccount.value.provider;
    const result = await api.getMusicAccountPlaylists(targetId);
    if (!result.ok) throw new Error(result.error || '歌单读取失败');
    playlists.value = result.data || [];
  } catch (error: any) {
    playlists.value = [];
    showToast(error.message || '歌单读取失败', 'error');
  } finally {
    loadingPlaylists.value = false;
  }
}

// 解析并进入选歌（直接在当前 modal 内部进入解析与挑选，无需二次弹窗）
function handleSelectTracksAndImport(playlist: RemotePlaylist) {
  if (activeAccount.value?.owner_user) {
    targetType.value = 'user';
    targetUser.value = activeAccount.value.owner_user;
  } else if (props.currentUser?.username) {
    targetType.value = 'user';
    targetUser.value = props.currentUser.username;
  }
  selectedPlaylistForImport.value = playlist;
}

// 快速直接一键导入
async function handleQuickImport(playlist: RemotePlaylist) {
  if (!activeAccount.value) return;
  importingId.value = playlist.id;
  try {
    const targetId = activeAccount.value.id || activeAccount.value.provider;
    const result = await api.importMusicAccountPlaylist(targetId, {
      urls: [playlist.import_url],
      target: targetType.value,
      user: targetUser.value
    });
    if (!result.ok) throw new Error(result.error || result.message || '导入未能开始');
    showToast(`《${playlist.name}》已进入同步队列。`, 'success');
    emit('started');
    closeModal();
  } catch (error: any) {
    showToast(error.message || '导入未能开始', 'error');
  } finally {
    importingId.value = '';
  }
}

function closeModal() {
  stopQrPoll();
  selectedPlaylistForImport.value = null;
  activeAccount.value = null;
  playlists.value = [];
  cookieInput.value = '';
  emit('close');
  emit('update:open', false);
}

function handleOpenUpdate(value: boolean) {
  if (!value) closeModal();
}

watch(() => props.open, async value => {
  if (value) {
    await Promise.all([loadAccounts(), loadUsers()]);
  } else {
    stopQrPoll();
  }
});

onBeforeUnmount(() => {
  stopQrPoll();
});
</script>

<template>
  <Dialog :open="props.open" @update:open="handleOpenUpdate">
    <DialogContent class="inset-x-0 bottom-0 max-h-[96dvh] gap-0 rounded-b-none p-0 sm:max-w-4xl sm:overflow-hidden sm:rounded-[1.5rem]">
      <div class="flex max-h-[96dvh] min-h-[560px] flex-col overflow-hidden sm:max-h-[82dvh]">
        <!-- 头部导航 -->
        <DialogHeader class="shrink-0 border-b border-border/80 px-5 pb-4 pt-5 pr-14 sm:px-6 sm:pb-5 sm:pt-6">
          <div class="flex items-start gap-3">
            <Button
              v-if="selectedPlaylistForImport"
              variant="ghost"
              size="icon"
              class="-ml-2 mt-0.5 shrink-0 h-9 w-9 rounded-xl"
              aria-label="返回歌单列表"
              @click="selectedPlaylistForImport = null"
            >
              <ArrowLeft class="h-4 w-4" />
            </Button>
            <Button
              v-else-if="activeAccount"
              variant="ghost"
              size="icon"
              class="-ml-2 mt-0.5 shrink-0 h-9 w-9 rounded-xl"
              aria-label="返回账号列表"
              @click="stopQrPoll(); activeAccount = null; playlists = []"
            >
              <ArrowLeft class="h-4 w-4" />
            </Button>
            <div v-else class="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
              <Cloud class="h-5 w-5" />
            </div>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <DialogTitle class="truncate text-base sm:text-lg font-bold tracking-[-0.02em]">
                  {{ selectedPlaylistForImport
                    ? `选歌导入: ${selectedPlaylistForImport.name}`
                    : (activeAccount ? (activeAccount.connected ? (activeAccount.nickname || activeAccount.name) : `连接 ${activeAccount.name}`) : '第三方音乐账号') }}
                </DialogTitle>
                <Badge v-if="activeAccount?.connected" variant="secondary" class="text-[10px] font-normal px-2 py-0.5 rounded-full">
                  {{ activeAccount.provider === 'netease' ? '网易云' : (activeAccount.provider === 'qq' ? 'QQ音乐' : activeAccount.name) }}
                </Badge>
              </div>
              <DialogDescription class="mt-1 text-xs leading-5 text-muted-foreground truncate">
                {{ selectedPlaylistForImport
                  ? '挑选要同步的曲目并按需配置音质与保存归属。'
                  : (activeAccount
                    ? (activeAccount.connected ? '选择并解析账号自建或收藏的歌单，按需勾选导入至 NAS。' : '授权连接第三方音乐平台。')
                    : '绑定网易云或 QQ 音乐等账号，一键同步与挑选歌单。')
                }}
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <!-- 主内容区域 -->
        <div
          class="min-h-0 flex-1 flex flex-col"
          :class="selectedPlaylistForImport ? 'overflow-hidden p-3 sm:p-5' : 'overflow-y-auto px-4 py-4 sm:px-6 sm:py-5'"
        >
          <!-- 选歌确认视图 (直接复用 PlaylistImportConfirm，单 Modal 顺畅闭环) -->
          <PlaylistImportConfirm
            v-if="selectedPlaylistForImport && activeAccount"
            :url="selectedPlaylistForImport.import_url"
            :account-id="activeAccount.id || activeAccount.provider"
            :provider="activeAccount.provider"
            :initial-playlist-name="selectedPlaylistForImport.name"
            :default-target-type="targetType"
            :default-target-user="targetUser"
            :user-list="userList"
            :show-back-button="true"
            @back="selectedPlaylistForImport = null"
            @started="emit('started'); closeModal();"
            @cancel="closeModal"
          />

          <!-- 账号列表视图 -->
          <div v-else-if="!activeAccount" class="space-y-4">
            <!-- 管理员切换筛选栏 -->
            <div v-if="currentUser?.isAdmin" class="flex items-center justify-between gap-3 border-b border-border/50 pb-3">
              <div class="flex items-center gap-1.5 p-1 bg-muted/50 rounded-xl">
                <button
                  type="button"
                  class="px-3 py-1 text-xs font-medium rounded-lg transition-all"
                  :class="accountFilterTab === 'all' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'"
                  @click="accountFilterTab = 'all'"
                >
                  全部成员绑定账号
                </button>
                <button
                  type="button"
                  class="px-3 py-1 text-xs font-medium rounded-lg transition-all"
                  :class="accountFilterTab === 'my' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'"
                  @click="accountFilterTab = 'my'"
                >
                  我的账号
                </button>
              </div>
            </div>

            <!-- 加载状态 -->
            <div v-if="loadingAccounts" class="grid min-h-[280px] place-items-center text-xs text-muted-foreground">
              <span class="flex items-center gap-2"><Loader2 class="h-4 w-4 animate-spin text-primary" />正在读取云端账号绑定状态…</span>
            </div>

            <!-- 账号卡片网格 -->
            <div v-else class="grid gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
              <button
                v-for="account in displayedAccounts"
                :key="account.id"
                type="button"
                class="group relative flex flex-col justify-between h-auto min-h-[175px] w-full rounded-2xl border border-border/80 bg-card p-4 text-left transition-all hover:border-primary/40 hover:shadow-md hover:shadow-black/5 disabled:hover:translate-y-0 disabled:opacity-60"
                :disabled="!account.available"
                @click="chooseAccount(account)"
              >
                <div>
                  <div class="flex items-start justify-between gap-2.5">
                    <div class="flex items-center gap-2.5">
                      <img
                        v-if="account.connected && account.avatar"
                        :src="account.avatar"
                        alt=""
                        class="h-10 w-10 rounded-full border border-border/60 object-cover"
                        referrerpolicy="no-referrer"
                      />
                      <span v-else class="grid h-10 w-10 place-items-center rounded-xl font-black text-xs border" :class="providerTone(account.provider)">
                        {{ providerBadge(account.provider) }}
                      </span>
                      <div class="min-w-0">
                        <h3 class="text-sm font-bold text-foreground truncate">
                          {{ account.connected ? (account.nickname || account.name) : account.name }}
                        </h3>
                        <p class="text-[11px] text-muted-foreground truncate">
                          {{ account.name }}
                        </p>
                      </div>
                    </div>

                    <!-- 状态标签 -->
                    <div class="flex flex-col items-end gap-1">
                      <span v-if="account.connected" class="flex items-center gap-1 rounded-full bg-emerald-500/15 border border-emerald-500/20 px-2 py-0.5 text-[10px] font-semibold text-emerald-600 dark:text-emerald-400">
                        <Check class="h-3 w-3" />已连接
                      </span>
                      <span v-else-if="!account.available" class="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                        暂未开放
                      </span>
                    </div>
                  </div>

                  <!-- 提示或详细归属信息 -->
                  <div class="mt-3.5 space-y-1">
                    <div v-if="currentUser?.isAdmin && account.connected" class="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                      <UserRound class="h-3.5 w-3.5 text-primary/70 shrink-0" />
                      <span>所属成员：<strong class="text-foreground font-medium">{{ account.owner_user }}</strong></span>
                      <Badge v-if="account.is_self" variant="outline" class="text-[9px] px-1.5 py-0 h-4 border-primary/40 text-primary">本人</Badge>
                    </div>
                    <p class="text-[11px] leading-relaxed text-muted-foreground line-clamp-2">
                      {{ account.connected ? (account.user_id ? `UID: ${account.user_id} · 点击浏览与同步歌单` : '点击浏览与同步歌单') : account.hint }}
                    </p>
                  </div>
                </div>

                <!-- 底部操作引导 -->
                <div class="mt-3 pt-3 border-t border-border/40 flex items-center justify-between text-[11px] font-medium">
                  <span :class="account.connected ? 'text-primary' : (account.available ? 'text-foreground' : 'text-muted-foreground')" class="flex items-center gap-1.5">
                    <QrCode v-if="!account.connected && account.provider === 'netease'" class="h-3.5 w-3.5" />
                    <KeyRound v-else-if="!account.connected" class="h-3.5 w-3.5" />
                    <LibraryBig v-else class="h-3.5 w-3.5" />
                    {{ account.connected ? '浏览账号歌单' : (account.provider === 'netease' ? '扫码 / 连接' : '连接账号') }}
                  </span>
                </div>
              </button>
            </div>
          </div>

          <!-- 未连接：登录绑定视图 -->
          <div v-else-if="!activeAccount.connected" class="mx-auto max-w-xl space-y-4">
            <!-- 平台标题及模式切换 -->
            <div class="flex items-center justify-between rounded-2xl border border-border/80 bg-card p-4">
              <div class="flex items-center gap-3">
                <span class="grid h-11 w-11 place-items-center rounded-2xl text-xs font-black border" :class="providerTone(activeAccount.provider)">
                  {{ providerBadge(activeAccount.provider) }}
                </span>
                <div>
                  <h3 class="text-sm font-bold text-foreground">连接 {{ activeAccount.name }}</h3>
                  <p class="mt-0.5 text-[11px] text-muted-foreground">凭据将绑定至当前登录成员：<span class="font-semibold text-foreground">{{ currentUser?.username || 'admin' }}</span></p>
                </div>
              </div>

              <!-- 网易云支持扫码 / Cookie 切换 -->
              <div v-if="activeAccount.provider === 'netease'" class="flex items-center p-1 bg-muted/60 rounded-xl">
                <button
                  type="button"
                  class="px-2.5 py-1 text-xs font-medium rounded-lg transition-all flex items-center gap-1.5"
                  :class="loginMode === 'qr' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'"
                  @click="loginMode = 'qr'; fetchNeteaseQr()"
                >
                  <Smartphone class="h-3.5 w-3.5" />扫码
                </button>
                <button
                  type="button"
                  class="px-2.5 py-1 text-xs font-medium rounded-lg transition-all flex items-center gap-1.5"
                  :class="loginMode === 'cookie' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'"
                  @click="loginMode = 'cookie'; stopQrPoll()"
                >
                  <KeyRound class="h-3.5 w-3.5" />cookie
                </button>
              </div>
            </div>

            <!-- 网易云：二维码扫码登录 -->
            <div v-if="activeAccount.provider === 'netease' && loginMode === 'qr'" class="rounded-2xl border border-border/80 bg-card p-6 text-center">
              <div class="mx-auto max-w-xs space-y-4">
                <!-- 二维码白色容器（确保手机摄像头在 Dark Mode 下秒级对焦与识别） -->
                <div class="relative mx-auto w-[220px] h-[220px] rounded-2xl bg-white p-3.5 shadow-sm border border-neutral-200 flex items-center justify-center overflow-hidden">
                  <img
                    v-if="qrImg"
                    :src="qrImg"
                    alt="网易云登录二维码"
                    class="h-full w-full object-contain"
                    :class="qrStatus === 'expired' ? 'blur-sm opacity-20' : ''"
                  />
                  <div v-else class="flex flex-col items-center justify-center gap-2 text-xs text-neutral-500">
                    <Loader2 class="h-6 w-6 animate-spin text-neutral-700" />
                    <span>生成二维码中…</span>
                  </div>

                  <!-- 二维码失效遮罩 -->
                  <div
                    v-if="qrStatus === 'expired'"
                    class="absolute inset-0 flex flex-col items-center justify-center bg-black/40 backdrop-blur-[2px] p-4 text-white"
                  >
                    <AlertCircle class="h-7 w-7 text-amber-300 mb-1.5" />
                    <p class="text-xs font-bold">二维码已失效</p>
                    <Button size="sm" variant="secondary" class="mt-3 h-8 text-xs font-medium" @click="fetchNeteaseQr">
                      <RefreshCw class="h-3.5 w-3.5 mr-1.5" />点击刷新
                    </Button>
                  </div>
                </div>

                <!-- 扫码状态说明提示 -->
                <div class="space-y-1.5">
                  <div class="flex items-center justify-center gap-2 text-xs font-semibold" :class="qrStatus === 'scanned' ? 'text-amber-500' : (qrStatus === 'success' ? 'text-emerald-500' : 'text-foreground')">
                    <span v-if="qrStatus === 'waiting'" class="relative flex h-2 w-2">
                      <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                      <span class="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
                    </span>
                    <CheckCircle2 v-else-if="qrStatus === 'scanned' || qrStatus === 'success'" class="h-4 w-4" />
                    <span>{{ qrMessage }}</span>
                  </div>
                  <p class="text-[11px] text-muted-foreground">
                    请打开「网易云音乐」手机 App 扫一扫
                  </p>
                </div>
              </div>
            </div>

            <!-- Cookie 填入模式 (通用) -->
            <div v-else class="rounded-2xl border border-border/80 bg-card p-5 space-y-4">
              <div>
                <label class="block text-xs font-semibold text-foreground">Cookie 请求头内容</label>
                <Input
                  v-model="cookieInput"
                  type="password"
                  spellcheck="false"
                  autocomplete="off"
                  class="mt-2 h-11 w-full font-mono text-[11px]"
                  :placeholder="activeAccount.provider === 'netease' ? '包含 MUSIC_U=…' : '包含 uin=… 与 qm_keyst / qqmusic_key 等登录票据'"
                  @keyup.enter="connectAccountByCookie"
                />
              </div>

              <div class="rounded-xl bg-muted/40 p-3.5 text-[11px] leading-relaxed text-muted-foreground space-y-1.5">
                <div class="font-medium text-foreground flex items-center gap-1.5">
                  <LockKeyhole class="h-3.5 w-3.5 text-primary" />如何提取网页版 Cookie：
                </div>
                <p>
                  在电脑浏览器中登录
                  <code class="rounded bg-muted px-1.5 py-0.5 text-foreground font-mono text-[10px]">
                    {{ activeAccount.provider === 'netease' ? 'https://music.163.com' : 'https://y.qq.com' }}
                  </code>，
                  按 F12 打开开发者工具并切换至 Network（网络）标签页，刷新网页后点击任意发往该域名的请求，在 Request Headers（请求标头）中复制完整
                  <code class="rounded bg-muted px-1.5 py-0.5 text-foreground font-mono text-[10px]">Cookie</code>
                  值粘贴至上方。
                </p>
              </div>

              <Button
                class="w-full h-11 font-medium"
                :disabled="connecting || !cookieInput.trim()"
                @click="connectAccountByCookie"
              >
                <Loader2 v-if="connecting" class="h-4 w-4 animate-spin mr-2" />
                <KeyRound v-else class="h-4 w-4 mr-2" />
                {{ connecting ? '正在校验并验证会话…' : '验证并加密连接' }}
              </Button>
            </div>
          </div>

          <!-- 已连接：歌单列表与同步操作 -->
          <div v-else class="space-y-4">
            <!-- 账号概览与管理卡片 -->
            <div class="flex flex-col gap-3.5 rounded-2xl border border-border/80 bg-card p-4 sm:flex-row sm:items-center sm:justify-between">
              <div class="flex min-w-0 items-center gap-3">
                <img
                  v-if="activeAccount.avatar"
                  :src="activeAccount.avatar"
                  alt=""
                  class="h-12 w-12 shrink-0 rounded-full border border-border/60 object-cover"
                  referrerpolicy="no-referrer"
                />
                <span v-else class="grid h-12 w-12 shrink-0 place-items-center rounded-full border" :class="providerTone(activeAccount.provider)">
                  <UserRound class="h-6 w-6" />
                </span>
                <div class="min-w-0">
                  <div class="flex items-center gap-2">
                    <p class="truncate text-sm font-bold text-foreground">{{ activeAccount.nickname || activeAccount.name }}</p>
                    <Badge variant="outline" class="text-[10px] px-1.5 py-0 h-4 border-emerald-500/30 text-emerald-600 dark:text-emerald-400">
                      已就绪
                    </Badge>
                  </div>
                  <p class="mt-1 text-[11px] text-muted-foreground truncate">
                    <span>平台：{{ activeAccount.name }}</span>
                    <span v-if="activeAccount.owner_user" class="ml-2">归属：{{ activeAccount.owner_user }}</span>
                    <span v-if="activeAccount.user_id" class="ml-2 font-mono">UID: {{ activeAccount.user_id }}</span>
                  </p>
                </div>
              </div>

              <div class="flex items-center gap-2 self-end sm:self-auto">
                <Button variant="outline" size="sm" :disabled="loadingPlaylists" @click="loadPlaylists">
                  <RefreshCw class="h-3.5 w-3.5 mr-1.5" :class="loadingPlaylists ? 'animate-spin' : ''" />刷新歌单
                </Button>
                <Popconfirm
                  title="断开账号连接？"
                  description="NAS 将彻底销毁保存的加密会话凭据；此前已同步到飞牛音乐中的歌曲与歌单不受影响。"
                  confirm-text="断开连接"
                  :loading="disconnecting"
                  @confirm="disconnectAccount"
                >
                  <Button variant="ghost" size="sm" class="text-muted-foreground hover:text-destructive" :disabled="disconnecting">
                    <Unplug class="h-3.5 w-3.5 mr-1.5" />断开
                  </Button>
                </Popconfirm>
              </div>
            </div>

            <!-- 目标存储归属配置 -->
            <div class="grid gap-3 rounded-2xl border border-border/60 bg-muted/20 p-3 sm:grid-cols-2">
              <div class="space-y-1.5">
                <label class="text-[10px] font-semibold text-muted-foreground">导入歌单权限</label>
                <Select v-model="targetType">
                  <SelectTrigger class="h-9 bg-card text-xs"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="public">公共歌单（所有家庭成员可见）</SelectItem>
                    <SelectItem value="user">个人专属歌单（指定成员可见）</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div v-if="targetType === 'user'" class="space-y-1.5">
                <label class="text-[10px] font-semibold text-muted-foreground">选择飞牛所属成员</label>
                <Select v-model="targetUser">
                  <SelectTrigger class="h-9 bg-card text-xs"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem v-for="user in userList" :key="user.id" :value="user.name">{{ user.name }}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <!-- 歌单列表 -->
            <div v-if="loadingPlaylists" class="grid min-h-[260px] place-items-center text-xs text-muted-foreground">
              <span class="flex items-center gap-2"><Loader2 class="h-4 w-4 animate-spin text-primary" />正在读取该账号下的歌单…</span>
            </div>

            <div v-else-if="!playlists.length" class="grid min-h-[260px] place-items-center rounded-2xl border border-dashed border-border text-center p-6">
              <div>
                <LibraryBig class="mx-auto h-8 w-8 text-muted-foreground/50" />
                <p class="mt-3 text-xs font-semibold text-foreground">暂无读取到歌单</p>
                <p class="mt-1 text-[11px] text-muted-foreground">可能该账号未创建公开/自建歌单，或 Cookie 已失效需重新授权。</p>
              </div>
            </div>

            <div v-else class="grid gap-3 sm:grid-cols-2">
              <article
                v-for="playlist in playlists"
                :key="playlist.id"
                class="flex min-w-0 items-center gap-3 rounded-2xl border border-border/70 bg-card p-3.5 transition-all hover:border-primary/30 hover:bg-muted/15"
              >
                <!-- 歌单封面 -->
                <div class="relative h-16 w-16 shrink-0 overflow-hidden rounded-xl bg-muted border border-border/50">
                  <img
                    v-if="playlist.cover"
                    :src="playlist.cover"
                    :alt="playlist.name"
                    class="h-full w-full object-cover"
                    loading="lazy"
                    referrerpolicy="no-referrer"
                  />
                  <Music2 v-else class="absolute left-1/2 top-1/2 h-6 w-6 -translate-x-1/2 -translate-y-1/2 text-muted-foreground/40" />
                </div>

                <!-- 歌单信息 -->
                <div class="min-w-0 flex-1">
                  <h4 class="truncate text-xs sm:text-sm font-bold text-foreground" :title="playlist.name">
                    {{ playlist.name }}
                  </h4>
                  <p class="mt-1 text-[11px] text-muted-foreground truncate">
                    {{ playlist.track_count }} 首歌曲 · {{ playlist.subscribed ? '收藏歌单' : '自建歌单' }}
                  </p>
                  <p class="mt-0.5 text-[10px] text-muted-foreground/75 truncate">
                    创建者: {{ playlist.creator }}
                  </p>
                </div>

                <!-- 操作按钮组 -->
                <div class="flex flex-col sm:flex-row items-end sm:items-center gap-1.5 shrink-0">
                  <!-- 核心推荐：解析选歌 (复用 NewTaskModal) -->
                  <Button
                    variant="default"
                    size="sm"
                    class="h-8 px-2.5 text-xs font-medium gap-1.5 shadow-sm"
                    :title="`解析选歌并导入《${playlist.name}》`"
                    @click="handleSelectTracksAndImport(playlist)"
                  >
                    <ListMusic class="h-3.5 w-3.5" />
                    <span>选歌</span>
                  </Button>

                  <!-- 快捷操作：一键全选导入 -->
                  <Button
                    variant="secondary"
                    size="icon"
                    class="h-8 w-8"
                    :disabled="!!importingId"
                    :title="`一键导入整单`"
                    @click="handleQuickImport(playlist)"
                  >
                    <Loader2 v-if="importingId === playlist.id" class="h-3.5 w-3.5 animate-spin" />
                    <Download v-else class="h-3.5 w-3.5" />
                  </Button>
                </div>
              </article>
            </div>
          </div>
        </div>
      </div>
    </DialogContent>
  </Dialog>
</template>
