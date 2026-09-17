<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type { MusicAccount, MusicProviderId, RemotePlaylist } from '@/types';
import { api } from '@/api';
import { showToast } from '@/composables/useToast';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Popconfirm } from '@/components/ui/popconfirm';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  ArrowLeft, Check, Cloud, Download, KeyRound, LibraryBig, Loader2,
  LockKeyhole, Music2, RefreshCw, ShieldCheck, Unplug, UserRound
} from 'lucide-vue-next';

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'update:open', value: boolean): void;
  (e: 'started'): void;
}>();

const accounts = ref<MusicAccount[]>([]);
const activeProvider = ref<MusicProviderId | null>(null);
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

const activeAccount = computed(() => accounts.value.find(item => item.id === activeProvider.value) || null);
const providerBadge = (id: MusicProviderId) => ({ netease: '163', qq: 'QQ', bodian: 'BD' }[id]);
const providerTone = (id: MusicProviderId) => ({
  netease: 'bg-red-500/12 text-red-600 dark:text-red-400',
  qq: 'bg-sky-500/12 text-sky-600 dark:text-sky-400',
  bodian: 'bg-violet-500/12 text-violet-600 dark:text-violet-400'
}[id]);

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
      targetUser.value = result.data[0].name;
    }
  } catch {}
}

async function chooseProvider(account: MusicAccount) {
  activeProvider.value = account.id;
  playlists.value = [];
  cookieInput.value = '';
  if (account.connected) await loadPlaylists();
}

async function connectAccount() {
  if (!activeProvider.value || !cookieInput.value.trim()) {
    showToast('请粘贴该平台网页端的登录 Cookie。', 'warning');
    return;
  }
  connecting.value = true;
  try {
    const result = await api.connectMusicAccount(activeProvider.value, cookieInput.value.trim());
    if (!result.ok || !result.data) throw new Error(result.error || '连接失败');
    const index = accounts.value.findIndex(item => item.id === activeProvider.value);
    if (index >= 0) accounts.value[index] = result.data;
    cookieInput.value = '';
    showToast(`已连接 ${result.data.nickname || result.data.name}`, 'success');
    await loadPlaylists();
  } catch (error: any) {
    showToast(error.message || '账号连接失败', 'error');
  } finally {
    connecting.value = false;
  }
}

async function disconnectAccount() {
  if (!activeProvider.value) return;
  disconnecting.value = true;
  try {
    const result = await api.disconnectMusicAccount(activeProvider.value);
    if (!result.ok) throw new Error(result.error || '断开失败');
    const account = accounts.value.find(item => item.id === activeProvider.value);
    if (account) Object.assign(account, { connected: false, nickname: '', avatar: '', user_id: '', connected_at: null });
    playlists.value = [];
    showToast('账号凭据已从 NAS 删除。', 'success');
  } catch (error: any) {
    showToast(error.message || '断开账号失败', 'error');
  } finally {
    disconnecting.value = false;
  }
}

async function loadPlaylists() {
  if (!activeProvider.value) return;
  loadingPlaylists.value = true;
  try {
    const result = await api.getMusicAccountPlaylists(activeProvider.value);
    if (!result.ok) throw new Error(result.error || '歌单读取失败');
    playlists.value = result.data || [];
  } catch (error: any) {
    playlists.value = [];
    showToast(error.message || '歌单读取失败', 'error');
  } finally {
    loadingPlaylists.value = false;
  }
}

