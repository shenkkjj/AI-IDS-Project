# 输出语言规则
- 思考过程(Thinking)必须用中文表述
- 所有回复(Reply)必须用中文
- 使用/init命令生成的AGENTS.md也采用中文格式
- 紧急重要：ALWAYS RESPOND IN CHINESE（增强模型理解）

## Skill routing

当用户的请求匹配到可用的skill时，始终使用Skill工具作为你的第一个操作。不要直接回答，不要先使用其他工具。Skill有专门的工作流，比临时回答产生更好的结果。

关键路由规则：
- 产品创意、"是否值得构建"、头脑风暴 → 调用 office-hours
- Bug、错误、"为什么坏了"、500错误 → 调用 investigate
- Ship、部署、推送、创建PR → 调用 ship
- QA、测试网站、找bug → 调用 qa
- 代码审查、检查diff → 调用 review
- 运输后更新文档 → 调用 document-release
- 周回顾 → 调用 retro
- 设计系统、品牌 → 调用 design-consultation
- 视觉审计、设计优化 → 调用 design-review
- 架构审查 → 调用 plan-eng-review
- 保存进度、检查点、恢复 → 调用 checkpoint
- 代码质量、健康检查 → 调用 health

## gstack

Use /browse from gstack for all web browsing. Never use mcp__claude-in-chrome__* tools.

Available skills:
- /office-hours - 产品头脑风暴
- /plan-ceo-review - CEO模式计划审查
- /plan-eng-review - 工程经理模式计划审查
- /plan-design-review - 设计师视角计划审查
- /plan-devex-review - 开发者体验计划审查
- /design-consultation - 设计咨询
- /design-shotgun - 设计探索
- /design-html - 设计转HTML
- /design-review - 设计QA
- /devex-review - 开发者体验审计
- /review - 代码审查
- /ship - 发布工作流
- /land-and-deploy - 合并并部署
- /canary - 部署后监控
- /benchmark - 性能基准测试
- /browse - 浏览器自动化
- /open-gstack-browser - 打开GStack浏览器
- /connect-chrome - 连接Chrome
- /qa - QA测试
- /qa-only - 仅报告QA
- /setup-browser-cookies - 设置浏览器Cookies
- /setup-deploy - 配置部署
- /retro - 周回顾
- /investigate - 调试调查
- /document-release - 文档发布
- /codex - Codex第二意见
- /cso - 安全审计
- /autoplan - 自动审查管道
- /careful - 安全警告
- /freeze - 冻结编辑
- /guard - 完整安全模式
- /unfreeze - 解冻编辑
- /gstack-upgrade - 升级gstack
- /learn - 项目学习管理