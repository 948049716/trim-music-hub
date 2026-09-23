<script setup lang="ts">
import { ref, watch } from 'vue';
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
  { value: 'search', label: '导歌', icon: Search },
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

// 维护本地即时响应状态，实现触控点击瞬间 0ms 视觉更新反馈
const localActiveTab = ref<TabKey>(props.activeTab);

watch(() => props.activeTab, (val) => {
  localActiveTab.value = val;
});

const { isReady, updateIndicator } = useSpringInertia(
  navBarRef,
  sliderRef,
  buttonRefs,
  {
    getActiveIndex: () => navigation.findIndex(item => item.value === localActiveTab.value),
  }
);

let internalTargetVal: TabKey | null = null;

function handleTabClick(val: TabKey, newIdx: number) {
  if (val === localActiveTab.value) return;
  const oldIdx = navigation.findIndex(item => item.value === localActiveTab.value);
  const steps = Math.abs(newIdx - (oldIdx !== -1 ? oldIdx : newIdx)) || 1;
  internalTargetVal = val;
  localActiveTab.value = val;

  // 零延迟响应：立即启动物理弹簧滑块
  updateIndicator(false, steps, newIdx);
  emit('update:activeTab', val);
}

// 仅在外部程序化改变 activeTab 时触发动画（避免点击时重复计算触发）
watch(() => props.activeTab, (newVal, oldVal) => {
  if (internalTargetVal === newVal) {
    internalTargetVal = null;
    return;
  }
  internalTargetVal = null;
  const oldIdx = oldVal ? navigation.findIndex(item => item.value === oldVal) : -1;
  const newIdx = navigation.findIndex(item => item.value === newVal);
  if (newIdx !== -1) {
    const steps = Math.abs(newIdx - (oldIdx !== -1 ? oldIdx : newIdx)) || 1;
    updateIndicator(false, steps, newIdx);
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
      :class="{ 'mobile-tab-item--active': localActiveTab === item.value }"
      :aria-current="localActiveTab === item.value ? 'page' : undefined"
      @click="handleTabClick(item.value, idx)"
    >
      <span class="mobile-tab-icon-wrapper">
        <component :is="item.icon" />
      </span>
      <span class="mobile-tab-label">{{ item.label }}</span>
    </button>
  </nav>
</template>
