import { ref } from 'vue';

export interface ToastItem {
  id: number;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error';
}

export const toasts = ref<ToastItem[]>([]);

export function showToast(message: string, type: 'info' | 'success' | 'warning' | 'error' = 'info', duration = 3000) {
  const id = Date.now() + Math.random();
  toasts.value.push({ id, message, type });
  setTimeout(() => {
    toasts.value = toasts.value.filter(t => t.id !== id);
  }, duration);
}
