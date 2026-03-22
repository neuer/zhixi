import type { DigestItemResponse } from "@zhixi/openapi-client";

/** 过滤已剔除条目，按 display_order 排序。 */
export function filterVisibleItems(
  items: DigestItemResponse[],
): DigestItemResponse[] {
  return items
    .filter((item) => !item.is_excluded)
    .sort((a, b) => a.display_order - b.display_order);
}

/**
 * 观点对象（后端格式：{author, handle, viewpoint}）。
 *
 * 注意：后端 snapshot_perspectives 字段为 JSON 字符串，无独立 OpenAPI Schema。
 * 此类型需与后端 app/schemas/processor_types.py 中 AnalysisResult.perspectives 结构保持同步。
 */
export interface PerspectiveItem {
  author: string;
  handle: string;
  viewpoint: string;
}

/** 解析 perspectives JSON，支持对象数组和字符串数组两种格式。 */
export function parsePerspectives(raw: string | null): PerspectiveItem[] {
  if (!raw) return [];
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    const results: PerspectiveItem[] = [];
    for (const item of parsed) {
      if (typeof item === "string") {
        results.push({ author: "", handle: "", viewpoint: item });
      } else if (
        typeof item === "object" &&
        item !== null &&
        typeof (item as Record<string, unknown>).viewpoint === "string"
      ) {
        const obj = item as Record<string, unknown>;
        results.push({
          author: typeof obj.author === "string" ? obj.author : "",
          handle: typeof obj.handle === "string" ? obj.handle : "",
          viewpoint: obj.viewpoint as string,
        });
      }
    }
    return results;
  } catch {
    return [];
  }
}
