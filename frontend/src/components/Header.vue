<script setup lang="ts">
import { Activity, Search, ListMusic, Database, History, Radio, Plus, Wifi, WifiOff, Settings, Sun, Moon, UserRound } from 'lucide-vue-next';
import { Button } from '@/components/ui/button';
import { useTheme } from '@/composables/useTheme';

type TabKey = 'monitor' | 'search' | 'playlists' | 'library' | 'history';

defineProps<{ activeTab: TabKey; connected: boolean }>();
const emit = defineEmits<{
  (e: 'update:activeTab', val: TabKey): void;
  (e: 'new-task'): void;
  (e: 'open-settings'): void;
  (e: 'open-accounts'): void;
}>();

const { resolvedTheme, setTheme } = useTheme();

function toggleTheme() {
  setTheme(resolvedTheme.value === 'dark' ? 'light' : 'dark');
}
const navigation = [
  { value: 'monitor' as const, label: '任务', fullLabel: '同步任务', hint: '进度与状态', icon: Activity },
  { value: 'search' as const, label: '搜歌', fullLabel: '搜索歌曲', hint: '发现并下载', icon: Search },
  { value: 'playlists' as const, label: '歌单', fullLabel: '飞牛歌单', hint: '整理与分配', icon: ListMusic },
  { value: 'library' as const, label: '曲库', fullLabel: '本地曲库', hint: '检索与清理', icon: Database },
  { value: 'history' as const, label: '记录', fullLabel: '操作记录', hint: '查看历史', icon: History },
];
</script>

