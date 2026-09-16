<script setup lang="ts">
import {
  Activity,
  Search,
  ListMusic,
  Database,
  History,
  Radio,
  Plus,
  Wifi,
  WifiOff,
  ChevronRight,
  Settings
} from "lucide-vue-next";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

type TabKey = "monitor" | "search" | "playlists" | "library" | "history";

defineProps<{
  activeTab: TabKey;
  connected: boolean;
}>();

const emit = defineEmits<{
  (e: "update:activeTab", val: TabKey): void;
  (e: "new-task"): void;
  (e: "open-settings"): void;
}>();

const navigation = [
  { value: "monitor" as const, label: "任务监控", hint: "实时流水线", icon: Activity },
  { value: "search" as const, label: "全网搜歌", hint: "发现与下载", icon: Search },
  { value: "playlists" as const, label: "飞牛歌单", hint: "歌单资产", icon: ListMusic },
  { value: "library" as const, label: "曲库检索", hint: "本地音乐库", icon: Database },
  { value: "history" as const, label: "下载历史", hint: "任务记录", icon: History },
];
</script>

<template>
  <aside class="hidden lg:flex fixed inset-y-0 left-0 z-40 w-[268px] flex-col border-r border-white/[0.065] bg-[#090d0d]/95 px-4 py-5 backdrop-blur-2xl">
    <div class="flex items-center gap-3 px-2">
      <div class="brand-mark">
        <Radio class="h-5 w-5" />
      </div>
      <div class="min-w-0">
        <div class="flex items-center gap-2">
          <h1 class="truncate text-sm font-semibold tracking-[-0.01em] text-white">TRIM Music</h1>
          <Badge variant="brand" class="px-1.5 py-0 text-[9px] tracking-[0.12em]">HUB</Badge>
        </div>
        <p class="mt-0.5 text-[11px] text-slate-500">fnOS 音乐工作台</p>
      </div>
    </div>

    <div class="mt-8 px-2 text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-600">Workspace</div>
    <nav class="mt-3 space-y-1.5" aria-label="主要导航">
      <Button
        v-for="item in navigation"
        :key="item.value"
        variant="ghost"
        size="lg"
        class="group h-auto w-full justify-start rounded-xl px-3 py-2.5 text-left"
        :class="activeTab === item.value
          ? 'bg-white/[0.075] text-white shadow-[inset_0_0_0_1px_rgba(255,255,255,0.055)] hover:bg-white/[0.09]'
          : 'text-slate-500 hover:bg-white/[0.035] hover:text-slate-200'"
        @click="emit('update:activeTab', item.value)"
      >
        <span
          class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border transition-colors"
          :class="activeTab === item.value
            ? 'border-primary/25 bg-primary/10 text-primary'
            : 'border-white/[0.055] bg-white/[0.025] text-slate-500 group-hover:text-slate-300'"
        >
          <component :is="item.icon" class="h-4 w-4" />
        </span>
        <span class="min-w-0 flex-1">
          <span class="block text-[13px] font-medium">{{ item.label }}</span>
          <span class="mt-0.5 block text-[10px] font-normal text-slate-600">{{ item.hint }}</span>
        </span>
        <ChevronRight
          class="h-3.5 w-3.5 transition-all"
          :class="activeTab === item.value ? 'translate-x-0 text-primary' : '-translate-x-1 opacity-0 group-hover:translate-x-0 group-hover:opacity-100'"
        />
      </Button>
    </nav>

    <div class="mt-auto space-y-3">
      <Button variant="brand" size="lg" class="w-full justify-center" @click="emit('new-task')">
        <Plus class="h-4 w-4" />
        新建同步任务
      </Button>

      <Button
        variant="outline"
        size="default"
        class="w-full justify-start gap-2 rounded-xl text-xs text-slate-300 border-white/[0.08] hover:bg-white/[0.05]"
        @click="emit('open-settings')"
      >
        <Settings class="h-4 w-4 text-brand-400" />
        <span>音源设置 (更换下载源)</span>
      </Button>

      <div class="rounded-2xl border border-white/[0.06] bg-white/[0.025] p-3.5">
        <div class="flex items-center gap-2.5">
          <span
            class="flex h-8 w-8 items-center justify-center rounded-lg"
            :class="connected ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'"
          >
            <Wifi v-if="connected" class="h-4 w-4" />
            <WifiOff v-else class="h-4 w-4" />
          </span>
          <div>
            <p class="text-[11px] font-medium text-slate-300">{{ connected ? '实时服务在线' : '实时服务离线' }}</p>
            <p class="mt-0.5 text-[10px] text-slate-600">SSE · Port 4175</p>
          </div>
          <span class="ml-auto h-2 w-2 rounded-full" :class="connected ? 'bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,.65)]' : 'bg-rose-400'" />
        </div>
      </div>
      <p class="px-2 text-[10px] leading-relaxed text-slate-700">TRIM Music Hub · NAS local workspace</p>
    </div>
  </aside>

  <header class="sticky top-0 z-40 border-b border-white/[0.065] bg-[#090d0d]/90 backdrop-blur-2xl lg:hidden">
    <div class="flex h-16 items-center justify-between px-4">
      <div class="flex items-center gap-2.5">
        <div class="brand-mark h-9 w-9 rounded-xl">
          <Radio class="h-4 w-4" />
        </div>
        <div>
          <h1 class="text-sm font-semibold text-white">TRIM Music</h1>
          <p class="text-[10px] text-slate-500">fnOS 音乐工作台</p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <span class="h-2 w-2 rounded-full" :class="connected ? 'bg-emerald-400' : 'bg-rose-400'" />
        <Button variant="ghost" size="icon" aria-label="音源设置" @click="emit('open-settings')">
          <Settings class="h-4 w-4 text-slate-300" />
        </Button>
        <Button variant="brand" size="icon" aria-label="新建同步任务" @click="emit('new-task')">
          <Plus class="h-4 w-4" />
        </Button>
      </div>
    </div>
    <nav class="flex gap-1 overflow-x-auto px-3 pb-3" aria-label="移动端导航">
      <Button
        v-for="item in navigation"
        :key="item.value"
        variant="ghost"
        size="sm"
        class="shrink-0 gap-1.5 rounded-lg px-3"
        :class="activeTab === item.value ? 'bg-primary/10 text-primary' : 'text-slate-500'"
        @click="emit('update:activeTab', item.value)"
      >
        <component :is="item.icon" class="h-3.5 w-3.5" />
        {{ item.label }}
      </Button>
    </nav>
  </header>
</template>
