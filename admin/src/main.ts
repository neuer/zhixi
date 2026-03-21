import { showToast } from "vant";
import { createApp } from "vue";
import App from "./App.vue";
import router from "./router";

import "vant/lib/index.css";

const app = createApp(App);
app.use(router);

app.config.errorHandler = (err, _instance, info) => {
  console.error(`[全局错误] ${info}:`, err);
  showToast({
    type: "fail",
    message: "页面出现异常，请刷新重试",
    duration: 5000,
  });
};

app.mount("#app");
