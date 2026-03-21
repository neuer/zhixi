/** 状态映射工具 — 统一 Dashboard/Digest/History 的状态展示。 */

export type TagType = "primary" | "success" | "warning" | "danger" | "default";

export interface StatusInfo {
  text: string;
  type: TagType;
  color: string;
}

const statusMap: Record<string, StatusInfo> = {
  running: { text: "运行中", type: "primary", color: "#1989fa" },
  success: { text: "已完成", type: "success", color: "#07c160" },
  completed: { text: "已完成", type: "success", color: "#07c160" },
  failed: { text: "失败", type: "danger", color: "#ee0a24" },
  draft: { text: "草稿", type: "warning", color: "#ff976a" },
  published: { text: "已发布", type: "success", color: "#07c160" },
  idle: { text: "空闲", type: "default", color: "#969799" },
};

const defaultStatus: StatusInfo = {
  text: "未知",
  type: "default",
  color: "#969799",
};

export function getStatus(status: string | null | undefined): StatusInfo {
  return statusMap[status ?? ""] ?? defaultStatus;
}
