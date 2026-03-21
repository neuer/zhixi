<script setup lang="ts">
</script>

<template>
  <router-view v-slot="{ Component }">
    <Transition name="zx-fade" mode="out-in">
      <component :is="Component" />
    </Transition>
  </router-view>
</template>
