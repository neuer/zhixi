import type { DigestItemResponse } from "@zhixi/openapi-client";

/** 过滤已剔除条目，按 display_order 排序。 */
export function filterVisibleItems(
  items: DigestItemResponse[],
): DigestItemResponse[] {
  return items
    .filter((item) => !item.is_excluded)
    .sort((a, b) => a.display_order - b.display_order);
}
