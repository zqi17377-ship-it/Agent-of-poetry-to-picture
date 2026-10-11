# 图像供应商选择（2026-10-11）

用户没有 API 账号，当前目标是免费调试并保留切换能力。首版选择 Black Forest Labs 发布的公共 FLUX.1-schnell Hugging Face Space，通过 Gradio 的公开 `/gradio_api/call/infer` 接口提交，接收任务事件后下载同一 Space 返回的图片。

官方页面：[FLUX.1-schnell Space](https://huggingface.co/spaces/black-forest-labs/FLUX.1-schnell)、[ZeroGPU 额度说明](https://huggingface.co/docs/hub/main/spaces-zerogpu)。匿名用户有每日 GPU 时间限制和较低队列优先级；额度政策及服务状态可能变化。无需密钥的调试已经成功，不承诺持续可用、无限免费或生产 SLA。

支持比例：3:2 → 768×512、1:1 → 640×640、2:3 → 512×768。图片可能为 WebP，应用校验实际内容并按实际格式下载。当前实际验证横幅；方形和竖幅参数通过适配器测试，尚未逐一进行真实出图。

免费 Space 只承诺文生图。因此“修改”是依据新画面描述重新生成，不能保证局部编辑或构图保持。每次均保存新版本，原图不覆盖。

文字理解默认 `local`：官方 [Qwen3-4B-GGUF](https://huggingface.co/Qwen/Qwen3-4B-GGUF) 的 Q4_K_M 文件，经官方 [llama.cpp server](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) 在本机 CPU 提供结构化响应。两个请求分别理解文字和构思画面；图像仍由 FLUX 生成。安装脚本固定模型修订与 llama.cpp b10025 运行版本并校验 SHA256。结构化输出须使用有界且不接受未转义 JSON 引号的字符串模式；普通正则的无限匹配不适合直接作为生成语法。没有收费文字 API、权重微调或自动切换收费服务；默认模型能力仍有限，用户需核对解释和图片。

旧 `basic` 为本地中英文关键词匹配，保留为调试接口。未识别到意象时现在会停止生成并提示接入语言模型，避免用任意草地代替原文。关键词模式仍不能可靠理解隐喻、否定或时序。所有新画面方案须保留提取的每个原文意象，画面元素直接加入提示词；界面可以展开查看对应依据。

曾实际尝试官方公共 Qwen 文字演示，模型服务返回错误，因此未把不可靠演示设为默认。Hugging Face Inference Providers 当前免费账号没有每月包含额度，不能把其路由当作免费接口；详见[官方价格说明](https://huggingface.co/docs/inference-providers/pricing)。HF Token 只用于已有免费 Space 身份认证。

备选 Gemini：实现结构化文字响应和参考图图像请求，测试覆盖请求格式、图片解码及错误处理；未创建账号，未真实调用付费 API。图像价格与模型可用性以 [官方价格说明](https://ai.google.dev/gemini-api/docs/pricing) 和 [图像生成文档](https://ai.google.dev/gemini-api/docs/image-generation) 为准。

兼容 API：实现 `chat/completions` JSON 输出、`images/generations` base64/允许主机图片 URL。不同供应商兼容程度不一，换服务后应先验证结构化输出和一张图，不承诺任意接口均可直接使用。

所有供应商均不自动重试。超时、网络中断或结果不明时保存“需核查”；额度不足等明确失败显示错误。图片的真实性和文学氛围目前由人工看图评价，自动视觉评估适配器留待后续接入。
