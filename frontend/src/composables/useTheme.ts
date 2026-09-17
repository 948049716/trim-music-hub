import { computed, ref } from 'vue';

export type ThemeMode = 'system' | 'light' | 'dark';

const STORAGE_KEY = 'trim-music-theme';
const mode = ref<ThemeMode>('system');
const resolvedTheme = ref<'light' | 'dark'>('light');
let initialized = false;
let mediaQuery: MediaQueryList | null = null;

function resolveTheme() {
  const next = mode.value === 'system'
    ? (mediaQuery?.matches ? 'dark' : 'light')
    : mode.value;
  resolvedTheme.value = next;
  document.documentElement.classList.toggle('dark', next === 'dark');
  document.documentElement.dataset.theme = next;
}

function initTheme() {
  if (initialized || typeof window === 'undefined') return;
  initialized = true;
  mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
  const saved = window.localStorage.getItem(STORAGE_KEY) as ThemeMode | null;
  if (saved === 'system' || saved === 'light' || saved === 'dark') mode.value = saved;
  mediaQuery.addEventListener('change', resolveTheme);
  resolveTheme();
}

function setTheme(next: ThemeMode) {
  mode.value = next;
  window.localStorage.setItem(STORAGE_KEY, next);
  resolveTheme();
}

function cycleTheme() {
  const order: ThemeMode[] = ['system', 'light', 'dark'];
  setTheme(order[(order.indexOf(mode.value) + 1) % order.length]);
}

export function useTheme() {
  initTheme();
  return {
    mode,
    resolvedTheme,
    modeLabel: computed(() => ({ system: '跟随系统', light: '浅色模式', dark: '深色模式' }[mode.value])),
    setTheme,
    cycleTheme,
  };
}
