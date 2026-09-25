<template>
  <Teleport to="body">
    <Transition
      enter-active-class="duration-200 ease-out"
      enter-from-class="opacity-0"
      leave-active-class="duration-150 ease-in"
      leave-to-class="opacity-0"
    >
      <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4" @click.self="$emit('close')">
        <Transition
          appear
          enter-active-class="duration-200 ease-out"
          enter-from-class="opacity-0 translate-y-2 scale-95"
          appear-active-class=""
        >
          <div
            class="w-full max-w-lg rounded-2xl bg-white shadow-2xl"
            role="dialog"
            aria-modal="true"
            :aria-labelledby="titleId"
          >
            <div class="flex items-center justify-between border-b border-gray-100 px-5 py-4">
              <h2 :id="titleId" class="text-base font-semibold text-gray-900">{{ title }}</h2>
              <button class="btn-ghost -mr-1.5 rounded-lg p-1.5" type="button" aria-label="Закрыть" @click="$emit('close')">
                <AppIcon name="x" size="sm" />
              </button>
            </div>
            <div class="px-5 py-5">
              <slot />
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
const props = defineProps<{ open: boolean; title: string }>()
const emit = defineEmits<{ close: [] }>()

const titleId = useId()

// Esc закрывает открытую модалку
function onKeydown(e: KeyboardEvent) {
  if (props.open && e.key === 'Escape') emit('close')
}
onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>
