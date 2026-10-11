# 外国诗文意境图 Agent 开发计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将外国诗文自动转成自然写实、偏冷色但尊重原文情绪的意境图，支持自然语言修改和作品保存。

**Architecture:** 显式工作流分别完成文学理解、画面设计、图像生成、有限质检和版本保存。云端模型经适配器调用；FastAPI 接收请求，独立 worker 处理持久化任务，React 展示作品。

**Tech Stack:** Python、FastAPI、React、TypeScript、SQLite、pytest；具体依赖版本在开发启动时锁定。

**Spec:** ../specs/2026-10-11-literature-to-image-design.md

状态：依据目前需求和标明的默认决定制定的开发草案。这里只交付计划，不创建应用、不安装依赖、不实际调用付费模型。

## 全局约束

- 首版输入限制为去除首尾空白后 1–8000 个 Unicode 字符，超限明确提示，不静默截断。
- 每次默认生成 1 张图；默认横幅 3:2，允许用户改为其他已验证的比例。
- 自动完成理解、画面设计和出图，构想不需要用户逐项确认。
- 默认自然写实、偏冷色、低至中等饱和度；原文明示的季节、天气、色彩和情绪优先于默认偏好。
- 首版最多 1 个活动任务；付费图像请求不进行盲目重试。
- 原文中的命令式语言属于文学内容，不得被当作系统指令或调用工具的授权。
- 当前不实施视频接口。
- UI 界面简洁，操作简便；采用单页主流程，默认不要求填写模型参数或选择画风。

## 审阅重点

1. 明亮或温暖诗文不能被默认冷色调压成悲伤画面：任务 1 和 2 验证。
2. 抽象、多义诗文需要允许克制转译，不能编造确定的作者意图：任务 2 验证。
3. 服务商已接收但本地超时的请求不能自动重复付费：任务 3 验证。
4. 修改原图的能力必须实测，不能以重新生成假装完成编辑：任务 1 和 4 验证。
5. 长文本、空文本、恶意命令及程序重启需要明确行为：任务 2、3 和 5 验证。

## 阶段安排

| 阶段 | 估计 | 交付物 | 进入下一阶段的条件 |
| --- | --- | --- | --- |
| 1. 样例与模型验证 | 1–2 个工作日 | 12 个样本、真实生成记录、供应商选择 | 生成与编辑可用，效果值得继续调试 |
| 2. 文学理解和画面设计 | 2–3 个工作日 | 结构化理解和画面方案 | 意象有证据，氛围与原文一致 |
| 3. 生成和任务系统 | 2–3 个工作日 | 可出图、保存、恢复和报告失败的后端 | 全流程成功，异常不盲目重复调用 |
| 4. 页面和自然语言修改 | 3–4 个工作日 | 可在本机浏览器使用的产品 | 输入到下载、修改到历史完整可用 |
| 5. 质量验收和交付 | 2 个工作日 | 评估记录、运行指南、完整初版 | 人工审美评估及功能检查达到约定目标 |

估计合计 10–14 个工作日，假设单人开发、供应商账号可用；不构成固定交付承诺。

## 预定目录及职责

当前项目只有方案文档，尚无应用代码。下列均为未来开发时新建，不在制定计划时创建。

```text
backend/app/main.py                  # HTTP 应用及依赖注入
backend/app/models.py                # 输入、理解、画面、任务、图片版本类型
backend/app/literature.py            # 文学分析与画面设计
backend/app/prompts/                 # 版本化的提示词模板
backend/app/providers/base.py        # 文本、图像和评估能力接口
backend/app/providers/selected.py    # 实际选定的供应商实现
backend/app/storage.py               # SQLite 数据和本地图片
backend/app/jobs.py                  # 任务提交、查询、状态变更
backend/app/worker.py                # 顺序执行、重启处理
backend/app/workflow.py              # 组合分析、设计、生成、评估和保存
backend/app/routes/artworks.py       # 作品、修改、任务及下载接口
backend/tests/                      # 关键逻辑及错误路径测试
frontend/src/App.tsx                # 输入、作品预览和操作
frontend/src/api.ts                 # 类型化后端请求
frontend/src/components/            # 状态、历史、修改框
eval/samples.json                   # 人工标注的文学样本
eval/results.csv                    # 真实生成与人工评价记录
docs/runbook.md                     # 启动、配置、备份、失败处理
```

## 核心数据及接口约定

