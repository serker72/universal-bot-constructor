<template>
  <span :class="cls">{{ text }}</span>
</template>

<script setup lang="ts">
// Булевой флаг в таблице (Активен/Заблокирован/Есть PDF…).
// Строковые статусы заявок — StatusBadge, сюда не подмешиваются.
const props = withDefaults(
  defineProps<{
    value: boolean
    yesText?: string
    noText?: string
    /** ok: «да» — зелёный; danger: «да» — красный (бан) */
    tone?: 'ok' | 'danger'
  }>(),
  { yesText: 'Да', noText: 'Нет', tone: 'ok' },
)

const cls = computed(() => {
  if (props.tone === 'danger') return props.value ? 'text-red-600' : 'text-green-600'
  return props.value ? 'text-green-600' : 'text-gray-400'
})
const text = computed(() => (props.value ? props.yesText : props.noText))
</script>
