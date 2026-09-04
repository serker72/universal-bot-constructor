<template>
  <div v-if="totalPages > 1" class="mt-4 flex items-center justify-between text-sm">
    <span class="text-gray-500">Всего: <span class="font-medium text-gray-700">{{ total }}</span></span>
    <div class="flex items-center gap-1.5">
      <button class="btn-ghost !px-2.5" :disabled="offset === 0" @click="$emit('change', offset - limit)">
        <AppIcon name="back" size="sm" />
      </button>
      <span class="rounded-lg bg-gray-100 px-3 py-1.5 text-xs font-medium text-gray-600">
        {{ page }} / {{ totalPages }}
      </span>
      <button class="btn-ghost !px-2.5" :disabled="offset + limit >= total" @click="$emit('change', offset + limit)">
        <AppIcon name="forward" size="sm" />
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{ total: number; limit: number; offset: number }>()
defineEmits<{ change: [offset: number] }>()

const page = computed(() => Math.floor(props.offset / props.limit) + 1)
const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.limit)))
</script>
