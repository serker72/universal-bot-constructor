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
          <div class="w-full max-w-lg rounded-2xl bg-white shadow-2xl">
            <div class="flex items-center justify-between border-b border-gray-100 px-5 py-4">
              <h2 class="text-base font-semibold text-gray-900">{{ title }}</h2>
              <button class="btn-ghost -mr-1.5 rounded-lg p-1.5" @click="$emit('close')">
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
defineProps<{ open: boolean; title: string }>()
defineEmits<{ close: [] }>()
</script>
