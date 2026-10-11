# 余境 · 诗文意境图

把外国诗歌、散文或中文译文转成自然写实的意境风景。界面只需粘贴文字、点击生成；标题、作者和比例默认折叠。原文情绪优先于偏冷色的默认偏好。

这是可运行的本机调试版：免费 FLUX 出图已实测，支持下载、自然语言调整后重画、作品历史和图片版本。当前不包含视频、字幕或旁白。

## 立即使用

本机已安装依赖并完成构建。双击 **启动.cmd**，或运行：

```powershell
.\.venv\Scripts\python.exe launch.py
```

浏览器打开 `http://127.0.0.1:8765`。关闭启动终端即可停止服务。如果已有服务运行，直接打开上述地址。

从 GitHub 下载到新电脑后，需要 Python 3.11+ 和 Node.js 24+；先双击 **安装依赖.cmd**，成功后双击 **启动.cmd**。详情见 [运行指南](docs/runbook.md)。

## 免费模式与替换 API

默认配置无需密钥：

- 图像：Black Forest Labs 的公共 [FLUX.1-schnell Space](https://huggingface.co/spaces/black-forest-labs/FLUX.1-schnell)。有共享队列、每日额度和服务可用性限制，适合调试。
- 文学理解：本地基础关键词提取，只可靠处理明显的英文/中文景物和部分情绪；不等同于语言模型，也不能可靠理解复杂隐喻。
- 修改：免费模型根据新描述重新生成，构图可能改变；旧图片会保留。界面标为“调整后重画”。

复制 `.env.example` 为 `.env`，分别配置文字和图片服务，再重启。可选 Gemini 或提供 `chat/completions`、`images/generations` 的兼容 API。Gemini 图像服务可能收费；具体模型和额度由服务商账号决定。参考图编辑仅在启用相应能力的 Gemini 适配器时提供；目前该能力通过模拟请求测试，尚未用真实账号验收。

密钥由本机后端读取；`.env`、作品数据和生成图片均不会提交到 GitHub。需要 URL 返回图片的兼容服务须配置 `IMAGE_ALLOWED_HOSTS`。

## 工作流

文字 → 意象与情绪 → 画面方案 → 出图 → 图片格式校验 → 本地保存。

每幅作品保存原文、画面方案、提示词、模型、调用记录和版本关系。SQLite 队列顺序处理任务；运行中断或结果不明确时停止自动重试，避免重复请求。刷新页面可以恢复最近的作品。

图片是否自然、意境是否贴合目前由人工评估；页面不会声称已自动通过审美质检。

## 开发与验证

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
cd frontend
npm ci
npm test
npm run build
```

测试使用模拟供应商，不调用付费模型。真实免费出图调试可运行 `.\.venv\Scripts\python.exe scripts/smoke_free.py`；脚本要求 HF 图像服务和 basic 文字模式，拒绝其他配置。

代码结构：`backend/app` 为工作流、模型适配器和持久化；`frontend/src` 为界面；`docs` 为开发计划、供应商说明、运行指南和验收记录；`eval/samples.json` 为 12 个自编回归样本，尚待用户审美评分。

请查看 [开发记录](docs/development-status.md)、[模型选择与限制](docs/provider-selection.md)、[原始开发计划](docs/superpowers/plans/2026-10-11-literature-to-image-plan.md)。
