import type { Page } from "@playwright/test";

/** 注入有效 JWT token + mock setup/status，绕过路由守卫。 */
export async function setupAuth(page: Page) {
  await page.addInitScript(() => {
    // exp = 9999999999（远未来）
    localStorage.setItem(
      "zhixi_token",
      "eyJhbGciOiJIUzI1NiJ9.eyJleHAiOjk5OTk5OTk5OTl9.K1OA0LOhkn5tEQm8YCOqEIReFGKBsMC-NLslkz1qxYg",
    );
  });
  await page.route("**/api/setup/status", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ need_setup: false }),
    }),
  );
}
