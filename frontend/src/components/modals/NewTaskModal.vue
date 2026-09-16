<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { api } from '../../api';
import { showToast } from '../../composables/useToast';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter
} from '@/components/ui/dialog';
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem
} from '@/components/ui/select';
import { Plus, Loader2 } from 'lucide-vue-next';

const props = defineProps<{
  open: boolean;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'update:open', val: boolean): void;
  (e: 'started'): void;
}>();

const playlistUrl = ref('');
const targetType = ref<'public' | 'user'>('public');
const targetUser = ref('admin');
const userList = ref<Array<{ id: number; name: string }>>([]);
const starting = ref(false);

async function loadUsers() {
  try {
    const res = await api.getUsers();
    if (res.ok && res.data.length > 0) {
      userList.value = res.data;
      targetUser.value = res.data[0].name;
    }
  } catch (e) {}
}

async function handleSubmit() {
  const url = playlistUrl.value.trim();
  if (!url) {
    showToast('请输入歌单链接或分享文本', 'warning');
    return;
  }
  starting.value = true;
  try {
    const res = await api.startTask({
      url,
      target: targetType.value,
      user: targetUser.value
    });
    if (res.ok) {
      showToast('歌单同步任务已启动！', 'success');
      playlistUrl.value = '';
      emit('started');
      emit('close');
      emit('update:open', false);
    } else {
      showToast(res.message || '任务启动失败', 'error');
    }
  } catch (e: any) {
    showToast(`启动失败: ${e.message}`, 'error');
  } finally {
    starting.value = false;
  }
}

function handleOpenUpdate(val: boolean) {
  emit('update:open', val);
  if (!val) {
    emit('close');
  }
}

onMounted(() => {
  loadUsers();
});
</script>

<template>
  <Dialog :open="props.open" @update:open="handleOpenUpdate">
    <DialogContent class="sm:max-w-lg p-6">
      <DialogHeader>
        <DialogTitle class="flex items-center gap-2 text-base font-bold text-white">
          <Plus class="w-4 h-4 text-brand-400" />
          <span>新建第三方歌单同步任务</span>
        </DialogTitle>
        <DialogDescription class="text-xs text-slate-400 leading-relaxed pt-1">
          支持粘贴网易云音乐、QQ音乐的歌单分享链接或完整文本。系统将自动解析封面、查重、抓取并同步至飞牛音乐库。
        </DialogDescription>
      </DialogHeader>

      <div class="space-y-4 py-2">
        <div class="space-y-1.5">
          <label class="block text-xs font-semibold text-slate-300">歌单链接 / 文本</label>
          <Input
            v-model="playlistUrl"
            type="text"
            class="h-11"
            placeholder="粘贴网易云 / QQ 音乐歌单链接或分享文本..."
          />
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div class="space-y-1.5">
            <label class="block text-xs font-semibold text-slate-300">目标歌单类型</label>
            <Select v-model="targetType">
              <SelectTrigger class="h-9 rounded-xl">
                <SelectValue placeholder="选择歌单类型" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="public">公共歌单 (全员可见)</SelectItem>
                <SelectItem value="user">指定用户专属歌单</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div v-if="targetType === 'user'" class="space-y-1.5">
            <label class="block text-xs font-semibold text-slate-300">选择归属用户</label>
            <Select v-model="targetUser">
              <SelectTrigger class="h-9 rounded-xl">
                <SelectValue placeholder="选择归属用户" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem v-for="u in userList" :key="u.id" :value="u.name">
                  {{ u.name }}
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      <DialogFooter class="pt-3 border-t border-border/80 flex items-center justify-end gap-2">
        <Button
          variant="ghost"
          size="sm"
          @click="emit('close')"
        >
          取消
        </Button>
        <Button
          variant="default"
          size="sm"
          @click="handleSubmit"
          :disabled="starting"
          class="gap-1.5"
        >
          <Loader2 v-if="starting" class="w-3.5 h-3.5 animate-spin" />
          <span>{{ starting ? '正在启动...' : '立即开始同步' }}</span>
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>