<template>
  <aside class="fixed inset-y-0 left-0 z-40 hidden w-[248px] flex-col border-r border-border/80 bg-[hsl(var(--sidebar)/.94)] px-4 py-5 backdrop-blur-xl lg:flex">
    <div class="flex items-center gap-3 px-2">
      <div class="brand-mark"><Radio class="h-5 w-5" /></div>
      <div class="min-w-0">
        <h1 class="truncate text-[15px] font-bold tracking-[-0.02em] text-foreground">TRIM Music</h1>
        <p class="mt-0.5 text-[11px] text-muted-foreground">你的飞牛音乐控制台</p>
      </div>
    </div>

    <nav class="mt-8 space-y-1" aria-label="主要导航">
      <Button variant="ghost" v-for="item in navigation" :key="item.value" type="button"
        class="group flex h-auto w-full items-center justify-start gap-3 whitespace-normal rounded-xl px-3 py-2.5 text-left transition-colors focus-visible:ring-2 focus-visible:ring-ring/60"
        :class="activeTab === item.value ? 'bg-card text-foreground shadow-sm ring-1 ring-border/80' : 'text-muted-foreground hover:bg-card/60 hover:text-foreground'"
        @click="emit('update:activeTab', item.value)">
        <span class="grid h-9 w-9 shrink-0 place-items-center rounded-[11px] transition-colors"
          :class="activeTab === item.value ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground group-hover:text-foreground'">
          <component :is="item.icon" class="h-4 w-4" />
        </span>
        <span class="min-w-0 flex-1">
          <span class="block text-[13px] font-semibold">{{ item.fullLabel }}</span>
          <span class="mt-0.5 block text-[10px] text-muted-foreground">{{ item.hint }}</span>
        </span>
      </Button>
    </nav>

    <div class="mt-auto space-y-3">
      <Button variant="brand" size="lg" class="w-full justify-center" @click="emit('new-task')">
        <Plus class="h-4 w-4" />导入歌单
      </Button>
      <Button variant="outline" class="w-full justify-center" @click="emit('open-accounts')">
        <UserRound class="h-4 w-4" />音乐账号
      </Button>
      <div class="grid grid-cols-2 gap-2">
        <Button variant="outline" class="justify-start px-3" @click="emit('open-settings')"><Settings class="h-4 w-4" />设置</Button>
        <Button variant="outline" class="justify-start px-3" :title="resolvedTheme === 'dark' ? '切换到浅色模式' : '切换到深色模式'" @click="toggleTheme">
          <Sun v-if="resolvedTheme === 'dark'" class="h-4 w-4" />
          <Moon v-else class="h-4 w-4" />
          主题
        </Button>
      </div>
      <div class="flex items-center gap-3 rounded-xl border border-border/80 bg-card/65 px-3 py-3">
        <span class="grid h-8 w-8 place-items-center rounded-lg" :class="connected ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400' : 'bg-destructive/10 text-destructive'">
          <Wifi v-if="connected" class="h-4 w-4" /><WifiOff v-else class="h-4 w-4" />
        </span>
        <div class="min-w-0">
          <p class="text-[11px] font-semibold text-foreground">{{ connected ? '服务运行正常' : '正在重新连接' }}</p>
          <p class="mt-0.5 text-[10px] text-muted-foreground">{{ connected ? '任务状态会实时更新' : '请检查 NAS 服务' }}</p>
        </div>
      </div>
    </div>
  </aside>

  <header class="sticky top-0 z-40 border-b border-border/75 bg-background/85 backdrop-blur-xl lg:hidden">
    <div class="flex h-14 items-center justify-between gap-2 px-3.5">
      <!-- 品牌与连接状态 -->
      <div class="flex min-w-0 items-center gap-2">
        <div class="brand-mark !h-8 !w-8"><Radio class="h-3.5 w-3.5" /></div>
        <div class="min-w-0">
          <div class="flex items-center gap-1.5">
            <h1 class="truncate text-[13.5px] font-bold tracking-tight text-foreground">TRIM Music</h1>
            <span
              class="inline-block h-1.5 w-1.5 shrink-0 rounded-full"
              :class="connected ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.7)]' : 'bg-destructive shadow-[0_0_8px_rgba(239,68,68,0.7)]'"
            />
          </div>
          <p class="truncate text-[9.5px] text-muted-foreground">{{ connected ? '飞牛曲库就绪' : '连接中断' }}</p>
        </div>
      </div>

      <!-- 操作按钮群（符合人体工学触摸区域与层级） -->
      <div class="flex items-center gap-1">
        <Button
          variant="ghost"
          size="icon"
          class="h-9 w-9 rounded-full text-muted-foreground transition-transform active:scale-90 hover:text-foreground"
          :aria-label="resolvedTheme === 'dark' ? '切换到浅色模式' : '切换到深色模式'"
          @click="toggleTheme"
        >
          <Sun v-if="resolvedTheme === 'dark'" class="h-4 w-4" />
          <Moon v-else class="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          class="h-9 w-9 rounded-full text-muted-foreground transition-transform active:scale-90 hover:text-foreground"
          aria-label="管理音乐账号"
          @click="emit('open-accounts')"
        >
          <UserRound class="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          class="h-9 w-9 rounded-full text-muted-foreground transition-transform active:scale-90 hover:text-foreground"
          aria-label="打开设置"
          @click="emit('open-settings')"
        >
          <Settings class="h-4 w-4" />
        </Button>
        <Button
          variant="brand"
          size="sm"
          class="h-8 gap-1 rounded-full px-2.5 text-xs font-semibold shadow-sm transition-transform active:scale-95"
          aria-label="导入歌单"
          @click="emit('new-task')"
        >
          <Plus class="h-3.5 w-3.5" />
          <span>导入</span>
        </Button>
      </div>
    </div>
  </header>

  <nav class="mobile-tab-bar fixed z-50 grid grid-cols-5 lg:hidden" aria-label="移动端导航">
    <Button
      variant="ghost"
      v-for="item in navigation"
      :key="item.value"
      type="button"
      class="mobile-tab-item h-auto"
      :class="{ 'mobile-tab-item--active': activeTab === item.value }"
      :aria-current="activeTab === item.value ? 'page' : undefined"
      @click="emit('update:activeTab', item.value)"
    >
      <span class="mobile-tab-icon">
        <component :is="item.icon" class="h-[19px] w-[19px]" />
      </span>
      <span class="mobile-tab-label">{{ item.label }}</span>
    </Button>
  </nav>
</template>
