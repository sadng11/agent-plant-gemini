<script setup lang="ts">
import AppHeader from './components/layout/AppHeader.vue';
import TabNavigation from './components/layout/TabNavigation.vue';
</script>

<template>
  <div class="min-h-full flex flex-col bg-slate-50 text-slate-800 selection:bg-emerald-200">
    <!-- Main Header -->
    <AppHeader />

    <!-- Tab Navigation -->
    <TabNavigation />

    <!-- Main Workspace Content -->
    <main class="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
      <RouterView v-slot="{ Component }">
        <Transition name="fade" mode="out-in">
          <component :is="Component" />
        </Transition>
      </RouterView>
    </main>


    <!-- Footer -->
    <footer class="bg-white border-t border-slate-200 py-4 mt-auto">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
        <div class="flex items-center gap-2">
          <span>🌿 فیتو (PhytoAgent)</span>
          <span>•</span>
          <span>سامانه هوشمند گیاه‌پزشکی و برنامه‌ریزی تغذیه</span>
        </div>
        <div>
          <span>موتور هوش مصنوعی: LangGraph & Knowledge Base</span>
        </div>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.fade-enter-from {
  opacity: 0;
  transform: translateY(4px);
}

.fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
