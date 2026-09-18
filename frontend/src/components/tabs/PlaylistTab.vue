<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import type { PlaylistSummary } from '../../types';
import { api } from '../../api';
import { showToast } from '../../composables/useToast';
import PlaylistTracksModal from '../modals/PlaylistTracksModal.vue';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Popconfirm } from '@/components/ui/popconfirm';
import { Card } from '@/components/ui/card';
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

// Delete state for Popconfirm
const deletingName = ref<string | null>(null);
const deletePhysicalMap = ref<Record<string, boolean>>({});

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

async function handleDelete(pl: PlaylistSummary) {
  deletingName.value = pl.name;
  const physical = Boolean(deletePhysicalMap.value[pl.name]);
  try {
    const res = await api.deletePlaylist(pl.name, physical);
    if (res.ok) {
      showToast(`已删除“${pl.name}”${physical ? `，并清理 ${res.deleted_files || 0} 个本地文件` : ''}。`, 'success');
      playlists.value = playlists.value.filter(p => p.name !== pl.name);
      delete deletePhysicalMap.value[pl.name];
    } else {
      showToast(res.error || '删除失败', 'error');
    }
  } catch (e: any) {
    showToast(`删除歌单失败：${e.message}`, 'error');
  } finally {
    deletingName.value = null;
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

      <!-- 可滚动歌单列表 -->
      <div
        v-else
        class="flex-1 overflow-y-auto overflow-x-hidden pr-1 space-y-2 select-text scrollbar-thin"
      >
        <div
          v-for="pl in displayedPlaylists"
          :key="pl.name"
          class="swipe-list-item"
        >
          <article
            class="media-list-row media-list-row--playlist"
            role="button"
            tabindex="0"
            :aria-label="`查看歌单 ${pl.name}`"
            @click="viewTracks(pl)"
            @keydown.enter.prevent="viewTracks(pl)"
            @keydown.space.prevent="viewTracks(pl)"
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

            <div class="media-list-row__playlist-tools" @click.stop>
              <Button variant="ghost" size="iconSm" title="编辑歌单" @click="openEdit(pl)">
                <Edit3 class="h-3.5 w-3.5" />
              </Button>
              <Popconfirm
                :title="`删除歌单《${pl.name}》？`"
                description="歌单会从飞牛音乐中移除，歌曲文件默认保留。"
                confirmText="删除歌单"
                :danger="true"
                :loading="deletingName === pl.name"
                side="left"
                align="center"
                widthClass="w-80"
                @confirm="handleDelete(pl)"
              >
                <template #extra>
                  <label class="mt-2 flex cursor-pointer select-none items-center gap-2.5 rounded-xl border border-destructive/25 bg-destructive/10 p-2 text-[11px] text-destructive">
                    <Checkbox v-model="deletePhysicalMap[pl.name]" />
                    <span>同时删除歌单中的本地歌曲和歌词</span>
                  </label>
                </template>
                <Button variant="ghost" size="iconSm" title="删除歌单" class="hover:bg-destructive/10 hover:text-destructive">
                  <Trash2 class="h-3.5 w-3.5" />
                </Button>
              </Popconfirm>
            </div>
          </article>

          <div class="swipe-list-item__action md:hidden">
            <Popconfirm
              :title="`删除歌单《${pl.name}》？`"
              description="歌单会从飞牛音乐中移除，歌曲文件默认保留。"
              confirmText="删除歌单"
              :danger="true"
              :loading="deletingName === pl.name"
              side="left"
              align="center"
              widthClass="w-80"
              @confirm="handleDelete(pl)"
            >
              <template #extra>
                <label class="mt-2 flex cursor-pointer select-none items-center gap-2.5 rounded-xl border border-destructive/25 bg-destructive/10 p-2 text-[11px] text-destructive">
                  <Checkbox v-model="deletePhysicalMap[pl.name]" />
                  <span>同时删除本地歌曲和歌词</span>
                </label>
              </template>
              <Button variant="destructive" class="swipe-list-item__delete" title="删除歌单">
                <Trash2 class="h-4 w-4" />
                <span>删除</span>
              </Button>
            </Popconfirm>
          </div>
        </div>

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

        <!-- 歌单名称 -->
        <div class="space-y-1.5">
          <label class="text-xs font-medium text-foreground/85">歌单名称</label>
          <Input
            v-model="editNewName"
            placeholder="输入歌单名称..."
            class="h-9 text-xs"
          />
        </div>

        <!-- 可见成员分配模式 -->
        <div class="space-y-2 pt-1">
          <label class="text-xs font-medium text-foreground/85">可见范围与成员分配</label>
          
          <div class="grid grid-cols-2 gap-2">
            <Button variant="ghost"
              type="button"
              @click="toggleEditPublic(true)"
              class="h-auto justify-start whitespace-normal p-2.5 rounded-xl border text-left text-xs transition-all flex items-center gap-2"
              :class="editIsPublic
                ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
                : 'border-border bg-muted/60 text-muted-foreground hover:text-foreground'"
            >
              <Globe class="w-4 h-4" />
              <div>
                <div class="font-semibold">公共歌单</div>
                <div class="text-[10px] text-muted-foreground">所有家庭成员可见</div>
              </div>
            </Button>

            <Button variant="ghost"
              type="button"
              @click="toggleEditPublic(false)"
              class="h-auto justify-start whitespace-normal p-2.5 rounded-xl border text-left text-xs transition-all flex items-center gap-2"
              :class="!editIsPublic
                ? 'border-indigo-500/50 bg-indigo-950/20 text-indigo-300'
                : 'border-border bg-muted/60 text-muted-foreground hover:text-foreground'"
            >
              <UserCheck class="w-4 h-4" />
              <div>
                <div class="font-semibold">指定成员专属</div>
                <div class="text-[10px] text-muted-foreground">仅勾选的用户可见</div>
              </div>
            </Button>
          </div>

          <!-- 指定用户勾选列表 -->
          <div v-if="!editIsPublic" class="space-y-1.5 pt-1.5">
            <div class="text-[11px] text-muted-foreground">请勾选允许访问此歌单的飞牛用户：</div>
            <div class="rounded-xl border border-border bg-muted/70 p-2.5 space-y-2 max-h-40 overflow-y-auto scrollbar-thin">
              <label
                v-for="u in systemUsers"
                :key="u.id"
                class="flex items-center justify-between p-1.5 rounded-lg hover:bg-muted/60 cursor-pointer select-none text-xs"
              >
                <div class="flex items-center gap-2">
                  <Checkbox
                    :checked="editSelectedUserIds.includes(u.id)"
                    @update:checked="() => toggleEditUserId(u.id)"
                  />
                  <span class="text-foreground font-medium">{{ u.name }}</span>
                </div>
                <Badge v-if="u.role === 'admin'" variant="secondary" class="text-[9px] px-1 py-0 text-muted-foreground">
                  管理员
                </Badge>
              </label>
            </div>
          </div>
        </div>

        <DialogFooter class="flex justify-end gap-2 pt-2">
          <Button variant="ghost" size="sm" @click="editDialogOpen = false">取消</Button>
          <Button
            variant="default"
            size="sm"
            @click="handleSaveEdit"
            :disabled="isSavingEdit"
            class="flex items-center gap-1.5"
          >
            <Loader2 v-if="isSavingEdit" class="w-3.5 h-3.5 animate-spin" />
            <span>{{ isSavingEdit ? '保存中...' : '保存修改' }}</span>
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
