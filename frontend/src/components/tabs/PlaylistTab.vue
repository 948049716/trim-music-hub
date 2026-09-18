<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import type { PlaylistSummary } from '../../types';
import { api } from '../../api';
import { showToast } from '../../composables/useToast';
import PlaylistTracksModal from '../modals/PlaylistTracksModal.vue';
import BatchActionBar from '@/components/ui/BatchActionBar.vue';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Popconfirm } from '@/components/ui/popconfirm';
import { Card } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter
} from '@/components/ui/dialog';
import {
  ListMusic,
  Disc3,
  UserCheck,
  RefreshCw,
  Loader2,
  Trash2,
  Edit3,
  Music,
  CalendarDays,
  Search,
  Globe,
  Check,
  X,
  Clock
} from 'lucide-vue-next';

const playlists = ref<PlaylistSummary[]>([]);
const systemUsers = ref<Array<{ id: number; name: string; role?: string }>>([]);
const isLoading = ref(false);
const loadError = ref('');
const searchKw = ref('');
const failedCoverKeys = ref<Set<string>>(new Set());

// 批量选择与操作状态（对齐曲库多选交互）
const selectedPlaylistNames = ref<Set<string>>(new Set());
const isBatchDeletingPlaylists = ref(false);
const batchDeletePhysical = ref(false);

// 滚动分页控制
const displayLimit = ref(15);
const sentinelRef = ref<HTMLElement | null>(null);
let observer: IntersectionObserver | null = null;

const filteredPlaylists = computed(() => {
  const kw = searchKw.value.trim().toLowerCase();
  if (!kw) return playlists.value;
  return playlists.value.filter(p => {
    const nameMatch = p.name.toLowerCase().includes(kw);
    const userStr = typeof p.users === 'string' ? p.users : '';
    const userMatch = userStr.toLowerCase().includes(kw);
    return nameMatch || userMatch;
  });
});

const displayedPlaylists = computed(() => {
  return filteredPlaylists.value.slice(0, displayLimit.value);
});

const hasMore = computed(() => displayLimit.value < filteredPlaylists.value.length);

function loadMore() {
  if (hasMore.value) {
    displayLimit.value += 15;
  }
}

watch(searchKw, () => {
  displayLimit.value = 15;
});

// View & Edit Tracks Dialog (复用通用歌单曲目组件 PlaylistTracksModal)
const tracksDialogOpen = ref(false);
const activePlaylistName = ref('');
const activePlaylist = ref<PlaylistSummary | null>(null);

function handleModalTracksChanged(event: { playlistName: string; remainingCount: number }) {
  const pl = playlists.value.find(p => p.name === event.playlistName);
  if (pl) {
    pl.track_count = event.remainingCount;
  }
  if (activePlaylist.value && activePlaylist.value.name === event.playlistName) {
    activePlaylist.value.track_count = event.remainingCount;
  }
}

// Edit Playlist Dialog (Name + User Assignment)
const editDialogOpen = ref(false);
const editOldName = ref('');
const editNewName = ref('');
const editIsPublic = ref(true);
const editSelectedUserIds = ref<number[]>([]);
const isSavingEdit = ref(false);

async function fetchUsers() {
  try {
    const res = await api.getUsers();
    if (res.ok && res.data) {
      systemUsers.value = res.data;
    }
  } catch (e) {}
}

async function fetchPlaylists() {
  isLoading.value = true;
  loadError.value = '';
  try {
    const res = await api.getPlaylists();
    if (res.ok) {
      playlists.value = res.data || [];
      const currentNames = new Set(playlists.value.map(p => p.name));
      selectedPlaylistNames.value = new Set(
        Array.from(selectedPlaylistNames.value).filter(name => currentNames.has(name))
      );
    } else {
      loadError.value = res.error || '无法读取飞牛歌单';
      showToast('无法读取歌单列表，请稍后重试。', 'error');
    }
  } catch (e: any) {
    loadError.value = e.message || '网络连接异常';
    showToast(`读取歌单失败：${loadError.value}`, 'error');
  } finally {
    isLoading.value = false;
  }
}

