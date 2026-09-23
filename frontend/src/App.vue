<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue';
import type { TaskState, QueueTask, CurrentUser } from './types';
import { api } from './api';
import { showToast } from './composables/useToast';
import { useTheme } from './composables/useTheme';
import Header from './components/Header.vue';
import Toast from './components/Toast.vue';
import MonitorTab from './components/tabs/MonitorTab.vue';
import SearchTab from './components/tabs/SearchTab.vue';
import PlaylistTab from './components/tabs/PlaylistTab.vue';
import LibraryTab from './components/tabs/LibraryTab.vue';
import HistoryTab from './components/tabs/HistoryTab.vue';
import NewTaskModal from './components/modals/NewTaskModal.vue';
import SettingsModal from './components/modals/SettingsModal.vue';
import MusicAccountsModal from './components/modals/MusicAccountsModal.vue';
import LoginModal from './components/modals/LoginModal.vue';
import MobileTaskPill from './components/mobile/MobileTaskPill.vue';

useTheme();
type TabKey = 'monitor' | 'search' | 'playlists' | 'library' | 'history';
const activeTab = ref<TabKey>('monitor');
// 懒挂载集合：首次访问时挂载，后续通过 v-show 毫秒级切换，杜绝 DOM 反复卸载重排导致 TabBar 动画卡顿
const visitedTabs = ref<Set<TabKey>>(new Set(['monitor']));

watch(activeTab, (tab) => {
  if (!visitedTabs.value.has(tab)) {
    visitedTabs.value.add(tab);
  }
});

const connected = ref(false);
const taskModalOpen = ref(false);
const taskModalUrl = ref('');
const taskModalAccountId = ref('');
const taskModalPlaylistName = ref('');
const settingsModalOpen = ref(false);
const accountsModalOpen = ref(false);
const loginModalOpen = ref(false);
const isFirstInstall = ref(false);
const currentUser = ref<CurrentUser | null>(null);

const searchSubTab = ref<'parse' | 'search'>('parse');
const searchImportPayload = ref<{ url: string; accountId?: string; playlistName?: string; ts?: number } | null>(null);

function handleOpenImportTab(payload?: { url: string; accountId?: string; playlistName?: string }) {
  activeTab.value = 'search';
  searchSubTab.value = 'parse';
  if (payload) {
    searchImportPayload.value = { ...payload, ts: Date.now() };
  }
}

function handleTaskModalClose() {
  taskModalOpen.value = false;
  taskModalUrl.value = '';
  taskModalAccountId.value = '';
  taskModalPlaylistName.value = '';
}

function handleOpenImportFromAccount(payload: { url: string; accountId?: string; playlistName?: string }) {
  accountsModalOpen.value = false;
  handleOpenImportTab(payload);
}

async function checkInitialization() {
  try {
    const res = await api.getSettings();
    if (res.ok && res.data && (res.data.is_configured === false || !res.data.download_dir)) {
      isFirstInstall.value = true;
      settingsModalOpen.value = true;
    }
  } catch {}
}

const taskState = ref<TaskState>(({
  status: 'idle', playlist_name: '还没有进行中的任务', platform: 'TRIM Music', target: 'public', user: 'all', total: 0,
  processed_count: 0, reused_count: 0, downloaded_count: 0, failed_count: 0, current_track: null,
  start_time: null, end_time: null, tracks: [], updated_at: new Date().toISOString()
}) as TaskState);
const queue = ref<QueueTask[]>([]);
const logs = ref<string[]>([]);

async function loadQueue() {
  try {
    const res = await api.getTaskQueue();
    if (res.ok && Array.isArray(res.data)) {
      queue.value = res.data;
    }
  } catch {}
}

let eventSource: EventSource | null = null;

function setupSSE() {
  eventSource?.close();
  eventSource = new EventSource('/api/stream');
  eventSource.onopen = () => { connected.value = true; };
  eventSource.onerror = () => { connected.value = false; };
  eventSource.addEventListener('init', (e: MessageEvent) => { try { taskState.value = JSON.parse(e.data); } catch {} });
  eventSource.addEventListener('status', (e: MessageEvent) => { try { taskState.value = JSON.parse(e.data); } catch {} });
  eventSource.addEventListener('queue', (e: MessageEvent) => { try { queue.value = JSON.parse(e.data); } catch {} });
  eventSource.addEventListener('speed', (e: MessageEvent) => {
    try {
      const payload = JSON.parse(e.data);
      if (taskState.value) {
        taskState.value.speed = payload.speed || '';
      }
    } catch {}
  });
  eventSource.addEventListener('log', (e: MessageEvent) => {
    try { const payload = JSON.parse(e.data); if (payload.text) { logs.value.push(payload.text); if (logs.value.length > 500) logs.value.shift(); } } catch {}
  });
}

