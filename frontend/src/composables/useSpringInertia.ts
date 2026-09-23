import { ref, onMounted, onUnmounted, nextTick, type Ref } from 'vue';

export interface SpringInertiaOptions {
  /** 外部传入获取当前激活项索引的函数 */
  getActiveIndex: () => number;
  /** 是否在初始化后立即定位，不执行初始动效 */
  immediateOnInit?: boolean;
  /** 样式更新自定义回调 (默认直接修改 sliderRef 的 transform 与 width) */
  onApplyStyle?: (x: number, width: number, scaleX: number) => void;
}

interface RectCache {
  x: number;
  width: number;
}

interface SpringMotionState {
  startX: number;
  targetX: number;
  startW: number;
  targetW: number;
  startV: number;
  steps: number;
  omega0: number;
  zeta: number;
  omegaD: number;
  gamma: number;
  dir: number;
  durationSec: number;
  startTime: number;
}

export function useSpringInertia(
  containerRef: Ref<HTMLElement | null>,
  sliderRef: Ref<HTMLElement | null>,
  itemRefs: Ref<HTMLElement[]>,
  options: SpringInertiaOptions
) {
  const isReady = ref(false);

  // 物理弹簧模型状态 (供外部读取或诊断)
  const spring = {
    x: 0,
    width: 0,
    vx: 0,
    vw: 0,
    scaleX: 1.0,
  };

  let cachedRects: RectCache[] = [];
  let lastAppliedWidth = -1;
  let lastContainerWidth = -1;

  // 动画状态管理 (支持 Web Animations API 硬件合成层 + RAF 精确回退)
  let activeAnimation: Animation | null = null;
  let rafId: number | null = null;
  let currentMotion: SpringMotionState | null = null;

  function measureRects() {
    if (!containerRef.value || !itemRefs.value.length) return;
    cachedRects = itemRefs.value.map(el => {
      if (!el) return { x: 0, width: 0 };
      return {
        x: el.offsetLeft,
        width: el.offsetWidth,
      };
    });
  }

  function defaultApplyStyle(x: number, width: number, scaleX: number) {
    const el = sliderRef.value;
    if (!el) return;
    if (Math.abs(width - lastAppliedWidth) >= 0.5) {
      el.style.width = `${width.toFixed(1)}px`;
      lastAppliedWidth = width;
    }
    el.style.transform = `translate3d(${x.toFixed(2)}px, 0, 0) scaleX(${scaleX.toFixed(4)})`;
  }

  function applyStyle(x: number, width: number, scaleX: number) {
    spring.x = x;
    spring.width = width;
    spring.scaleX = scaleX;
    if (options.onApplyStyle) {
      options.onApplyStyle(x, width, scaleX);
    } else {
      defaultApplyStyle(x, width, scaleX);
    }
  }

  /**
   * 计算指定相对流逝时间 t (秒) 下的解析解位置、速度与形变因子
   * 基于闭式解析解 (Closed-Form Analytical Solution)，100% 免疫帧率抖动与微卡顿
   */
  function evaluateMotion(m: SpringMotionState, tSec: number) {
    const t = Math.max(0, Math.min(tSec, m.durationSec));
    const D = m.targetX - m.startX;
    const x0 = -D;
    const v0 = m.startV;

    const env = Math.exp(-m.gamma * t);
    const cos = Math.cos(m.omegaD * t);
    const sin = Math.sin(m.omegaD * t);

    // X 轴欠阻尼解析解
    const x = m.targetX + env * (x0 * cos + ((v0 + m.gamma * x0) / m.omegaD) * sin);
    const vx = env * (v0 * cos - ((m.omega0 * m.omega0 * x0 + m.gamma * v0) / m.omegaD) * sin);

    // 宽度解析解 (若宽度相同则恒为 targetW)
    let w = m.targetW;
    if (Math.abs(m.startW - m.targetW) >= 0.5) {
      const w0 = m.startW - m.targetW;
      w = m.targetW + env * (w0 * cos + ((m.gamma * w0) / m.omegaD) * sin);
    }

    // 连续光滑 C-infinity 惯性拉伸与压缩 (Squash & Stretch):
    // 运动方向上速度峰值时柔和拉伸，过冲拐点 (v=0) 处精确为 1.0 (绝无突变)，慢回弹反向期间呈微粘滞压缩
    const signedV = vx * m.dir;
    const stretchCap = 0.12 * (Math.abs(D) / (Math.abs(D) + 70));
    const deform = (signedV / (m.omega0 * Math.max(Math.abs(D), 60))) * stretchCap * 2.6;
    const scaleX = 1 + Math.max(-0.025, Math.min(0.09, deform));

    return { x, vx, w, scaleX };
  }

  /**
   * 中断当前正在进行中的动画，并提取当前精确物理状态 (x, vx, w)
   */
  function interruptCurrentMotion(): { x: number; vx: number; w: number } {
    if (activeAnimation) {
      const elapsedSec = ((activeAnimation.currentTime as number) || 0) / 1000;
      let state = { x: spring.x, vx: spring.vx, w: spring.width };
      if (currentMotion) {
        state = evaluateMotion(currentMotion, elapsedSec);
      }
      try {
        activeAnimation.cancel();
      } catch {}
      activeAnimation = null;
      currentMotion = null;
      return state;
    }
    if (rafId !== null) {
      cancelAnimationFrame(rafId);
      rafId = null;
      let state = { x: spring.x, vx: spring.vx, w: spring.width };
      if (currentMotion) {
        const elapsedSec = (performance.now() - currentMotion.startTime) / 1000;
        state = evaluateMotion(currentMotion, elapsedSec);
      }
      currentMotion = null;
      return state;
    }
    return { x: spring.x, vx: 0, w: spring.width };
  }

  function startSpring(targetX: number, targetWidth: number, steps: number) {
    const currentState = interruptCurrentMotion();
    const startX = currentState.x;
    const startW = currentState.w > 0 ? currentState.w : targetWidth;
    const startV = currentState.vx;

    // 若位置与宽度均已就位且无初速度，直接完成
    if (Math.abs(startX - targetX) < 0.3 && Math.abs(startW - targetWidth) < 0.5 && Math.abs(startV) < 2) {
      applyStyle(targetX, targetWidth, 1.0);
      return;
    }

    const D = targetX - startX;
    const dir = D >= 0 ? 1 : -1;

    // 欠阻尼物理系统参数配置 (适配跨步长初始冲量与恢复力)
    const omega0 = steps <= 1 ? 22.5 : steps === 2 ? 20.5 : 19.0;
    const zeta = 0.77; // 欠阻尼谐振子 (~2.5% 自然有机过冲)
    const omegaD = omega0 * Math.sqrt(1 - zeta * zeta);
    const gamma = zeta * omega0;

    // 阻尼包络收敛至 < 0.5% 的自然时长
    const durationSec = Math.max(0.28, Math.min(0.42, 5.2 / gamma));

    const motionState: SpringMotionState = {
      startX,
      targetX,
      startW,
      targetW: targetWidth,
      startV,
      steps,
      omega0,
      zeta,
      omegaD,
      gamma,
      dir,
      durationSec,
      startTime: performance.now(),
    };
    currentMotion = motionState;

    const el = sliderRef.value;
    const canUseWaapi = el && typeof el.animate === 'function' && !options.onApplyStyle;

    if (canUseWaapi) {
      // 硬件合成层优化：通过 Web Animations API 直接交由浏览器 GPU 渲染线程运行
      // 彻底消除主线程 Vue 响应式处理与视图切换带来的任何掉帧
      const SAMPLES = 36;
      const keyframes: Keyframe[] = [];

      for (let i = 0; i <= SAMPLES; i++) {
        const progress = i / SAMPLES;
        const tSec = progress * durationSec;
        const { x, w, scaleX } = evaluateMotion(motionState, tSec);
        const kf: Keyframe = {
          offset: progress,
          transform: `translate3d(${x.toFixed(2)}px, 0, 0) scaleX(${scaleX.toFixed(4)})`,
        };
        if (Math.abs(startW - targetWidth) >= 0.5) {
          kf.width = `${w.toFixed(1)}px`;
        }
        keyframes.push(kf);
      }

      // 保证最后一帧精确对齐目标
      keyframes[keyframes.length - 1] = {
        offset: 1,
        transform: `translate3d(${targetX.toFixed(2)}px, 0, 0) scaleX(1.0000)`,
        ...(Math.abs(startW - targetWidth) >= 0.5 ? { width: `${targetWidth.toFixed(1)}px` } : {}),
      };

      try {
        const anim = el.animate(keyframes, {
          duration: Math.round(durationSec * 1000),
          easing: 'linear',
          fill: 'forwards',
        });

        activeAnimation = anim;

        anim.onfinish = () => {
          if (activeAnimation === anim) {
            applyStyle(targetX, targetWidth, 1.0);
            activeAnimation = null;
            currentMotion = null;
            try {
              anim.cancel();
            } catch {}
          }
        };
        return;
      } catch {
        // 若环境不支持或异常则自动回退至高精度解析 RAF
      }
    }

    // 回退路径：高精度闭式解析 RAF (无累计欧拉误差，每帧依真实时钟采样)
    function frame(now: number) {
      if (!currentMotion) return;
      const elapsedSec = (now - currentMotion.startTime) / 1000;
      if (elapsedSec >= currentMotion.durationSec) {
        applyStyle(currentMotion.targetX, currentMotion.targetW, 1.0);
        rafId = null;
        currentMotion = null;
        return;
      }

      const { x, vx, w, scaleX } = evaluateMotion(currentMotion, elapsedSec);
      spring.vx = vx;
      applyStyle(x, w, scaleX);

      rafId = requestAnimationFrame(frame);
    }

    rafId = requestAnimationFrame(frame);
  }

  function updateIndicator(immediate = false, customSteps?: number, explicitIndex?: number) {
    const activeIdx = explicitIndex !== undefined ? explicitIndex : options.getActiveIndex();
    if (activeIdx === -1) return;

    const el = itemRefs.value[activeIdx];
    if (!el || !containerRef.value) return;

    let rect = cachedRects[activeIdx];
    if (!rect || rect.width <= 0 || immediate) {
      measureRects();
      rect = cachedRects[activeIdx];
    }

    const targetX = rect && rect.width > 0 ? rect.x : el.offsetLeft;
    const targetWidth = rect && rect.width > 0 ? rect.width : el.offsetWidth;

    // 若容器处于 v-show 隐藏状态 (width === 0)，暂不更新，待容器显现时由 ResizeObserver 激活
    if (targetWidth <= 0) return;

    if (immediate || !isReady.value) {
      interruptCurrentMotion();
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
      measureRects();
      updateIndicator(true);
      if (containerRef.value && typeof ResizeObserver !== 'undefined') {
        resizeObserver = new ResizeObserver((entries) => {
          const entry = entries[0];
          const newWidth = entry?.contentRect?.width ?? 0;
          // 若容器处于 v-show 隐藏 (width === 0)，坚决不触碰 DOM，杜绝切换 Tab 时的强制回流
          if (newWidth <= 0) return;

          // 仅在宽度发生实质变化 (如窗口缩放、横竖屏切换) 时重新测量定位
          if (Math.abs(newWidth - lastContainerWidth) >= 1) {
            lastContainerWidth = newWidth;
            measureRects();
            updateIndicator(true);
          }
        });
        resizeObserver.observe(containerRef.value);
      }
    });
  });

  onUnmounted(() => {
    interruptCurrentMotion();
    if (resizeObserver) resizeObserver.disconnect();
  });

  return {
    isReady,
    updateIndicator,
    measureRects,
    spring,
  };
}
