<script setup lang="ts">
import { ref } from 'vue';
import type { CurrentUser } from '@/types';
import { api } from '@/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { ShieldCheck, User, Lock, Loader2, AlertCircle, Radio } from 'lucide-vue-next';

defineProps<{ open: boolean }>();
const emit = defineEmits<{ (e: 'logged-in', user: CurrentUser): void }>();

const username = ref('');
const password = ref('');
const loading = ref(false);
const errorMessage = ref('');

async function handleLogin() {
  const u = username.value.trim();
  const p = password.value;
  if (!u) {
    errorMessage.value = '请输入飞牛账号';
    return;
  }
  if (!p) {
    errorMessage.value = '请输入登录密码';
    return;
  }

  loading.value = true;
  errorMessage.value = '';

  try {
    const res = await api.login(u, p);
    if (res.ok && res.user) {
      emit('logged-in', res.user);
    } else {
      errorMessage.value = res.error || '飞牛账号或密码错误';
    }
  } catch (e: any) {
    errorMessage.value = e.message || '网络连接异常，请检查 NAS 状态';
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <Dialog :open="open">
    <DialogContent
      class="sm:max-w-[400px] p-0 overflow-hidden border border-border/80 bg-card/95 backdrop-blur-2xl shadow-2xl rounded-2xl"
      :hide-close="true"
      @pointer-down-outside.prevent
      @escape-key-down.prevent
    >
      <!-- 顶部品牌微光装饰 -->
      <div class="relative bg-gradient-to-b from-primary/15 via-primary/5 to-transparent px-6 pt-6 pb-4 border-b border-border/50 text-center">
        <div class="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/15 text-primary ring-1 ring-primary/25 shadow-[0_0_24px_hsl(var(--primary)/0.25)] mb-3">
          <Radio class="h-6 w-6 animate-pulse" />
        </div>
        <DialogTitle class="text-lg font-bold tracking-tight text-foreground">
          飞牛音乐控制台
        </DialogTitle>
        <DialogDescription class="mt-1 text-xs text-muted-foreground leading-relaxed max-w-[280px] mx-auto">
          请输入飞牛 NAS / 飞牛音乐的账号与密码进行登录
        </DialogDescription>
      </div>

      <!-- 登录表单内容 -->
      <form @submit.prevent="handleLogin" class="px-6 py-5 space-y-4">
        <!-- 错误提示 -->
        <div
          v-if="errorMessage"
          class="flex items-center gap-2.5 rounded-xl border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-xs text-destructive font-medium animate-in fade-in-50 duration-200"
        >
          <AlertCircle class="h-4 w-4 shrink-0" />
          <span>{{ errorMessage }}</span>
        </div>

        <div class="space-y-1.5">
          <label class="text-xs font-semibold text-muted-foreground flex items-center gap-1.5">
            <User class="h-3.5 w-3.5" />飞牛账号
          </label>
          <Input
            v-model="username"
            type="text"
            autocomplete="username"
            placeholder="如 948049716"
            :disabled="loading"
            class="h-10 text-sm bg-surface-inset border-border/75 focus:border-primary focus:ring-1 focus:ring-primary"
          />
        </div>

        <div class="space-y-1.5">
          <label class="text-xs font-semibold text-muted-foreground flex items-center gap-1.5">
            <Lock class="h-3.5 w-3.5" />登录密码
          </label>
          <Input
            v-model="password"
            type="password"
            autocomplete="current-password"
            placeholder="飞牛系统登录密码"
            :disabled="loading"
            class="h-10 text-sm bg-surface-inset border-border/75 focus:border-primary focus:ring-1 focus:ring-primary"
          />
        </div>

        <div class="pt-2">
          <Button
            type="submit"
            variant="brand"
            size="lg"
            :disabled="loading"
            class="w-full font-semibold shadow-md active:scale-[0.99] transition-all flex items-center justify-center gap-2"
          >
            <Loader2 v-if="loading" class="h-4 w-4 animate-spin" />
            <ShieldCheck v-else class="h-4 w-4" />
            <span>{{ loading ? '正在验证身份...' : '立即登录' }}</span>
          </Button>
        </div>

        <div class="pt-1 text-center">
          <p class="text-[11px] text-muted-foreground/80 leading-relaxed">
            🛡️ 系统直通飞牛原生鉴权，自动对齐飞牛音乐角色（管理员 / 成员）并授予对应权限。
          </p>
        </div>
      </form>
    </DialogContent>
  </Dialog>
</template>
