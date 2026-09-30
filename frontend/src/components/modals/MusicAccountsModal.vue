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
  QrCode, Smartphone, ListMusic, CheckCircle2, AlertCircle,
  Sparkles, Clock
} from 'lucide-vue-next';
import type { PlaylistPreview } from '@/types';

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
const targetType = ref<'public' | 'user'>('user');
const targetUser = ref('');
const userList = ref<Array<{ id: number; name: string }>>([]);

// 每日推荐与偏好配置状态
const dailyRecommendPreview = ref<PlaylistPreview | null>(null);
const loadingDailyRecommend = ref(false);
const syncingDailyRecommend = ref(false);
const savingDailySettings = ref(false);
const dailySyncEnabled = ref(false);
const dailySyncTime = ref('04:00');
const dailySyncTarget = ref<'public' | 'user'>('user');
const dailySyncUser = ref('');
const dailySyncQuality = ref('flac');
const dailySyncPlaylistName = ref('');

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
      const currentUsername = props.currentUser?.username;
      // 优先使用当前选定云端账号绑定的飞牛成员
      if (activeAccount.value?.owner_user) {
        targetType.value = 'user';
        targetUser.value = activeAccount.value.owner_user;
      } else if (!targetUser.value || !result.data.some(u => u.name === targetUser.value)) {
        if (currentUsername && result.data.some(u => u.name === currentUsername)) {
          targetUser.value = currentUsername;
        } else {
          targetUser.value = result.data[0].name;
        }
      }
    }
  } catch {}
}

function formatSyncTime(isoStr?: string | null): string {
  if (!isoStr) return '';
  try {
    const d = new Date(isoStr);
    const now = new Date();
    const isToday = d.toDateString() === now.toDateString();
    const time = d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false });
    return isToday ? `今日 ${time}` : `${d.getMonth() + 1}月${d.getDate()}日 ${time}`;
  } catch {
    return isoStr || '';
  }
}

function initAccountSettings(account: MusicAccount) {
  dailySyncEnabled.value = Boolean(account.daily_sync_enabled);
  dailySyncTime.value = account.daily_sync_time || '04:00';
  dailySyncTarget.value = account.daily_sync_target || 'user';
  dailySyncUser.value = account.daily_sync_user || account.owner_user || props.currentUser?.username || '';
  dailySyncQuality.value = account.daily_sync_quality || 'flac';
  dailySyncPlaylistName.value = account.daily_sync_playlist_name || '';
}

async function handleSaveDailySettings() {
  if (!activeAccount.value) return;
  savingDailySettings.value = true;
  try {
    const targetId = activeAccount.value.id || activeAccount.value.provider;
    const res = await api.updateAccountSettings(targetId, {
      daily_sync_enabled: dailySyncEnabled.value,
      daily_sync_time: dailySyncTime.value,
      daily_sync_target: dailySyncTarget.value,
      daily_sync_user: dailySyncUser.value || activeAccount.value.owner_user || props.currentUser?.username || 'admin',
      daily_sync_quality: dailySyncQuality.value,
      daily_sync_playlist_name: dailySyncPlaylistName.value.trim()
    });
    if (!res.ok || !res.data) throw new Error(res.error || '保存设置失败');
    activeAccount.value = res.data;
    const idx = accounts.value.findIndex(a => a.id === res.data!.id);
    if (idx >= 0) accounts.value[idx] = res.data;
    showToast(dailySyncEnabled.value ? '已开启每日推荐自动同步' : '已保存设置', 'success');
  } catch (err: any) {
    showToast(`设置保存失败：${err.message}`, 'error');
  } finally {
    savingDailySettings.value = false;
  }
}

async function handleToggleDailySync(val: boolean) {
  dailySyncEnabled.value = val;
  await handleSaveDailySettings();
}

async function handleViewDailyRecommend() {
  if (!activeAccount.value) return;
  loadingDailyRecommend.value = true;
  try {
    const targetId = activeAccount.value.id || activeAccount.value.provider;
    const res = await api.getDailyRecommend(targetId);
    if (!res.ok || !res.data) throw new Error(res.error || '未能获取今日推荐歌曲');
    dailyRecommendPreview.value = res.data;
    selectedPlaylistForImport.value = {
      id: 'daily_recommend',
      name: res.data.playlist_name || `${activeAccount.value.name}每日推荐`,
      cover: res.data.cover_url || '',
      track_count: res.data.track_count || res.data.tracks.length,
      creator: activeAccount.value.nickname || activeAccount.value.name,
      subscribed: false,
      import_url: res.data.import_url || `daily://${activeAccount.value.provider}/${activeAccount.value.id}`
    };
  } catch (err: any) {
    showToast(`获取今日推荐失败：${err.message}`, 'error');
  } finally {
    loadingDailyRecommend.value = false;
  }
}