async function checkAuth() {
  try {
    const res = await api.getAuthMe();
    if (res.ok && res.loggedIn && res.user) {
      currentUser.value = res.user;
      loginModalOpen.value = false;
      setupSSE();
      loadQueue();
      checkInitialization();
    } else {
      currentUser.value = null;
      loginModalOpen.value = true;
    }
  } catch {
    currentUser.value = null;
    loginModalOpen.value = true;
  }
}

function handleLoggedIn(user: CurrentUser) {
  currentUser.value = user;
  loginModalOpen.value = false;
  showToast(`欢迎回来，${user.username}（${user.isAdmin ? '管理员' : '普通成员'}）`, 'success');
  setupSSE();
  checkInitialization();
}

async function handleLogout() {
  try {
    await api.logout();
    currentUser.value = null;
    eventSource?.close();
    connected.value = false;
    loginModalOpen.value = true;
    showToast('已安全退出当前账号', 'info');
  } catch (e: any) {
    showToast(`退出登录失败: ${e.message}`, 'error');
  }
}

async function handleStopTask() {
  try {
    const res = await api.stopTask();
    if (res.ok) showToast('任务已停止，已完成的歌曲会保留。', 'warning');
  } catch (e: any) { showToast(`停止失败：${e.message}`, 'error'); }
}

onMounted(() => {
  if (typeof window !== 'undefined') {
    window.addEventListener('auth:unauthorized', () => {
      currentUser.value = null;
      loginModalOpen.value = true;
    });
  }
  checkAuth();
});
onUnmounted(() => eventSource?.close());
</script>

<template>
  <div class="min-h-screen bg-background text-foreground">
    <Header
      :active-tab="activeTab"
      :connected="connected"
      :current-user="currentUser"
      @update:active-tab="activeTab = $event"
      @new-task="handleOpenImportTab()"
      @open-settings="settingsModalOpen = true"
      @open-accounts="accountsModalOpen = true"
      @logout="handleLogout"
    />
    <div class="lg:pl-[248px]">
      <main class="app-main-viewport mx-auto w-full max-w-[1500px] px-3 pt-2 sm:px-6 sm:pt-4 lg:px-9 lg:pb-4 lg:pt-6 xl:px-11 flex flex-col">
        <MonitorTab
          v-if="visitedTabs.has('monitor')"
          v-show="activeTab === 'monitor'"
          :task="taskState"
          :logs="logs"
          :queue="queue"
          :current-user="currentUser"
          @open-task-modal="handleOpenImportTab"
          @stop-task="handleStopTask"
          @refresh-queue="loadQueue"
        />
        <SearchTab
          v-if="visitedTabs.has('search')"
          v-show="activeTab === 'search'"
          :current-user="currentUser"
          :initial-sub-tab="searchSubTab"
          :import-payload="searchImportPayload"
          @task-started="activeTab = 'monitor'; loadQueue();"
          @open-accounts="accountsModalOpen = true"
          @update:initial-sub-tab="searchSubTab = $event"
        />
        <PlaylistTab
          v-if="visitedTabs.has('playlists')"
          v-show="activeTab === 'playlists'"
          :current-user="currentUser"
        />
        <LibraryTab
          v-if="visitedTabs.has('library')"
          v-show="activeTab === 'library'"
          :current-user="currentUser"
        />
        <HistoryTab
          v-if="visitedTabs.has('history')"
          v-show="activeTab === 'history'"
          :current-user="currentUser"
        />
        <footer class="hidden sm:block shrink-0 py-2 border-t border-border/60 text-[10px] text-muted-foreground/75 text-center">TRIM Music Hub · 连接你的飞牛音乐与 NAS 曲库</footer>
      </main>
    </div>
    <NewTaskModal
      :open="taskModalOpen"
      :initial-url="taskModalUrl"
      :initial-account-id="taskModalAccountId"
      :initial-playlist-name="taskModalPlaylistName"
      @close="handleTaskModalClose"
      @started="activeTab = 'monitor'"
    />
    <SettingsModal
      :open="settingsModalOpen"
      :is-first-install="isFirstInstall"
      :current-user="currentUser"
      @close="settingsModalOpen = false; isFirstInstall = false;"
      @open-accounts="settingsModalOpen = false; accountsModalOpen = true;"
      @logout="handleLogout"
    />
    <MusicAccountsModal
      :open="accountsModalOpen"
      :current-user="currentUser"
      @close="accountsModalOpen = false"
      @started="activeTab = 'monitor'"
      @open-import="handleOpenImportFromAccount"
    />
    <LoginModal :open="loginModalOpen" @logged-in="handleLoggedIn" />
    
    <!-- 移动端后台任务微条 (Now Syncing Pill) -->
    <MobileTaskPill
      :task="taskState"
      :visible="activeTab !== 'monitor'"
      @click="activeTab = 'monitor'"
    />

    <Toast />
  </div>
</template>
