/** 日期格式化工具。 */

export function formatDate(dateStr: string, withYear = true): string {
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return dateStr;
  const month = d.getMonth() + 1;
  const day = d.getDate();
  if (withYear) return `${d.getFullYear()}年${month}月${day}日`;
  return `${month}月${day}日`;
}

/** 格式化星期几。 */
export function formatWeekday(dateStr: string): string {
  const days = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
  const d = new Date(dateStr);
  return days[d.getDay()] ?? "";
}

/** URL 协议安全校验，仅允许 http/https。 */
export function safeHref(url: string): string {
  if (/^https?:\/\//i.test(url)) return url;
  return "#";
}