function toggleSelectPlaylist(name: string) {
  const next = new Set(selectedPlaylistNames.value);
  if (next.has(name)) {
    next.delete(name);
  } else {
    next.add(name);
  }
  selectedPlaylistNames.value = next;
}

function toggleSelectAllPlaylists() {
  if (selectedPlaylistNames.value.size === filteredPlaylists.value.length && filteredPlaylists.value.length > 0) {
    selectedPlaylistNames.value = new Set();
  } else {
    selectedPlaylistNames.value = new Set(filteredPlaylists.value.map(p => p.name));
  }
}

async function handleBatchDeletePlaylists() {
  const targetNames = Array.from(selectedPlaylistNames.value);
  if (targetNames.length === 0) return;

  isBatchDeletingPlaylists.value = true;
  try {
    const results = await Promise.all(
      targetNames.map(name => api.deletePlaylist(name, batchDeletePhysical.value))
    );
    const successCount = results.filter(r => r.ok).length;
    const targetSet = new Set(targetNames);
    playlists.value = playlists.value.filter(p => !targetSet.has(p.name));
    selectedPlaylistNames.value = new Set();
    showToast(`已删除 ${successCount} 个歌单${batchDeletePhysical.value ? '，并清理本地文件' : ''}。`, 'success');
  } catch (e: any) {
    showToast(`批量删除歌单失败: ${e.message}`, 'error');
  } finally {
    isBatchDeletingPlaylists.value = false;
  }
}

function getPlaylistMembers(users: PlaylistSummary['users']) {
  if (Array.isArray(users)) {
    return users.map(user => user.name).filter(Boolean);
  }
  return (users || '').split(',').map(user => user.trim()).filter(Boolean);
}

function isPublicPlaylist(pl: PlaylistSummary): boolean {
  if (systemUsers.value.length > 0 && pl.user_ids && pl.user_ids.length > 0) {
    const allUids = systemUsers.value.map(u => u.id);
    if (allUids.every(uid => pl.user_ids?.includes(uid))) {
      return true;
    }
  }
  const members = getPlaylistMembers(pl.users);
  return members.length === 0 || members.some(m => /公共|所有成员/.test(m));
}

function formatMemberSummary(pl: PlaylistSummary) {
  if (isPublicPlaylist(pl)) {
    return '公共歌单 (全部成员)';
  }
  const members = getPlaylistMembers(pl.users);
  return `专属 · ${members.join(', ')}`;
}

function formatPlaylistDate(value?: string) {
  if (!value) return '创建时间未知';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '创建时间未知';
  return date.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' });
}

type CoverType = 'playlist' | 'track';

function coverUrl(type: CoverType, guid?: string) {
  return guid ? `/api/covers/${type}/${encodeURIComponent(guid)}?size=160` : '';
}

function coverAvailable(type: CoverType, guid?: string) {
  return Boolean(guid) && !failedCoverKeys.value.has(`${type}:${guid}`);
}

function markCoverFailed(type: CoverType, guid?: string) {
  const next = new Set(failedCoverKeys.value);
  next.add(`${type}:${guid || ''}`);
  failedCoverKeys.value = next;
}

function viewTracks(pl: PlaylistSummary) {
  activePlaylist.value = pl;
  activePlaylistName.value = pl.name;
  tracksDialogOpen.value = true;
}

function openEdit(pl: PlaylistSummary) {
  editOldName.value = pl.name;
  editNewName.value = pl.name;

  const allUids = systemUsers.value.map(u => u.id);
  const currentUids = pl.user_ids || [];

  const isPublic = isPublicPlaylist(pl);
  editIsPublic.value = isPublic;

  if (isPublic) {
    editSelectedUserIds.value = [...allUids];
  } else {
    editSelectedUserIds.value = currentUids.length > 0 ? [...currentUids] : (allUids[0] ? [allUids[0]] : []);
  }

  editDialogOpen.value = true;
}

