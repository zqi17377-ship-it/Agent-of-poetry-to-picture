# Windows 运行指南

## 安装与启动

项目需要 Python 3.11+、Node.js 24+（前端回归测试使用 Node 原生 TypeScript 支持）。安装脚本优先使用本机 Codex 的 Python，没有时使用 PATH 中的 `python`。在项目目录双击 `安装依赖.cmd`，会创建 `.venv`、按锁文件安装 Python/前端依赖并构建网页。

双击 `启动.cmd`，或执行 `.\.venv\Scripts\python.exe launch.py`。默认只监听本机 `127.0.0.1:8765`，随后自动打开浏览器。可用 `--no-browser` 不自动打开；端口被占用时先使用现有服务，或指定 `--port 8766`。

关闭终端或按 Ctrl+C 停止。重新启动不会重复提交原来的运行中请求；这类任务会显示“需核查”。原本排队但尚未开始的任务会继续处理。

## 模型配置

复制 `.env.example` 为 `.env`，用文本编辑器修改并重启服务。项目默认即为免费调试配置，不复制也能运行：

```dotenv
IMAGE_PROVIDER=hf_space
TEXT_PROVIDER=basic
HF_SPACE_URL=https://black-forest-labs-flux-1-schnell.hf.space
```

HF Space 是公共演示服务，没有应用自己的无限免费额度。排队、配额不足或服务暂停会提示失败；不会偷偷切换为收费模型。

接入 Gemini：

```dotenv
TEXT_PROVIDER=gemini
IMAGE_PROVIDER=gemini
GEMINI_API_KEY=在本机填写
GEMINI_TEXT_MODEL=填写账号支持的文字模型
GEMINI_IMAGE_MODEL=填写账号支持的图像模型
```

也可以只替换文字服务、保留免费图像服务。图像模型可能收费，请以账号和服务商价格表为准。代码里的默认模型名不保证所有账号均可使用。

兼容 API：`TEXT_PROVIDER=compatible` 配置 `TEXT_BASE_URL`、`TEXT_API_KEY`、`TEXT_MODEL`；`IMAGE_PROVIDER=compatible` 配置 `IMAGE_BASE_URL`、`IMAGE_API_KEY`、`IMAGE_MODEL`。BASE_URL 填 API 根地址（如 `https://你的服务/v1`），后端追加 `/chat/completions` 或 `/images/generations`。远程地址使用 HTTPS，本机开发服务允许 HTTP。文字端需支持 JSON 输出；图像端支持 base64 或返回图片 URL。

图片 URL 必须为 HTTPS，主机名写入 `IMAGE_ALLOWED_HOSTS`，多个用逗号分隔。不会向图片 CDN 发送 API 密钥，也不会跟随重定向。

当前兼容图像服务只支持文生图；Gemini 适配器支持参考图请求。界面依据适配器能力显示“调整后重画”或“调整画面”。实际编辑质量仍须用你自己的账号验证。

## 数据、备份与异常

原文、任务、方案与版本记录在 `data/studio.sqlite3`，图片在 `data/images`。可通过 `DATA_DIR` 配置其他目录。备份前停止应用，再复制整个数据目录；恢复时完整还原，不能只复制数据库或图片中的一部分。

配额、认证或配置失败后，原文及已有版本保留。修正问题后可由用户手动重新生成。状态为“需核查”时，先核对服务商生成记录和页面中的请求编号，确认后再发起新请求。应用不会自动重试。

调用记录统计请求次数和耗时，保存图像服务返回的 usage；没有提供 usage/金额时不推算为零费用。文字服务目前不累计 token 用量或金额。

不要把 `.env`、`data` 或终端中手动填写的密钥提交到仓库。这些目录已有 Git 忽略规则。

## 开发检查

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
cd frontend
npm test
npm run build
```

改动后端后重启服务；改动前端后重新构建并刷新浏览器。测试不需要 API 账号，不会真实出图。`scripts/smoke_free.py` 会请求一张真实图片；请保持免费配置，注意共享额度。