async function importPlaylist(playlist: RemotePlaylist) {
  if (!activeProvider.value) return;
  importingId.value = playlist.id;
  try {
    const result = await api.importMusicAccountPlaylist(activeProvider.value, {
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
  activeProvider.value = null;
  playlists.value = [];
  cookieInput.value = '';
  emit('close');
  emit('update:open', false);
}

function handleOpenUpdate(value: boolean) {
  if (!value) closeModal();
}

watch(() => props.open, async value => {
  if (value) await Promise.all([loadAccounts(), loadUsers()]);
});
</script>

<template>
  <Dialog :open="props.open" @update:open="handleOpenUpdate">
    <DialogContent class="inset-x-0 bottom-0 max-h-[96dvh] gap-0 rounded-b-none p-0 sm:max-w-4xl sm:overflow-hidden sm:rounded-[1.5rem]">
      <div class="flex max-h-[96dvh] min-h-[560px] flex-col overflow-hidden sm:max-h-[82dvh]">
        <DialogHeader class="shrink-0 border-b border-border px-5 pb-4 pt-5 pr-14 sm:px-6 sm:pb-5 sm:pt-6">
          <div class="flex items-start gap-3">
            <Button v-if="activeAccount" variant="ghost" size="icon" class="-ml-2 mt-0.5 shrink-0" aria-label="返回平台列表" @click="activeProvider = null; playlists = []">
              <ArrowLeft class="h-4 w-4" />
            </Button>
            <div v-else class="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary"><Cloud class="h-5 w-5" /></div>
            <div class="min-w-0">
              <DialogTitle class="truncate text-lg font-bold tracking-[-0.02em]">
                {{ activeAccount ? activeAccount.name : '连接音乐账号' }}
              </DialogTitle>
              <DialogDescription class="mt-1 text-xs leading-5">
                {{ activeAccount ? '读取账号里的歌单，选一个直接同步到飞牛音乐。' : '账号凭据只加密保存在这台 NAS，不会返回浏览器。' }}
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div class="min-h-0 flex-1 overflow-y-auto px-4 py-4 sm:px-6 sm:py-5">
          <div v-if="!activeAccount">
            <div v-if="loadingAccounts" class="grid min-h-[300px] place-items-center text-xs text-muted-foreground">
              <span class="flex items-center gap-2"><Loader2 class="h-4 w-4 animate-spin" />正在读取连接状态…</span>
            </div>
            <div v-else class="grid gap-3 sm:grid-cols-3">
              <Button
                v-for="account in accounts"
                :key="account.id"
                type="button"
                variant="outline"
                class="group relative h-auto min-h-[190px] w-full flex-col items-stretch justify-start whitespace-normal rounded-2xl bg-card p-4 text-left transition-all hover:-translate-y-0.5 hover:border-primary/35 hover:shadow-lg hover:shadow-black/5 disabled:hover:translate-y-0"
                :disabled="!account.available"
                @click="chooseProvider(account)"
              >
                <div class="flex items-start justify-between gap-3">
                  <span class="grid h-11 min-w-11 place-items-center rounded-2xl px-2 text-xs font-black" :class="providerTone(account.id)">{{ providerBadge(account.id) }}</span>
                  <span v-if="account.connected" class="flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-1 text-[10px] font-semibold text-emerald-600 dark:text-emerald-400"><Check class="h-3 w-3" />已连接</span>
                  <span v-else-if="!account.available" class="rounded-full bg-muted px-2 py-1 text-[10px] font-medium text-muted-foreground">暂不可用</span>
                </div>
                <h3 class="mt-5 text-sm font-bold text-foreground">{{ account.name }}</h3>
                <p class="mt-1.5 min-h-10 text-[11px] leading-5 text-muted-foreground">{{ account.connected ? `${account.nickname} · 点击查看歌单` : account.hint }}</p>
                <div class="mt-4 flex items-center gap-1.5 text-[11px] font-semibold" :class="account.available ? 'text-primary' : 'text-muted-foreground'">
                  <UserRound class="h-3.5 w-3.5" />{{ account.connected ? '管理账号与歌单' : account.available ? '连接账号' : '等待平台开放' }}
                </div>
              </Button>
            </div>

            <div class="mt-4 flex items-start gap-3 rounded-2xl border border-border bg-muted/35 p-4 text-[11px] leading-5 text-muted-foreground">
              <ShieldCheck class="mt-0.5 h-4 w-4 shrink-0 text-primary" />
              <p><strong class="font-semibold text-foreground">安全说明：</strong>不需要输入账号密码。连接后可随时断开，NAS 会立即删除保存的会话凭据。平台可能使 Cookie 过期，届时重新连接即可。</p>
            </div>
          </div>

          <div v-else-if="!activeAccount.connected" class="mx-auto max-w-2xl space-y-4">
            <div class="rounded-2xl border border-border bg-card p-4 sm:p-5">
              <div class="flex items-center gap-3">
                <span class="grid h-11 min-w-11 place-items-center rounded-2xl px-2 text-xs font-black" :class="providerTone(activeAccount.id)">{{ providerBadge(activeAccount.id) }}</span>
                <div>
                  <h3 class="text-sm font-bold">用网页登录状态连接</h3>
                  <p class="mt-1 text-[11px] text-muted-foreground">不会保存密码，仅验证当前登录会话。</p>
                </div>
              </div>

              <label class="mt-5 block text-xs font-semibold text-foreground">Cookie 请求头</label>
              <Input
                v-model="cookieInput"
                type="password"
                spellcheck="false"
                autocomplete="off"
                class="mt-2 h-11 w-full bg-background font-mono text-[11px]"
                :placeholder="activeAccount.id === 'netease' ? '需要包含 MUSIC_U=…' : '需要包含 uin=… 与 qm_keyst / qqmusic_key 等登录票据'"
                @keyup.enter="connectAccount"
              />
              <div class="mt-3 rounded-xl bg-muted/50 p-3 text-[10px] leading-5 text-muted-foreground">
                在已登录的 {{ activeAccount.name }} 网页中打开开发者工具 → Network，刷新页面，选择发往
                <code class="rounded bg-background px-1 py-0.5">{{ activeAccount.id === 'netease' ? 'music.163.com' : 'y.qq.com' }}</code>
                的请求，复制 Request Headers 里的 Cookie 值。
              </div>
              <Button class="mt-4 w-full" :disabled="connecting || !cookieInput.trim()" @click="connectAccount">
                <Loader2 v-if="connecting" class="h-4 w-4 animate-spin" /><KeyRound v-else class="h-4 w-4" />
                {{ connecting ? '正在验证登录状态…' : '验证并连接' }}
              </Button>
            </div>
            <div class="flex items-start gap-2 px-1 text-[10px] leading-5 text-muted-foreground"><LockKeyhole class="mt-0.5 h-3.5 w-3.5 shrink-0" />Cookie 使用 AES-256-GCM 加密后写入 NAS 的本地 data 目录，并已排除 Git。</div>
          </div>

          <div v-else class="space-y-4">
            <div class="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 sm:flex-row sm:items-center">
              <div class="flex min-w-0 flex-1 items-center gap-3">
                <img v-if="activeAccount.avatar" :src="activeAccount.avatar" alt="" class="h-11 w-11 shrink-0 rounded-full bg-muted object-cover" referrerpolicy="no-referrer" />
                <span v-else class="grid h-11 w-11 shrink-0 place-items-center rounded-full" :class="providerTone(activeAccount.id)"><UserRound class="h-5 w-5" /></span>
                <div class="min-w-0">
                  <p class="truncate text-sm font-bold">{{ activeAccount.nickname || activeAccount.name }}</p>
                  <p class="mt-1 flex items-center gap-1.5 text-[10px] text-emerald-600 dark:text-emerald-400"><span class="h-1.5 w-1.5 rounded-full bg-current" />账号已连接</p>
                </div>
              </div>
              <div class="flex gap-2">
                <Button variant="outline" size="sm" :disabled="loadingPlaylists" @click="loadPlaylists"><RefreshCw class="h-3.5 w-3.5" :class="loadingPlaylists ? 'animate-spin' : ''" />刷新歌单</Button>
                <Popconfirm
                  title="断开这个音乐账号？"
                  description="NAS 会删除已保存的登录凭据；已导入到飞牛音乐的歌单不受影响。"
                  confirm-text="断开账号"
                  :loading="disconnecting"
                  @confirm="disconnectAccount"
                >
                  <Button variant="ghost" size="sm" class="text-muted-foreground" :disabled="disconnecting"><Unplug class="h-3.5 w-3.5" />断开</Button>
                </Popconfirm>
              </div>
            </div>

            <div class="grid gap-3 rounded-2xl border border-border bg-muted/25 p-3 sm:grid-cols-2">
              <div class="space-y-1.5">
                <label class="text-[10px] font-semibold text-muted-foreground">导入后谁可以看到</label>
                <Select v-model="targetType"><SelectTrigger class="h-9 bg-card text-xs"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="public">所有家庭成员</SelectItem><SelectItem value="user">指定成员</SelectItem></SelectContent></Select>
              </div>
              <div v-if="targetType === 'user'" class="space-y-1.5">
                <label class="text-[10px] font-semibold text-muted-foreground">选择成员</label>
                <Select v-model="targetUser"><SelectTrigger class="h-9 bg-card text-xs"><SelectValue /></SelectTrigger><SelectContent><SelectItem v-for="user in userList" :key="user.id" :value="user.name">{{ user.name }}</SelectItem></SelectContent></Select>
              </div>
            </div>

            <div v-if="loadingPlaylists" class="grid min-h-[260px] place-items-center text-xs text-muted-foreground"><span class="flex items-center gap-2"><Loader2 class="h-4 w-4 animate-spin" />正在读取账号歌单…</span></div>
            <div v-else-if="!playlists.length" class="grid min-h-[260px] place-items-center rounded-2xl border border-dashed border-border text-center">
              <div><LibraryBig class="mx-auto h-8 w-8 text-muted-foreground/45" /><p class="mt-3 text-xs font-semibold">没有读取到歌单</p><p class="mt-1 text-[10px] text-muted-foreground">尝试刷新，或重新连接账号。</p></div>
            </div>
            <div v-else class="grid gap-2.5 sm:grid-cols-2">
              <article v-for="playlist in playlists" :key="playlist.id" class="flex min-w-0 items-center gap-3 rounded-2xl border border-border bg-card p-3 transition-colors hover:bg-muted/30">
                <div class="relative h-14 w-14 shrink-0 overflow-hidden rounded-xl bg-muted">
                  <img v-if="playlist.cover" :src="playlist.cover" :alt="`${playlist.name}封面`" class="h-full w-full object-cover" loading="lazy" referrerpolicy="no-referrer" />
                  <Music2 v-else class="absolute left-1/2 top-1/2 h-5 w-5 -translate-x-1/2 -translate-y-1/2 text-muted-foreground/50" />
                </div>
                <div class="min-w-0 flex-1">
                  <h4 class="truncate text-xs font-bold" :title="playlist.name">{{ playlist.name }}</h4>
                  <p class="mt-1 truncate text-[10px] text-muted-foreground">{{ playlist.track_count }} 首 · {{ playlist.subscribed ? '收藏歌单' : '创建歌单' }}</p>
                  <p class="mt-0.5 truncate text-[10px] text-muted-foreground/75">{{ playlist.creator }}</p>
                </div>
                <Button size="icon" variant="secondary" class="shrink-0" :disabled="!!importingId" :aria-label="`导入${playlist.name}`" @click="importPlaylist(playlist)">
                  <Loader2 v-if="importingId === playlist.id" class="h-4 w-4 animate-spin" /><Download v-else class="h-4 w-4" />
                </Button>
              </article>
            </div>
          </div>
        </div>
      </div>
    </DialogContent>
  </Dialog>
</template>