function toggleEditPublic(isPub: boolean) {
  editIsPublic.value = isPub;
  if (isPub) {
    editSelectedUserIds.value = systemUsers.value.map(u => u.id);
  } else if (editSelectedUserIds.value.length === 0 && systemUsers.value.length > 0) {
    editSelectedUserIds.value = [systemUsers.value[0].id];
  }
}

function toggleEditUserId(uid: number) {
  const s = new Set(editSelectedUserIds.value);
  if (s.has(uid)) {
    s.delete(uid);
  } else {
    s.add(uid);
  }
  editSelectedUserIds.value = Array.from(s);
  if (systemUsers.value.length > 0 && editSelectedUserIds.value.length === systemUsers.value.length) {
    editIsPublic.value = true;
  } else {
    editIsPublic.value = false;
  }
}

async function handleSaveEdit() {
  const newName = editNewName.value.trim();
  if (!newName) {
    showToast('歌单名称不能为空', 'error');
    return;
  }

  const targetUids = editIsPublic.value
    ? systemUsers.value.map(u => u.id)
    : editSelectedUserIds.value;

  if (targetUids.length === 0) {
    showToast('请至少选择一个可见成员', 'warning');
    return;
  }

  isSavingEdit.value = true;
  try {
    let effectiveName = editOldName.value;
    if (newName !== editOldName.value) {
      const resRename = await api.renamePlaylist(editOldName.value, newName);
      if (!resRename.ok) {
        showToast(resRename.error || '重命名失败', 'error');
        return;
      }
      effectiveName = newName;
    }

    const resUsers = await api.updatePlaylistUsers(effectiveName, targetUids);
    if (!resUsers.ok) {
      showToast(resUsers.error || '更新歌单可见成员失败', 'error');
      return;
    }

    showToast(`“${effectiveName}”已保存。`, 'success');
    editDialogOpen.value = false;
    await fetchPlaylists();
  } catch (e: any) {
    showToast(`保存失败：${e.message}`, 'error');
  } finally {
    isSavingEdit.value = false;
  }
}

onMounted(async () => {
  await fetchUsers();
  await fetchPlaylists();

  observer = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && hasMore.value) {
      loadMore();
    }
  }, { threshold: 0.1 });
  if (sentinelRef.value) observer.observe(sentinelRef.value);
});
</script>

