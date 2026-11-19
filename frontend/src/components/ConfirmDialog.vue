<script setup>
defineProps({
  open: Boolean,
  targetName: {
    type: String,
    default: '',
  },
  deleting: Boolean,
  error: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['cancel', 'confirm'])
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="open" class="modal-backdrop" @mousedown.self="!deleting && $emit('cancel')">
        <section class="confirm-card" role="alertdialog" aria-modal="true" aria-labelledby="delete-title">
          <div class="danger-icon">
            <svg viewBox="0 0 24 24"><path d="M12 9v4M12 17h.01" /><path d="M10.3 3.7 2.6 17a2 2 0 0 0 1.7 3h15.4a2 2 0 0 0 1.7-3L13.7 3.7a2 2 0 0 0-3.4 0Z" /></svg>
          </div>
          <h2 id="delete-title">删除监控入口？</h2>
          <p>“{{ targetName }}”将从入口列表中移除，此操作无法撤销。</p>
          <p v-if="error" class="modal-error">{{ error }}</p>
          <div class="confirm-actions">
            <button class="secondary-button" type="button" :disabled="deleting" @click="$emit('cancel')">取消</button>
            <button class="danger-button" type="button" :disabled="deleting" @click="$emit('confirm')">
              {{ deleting ? '正在删除…' : '确认删除' }}
            </button>
          </div>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>