- `ArtworkInput`: `text: str`、`title: str | None`、`author: str | None`、`aspect_ratio: str = "3:2"`。
- `Interpretation`: `language: str`、`emotions: list[str]`、`imagery: list[ImageryEvidence]`、`ambiguities: list[str]`；`ImageryEvidence` 为 `image: str`、`source_quote: str`。
- `VisualBrief`: `subject`、`setting`、`composition`、`lighting`、`palette`、`rendering`、`additions: list[str]`、`rationale: str`；前六项为字符串。
- `GenerationRequest`: `prompt: str`、`aspect_ratio: str`、`reference_path: Path | None`。
- `ImageResult`: `path: Path`、`provider_request_id: str | None`、`model: str`、`usage: dict | None`。
- `QualityReport`: `flags: list[str]`、`rationale: str`；只提示缺陷，不触发无限生成。
- `ImageVersion`: `id`、`artwork_id`、`parent_version_id`、`revision_text`、`brief`、`prompt`、`prompt_version`、`image_path`、`quality_report`。
- `JobRecord`: `id`、`artwork_id`、`status`、`operation`、`source_version_id`、`error`、`provider_request_id`、`call_count`、`elapsed_ms`、`usage`。
- `POST /api/artworks` 接收 `ArtworkInput`，返回 `artwork_id` 与 `job_id`（202）；无效输入返回 422。
- `POST /api/artworks/{id}/revisions` 接收 `source_version_id`、`instruction`，返回 `job_id`（202）；没有编辑能力时返回 409 并明确说明。
- `GET /api/jobs/{id}` 返回任务状态；`GET /api/artworks` 返回历史；`GET /api/artworks/{id}` 返回原文和版本。
- `GET /api/versions/{id}/image` 返回本地已生成原图；不存在返回 404。

### 任务 1：验证样例和供应商（1–2 天）

**文件：** `eval/samples.json`、`eval/results.csv`、`docs/provider-selection.md`。

**产出：** 12 个有人工标注的样本、供应商及具体模型选择、生成和参考图编辑能力记录；后续适配器只能承诺实测能力。

- [ ] 选 6 段英语原文和 6 段中文译文，标注关键意象、情绪及允许的画面转译。
- [ ] 使用同一组文学画面方案试验候选图像服务；记录样本、模型、提示词、调用次数、耗时、usage 和实际费用（可取得时）。
- [ ] 用“去掉人物，保持地形与光线”等修改测试参考图编辑；将变更成功率和无意变动记录下来。
- [ ] 比较情绪匹配、自然程度、修改能力、账号可用性和调用成本；选择一套首版服务。不在效果验证前建设完整界面。
- [ ] 固定第一版输出尺寸和支持比例；若 3:2 不支持，记录替代方案并更新设计文档后再实现。

### 任务 2：文学理解和画面设计（2–3 天）

**文件：** `backend/app/models.py`、`backend/app/literature.py`、`backend/app/prompts/`、`backend/app/providers/base.py`、`backend/tests/test_literature.py`。

**接口：** `analyze_text(text: str, provider: TextProvider) -> Interpretation`；`design_brief(interpretation: Interpretation, provider: TextProvider) -> VisualBrief`；二者为异步函数。`TextProvider.complete_json(system: str, content: str) -> dict` 为异步接口，使用 schema 校验输出。

- [ ] 编写关键失败测试：空白和 8001 字符拒绝、8000 字符接受；保留原文换行；文学命令不能覆盖系统指令；引用必须出现在输入中；结构化输出缺字段时报明确错误。
- [ ] 运行 `python -m pytest backend/tests/test_literature.py -q` 确认测试先暴露缺失功能。
- [ ] 实现分析、画面设计和输入校验，原文证据与创作补充分别记录；提示词明确“尊重原文色彩和情绪”优先于偏冷色默认值。
- [ ] 同一命令验证通过；以任务 1 的样本人工检查温暖、抽象与多义文本，记录不能由单元测试确认的审美问题。
- [ ] 保存提示词版本及分析样例，使后续更换模型可比较结果。

### 任务 3：图像生成、持久任务和异常处理（2–3 天）

**文件：** `backend/app/providers/selected.py`、`backend/app/storage.py`、`backend/app/jobs.py`、`backend/app/worker.py`、`backend/app/workflow.py`、`backend/tests/test_jobs.py`。

**接口：** 异步 `ImageProvider.generate(request: GenerationRequest) -> ImageResult`；`JobRepository.enqueue(artwork_id: str, operation: str, source_version_id: str | None) -> JobRecord`；`Workflow.run(job: JobRecord) -> ImageVersion`；后者异步。worker 使用事务领取 queued 任务，每次仅处理一个。

