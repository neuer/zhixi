<script setup lang="ts">
defineProps<{
  loading: boolean;
  error: string | null;
}>();
</script>

<template>
  <div v-if="loading" class="async-loading">
    <van-loading size="36px" vertical>加载中...</van-loading>
  </div>
  <div v-else-if="error" class="async-empty">
    <van-empty :description="error">
      <slot name="error-action" />
    </van-empty>
  </div>
  <slot v-else />
</template>

<style scoped>
.async-loading {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 60vh;
}

.async-empty {
  padding-top: 20vh;
}
</style>
