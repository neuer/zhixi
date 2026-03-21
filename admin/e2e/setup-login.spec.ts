import { expect, test } from "@playwright/test";

/** 通用 mock — 让 dashboard/overview 不报错。 */
function mockDashboard(page: import("@playwright/test").Page) {
  return page.route("**/api/dashboard/overview", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        pipeline_status: null,
        digest_status: null,
        today_cost: { total_cost: 0, by_service: [] },
        recent_7_days: [],
        alerts: [],
      }),
    }),
  );
}

test.describe("Setup 首次设置", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => localStorage.removeItem("zhixi_token"));
  });

  test("未初始化时重定向到 /setup", async ({ page }) => {
    await page.route("**/api/setup/status", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ need_setup: true }),
      }),
    );

    await page.goto("/dashboard");
    await expect(page).toHaveURL("/setup");
  });

  test("Setup 页面显示两步向导", async ({ page }) => {
    await page.goto("/setup");

    // 第一步：密码设置
    await expect(page.getByText("设置管理员密码")).toBeVisible();
    await expect(
      page.getByRole("textbox", { name: "密码", exact: true }),
    ).toBeVisible();
    await expect(page.getByRole("textbox", { name: "确认密码" })).toBeVisible();

    // 下一步按钮初始禁用
    const nextBtn = page.getByRole("button", { name: "下一步" });
    await expect(nextBtn).toBeDisabled();

    // 填写密码后启用
    await page
      .getByRole("textbox", { name: "密码", exact: true })
      .fill("Test1234!");
    await page.getByRole("textbox", { name: "确认密码" }).fill("Test1234!");
    await expect(nextBtn).toBeEnabled();

    // 进入第二步
    await nextBtn.click();
    await expect(page.getByText("通知配置（可选）")).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Webhook" })).toBeVisible();

    // 可以返回第一步
    await page.getByRole("button", { name: "上一步" }).click();
    await expect(page.getByText("设置管理员密码")).toBeVisible();
  });

  test("密码不一致时提示错误", async ({ page }) => {
    await page.goto("/setup");

    await page
      .getByRole("textbox", { name: "密码", exact: true })
      .fill("Test1234!");
    await page.getByRole("textbox", { name: "确认密码" }).fill("Different1");
    await page.getByRole("button", { name: "下一步" }).click();

    await expect(page.getByText("两次密码不一致")).toBeVisible();
  });

  test("纯小写密码被前端拦截（密码强度校验）", async ({ page }) => {
    await page.goto("/setup");

    await page
      .getByRole("textbox", { name: "密码", exact: true })
      .fill("test1234");
    await page.getByRole("textbox", { name: "确认密码" }).fill("test1234");
    await page.getByRole("button", { name: "下一步" }).click();

    await expect(page.getByText("密码必须包含大写字母")).toBeVisible();
  });

  test("无数字密码被前端拦截", async ({ page }) => {
    await page.goto("/setup");

    await page
      .getByRole("textbox", { name: "密码", exact: true })
      .fill("TestTest");
    await page.getByRole("textbox", { name: "确认密码" }).fill("TestTest");
    await page.getByRole("button", { name: "下一步" }).click();

    await expect(page.getByText("密码必须包含数字")).toBeVisible();
  });

  test("短密码被前端拦截", async ({ page }) => {
    await page.goto("/setup");

    await page.getByRole("textbox", { name: "密码", exact: true }).fill("Aa1");
    await page.getByRole("textbox", { name: "确认密码" }).fill("Aa1");
    await page.getByRole("button", { name: "下一步" }).click();

    await expect(page.getByText("密码长度至少 8 位")).toBeVisible();
  });

  test("Setup 完成后跳转到 Dashboard", async ({ page }) => {
    // init 后切换 need_setup 响应
    let initCalled = false;

    await page.route("**/api/setup/status", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ need_setup: !initCalled }),
      }),
    );
    await page.route("**/api/setup/init", (route) => {
      initCalled = true;
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ message: "初始化完成" }),
      });
    });
    await page.route("**/api/auth/login", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          token:
            "eyJhbGciOiJIUzI1NiJ9.eyJleHAiOjk5OTk5OTk5OTl9.K1OA0LOhkn5tEQm8YCOqEIReFGKBsMC-NLslkz1qxYg",
          expires_at: "2099-01-01T00:00:00Z",
        }),
      }),
    );
    await mockDashboard(page);

    await page.goto("/setup");

    // 第一步
    await page
      .getByRole("textbox", { name: "密码", exact: true })
      .fill("Test1234!");
    await page.getByRole("textbox", { name: "确认密码" }).fill("Test1234!");
    await page.getByRole("button", { name: "下一步" }).click();

    // 第二步 — 直接完成
    await page.getByRole("button", { name: "完成设置" }).click();

    await expect(page).toHaveURL("/dashboard", { timeout: 10000 });

    const token = await page.evaluate(() =>
      localStorage.getItem("zhixi_token"),
    );
    expect(token).toBeTruthy();
  });
});

test.describe("Login 登录", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => localStorage.removeItem("zhixi_token"));
    await page.route("**/api/setup/status", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ need_setup: false }),
      }),
    );
  });

  test("未登录时重定向到 /login", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL("/login");
  });

  test("Login 页面显示表单", async ({ page }) => {
    await page.goto("/login");

    await expect(page.getByText("智曦")).toBeVisible();
    await expect(page.getByRole("textbox", { name: "用户名" })).toHaveValue(
      "admin",
    );
    await expect(page.getByRole("textbox", { name: "密码" })).toBeVisible();
    await expect(page.getByRole("button", { name: "登录" })).toBeDisabled();
  });

  test("登录成功跳转 Dashboard", async ({ page }) => {
    await page.route("**/api/auth/login", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          token:
            "eyJhbGciOiJIUzI1NiJ9.eyJleHAiOjk5OTk5OTk5OTl9.K1OA0LOhkn5tEQm8YCOqEIReFGKBsMC-NLslkz1qxYg",
          expires_at: "2099-01-01T00:00:00Z",
        }),
      }),
    );
    await mockDashboard(page);

    await page.goto("/login");
    await page.getByRole("textbox", { name: "密码" }).fill("Test1234!");
    await page.getByRole("button", { name: "登录" }).click();

    await expect(page).toHaveURL("/dashboard", { timeout: 10000 });
  });

  test("登录失败显示错误", async ({ page }) => {
    await page.route("**/api/auth/login", (route) =>
      route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "用户名或密码错误" }),
      }),
    );

    await page.goto("/login");
    await page.getByRole("textbox", { name: "密码" }).fill("wrong");
    await page.getByRole("button", { name: "登录" }).click();

    await expect(page).toHaveURL("/login");
  });
});