- [ ] 用 fake provider 编写测试：成功后文件与版本可读取、请求未提交时最多重试 1 次、提交状态不明时转 needs_review、重启保留 queued 并将遗留 running 转 needs_review、一次仅有 1 个活动任务。
- [ ] 运行 `python -m pytest backend/tests/test_jobs.py -q` 确认测试暴露缺失行为。
- [ ] 实现适配器、数据库、图片落盘和顺序 worker；调用分析与画面接口；原图先写临时文件再完成版本保存。
- [ ] 同一命令验证通过；真实生成一张图片后终止并重启 worker，确认状态和文件可恢复，不因重启自动再次提交付费请求。
- [ ] 保存模型、提示词版本、耗时和实际调用量；不将缺失 usage 或价格展示成 0 元。

### 任务 4：网页、修改和作品历史（3–4 天）

**文件：** `backend/app/main.py`、`backend/app/routes/artworks.py`、`frontend/src/App.tsx`、`frontend/src/api.ts`、`frontend/src/components/`、`backend/tests/test_artwork_routes.py`。

**接口：** 使用核心数据及接口约定中的 HTTP 路由；异步 `revise_brief(current: VisualBrief, instruction: str, provider: TextProvider) -> VisualBrief` 保留未被要求修改的画面要素；支持编辑的图像服务接收 `reference_path`。

- [ ] 写接口失败测试：无效输入返回 422、不存在的图像返回 404、编辑能力缺失返回 409、修改生成带父版本的新图且原版本可读取、提交任务返回 202。
- [ ] 运行 `python -m pytest backend/tests/test_artwork_routes.py -q` 确认测试先失败，再实现路由及修改编排并验证通过。
- [ ] 按设计文档“界面与操作设计”实现单页主流程：首页仅突出诗文输入框和“生成图片”；标题、作者、比例默认折叠；结果区突出原图，提供“下载原图”和“调整画面”。
- [ ] 将创作依据、历史版本和调用记录设为按需展开，顶部提供“我的作品”入口；采用灰白背景、留白和克制的蓝灰色强调色。
- [ ] 提交后立即禁用重复提交，展示真实的阶段状态；完成或失败后恢复操作，失败保留文字和已有作品。用户无需填写模型提示词或先批准构想。
- [ ] 用桌面和手机窄屏完成一次真实的“输入 → 生成 → 下载 → 修改 → 对比历史”流程；核对粘贴后一次点击即可生成、一次点击即可下载、自然语言修改可直接提交，检查键盘操作及断开页面后再次打开仍能看到任务结果。
- [ ] 后端检查版本与作品关联，拒绝错误的 source_version_id；密钥保留在后端。

### 任务 5：有限质检、审美验收和交付（2 天）

**文件：** `backend/app/quality.py`、`backend/tests/test_quality.py`、`eval/results.csv`、`docs/runbook.md`。

**接口：** 异步 `assess_image(image: ImageResult, interpretation: Interpretation, brief: VisualBrief, provider: VisionProvider) -> QualityReport`；异步 `VisionProvider.inspect(path: Path, criteria: dict) -> QualityReport`。视觉评估最多调用 1 次；失败不撤销已完成的图片，显示评估不可用。

- [ ] 写测试验证：低质量报告不自动重画；评估接口失败仍保留图片；评估调用量进入任务统计。
- [ ] 运行 `python -m pytest backend/tests/test_quality.py -q` 确认失败，完成质检逻辑，再确认通过。
- [ ] 由用户评价 12 个样本的原文关联、氛围、自然程度和喜好；以设计文档中的拟定目标判断是否继续调试，不用模型评分替代用户评价。
- [ ] 运行 `python -m pytest backend/tests -q`，执行前端构建；检查空输入、超限、接口失败、重启、下载和修改流程。
- [ ] 编写 Windows 下的启动、环境变量、费用记录、作品目录备份、失败任务恢复说明。交付完整初版和已知效果限制。

## 后续视频方向

图片效果达到用户预期后，再制定独立视频计划：从用户选定的图片生成有轻微风、雾、水面运动的短片，保存原图与视频关联。时长、运动幅度和供应商在该阶段确认；不默认增加字幕和旁白。

## 自检

- 确认需求：外国诗文、意境图、偏冷且自然写实、自主选氛围均已覆盖。
- 文学质量用人工样本验证；系统可靠性用接口与状态测试验证，二者分开验收。
- 任务接口使用相同类型名；供应商、模型及输出尺寸由任务 1 实测决定。
- 首版不产生复杂分布式基础设施，不承担视频或商业平台建设范围。
- 简洁 UI 已加入任务 4，并以真实操作步骤和桌面/窄屏检查验收。
