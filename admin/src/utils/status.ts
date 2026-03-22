/** 状态映射工具 -- 将后端状态字符串统一映射为中文文本、颜色与标签类型 */

import type { DigestStatus, JobStatus } from "@zhixi/openapi-client";

export type TagType = "primary" | "success" | "warning" | "danger" | "default";

export interface StatusInfo {
  text: string;
  type: TagType;
  color: string;
}

/** 后端状态枚举的联合类型 */
type KnownStatus = DigestStatus | JobStatus;

const statusMap: Record<KnownStatus, StatusInfo> = {
  running: { text: "运行中", type: "primary", color: "#1989fa" },
  completed: { text: "已完成", type: "success", color: "#07c160" },
  failed: { text: "失败", type: "danger", color: "#ee0a24" },
  draft: { text: "草稿", type: "warning", color: "#ff976a" },
  published: { text: "已发布", type: "success", color: "#07c160" },
  skipped: { text: "已跳过", type: "default", color: "#969799" },
};

const defaultStatus: StatusInfo = {
  text: "未知",
  type: "default",
  color: "#969799",
};

export function getStatus(status: KnownStatus | null | undefined): StatusInfo {
  if (status && status in statusMap) {
    return statusMap[status];
  }
  return defaultStatus;
}