<template>
  <div class="space-y-4">
    <!-- Top Control Bar (紧凑无冗余标题) -->
    <Card class="bg-card/80 border-border backdrop-blur-xl shadow-xl p-3 sm:p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shrink-0">
      <div class="flex items-center gap-2.5 text-xs">
        <span class="text-foreground/85 font-medium flex items-center gap-1.5">
          <ListMusic class="w-4 h-4 text-primary" />
          <span>歌单</span>
          <strong class="text-foreground font-mono text-sm">{{ playlists.length }}</strong> 个
        </span>
        <span class="text-muted-foreground/75">|</span>
        <span class="flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <span class="h-1.5 w-1.5 rounded-full bg-emerald-400" />
          已连接飞牛音乐
        </span>
      </div>

      <div class="flex items-center gap-2 w-full sm:w-auto">
        <div class="relative flex-1 sm:w-64">
          <Search class="w-3.5 h-3.5 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2 z-10" />
          <Input
            v-model="searchKw"
            type="text"
            placeholder="搜索歌单或成员"
            class="pl-9 pr-8 h-9 text-xs"
          />
          <button
            v-if="searchKw"
            type="button"
            @click="searchKw = ''"
            class="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground p-0.5 rounded-full"
            title="清空"
          >
            <X class="w-3.5 h-3.5" />
          </button>
        </div>

        <Button
          variant="outline"
          size="icon"
          @click="fetchPlaylists"
          title="刷新歌单列表"
          class="h-9 w-9 rounded-xl shrink-0"
        >
          <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': isLoading }" />
        </Button>
      </div>
    </Card>

    <!-- Playlist Assets List -->
    <Card class="relative bg-card/80 border-border backdrop-blur-xl shadow-2xl p-2.5 sm:p-4 md:p-5 flex flex-col h-[calc(100dvh-185px)] sm:h-[calc(100vh-220px)] min-h-[380px] sm:min-h-[500px]">
      <!-- 固定的列表头部栏（全选 / 统计，对齐曲库体验） -->
      <div v-if="filteredPlaylists.length > 0" class="flex items-center justify-between pb-2.5 border-b border-border/70 mb-2.5 text-xs shrink-0">
        <div class="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            class="h-7 px-2 text-muted-foreground text-[11px] sm:text-xs"
            @click="toggleSelectAllPlaylists"
          >
            {{ selectedPlaylistNames.size === filteredPlaylists.length && filteredPlaylists.length > 0 ? '取消全选' : '全选' }}
          </Button>
          <span class="text-muted-foreground/50">|</span>
          <span class="text-muted-foreground text-[11px] sm:text-xs">
            共 <strong class="text-foreground font-mono">{{ filteredPlaylists.length }}</strong> 个歌单
          </span>
          <span v-if="selectedPlaylistNames.size > 0" class="text-amber-600 dark:text-amber-400 font-medium text-[11px] sm:text-xs">
            · 已选 {{ selectedPlaylistNames.size }} 个
          </span>
        </div>
      </div>

      <div v-if="isLoading" class="py-20 text-center text-muted-foreground my-auto">
        <Loader2 class="mx-auto h-7 w-7 animate-spin text-primary" />
        <p class="mt-3 text-xs">正在读取歌单…</p>
      </div>

      <div v-else-if="loadError" class="my-auto flex flex-col items-center py-16 text-center">
        <span class="grid h-14 w-14 place-items-center rounded-2xl border border-destructive/20 bg-destructive/10 text-destructive">
          <RefreshCw class="h-5 w-5" />
        </span>
        <p class="mt-4 text-sm font-semibold text-foreground">歌单列表获取失败</p>
        <p class="mt-1 max-w-sm text-xs leading-relaxed text-muted-foreground">{{ loadError }}</p>
        <Button variant="outline" size="sm" class="mt-4" @click="fetchPlaylists">
          <RefreshCw class="h-3.5 w-3.5" />重新加载
        </Button>
      </div>

      <div v-else-if="playlists.length === 0" class="py-20 text-center text-muted-foreground my-auto">
        <div class="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-dashed border-border bg-muted/40">
          <ListMusic class="h-6 w-6 text-muted-foreground/55" />
        </div>
        <p class="mt-4 text-xs">还没有歌单，先导入一个第三方歌单。</p>
      </div>

      <div v-else-if="filteredPlaylists.length === 0" class="py-20 text-center text-muted-foreground my-auto space-y-2.5">
        <p class="text-xs">未找到与 "{{ searchKw }}" 匹配的歌单</p>
        <Button variant="outline" size="sm" class="h-7 text-xs" @click="searchKw = ''">清空搜索</Button>
      </div>

      <!-- 可滚动歌单列表 (无 swipe-list-item，点击卡片切换选中) -->
      <div
        v-else
        class="flex-1 overflow-y-auto overflow-x-hidden pr-1 space-y-2 select-text scrollbar-thin"
      >
        <article
          v-for="pl in displayedPlaylists"
          :key="pl.name"
          :class="[
            'media-list-row media-list-row--playlist transition-all',
            { 'media-list-row--selected': selectedPlaylistNames.has(pl.name) }
          ]"
          role="button"
          tabindex="0"
          :aria-pressed="selectedPlaylistNames.has(pl.name)"
          :aria-label="`${selectedPlaylistNames.has(pl.name) ? '取消选择' : '选择'}歌单 ${pl.name}`"
          @click="toggleSelectPlaylist(pl.name)"
          @keydown.enter.prevent="toggleSelectPlaylist(pl.name)"
          @keydown.space.prevent="toggleSelectPlaylist(pl.name)"
        >
          <div class="media-list-row__art" aria-hidden="true">
            <img
              v-if="coverAvailable('playlist', pl.cover_guid)"
              :src="coverUrl('playlist', pl.cover_guid)"
              :alt="`${pl.name} 封面`"
              loading="lazy"
              decoding="async"
              @error="markCoverFailed('playlist', pl.cover_guid)"
            />
            <div v-else class="media-list-row__art-fallback">
              <ListMusic class="h-6 w-6 text-primary/35" />
            </div>
          </div>

          <div class="media-list-row__content">
            <div class="media-list-row__title-line">
              <strong class="media-list-row__title">{{ pl.name }}</strong>
              <Badge :variant="pl.m3u_exists ? 'success' : 'outline'" class="shrink-0">
                {{ pl.m3u_exists ? '已同步' : '待生成 M3U' }}
              </Badge>
            </div>
            <p class="media-list-row__subtitle" :title="formatMemberSummary(pl)">
              {{ isPublicPlaylist(pl) ? '所有家庭成员可见' : formatMemberSummary(pl) }}
            </p>
            <div class="media-list-row__meta">
              <span class="flex items-center gap-1"><Music class="h-3 w-3" />{{ pl.track_count }} 首</span>
              <span class="flex items-center gap-1"><CalendarDays class="h-3 w-3" />{{ formatPlaylistDate(pl.updated_at || pl.created_at) }}</span>
              <span class="hidden items-center gap-1 sm:flex"><Globe v-if="isPublicPlaylist(pl)" class="h-3 w-3" /><UserCheck v-else class="h-3 w-3" />{{ isPublicPlaylist(pl) ? '公共歌单' : '指定成员' }}</span>
            </div>
          </div>

          <!-- 末尾操作工具栏：点击末尾 icon 展开详情或编辑，已去掉删除 icon -->
          <div class="media-list-row__playlist-tools" @click.stop>
            <Button
              variant="ghost"
              size="iconSm"
              title="查看歌单曲目与详情"
              class="text-muted-foreground hover:text-primary hover:bg-primary/10 transition-colors"
              @click="viewTracks(pl)"
            >
              <ListMusic class="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="iconSm"
              title="编辑歌单"
              class="text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
              @click="openEdit(pl)"
            >
              <Edit3 class="h-3.5 w-3.5" />
            </Button>
          </div>
        </article>

        <!-- 滚动触底 Sentinel 哨兵元素 -->
        <div ref="sentinelRef" class="py-3 text-center">
          <div v-if="hasMore" class="flex items-center justify-center gap-2 text-xs text-muted-foreground py-2">
            <RefreshCw class="w-4 h-4 animate-spin text-primary" />
            <span>正在加载更多歌单…</span>
          </div>
          <div v-else-if="filteredPlaylists.length > 0" class="py-2 text-center text-[11px] text-muted-foreground/75">
            — 已显示全部 {{ filteredPlaylists.length }} 个歌单 —
          </div>
        </div>
      </div>
    </Card>

    <!-- 底部浮动批量操作栏（歌单管理） -->
    <!-- 批量操作悬浮条 (通用组件复用) -->
    <BatchActionBar
      :show="selectedPlaylistNames.size > 0"
      :count="selectedPlaylistNames.size"
      unit="个歌单"
      action-text="彻底删除"
      confirm-title="彻底删除选中的歌单？"
      confirm-desc="歌单将从飞牛音乐中移除。"
      :loading="isBatchDeletingPlaylists"
      @cancel="selectedPlaylistNames = new Set()"
      @confirm="handleBatchDeletePlaylists"
    >
      <template #extra>
        <label class="mt-2 flex cursor-pointer select-none items-center gap-2.5 rounded-xl border border-destructive/25 bg-destructive/10 p-2 text-[11px] text-destructive">
          <Checkbox v-model="batchDeletePhysical" />
          <span>同时删除歌单中的本地歌曲和歌词</span>
        </label>
      </template>
    </BatchActionBar>

    <!-- Dialog: View & Edit Tracks (通用歌单曲目管理组件) -->
    <PlaylistTracksModal
      v-model:open="tracksDialogOpen"
      :playlist-name="activePlaylistName"
      :playlist-summary="activePlaylist"
      @tracks-changed="handleModalTracksChanged"
    />

    <!-- Dialog: Edit Playlist (支持修改歌单名与指定用户分配) -->
    <Dialog :open="editDialogOpen" @update:open="(val: boolean) => editDialogOpen = val">
      <DialogContent class="sm:max-w-md bg-popover border border-border backdrop-blur-2xl shadow-2xl rounded-2xl p-6 space-y-4">
        <DialogHeader>
          <DialogTitle class="text-base font-bold text-foreground flex items-center gap-2">
            <Edit3 class="w-4 h-4 text-primary" />
            <span>编辑歌单</span>
          </DialogTitle>
          <DialogDescription class="text-xs text-muted-foreground">
            修改歌单名称和可见成员。
          </DialogDescription>
        </DialogHeader>

        <div class="space-y-4 py-1">
          <!-- 歌单名称 -->
          <div class="space-y-1.5">
            <label class="text-xs font-medium text-foreground">歌单名称</label>
            <Input
              v-model="editNewName"
              placeholder="输入歌单名称"
              class="h-9 text-xs"
            />
          </div>

          <!-- 可见范围设置 -->
          <div class="space-y-2">
            <label class="text-xs font-medium text-foreground">可见成员</label>
            <div class="grid grid-cols-2 gap-2">
              <button
                type="button"
                @click="toggleEditPublic(true)"
                :class="[
                  'flex items-center gap-2 p-2.5 rounded-xl border text-xs font-medium text-left transition-all',
                  editIsPublic
                    ? 'border-primary/60 bg-primary/10 text-primary'
                    : 'border-border bg-card/60 text-muted-foreground hover:bg-muted'
                ]"
              >
                <Globe class="w-4 h-4 shrink-0" />
                <div>
                  <div class="font-semibold text-foreground">公共歌单</div>
                  <div class="text-[10px] text-muted-foreground">所有家庭成员均可见</div>
                </div>
              </button>

              <button
                type="button"
                @click="toggleEditPublic(false)"
                :class="[
                  'flex items-center gap-2 p-2.5 rounded-xl border text-xs font-medium text-left transition-all',
                  !editIsPublic
                    ? 'border-primary/60 bg-primary/10 text-primary'
                    : 'border-border bg-card/60 text-muted-foreground hover:bg-muted'
                ]"
              >
                <UserCheck class="w-4 h-4 shrink-0" />
                <div>
                  <div class="font-semibold text-foreground">指定成员</div>
                  <div class="text-[10px] text-muted-foreground">仅勾选的成员可见</div>
                </div>
              </button>
            </div>

            <!-- 成员勾选列表 -->
            <div
              v-if="!editIsPublic && systemUsers.length > 0"
              class="space-y-1 pt-1.5 max-h-40 overflow-y-auto"
            >
              <div
                v-for="u in systemUsers"
                :key="u.id"
                @click="toggleEditUserId(u.id)"
                class="flex items-center justify-between p-2 rounded-lg hover:bg-muted/60 cursor-pointer text-xs"
              >
                <div class="flex items-center gap-2">
                  <UserCheck class="w-3.5 h-3.5 text-muted-foreground" />
                  <span>{{ u.name }}</span>
                  <Badge v-if="u.role === 'admin'" variant="secondary" class="text-[9px] px-1 py-0">管理员</Badge>
                </div>
                <div
                  :class="[
                    'w-4 h-4 rounded border flex items-center justify-center transition-colors',
                    editSelectedUserIds.includes(u.id)
                      ? 'bg-primary border-primary text-primary-foreground'
                      : 'border-border'
                  ]"
                >
                  <Check v-if="editSelectedUserIds.includes(u.id)" class="w-3 h-3 stroke-[3]" />
                </div>
              </div>
            </div>
          </div>
        </div>

        <DialogFooter class="gap-2 sm:gap-0">
          <Button variant="ghost" size="sm" @click="editDialogOpen = false" class="text-xs">取消</Button>
          <Button size="sm" :disabled="isSavingEdit" @click="handleSaveEdit" class="text-xs gap-1.5">
            <Loader2 v-if="isSavingEdit" class="w-3.5 h-3.5 animate-spin" />
            <span>保存变更</span>
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
