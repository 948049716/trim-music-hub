<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue';
import type { TaskState } from './types';
import { api } from './api';
import { showToast } from './composables/useToast';
import Header from './components/Header.vue';
import Toast from './components/Toast.vue';
import MonitorTab from './components/tabs/MonitorTab.vue';
import SearchTab from './components/tabs/SearchTab.vue';
import PlaylistTab from './components/tabs/PlaylistTab.vue';
import LibraryTab from './components/tabs/LibraryTab.vue';
import HistoryTab from './components/tabs/HistoryTab.vue';
import NewTaskModal from './components/modals/NewTaskModal.vue';
import SettingsModal from './components/modals/SettingsModal.vue';

const activeTab = ref<'monitor' | 'search' | 'playlists' | 'library' | 'history'>('monitor');
const connected = ref(false);
const taskModalOpen = ref(false);
const settingsModalOpen = ref(false);
const isFirstInstall = ref(false);

async function checkInitialization() {
  try {
    const res = await api.getSettings();
    if (res.ok && res.data) {
      if (res.data.is_configured === false || !res.data.download_dir) {
        isFirstInstall.value = true;
        settingsModalOpen.value = true;
      }
    }
  } catch (e) {}
}

const pageMeta = computed(() => ({
  monitor: { eyebrow: 'OVERVIEW', title: '任务监控', description: '查看同步流水线、当前曲目与实时事件。' },
  search: { eyebrow: 'DISCOVER', title: '全网搜歌', description: '搜索高品质音源并安全写入本地曲库。' },
  playlists: { eyebrow: 'COLLECTIONS', title: '飞牛歌单', description: '管理飞牛音乐中的歌单与关联曲目。' },
  library: { eyebrow: 'LIBRARY', title: '曲库检索', description: '检索、核对和维护 NAS 本地音乐资产。' },
  history: { eyebrow: 'ACTIVITY', title: '下载历史', description: '回顾单曲下载与歌单同步执行记录。' },
})[activeTab.value]);

const taskState = ref<TaskState>(({
  status: 'idle',
  playlist_name: '等待任务中...',
  platform: 'TRIM Music',
  target: 'public',
  user: 'all',
  total: 0,
  processed_count: 0,
  reused_count: 0,
  downloaded_count: 0,
  failed_count: 0,
  current_track: null,
  start_time: null,
  end_time: null,
  tracks: [],
  updated_at: new Date().toISOString()
}));

const logs = ref<string[]>([]);
let eventSource: EventSource | null = null;

function setupSSE() {
  if (eventSource) eventSource.close();
  eventSource = new EventSource('/api/stream');
  eventSource.onopen = () => { connected.value = true; };
  eventSource.onerror = () => { connected.value = false; };
  eventSource.addEventListener('init', (e: MessageEvent) => {
    try { taskState.value = JSON.parse(e.data); } catch {}
  });
  eventSource.addEventListener('status', (e: MessageEvent) => {
    try { taskState.value = JSON.parse(e.data); } catch {}
  });
  eventSource.addEventListener('log', (e: MessageEvent) => {
    try {
      const payload = JSON.parse(e.data);
      if (payload.text) {
        logs.value.push(payload.text);
        if (logs.value.length > 500) logs.value.shift();
      }
    } catch {}
  });
}

async function handleStopTask() {
  try {
    const res = await api.stopTask();
    if (res.ok) showToast('已发送任务中止指令', 'warning');
  } catch (e: any) {
    showToast(`中止异常: ${e.message}`, 'error');
  }
}

onMounted(() => {
  setupSSE();
  checkInitialization();
});
onUnmounted(() => eventSource?.close());
</script>

<template>
  <div class="min-h-screen bg-background text-foreground selection:bg-primary/25 selection:text-white">
    <Header
      :active-tab="activeTab"
      :connected="connected"
      @update:active-tab="activeTab = $event"
      @new-task="taskModalOpen = true"
      @open-settings="settingsModalOpen = true"
    />

    <div class="lg:pl-[268px]">
      <main class="mx-auto min-h-screen w-full max-w-[1560px] px-4 pb-10 pt-6 sm:px-6 lg:px-10 lg:pb-14 lg:pt-9 xl:px-12">
        <div class="mb-7 flex items-end justify-between gap-4 lg:mb-9">
          <div>
            <p class="eyebrow">{{ pageMeta.eyebrow }}</p>
            <h2 class="mt-2 text-2xl font-semibold tracking-[-0.035em] text-white sm:text-[28px]">{{ pageMeta.title }}</h2>
            <p class="mt-2 max-w-xl text-xs leading-relaxed text-slate-500 sm:text-[13px]">{{ pageMeta.description }}</p>
          </div>
          <div class="hidden items-center gap-2 rounded-full border border-white/[0.06] bg-white/[0.025] px-3 py-1.5 text-[10px] text-slate-500 sm:flex">
            <span class="h-1.5 w-1.5 rounded-full" :class="connected ? 'bg-emerald-400' : 'bg-rose-400'" />
            {{ connected ? '实时数据已连接' : '正在重新连接' }}
          </div>
        </div>
        <div :key="activeTab" class="animate-in fade-in slide-in-from-bottom-1 duration-200">
            <MonitorTab
              v-if="activeTab === 'monitor'"
              :task="taskState"
              :logs="logs"
              @open-task-modal="taskModalOpen = true"
              @stop-task="handleStopTask"
            />
            <SearchTab v-else-if="activeTab === 'search'" />
            <PlaylistTab v-else-if="activeTab === 'playlists'" />
            <LibraryTab v-else-if="activeTab === 'library'" />
            <HistoryTab v-else-if="activeTab === 'history'" />
          </div>

        <footer class="mt-10 border-t border-white/[0.05] pt-5 text-[10px] text-slate-700">
          TRIM Music Hub · fnOS local music operations
        </footer>
      </main>
    </div>

    <NewTaskModal
      :open="taskModalOpen"
      @close="taskModalOpen = false"
      @started="activeTab = 'monitor'"
    />
    <SettingsModal
      :open="settingsModalOpen"
      :is-first-install="isFirstInstall"
      @close="settingsModalOpen = false; isFirstInstall = false;"
    />
    <Toast />
  </div>
</template>
