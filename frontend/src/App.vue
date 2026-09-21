<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import type { TaskState } from './types';
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
import MobileTaskPill from './components/mobile/MobileTaskPill.vue';

useTheme();
type TabKey = 'monitor' | 'search' | 'playlists' | 'library' | 'history';
const activeTab = ref<TabKey>('monitor');
const activeComponent = computed(() => ({
  monitor: MonitorTab,
  search: SearchTab,
  playlists: PlaylistTab,
  library: LibraryTab,
  history: HistoryTab,
}[activeTab.value]));
const connected = ref(false);
const taskModalOpen = ref(false);
const settingsModalOpen = ref(false);
const accountsModalOpen = ref(false);
const isFirstInstall = ref(false);

async function checkInitialization() {
  try {
    const res = await api.getSettings();
    if (res.ok && res.data && (res.data.is_configured === false || !res.data.download_dir)) {
      isFirstInstall.value = true;
      settingsModalOpen.value = true;
    }
  } catch {}
}

const taskState = ref<TaskState>({
  status: 'idle', playlist_name: '还没有进行中的任务', platform: 'TRIM Music', target: 'public', user: 'all', total: 0,
  processed_count: 0, reused_count: 0, downloaded_count: 0, failed_count: 0, current_track: null,
  start_time: null, end_time: null, tracks: [], updated_at: new Date().toISOString()
});
const logs = ref<string[]>([]);
const activeTabProps = computed(() => activeTab.value === 'monitor'
  ? { task: taskState.value, logs: logs.value }
  : {});
const activeTabListeners = computed(() => activeTab.value === 'monitor'
  ? {
      'open-task-modal': () => { taskModalOpen.value = true; },
      stopTask: handleStopTask,
    }
  : {});
let eventSource: EventSource | null = null;

function setupSSE() {
  eventSource?.close();
  eventSource = new EventSource('/api/stream');
  eventSource.onopen = () => { connected.value = true; };
  eventSource.onerror = () => { connected.value = false; };
  eventSource.addEventListener('init', (e: MessageEvent) => { try { taskState.value = JSON.parse(e.data); } catch {} });
  eventSource.addEventListener('status', (e: MessageEvent) => { try { taskState.value = JSON.parse(e.data); } catch {} });
  eventSource.addEventListener('log', (e: MessageEvent) => {
    try { const payload = JSON.parse(e.data); if (payload.text) { logs.value.push(payload.text); if (logs.value.length > 500) logs.value.shift(); } } catch {}
  });
}

async function handleStopTask() {
  try {
    const res = await api.stopTask();
    if (res.ok) showToast('任务已停止，已完成的歌曲会保留。', 'warning');
  } catch (e: any) { showToast(`停止失败：${e.message}`, 'error'); }
}

onMounted(() => { setupSSE(); checkInitialization(); });
onUnmounted(() => eventSource?.close());
</script>

<template>
  <div class="min-h-screen bg-background text-foreground">
    <Header :active-tab="activeTab" :connected="connected" @update:active-tab="activeTab = $event" @new-task="taskModalOpen = true" @open-settings="settingsModalOpen = true" @open-accounts="accountsModalOpen = true" />
    <div class="lg:pl-[248px]">
      <main class="app-main-viewport mx-auto w-full max-w-[1500px] px-3 pt-2 sm:px-6 sm:pt-4 lg:px-9 lg:pb-4 lg:pt-6 xl:px-11 flex flex-col">
        <Transition name="tab-fade" mode="out-in">
          <KeepAlive>
            <component
              :is="activeComponent"
              :key="activeTab"
              v-bind="activeTabProps"
              v-on="activeTabListeners"
            />
          </KeepAlive>
        </Transition>
        <footer class="hidden sm:block shrink-0 py-2 border-t border-border/60 text-[10px] text-muted-foreground/75 text-center">TRIM Music Hub · 连接你的飞牛音乐与 NAS 曲库</footer>
      </main>
    </div>
    <NewTaskModal :open="taskModalOpen" @close="taskModalOpen = false" @started="activeTab = 'monitor'" />
    <SettingsModal
      :open="settingsModalOpen"
      :is-first-install="isFirstInstall"
      @close="settingsModalOpen = false; isFirstInstall = false;"
      @open-accounts="settingsModalOpen = false; accountsModalOpen = true;"
    />
    <MusicAccountsModal :open="accountsModalOpen" @close="accountsModalOpen = false" @started="activeTab = 'monitor'" />
    
    <!-- 移动端后台任务微条 (Now Syncing Pill) -->
    <MobileTaskPill
      :task="taskState"
      :visible="activeTab !== 'monitor'"
      @click="activeTab = 'monitor'"
    />

    <Toast />
  </div>
</template>
