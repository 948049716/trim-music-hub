<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue';
import { Activity, Search, ListMusic, Database, History } from 'lucide-vue-next';

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
const isReady = ref(false);

function setButtonRef(el: any, idx: number) {
  if (el) buttonRefs.value[idx] = el as HTMLElement;
}

// 物理弹簧模型状态 (Underdamped Harmonic Oscillator with Viscoelastic Rebound)
const spring = {
  x: 0,
  width: 0,
  vx: 0,
  vw: 0,
  scaleX: 1.0,
};

let animId: number | null = null;
let lastTime = 0;

function applyStyle(x: number, width: number, scaleX: number) {
  if (!sliderRef.value) return;
  sliderRef.value.style.width = `${width}px`;
  sliderRef.value.style.transform = `translate3d(${x}px, 0, 0) scaleX(${scaleX})`;
}

function startSpring(targetX: number, targetWidth: number, steps: number) {
  if (animId) cancelAnimationFrame(animId);
  lastTime = performance.now();

  const dir = targetX >= spring.x ? 1 : -1;

  // 根据跨越距离自适应物理参数：
  // 步长越大 (steps = 3, 4)，初始恢复力越强，加速度越大，飞驰冲量越高，并在终点形成更明显的微过冲与更慢的回弹沉降
  // 步长较小 (steps = 1)，动作紧凑干脆，轻微过冲 (~3px) 快速回位
  const k = steps <= 1 ? 300 : steps === 2 ? 260 : 215;
  const cForward = steps <= 1 ? 21 : steps === 2 ? 18 : 15;
  // 回弹阻尼较大：过冲后吸收动能，产生“略微超过指定位置慢回弹”的细腻粘滞阻尼感
  const cRebound = 28;

  let overshot = false;

  function frame(now: number) {
    const dt = Math.min((now - lastTime) / 1000, 0.033);
    lastTime = now;

    const isPast = (spring.x - targetX) * dir > 0;
    if (isPast) overshot = true;

    // 过冲阶段切换至慢回弹高阻尼，飞行阶段保持低阻尼高加速度
    const c = overshot ? cRebound : cForward;

    // X 轴动力学微分方程: F = -k*(x - target) - c*v
    const fSpringX = -k * (spring.x - targetX);
    const fDampingX = -c * spring.vx;
    const ax = fSpringX + fDampingX;

    spring.vx += ax * dt;
    spring.x += spring.vx * dt;

    // 宽度微调动力学 (临界阻尼，跟随尺寸变化)
    const fSpringW = -340 * (spring.width - targetWidth);
    const fDampingW = -32 * spring.vw;
    const aw = fSpringW + fDampingW;

    spring.vw += aw * dt;
    spring.width += spring.vw * dt;

    // 物理惯性拉伸与挤压形变 (Squash & Stretch)
    // 飞行高速期沿 X 轴自然拉伸，过冲缓冲点微缩，沉降恢复 1.0
    const stretch = Math.min(0.14, Math.abs(spring.vx) / 1900);
    const overshootDist = overshot ? Math.abs(spring.x - targetX) : 0;
    const compression = Math.min(0.05, overshootDist / 120);
    spring.scaleX = overshot ? (1 - compression) : (1 + stretch);

    applyStyle(spring.x, spring.width, spring.scaleX);

    // 判定收敛稳定
    const isSettledX = Math.abs(spring.x - targetX) < 0.2 && Math.abs(spring.vx) < 1.0;
    const isSettledW = Math.abs(spring.width - targetWidth) < 0.2 && Math.abs(spring.vw) < 1.0;

    if (isSettledX && isSettledW) {
      spring.x = targetX;
      spring.width = targetWidth;
      spring.vx = 0;
      spring.vw = 0;
      spring.scaleX = 1.0;
      applyStyle(targetX, targetWidth, 1.0);
      animId = null;
      return;
    }

    animId = requestAnimationFrame(frame);
  }

  animId = requestAnimationFrame(frame);
}

function updateTabIndicator(immediate = false, customSteps?: number) {
  const currentIdx = navigation.findIndex(item => item.value === props.activeTab);
  if (currentIdx === -1) return;

  const btn = buttonRefs.value[currentIdx];
  if (!btn || !navBarRef.value) return;

  const targetX = btn.offsetLeft;
  const targetWidth = btn.offsetWidth;

  if (immediate) {
    if (animId) cancelAnimationFrame(animId);
    spring.x = targetX;
    spring.width = targetWidth;
    spring.vx = 0;
    spring.vw = 0;
    spring.scaleX = 1.0;
    applyStyle(targetX, targetWidth, 1.0);
    isReady.value = true;
    return;
  }

  const steps = customSteps ?? 1;
  startSpring(targetX, targetWidth, steps);
}

function handleTabClick(val: TabKey, newIdx: number) {
  if (val === props.activeTab) return;
  const oldIdx = navigation.findIndex(item => item.value === props.activeTab);
  const steps = Math.abs(newIdx - (oldIdx !== -1 ? oldIdx : newIdx)) || 1;
  emit('update:activeTab', val);
  nextTick(() => {
    updateTabIndicator(false, steps);
  });
}

// 监听外界引起的 Tab 变更 (例如快捷任务跳转)
watch(() => props.activeTab, (newVal, oldVal) => {
  const oldIdx = oldVal ? navigation.findIndex(item => item.value === oldVal) : -1;
  const newIdx = navigation.findIndex(item => item.value === newVal);
  if (newIdx !== -1) {
    const steps = Math.abs(newIdx - (oldIdx !== -1 ? oldIdx : newIdx)) || 1;
    nextTick(() => {
      updateTabIndicator(false, steps);
    });
  }
});

let resizeObserver: ResizeObserver | null = null;

onMounted(() => {
  nextTick(() => {
    updateTabIndicator(true);
    if (navBarRef.value && typeof ResizeObserver !== 'undefined') {
      resizeObserver = new ResizeObserver(() => {
        updateTabIndicator(true);
      });
      resizeObserver.observe(navBarRef.value);
    }
  });
});

onUnmounted(() => {
  if (animId) cancelAnimationFrame(animId);
  if (resizeObserver) resizeObserver.disconnect();
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
      <div class="mobile-tab-slider__pill">
        <span class="mobile-tab-slider__accent" />
      </div>
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