async function handleSyncDailyNow() {
  if (!activeAccount.value) return;
  syncingDailyRecommend.value = true;
  try {
    const targetId = activeAccount.value.id || activeAccount.value.provider;
    const res = await api.syncDailyRecommend(targetId);
    if (!res.ok) throw new Error(res.error || '触发同步失败');
    showToast('今日推荐已加入同步队列，正在后台下载入库。', 'success');
    emit('started');
    await loadAccounts();
    const updated = accounts.value.find(a => a.id === activeAccount.value?.id);
    if (updated) {
      activeAccount.value = updated;
      initAccountSettings(updated);
    }
  } catch (err: any) {
    showToast(`同步失败：${err.message}`, 'error');
  } finally {
    syncingDailyRecommend.value = false;
  }
}

async function chooseAccount(account: MusicAccount) {
  activeAccount.value = account;
  initAccountSettings(account);
  playlists.value = [];
  dailyRecommendPreview.value = null;
  cookieInput.value = '';
  stopQrPoll();

  // 默认可见范围严格优先读取当前云端音乐账号绑定的飞牛用户
  targetType.value = 'user';
  if (account.owner_user) {
    targetUser.value = account.owner_user;
  } else if (props.currentUser?.username) {
    targetUser.value = props.currentUser.username;
  } else if (userList.value.length) {
    targetUser.value = userList.value[0].name;
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
  // 严格优先保证目标成员与当前云端账号绑定的飞牛成员一致
  if (activeAccount.value?.owner_user) {
    targetType.value = 'user';
    targetUser.value = activeAccount.value.owner_user;
  } else if (!targetUser.value && props.currentUser?.username) {
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
  dailyRecommendPreview.value = null;
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
              @click="selectedPlaylistForImport = null; dailyRecommendPreview = null"
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
            :initial-preview="dailyRecommendPreview"
            :default-target-type="targetType"
            :default-target-user="targetUser"
            :user-list="userList"
            :show-back-button="true"
            @back="selectedPlaylistForImport = null; dailyRecommendPreview = null"
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
                      <span v-if="account.connected && account.daily_sync_enabled" class="flex items-center gap-1 rounded-full bg-amber-500/15 border border-amber-500/20 px-2 py-0.5 text-[10px] font-medium text-amber-600 dark:text-amber-400">
                        <Sparkles class="h-2.5 w-2.5" />自动日推
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

            <!-- 每日推荐歌曲同步专区 -->
            <div class="rounded-2xl border border-border/80 bg-card p-4 sm:p-5 space-y-4">
              <!-- 顶部标题与自动同步主开关 -->
              <div class="flex items-center justify-between gap-3">
                <div class="flex items-center gap-2.5 min-w-0">
                  <span class="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/20">
                    <Sparkles class="h-4 w-4" />
                  </span>
                  <div class="min-w-0">
                    <div class="flex items-center gap-2 flex-wrap">
                      <h4 class="text-sm font-bold text-foreground">每日推荐歌曲</h4>
                      <Badge
                        v-if="dailySyncEnabled"
                        variant="secondary"
                        class="text-[10px] font-semibold bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/25 px-2 py-0.5 rounded-full"
                      >
                        每天 {{ dailySyncTime || '04:00' }} 自动同步
                      </Badge>
                      <Badge
                        v-else
                        variant="outline"
                        class="text-[10px] text-muted-foreground px-2 py-0.5 rounded-full"
                      >
                        自动同步未开启
                      </Badge>
                    </div>
                    <p class="text-[11px] text-muted-foreground mt-0.5 truncate">
                      基于绑定的 {{ activeAccount.name }} 喜好算法，自动同步或手动导入每日专属推荐歌单
                    </p>
                  </div>
                </div>

                <!-- 自动同步 Switch 开关 -->
                <div class="flex items-center gap-2 shrink-0">
                  <span class="text-xs font-medium text-muted-foreground hidden sm:inline">
                    {{ dailySyncEnabled ? '已开启' : '已关闭' }}
                  </span>
                  <button
                    type="button"
                    role="switch"
                    :aria-checked="dailySyncEnabled"
                    class="relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    :class="dailySyncEnabled ? 'bg-primary' : 'bg-muted'"
                    :disabled="savingDailySettings"
                    @click="handleToggleDailySync(!dailySyncEnabled)"
                  >
                    <span
                      class="pointer-events-none inline-block h-5 w-5 transform rounded-full bg-background shadow-lg ring-0 transition duration-200 ease-in-out"
                      :class="dailySyncEnabled ? 'translate-x-5' : 'translate-x-0'"
                    />
                  </button>
                </div>
              </div>

              <!-- 自动同步偏好详细配置 (开启时展示) -->
              <div
                v-if="dailySyncEnabled"
                class="grid gap-3 pt-3 border-t border-border/50 sm:grid-cols-2 lg:grid-cols-4 text-xs"
              >
                <!-- 同步时间 -->
                <div class="space-y-1.5">
                  <label class="text-[10px] font-semibold text-muted-foreground flex items-center gap-1">
                    <Clock class="h-3 w-3" />每日同步时间
                  </label>
                  <Input
                    type="time"
                    v-model="dailySyncTime"
                    class="h-8 text-xs font-mono bg-muted/20"
                    @change="handleSaveDailySettings"
                  />
                </div>

                <!-- 下载音质 -->
                <div class="space-y-1.5">
                  <label class="text-[10px] font-semibold text-muted-foreground">下载音质偏好</label>
                  <Select v-model="dailySyncQuality" @update:model-value="handleSaveDailySettings">
                    <SelectTrigger class="h-8 bg-muted/20 text-xs"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="flac">FLAC (无损音质)</SelectItem>
                      <SelectItem value="320k">320K (高品质)</SelectItem>
                      <SelectItem value="128k">128K (标准品质)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <!-- 目标歌单归属 -->
                <div class="space-y-1.5">
                  <label class="text-[10px] font-semibold text-muted-foreground">入库可见范围</label>
                  <Select v-model="dailySyncTarget" @update:model-value="handleSaveDailySettings">
                    <SelectTrigger class="h-8 bg-muted/20 text-xs"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="user">专属成员歌单</SelectItem>
                      <SelectItem value="public">公共歌单 (全员可见)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <!-- 歌单命名 -->
                <div class="space-y-1.5">
                  <label class="text-[10px] font-semibold text-muted-foreground">飞牛歌单名称</label>
                  <Input
                    v-model="dailySyncPlaylistName"
                    :placeholder="activeAccount.provider === 'qq' ? '默认: QQ音乐每日推荐' : '默认: 网易云每日推荐'"
                    class="h-8 text-xs bg-muted/20"
                    @blur="handleSaveDailySettings"
                    @keyup.enter="handleSaveDailySettings"
                  />
                </div>
              </div>

              <!-- 状态与快捷操作栏 -->
              <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pt-3 border-t border-border/40">
                <!-- 同步状态提示 -->
                <div class="min-w-0 flex-1">
                  <div v-if="activeAccount.last_daily_sync_status === 'running'" class="flex items-center gap-1.5 text-xs text-primary font-medium">
                    <Loader2 class="h-3.5 w-3.5 animate-spin shrink-0" />
                    <span>正在同步今日推荐歌曲中…</span>
                  </div>
                  <div v-else-if="activeAccount.last_daily_sync_at" class="flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
                    <span
                      class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded font-medium text-[10px]"
                      :class="activeAccount.last_daily_sync_status === 'success' ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400' : 'bg-destructive/10 text-destructive'"
                    >
                      <CheckCircle2 v-if="activeAccount.last_daily_sync_status === 'success'" class="h-3 w-3" />
                      <AlertCircle v-else class="h-3 w-3" />
                      {{ activeAccount.last_daily_sync_status === 'success' ? '同步成功' : '同步失败' }}
                    </span>
                    <span>{{ formatSyncTime(activeAccount.last_daily_sync_at) }}</span>
                    <span v-if="activeAccount.last_daily_sync_message" class="text-muted-foreground/80 truncate max-w-xs sm:max-w-md">
                      · {{ activeAccount.last_daily_sync_message }}
                    </span>
                  </div>
                  <div v-else class="text-[11px] text-muted-foreground">
                    尚未执行过日推同步；开启后每天凌晨将按设定时间自动导入飞牛曲库。
                  </div>
                </div>

                <!-- 操作按钮组 -->
                <div class="flex items-center gap-2 shrink-0 self-end sm:self-auto">
                  <!-- 查看今日推荐 (选歌与导入) -->
                  <Button
                    variant="outline"
                    size="sm"
                    class="h-8 px-3 text-xs font-medium gap-1.5"
                    :disabled="loadingDailyRecommend"
                    @click="handleViewDailyRecommend"
                  >
                    <Loader2 v-if="loadingDailyRecommend" class="h-3.5 w-3.5 animate-spin" />
                    <ListMusic v-else class="h-3.5 w-3.5" />
                    <span>查看今日推荐</span>
                  </Button>

                  <!-- 立即同步 (带气泡确认) -->
                  <Popconfirm
                    title="立即同步今日推荐？"
                    description="将立即抓取今日推荐曲目并创建后台入库任务。"
                    confirm-text="立即同步"
                    :loading="syncingDailyRecommend"
                    @confirm="handleSyncDailyNow"
                  >
                    <Button
                      variant="default"
                      size="sm"
                      class="h-8 px-3 text-xs font-medium gap-1.5 shadow-sm"
                      :disabled="syncingDailyRecommend"
                    >
                      <Loader2 v-if="syncingDailyRecommend" class="h-3.5 w-3.5 animate-spin" />
                      <RefreshCw v-else class="h-3.5 w-3.5" />
                      <span>立即同步</span>
                    </Button>
                  </Popconfirm>
                </div>
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
