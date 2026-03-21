import { type Ref, onMounted, ref } from "vue";

interface UseAsyncDataReturn<T> {
  data: Ref<T | null>;
  loading: Ref<boolean>;
  error: Ref<string | null>;
  execute: () => Promise<void>;
}

export function useAsyncData<T>(
  fetcher: () => Promise<T>,
  options?: { immediate?: boolean },
): UseAsyncDataReturn<T> {
  const data = ref<T | null>(null) as Ref<T | null>;
  const loading = ref(false);
  const error = ref<string | null>(null);

  async function execute() {
    loading.value = true;
    error.value = null;
    try {
      data.value = await fetcher();
    } catch {
      // 拦截器已处理 toast，此处仅记录状态
    } finally {
      loading.value = false;
    }
  }

  if (options?.immediate !== false) {
    onMounted(execute);
  }

  return { data, loading, error, execute };
}
