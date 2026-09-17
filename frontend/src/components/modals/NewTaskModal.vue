<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { api } from '../../api';
import { showToast } from '../../composables/useToast';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select';
import { Link2, Loader2 } from 'lucide-vue-next';

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{ (e: 'close'): void; (e: 'update:open', val: boolean): void; (e: 'started'): void }>();
const playlistUrl = ref('');
const targetType = ref<'public' | 'user'>('public');
const targetUser = ref('admin');
const userList = ref<Array<{ id: number; name: string }>>([]);
const starting = ref(false);

async function loadUsers() {
  try { const res = await api.getUsers(); if (res.ok && res.data.length > 0) { userList.value = res.data; targetUser.value = res.data[0].name; } } catch {}
}
async function handleSubmit() {
  const url = playlistUrl.value.trim();
  if (!url) { showToast('粘贴歌单链接或分享文本后再继续。', 'warning'); return; }
  starting.value = true;
  try {
    const res = await api.startTask({ url, target: targetType.value, user: targetUser.value });
    if (res.ok) {
      showToast('歌单已开始导入，可在“任务”中查看进度。', 'success');
      playlistUrl.value = ''; emit('started'); emit('close'); emit('update:open', false);
    } else showToast(res.message || '歌单未能开始导入。', 'error');
  } catch (e: any) { showToast(`导入失败：${e.message}`, 'error'); }
  finally { starting.value = false; }
}
function handleOpenUpdate(val: boolean) { emit('update:open', val); if (!val) emit('close'); }
onMounted(loadUsers);
</script>

<template>
  <Dialog :open="props.open" @update:open="handleOpenUpdate">
    <DialogContent class="sm:max-w-lg">
      <DialogHeader class="pr-8">
        <div class="mb-2 grid h-10 w-10 place-items-center rounded-xl bg-primary/10 text-primary"><Link2 class="h-5 w-5" /></div>
        <DialogTitle class="text-lg font-bold tracking-[-0.02em] text-foreground">导入歌单</DialogTitle>
        <DialogDescription class="pt-1 text-xs leading-relaxed text-muted-foreground">粘贴网易云或 QQ 音乐的歌单链接。系统会查重，并把缺少的歌曲保存到飞牛音乐。</DialogDescription>
      </DialogHeader>
      <div class="space-y-4 py-1">
        <div class="space-y-2">
          <label class="block text-xs font-semibold text-foreground">歌单链接或分享文本</label>
          <Input v-model="playlistUrl" type="text" class="h-11" placeholder="粘贴到这里" @keyup.enter="handleSubmit" />
        </div>
        <div class="grid gap-3 sm:grid-cols-2">
          <div class="space-y-2">
            <label class="block text-xs font-semibold text-foreground">谁可以看到</label>
            <Select v-model="targetType"><SelectTrigger class="h-10"><SelectValue placeholder="选择可见范围" /></SelectTrigger><SelectContent><SelectItem value="public">所有家庭成员</SelectItem><SelectItem value="user">指定成员</SelectItem></SelectContent></Select>
          </div>
          <div v-if="targetType === 'user'" class="space-y-2">
            <label class="block text-xs font-semibold text-foreground">选择成员</label>
            <Select v-model="targetUser"><SelectTrigger class="h-10"><SelectValue placeholder="选择成员" /></SelectTrigger><SelectContent><SelectItem v-for="u in userList" :key="u.id" :value="u.name">{{ u.name }}</SelectItem></SelectContent></Select>
          </div>
        </div>
      </div>
      <DialogFooter class="flex-row justify-end gap-2 border-t border-border pt-4">
        <Button variant="ghost" @click="emit('close')">取消</Button>
        <Button @click="handleSubmit" :disabled="starting"><Loader2 v-if="starting" class="h-4 w-4 animate-spin" /><span>{{ starting ? '正在导入…' : '开始导入' }}</span></Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
