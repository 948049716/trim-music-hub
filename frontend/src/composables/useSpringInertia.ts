import { ref, watch, onMounted, onUnmounted, nextTick, type Ref } from 'vue';

export interface SpringInertiaOptions {
  /** 外部传入获取当前激活项索引的函数 */
  getActiveIndex: () => number;
  /** 是否在初始化后立即定位，不执行初始动效 */
  immediateOnInit?: boolean;
  /** 样式更新自定义回调 (默认直接修改 sliderRef 的 transform 与 width) */
  onApplyStyle?: (x: number, width: number, scaleX: number) => void;
}

export function useSpringInertia(
  containerRef: Ref<HTMLElement | null>,
  sliderRef: Ref<HTMLElement | null>,
  itemRefs: Ref<HTMLElement[]>,
  options: SpringInertiaOptions
) {
  const isReady = ref(false);

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

  function defaultApplyStyle(x: number, width: number, scaleX: number) {
    if (!sliderRef.value) return;
    sliderRef.value.style.width = `${width}px`;
    sliderRef.value.style.transform = `translate3d(${x}px, 0, 0) scaleX(${scaleX})`;
  }

  function applyStyle(x: number, width: number, scaleX: number) {
    if (options.onApplyStyle) {
      options.onApplyStyle(x, width, scaleX);
    } else {
      defaultApplyStyle(x, width, scaleX);
    }
  }

  function startSpring(targetX: number, targetWidth: number, steps: number) {
    if (animId) cancelAnimationFrame(animId);
    lastTime = performance.now();

    const dir = targetX >= spring.x ? 1 : -1;

    // 核心物理规律：
    // 跨越步长越长 (steps >= 2, 3, 4)，恢复力与加速度越大，初始冲量高，
    // 在到达终点时因惯性冲出指定位置更明显；过冲后切换高粘滞阻尼进行慢回弹。
    const k = steps <= 1 ? 320 : steps === 2 ? 270 : 220;
    const cForward = steps <= 1 ? 22 : steps === 2 ? 18 : 15;
    const cRebound = 28;

    let overshot = false;

    function frame(now: number) {
      const dt = Math.min((now - lastTime) / 1000, 0.033);
      lastTime = now;

      const isPast = (spring.x - targetX) * dir > 0;
      if (isPast) overshot = true;

      const c = overshot ? cRebound : cForward;

      // X 轴动力学微分方程: F = -k*(x - target) - c*v
      const fSpringX = -k * (spring.x - targetX);
      const fDampingX = -c * spring.vx;
      const ax = fSpringX + fDampingX;

      spring.vx += ax * dt;
      spring.x += spring.vx * dt;

      // 宽度动力学 (临界阻尼，跟随宽度平滑过度)
      const fSpringW = -340 * (spring.width - targetWidth);
      const fDampingW = -32 * spring.vw;
      const aw = fSpringW + fDampingW;

      spring.vw += aw * dt;
      spring.width += spring.vw * dt;

      // 物理惯性拉伸与微压缩 (Squash & Stretch)
      const stretch = Math.min(0.14, Math.abs(spring.vx) / 1900);
      const overshootDist = overshot ? Math.abs(spring.x - targetX) : 0;
      const compression = Math.min(0.05, overshootDist / 120);
      spring.scaleX = overshot ? (1 - compression) : (1 + stretch);

      applyStyle(spring.x, spring.width, spring.scaleX);

      // 收敛判定
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

  function updateIndicator(immediate = false, customSteps?: number) {
    const activeIdx = options.getActiveIndex();
    if (activeIdx === -1) return;

    const el = itemRefs.value[activeIdx];
    if (!el || !containerRef.value) return;

    const targetX = el.offsetLeft;
    const targetWidth = el.offsetWidth;

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

  let resizeObserver: ResizeObserver | null = null;

  onMounted(() => {
    nextTick(() => {
      updateIndicator(true);
      if (containerRef.value && typeof ResizeObserver !== 'undefined') {
        resizeObserver = new ResizeObserver(() => {
          updateIndicator(true);
        });
        resizeObserver.observe(containerRef.value);
      }
    });
  });

  onUnmounted(() => {
    if (animId) cancelAnimationFrame(animId);
    if (resizeObserver) resizeObserver.disconnect();
  });

  return {
    isReady,
    updateIndicator,
    spring,
  };
}
