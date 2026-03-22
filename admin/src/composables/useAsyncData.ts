import { type Ref, onMounted, ref } from "vue";

interface UseAsyncDataReturn<T> {
  data: Ref<T | null>;
  loading: Ref<boolean>;
  refreshing: Ref<boolean>;
  error: Ref<string | null>;
  execute: () => Promise<void>;
  refresh: () => Promise<void>;
}

export function useAsyncData<T>(
  fetcher: () => Promise<T>,
  options?: { immediate?: boolean },
): UseAsyncDataReturn<T> {
  const data = ref<T | null>(null) as Ref<T | null>;
  const loading = ref(false);
  const refreshing = ref(false);
  const error = ref<string | null>(null);

  async function execute() {
    loading.value = true;
    error.value = null;
    try {
      data.value = await fetcher();
    } catch (e: unknown) {
      // 拦截器已处理 toast，此处记录错误状态供组件判断
      error.value = e instanceof Error ? e.message : "请求失败";
    } finally {
      loading.value = false;
    }
  }

  async function refresh() {
    refreshing.value = true;
    error.value = null;
    try {
      data.value = await fetcher();
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : "请求失败";
    } finally {
      refreshing.value = false;
    }
  }

  if (options?.immediate !== false) {
    onMounted(execute);
  }

  return { data, loading, refreshing, error, execute, refresh };
}
