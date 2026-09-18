<script setup lang="ts">
import { ref, watch, nextTick } from 'vue';
import { Activity, Search, ListMusic, Database, History } from 'lucide-vue-next';
import { useSpringInertia } from '@/composables/useSpringInertia';

export type TabKey = 'monitor' | 'search' | 'playlists' | 'library' | 'history';

interface NavItem {
  value: TabKey;
  label: string;
  icon: any;
}

const props = defineProps<{
  activeTab: TabKey;
}>();

const emit = defineEmits<{
  (e: 'update:activeTab', val: TabKey): void;
}>();

const navigation: NavItem[] = [
  { value: 'monitor', label: '任务', icon: Activity },
  { value: 'search', label: '搜歌', icon: Search },
  { value: 'playlists', label: '歌单', icon: ListMusic },
  { value: 'library', label: '曲库', icon: Database },
  { value: 'history', label: '记录', icon: History },
];

const navBarRef = ref<HTMLElement | null>(null);
const sliderRef = ref<HTMLElement | null>(null);
const buttonRefs = ref<HTMLElement[]>([]);

function setButtonRef(el: any, idx: number) {
  if (el) buttonRefs.value[idx] = el as HTMLElement;
}

const { isReady, updateIndicator } = useSpringInertia(
  navBarRef,
  sliderRef,
  buttonRefs,
  {
    getActiveIndex: () => navigation.findIndex(item => item.value === props.activeTab),
  }
);

function handleTabClick(val: TabKey, newIdx: number) {
  if (val === props.activeTab) return;
  const oldIdx = navigation.findIndex(item => item.value === props.activeTab);
  const steps = Math.abs(newIdx - (oldIdx !== -1 ? oldIdx : newIdx)) || 1;
  emit('update:activeTab', val);
  nextTick(() => {
    updateIndicator(false, steps);
  });
}

watch(() => props.activeTab, (newVal, oldVal) => {
  const oldIdx = oldVal ? navigation.findIndex(item => item.value === oldVal) : -1;
  const newIdx = navigation.findIndex(item => item.value === newVal);
  if (newIdx !== -1) {
    const steps = Math.abs(newIdx - (oldIdx !== -1 ? oldIdx : newIdx)) || 1;
    nextTick(() => {
      updateIndicator(false, steps);
    });
  }
});
</script>

<template>
  <nav
    ref="navBarRef"
    class="mobile-tab-bar lg:hidden"
    aria-label="移动端导航"
  >
    <!-- 物理惯性滑块指示胶囊 (硬件加速层) -->
    <div
      ref="sliderRef"
      class="mobile-tab-slider"
      :class="{ 'mobile-tab-slider--ready': isReady }"
      aria-hidden="true"
    >
      <div class="mobile-tab-slider__pill" />
    </div>

    <!-- 导航按钮列表 -->
    <button
      v-for="(item, idx) in navigation"
      :key="item.value"
      :ref="(el) => setButtonRef(el, idx)"
      type="button"
      class="mobile-tab-item group"
      :class="{ 'mobile-tab-item--active': activeTab === item.value }"
      :aria-current="activeTab === item.value ? 'page' : undefined"
      @click="handleTabClick(item.value, idx)"
    >
      <span class="mobile-tab-icon-wrapper">
        <component :is="item.icon" />
      </span>
      <span class="mobile-tab-label">{{ item.label }}</span>
    </button>
  </nav>
</template>
