import type { RawTweet } from "@zhixi/openapi-client";
import { showToast } from "vant";
import { type Ref, ref } from "vue";

export interface ExperimentLog {
  id: number;
  label: string;
  timestamp: string;
  latencyMs: number | null;
  status: "ok" | "error";
  summary: string;
  tweets: RawTweet[] | null;
  rawJson: string;
  expanded: boolean;
  showRaw: boolean;
}

export type AddLogFn = (
  label: string,
  status: "ok" | "error",
  latencyMs: number | null,
  summary: string,
  rawData: unknown,
  tweets?: RawTweet[] | null,
) => void;

interface UseExperimentLogReturn {
  logs: Ref<ExperimentLog[]>;
  addLog: AddLogFn;
  toggleLog: (log: ExperimentLog) => void;
  toggleRaw: (log: ExperimentLog) => void;
  copyRaw: (log: ExperimentLog) => void;
  clearLogs: () => void;
}

export function useExperimentLog(): UseExperimentLogReturn {
  let logIdSeq = 0;
  const logs = ref<ExperimentLog[]>([]);

  function addLog(
    label: string,
    status: "ok" | "error",
    latencyMs: number | null,
    summary: string,
    rawData: unknown,
    tweets: RawTweet[] | null = null,
  ): void {
    logs.value.unshift({
      id: ++logIdSeq,
      label,
      timestamp: new Date().toLocaleTimeString("zh-CN", { hour12: false }),
      latencyMs,
      status,
      summary,
      tweets,
      rawJson: JSON.stringify(rawData, null, 2),
      expanded: true,
      showRaw: false,
    });
  }

  function toggleLog(log: ExperimentLog) {
    const target = logs.value.find((l) => l.id === log.id);
    if (target) target.expanded = !target.expanded;
  }

  function toggleRaw(log: ExperimentLog) {
    const target = logs.value.find((l) => l.id === log.id);
    if (target) target.showRaw = !target.showRaw;
  }

  function copyRaw(log: ExperimentLog) {
    navigator.clipboard.writeText(log.rawJson).then(() => {
      showToast("已复制");
    });
  }

  function clearLogs() {
    logs.value = [];
  }

  return { logs, addLog, toggleLog, toggleRaw, copyRaw, clearLogs };
}
