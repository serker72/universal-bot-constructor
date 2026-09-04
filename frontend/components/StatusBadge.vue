<template>
  <span class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium" :class="cls">
    <span class="h-1.5 w-1.5 rounded-full" :class="dot" />
    {{ label }}
  </span>
</template>

<script setup lang="ts">
const props = defineProps<{ status: string }>()

const MAP: Record<string, { label: string; cls: string; dot: string }> = {
  new: { label: 'Новая', cls: 'bg-blue-50 text-blue-700 ring-1 ring-inset ring-blue-600/20', dot: 'bg-blue-500' },
  approved: { label: 'Подтверждена', cls: 'bg-green-50 text-green-700 ring-1 ring-inset ring-green-600/20', dot: 'bg-green-500' },
  rejected: { label: 'Отклонена', cls: 'bg-red-50 text-red-700 ring-1 ring-inset ring-red-600/20', dot: 'bg-red-500' },
  completed: { label: 'Выполнена', cls: 'bg-gray-100 text-gray-600 ring-1 ring-inset ring-gray-500/20', dot: 'bg-gray-400' },
  cancelled_by_customer: { label: 'Отменена', cls: 'bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-600/20', dot: 'bg-amber-500' },
}

const label = computed(() => MAP[props.status]?.label ?? props.status)
const cls = computed(() => MAP[props.status]?.cls ?? 'bg-gray-100 text-gray-600')
const dot = computed(() => MAP[props.status]?.dot ?? 'bg-gray-400')
</script>
