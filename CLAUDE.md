 # 输出语言规则

  - 思考过程（Thinking）必须用中文表述。
  - 所有回复（Reply）必须用中文。
  - 使用 `/init` 命令生成或更新的 `AGENTS.md` 也必须采用中文格式。
  - 紧急重要：ALWAYS RESPOND IN CHINESE（增强模型理解）。

  ---

  # 文件删除与危险操作规则

  1. 所有业务源码、配置文件、文档、资源目录、自定义文件、关键项目目录，禁止永久彻底删除。
  2. 非缓存类文件/文件夹需要删除时，必须移入系统回收站，禁止使用 `rm`、`rm -rf`、`del /f` 等永久删除命令。
  3. 缓存、临时目录、构建缓存、运行缓存可以直接删除，包括但不限于：
     - `.cache`
     - `.next/cache`
     - `.turbo`
     - `dist` 缓存
     - `build` 缓存
     - 依赖缓存
     - 日志缓存
  4. 任何删除操作若无法判断是否为缓存，默认移入系统回收站。
  5. 任何影响远程仓库、生产环境、共享数据库、CI/CD、用户数据的操作，必须先获得用户明确确认。
  6. 未经确认禁止执行：
     - `git push`
     - `git push --force`
     - `git reset --hard`
     - 删除分支
     - 删除数据库
     - 修改生产配置
     - 发布上线
     - 合并 PR
     - 关闭 issue/PR
     - 发送外部消息

  ---

  # Claude Code 总原则

  本文件用于 Claude Code 环境。

  - `CLAUDE.md` 只放硬规则、默认路由和优先级原则。
  - 详细 Skill / Agent 路由表可放在 `AGENTS.md` 或 `SKILL_ROUTING.md`。
  - 当用户要求选择 Skill、Agent 或开发流程时，优先参考当前可用能力，而不是机械照搬固定列表。
  - 不要引用当前 Claude Code 环境不支持的其他工具生态概念。
  - MCP 工具不是 slash Skill，不要写成 `/tool-name` 调用。
  - 不确定库、框架、SDK、API、CLI 用法时，必须优先查官方文档或 Context7。
  - 不确定项目代码现状时，必须读取当前文件、搜索代码或运行验证，不要只凭记忆。
  - 多文件改动、复杂功能、重构、疑难 bug、发布前验证，应优先使用最合适的 Skill 或 Agent。
  - 简单解释、单行修改、轻量查询，不要过度调用复杂 Skill 或 Agent。
  - 独立任务应并行执行，避免无必要串行等待。
  - 写代码后必须验证；涉及安全边界时必须安全审查。

  ---

  # Skill 选择总规则

  核心原则：**根据当前可用的全部 Skill / Agent / 工具，选择最适合当前任务的路线。**

  - 本文件列出的 Skill 是常用默认路由，不是唯一允许列表。
  - 如果当前环境新增了更适合任务的 Skill，应优先考虑新增 Skill。
  - 不要因为某个 Skill 没写在 `CLAUDE.md` / `AGENTS.md` 里就忽略它。
  - 不要因为某个旧 Skill 写在规则里就机械优先它。
  - 不要机械固定某一个 Skill 顺序。
  - 不要因为某个 Skill 常用，就忽略更适合当前任务的专项 Skill。
  - 用户显式输入 `/skill-name` 时，如果该 Skill 可用，必须调用。
  - 当用户请求明确匹配到可用 Skill 时，必须把调用 Skill 作为第一步操作。
  - 如果多个 Skill 都可能匹配，选择最贴近用户真实目标的一个作为主 Skill。
  - 如果新 Skill 与旧 Skill 功能相似，选择更贴近当前任务目标、能力更强、风险更低的一个作为主 Skill。
  - 如果本文档或其他规则中提到的 Skill 当前不可用，不得臆造调用。
  - 如果 Skill 不存在但任务仍可完成，使用最接近的可用 Skill、Agent 或普通工具。
  - 如果缺失的是强制流程 Skill，应告知用户缺失情况，并请求确认是否继续。
  - 修改 Claude Code settings、hooks、permissions、env vars 时，必须使用 `/update-config`。
  - 用户说“以后每次……”“当……时自动……”这类自动化需求，必须配置 hook，不能只靠记忆。
  - Claude API / Anthropic SDK 相关任务必须使用 `/claude-api`。
  - 查库、框架、SDK、CLI、云服务文档时优先使用 Context7，而不是凭记忆回答。
  - AI/ML、深度学习、模型训练、神经网络、第一性原理解释、教学式推导、清晰代码实现类任务，如果 `/andrej-karpathy-skills` 可用且适合，应优先考虑它。

  ---

  # 主 Skill 与辅助 Skill 规则

  同类 Skill 可以一起参考，但不要无脑一起调用。

  ## 原则

  - 每个任务必须有一个主 Skill 或主 Agent。
  - 主 Skill 负责流程、产出和最终决策。
  - 辅助 Skill 只提供检查清单、模式、补充建议或专项验证。
  - 如果两个 Skill 给出冲突建议，以更贴近当前任务、项目规则和用户目标的建议为准。
  - 如果两个 Skill 都想接管完整流程，只选一个作为主流程。
  - 同类 Skill 可以辅助参考，但只能有一个主 Skill 接管流程。

  ## 推荐组合

  前端 UI：

  ```text
  主：/huashu-design
  辅：/frontend-design、/frontend-patterns
  验：/ui-demo、/e2e、/e2e-testing

  Bug 修复：

  主：/superpowers:systematic-debugging（可用且适合时）
  辅：/investigate、/oh-my-claudecode:trace
  验：/superpowers:verification-before-completion 或 /verify

  API 开发：

  主：/api-design
  辅：/backend-patterns 或框架专项 Skill
  测：/superpowers:test-driven-development 或 /tdd
  审：/security-review

  Claude API：

  主：/claude-api
  辅：Context7 官方文档
  审：/security-review（涉及用户输入、密钥、外部调用时）

  AI / ML / 深度学习：

  主：/andrej-karpathy-skills（可用且适合时）
  辅：/python-patterns、/python-testing、/benchmark
  审：/security-review（涉及外部数据、模型服务、密钥时）

  避免多个同类 Skill 同时接管

  不要让这些组合同时都当主流程：

  /dev + /feature-dev + /prp-implement
  /tdd + /tdd-workflow + /superpowers:test-driven-development
  /ship + /github-ops + git-master 全部自动接管发布
  /frontend-design + /huashu-design 同时都生成完整 UI

  ---
  superpowers 使用规则

  如果当前环境支持 superpowers 系列 Skill，开发类任务默认优先考虑它们作为流程纪律。

  ┌──────────────────────────┬─────────────────────────────────────────────┬──────────────────────┐
  │           阶段           │                 优先 Skill                  │         作用         │
  ├──────────────────────────┼─────────────────────────────────────────────┼──────────────────────┤
  │ 新功能、修改、重构启动前 │ /superpowers:brainstorming                  │ 澄清需求、边界、风险 │
  ├──────────────────────────┼─────────────────────────────────────────────┼──────────────────────┤
  │ 编码、修复 bug 前        │ /superpowers:test-driven-development        │ 先测试，再实现       │
  ├──────────────────────────┼─────────────────────────────────────────────┼──────────────────────┤
  │ 遇到 bug、异常、报错时   │ /superpowers:systematic-debugging           │ 先找根因，再修复     │
  ├──────────────────────────┼─────────────────────────────────────────────┼──────────────────────┤
  │ 任务完成、准备提交前     │ /superpowers:verification-before-completion │ 有验证证据再声明完成 │
  ├──────────────────────────┼─────────────────────────────────────────────┼──────────────────────┤
  │ 收到代码审查反馈时       │ /superpowers:receiving-code-review          │ 理解反馈后再改       │
  ├──────────────────────────┼─────────────────────────────────────────────┼──────────────────────┤
  │ 准备合并、上线前         │ /superpowers:finishing-a-development-branch │ 收尾检查、合并前验证 │
  └──────────────────────────┴─────────────────────────────────────────────┴──────────────────────┘

  降级规则

  如果当前环境不支持对应 superpowers Skill，则使用 Claude Code 可用的等价能力：

  ┌─────────────────────────────────────────────┬──────────────────────────────────────────────────────────────┐
  │                 superpowers                 │                           降级选择                           │
  ├─────────────────────────────────────────────┼──────────────────────────────────────────────────────────────┤
  │ /superpowers:brainstorming                  │ /plan、/autoplan、planner agent                              │
  ├─────────────────────────────────────────────┼──────────────────────────────────────────────────────────────┤
  │ /superpowers:test-driven-development        │ /tdd、/tdd-workflow、tdd-guide agent                         │
  ├─────────────────────────────────────────────┼──────────────────────────────────────────────────────────────┤
  │ /superpowers:systematic-debugging           │ /investigate、/oh-my-claudecode:trace、debugger/tracer agent │
  ├─────────────────────────────────────────────┼──────────────────────────────────────────────────────────────┤
  │ /superpowers:verification-before-completion │ /verify、/quality-gate、verifier agent                       │
  ├─────────────────────────────────────────────┼──────────────────────────────────────────────────────────────┤
  │ /superpowers:finishing-a-development-branch │ /ship、/github-ops、git-master agent                         │
  └─────────────────────────────────────────────┴──────────────────────────────────────────────────────────────┘

  可跳过情况

  以下情况可以跳过完整流程：

  - 纯解释、纯查询、只读分析。
  - 用户明确要求“只回答，不修改”。
  - 单行文案、格式、注释、拼写修正。
  - 不涉及业务逻辑的轻量样式微调。
  - 已有明确测试失败、根因证据和修复方向的小修复。
  - 当前环境缺少对应 Skill，且用户确认继续。
  - 用户明确要求跳过流程。

  跳过时必须说明：

  已跳过 XX 流程，风险是 YY。

  ---
  Agent 使用规则

  必须主动使用 Agent 的情况：

  - 复杂功能、跨文件计划：planner
  - 架构决策：architect
  - 新功能或 bug 修复：tdd-guide
  - 写完代码：code-reviewer
  - 安全相关代码：security-reviewer
  - 构建失败：对应 build resolver
  - 数据库、SQL、migration：database-reviewer
  - 前端 E2E：e2e-runner
  - 性能问题：performance-optimizer
  - 文档和 codemap：doc-updater
  - 大范围清理：refactor-cleaner

  Agent 使用约束：

  - Agent 适合多文件、复杂、审查、验证、搜索、架构类任务。
  - 简单单文件小改动可以直接处理。
  - 独立 Agent 任务应并行启动。
  - Agent 写完代码后，主上下文必须检查实际 diff、文件内容、测试或命令输出。
  - 不能只相信 Agent 总结。
  - 自己写的代码不能自己直接批准，必须使用 reviewer/verifier 独立审查。
  - 如果当前环境新增了更适合任务的新 Agent，应优先考虑新 Agent，而不是只使用本文档列出的 Agent。

  ---
  默认开发流程

  新功能

  默认流程：

  需求澄清 → 规划 → 测试 → 实现 → 验证 → 代码审查 → 安全审查（如涉及安全边界）

  优先路由：

  - 流程纪律：优先 /superpowers:brainstorming，不可用时用 /plan、/autoplan、planner agent
  - 复杂规划：/blueprint、/prp-plan、/prp-prd
  - 新功能实现：/feature-dev、/dev、/prp-implement
  - 测试驱动：优先 /superpowers:test-driven-development，不可用时用 /tdd、/tdd-workflow
  - 完成验证：优先 /superpowers:verification-before-completion，不可用时用 /verify
  - 代码审查：/code-review、code-reviewer agent

  规则：

  - 超过 3 步、跨多个文件、涉及多个模块时，先规划。
  - 新功能默认先写或补测试。
  - 不要为简单功能引入复杂抽象。
  - 如果当前环境存在更适合该技术栈或任务类型的新 Skill，应优先考虑新 Skill。

  ---
  Bug 修复

  默认流程：

  调查根因 → 补回归测试 → 修复 → 验证 → 代码审查

  优先路由：

  - 根因分析：优先 /superpowers:systematic-debugging
  - 复杂调查：/investigate、/oh-my-claudecode:trace
  - 测试驱动：/superpowers:test-driven-development 或 /tdd
  - 构建失败：/build-fix 或对应 build resolver agent
  - 完成验证：/superpowers:verification-before-completion 或 /verify
  - 代码审查：/code-review、code-reviewer agent

  禁止：

  - 未定位根因就大改代码。
  - 只改测试来掩盖实现问题。
  - 跳过失败检查声称完成。
  - 用临时 hack 掩盖真实错误。

  ---
  前端 / UI

  默认流程：

  确定设计方向 → 实现 → 浏览器验证 → E2E/视觉检查 → 代码审查

  优先级：

  1. /huashu-design
  2. /frontend-design
  3. /frontend-patterns
  4. /ui-demo、/e2e、/e2e-testing
  5. 普通代码修改

  路由规则：

  - 新 UI、高保真原型、App/iOS 原型、交互 Demo、视觉方向探索，优先使用 /huashu-design。
  - 通用 Web 页面、组件、Landing Page，在 /huashu-design 不适用或不可用时使用 /frontend-design。
  - React、Next.js、状态管理、性能优化、前端规范问题使用 /frontend-patterns。
  - UI 完成后必须进行浏览器验证；可使用 /ui-demo、/e2e、/e2e-testing。
  - 小型样式修复、文案调整、已有组件微调，可以直接处理，不必强行调用设计 Skill。
  - 如果当前环境新增了更适合 UI、原型、视觉设计或交互 Demo 的 Skill，应优先考虑新 Skill。

  前端规则：

  - 新 UI 不能做模板感默认界面。
  - 必须考虑响应式、可访问性、键盘导航、焦点状态、reduced motion。
  - 动画优先使用 transform、opacity 等合成层友好属性。
  - UI 改动完成后，应启动 dev server 并在浏览器中验证。
  - 如果无法浏览器验证，必须明确说明。

  ---
  后端 / API / 数据库

  默认流程：

  明确接口契约 → 实现 → 测试 → 安全审查 → 数据库审查（如涉及）→ 验证

  优先路由：

  - API 设计：/api-design
  - 后端模式：/backend-patterns 或对应框架 Skill
  - 第三方 API：/api-connector-builder
  - 数据库迁移：/database-migrations
  - PostgreSQL：/postgres-patterns
  - 数据库审查：database-reviewer agent
  - 安全审查：/security-review、security-reviewer agent

  规则：

  - 新 API 必须明确请求/响应 schema。
  - 用户输入必须在边界验证。
  - SQL 必须参数化。
  - 表结构变更必须评估锁表、回滚、数据迁移、并发写入。
  - 涉及生产数据风险时，不得擅自执行 destructive 操作。
  - 如果当前环境有更适合具体框架、数据库或 API 类型的 Skill，应优先考虑该专项 Skill。

  ---
  测试规则

  - 新功能和 bug 修复默认走 TDD。
  - 优先使用 /superpowers:test-driven-development；不可用时用 /tdd、/tdd-workflow 或 tdd-guide agent。
  - 默认目标覆盖率不低于 80%，除非项目另有配置。
  - 单元测试覆盖核心逻辑。
  - 集成测试覆盖 API、数据库、外部边界。
  - E2E 测试覆盖关键用户路径。
  - 测试失败时优先修实现，不随意修改测试。
  - 如果无法运行测试，必须说明原因和风险。
  - 不允许删除、跳过或弱化测试来制造通过结果。
  - 如果当前环境新增了更适合当前技术栈的测试 Skill，应优先考虑新 Skill。

  ---
  代码审查规则

  写代码后必须审查。

  优先路由：

  - 通用代码审查：/code-review、code-reviewer agent
  - TypeScript / JavaScript：typescript-reviewer
  - Python：python-reviewer
  - Go：go-reviewer
  - Rust：rust-reviewer
  - Java：java-reviewer
  - Kotlin：kotlin-reviewer
  - Flutter / Dart：flutter-reviewer
  - C++：cpp-reviewer
  - C#：csharp-reviewer
  - 数据库 / SQL：database-reviewer
  - 安全敏感代码：security-reviewer

  审查重点：

  - 正确性
  - 安全性
  - 类型安全
  - 错误处理
  - 测试覆盖
  - 可维护性
  - 是否有过度抽象
  - 是否有硬编码密钥
  - 是否有 silent failure

  CRITICAL / HIGH 问题必须修复后再声明完成。

  如果当前环境新增了更适合当前语言、框架或审查类型的 reviewer Skill / Agent，应优先考虑新能力。

  ---
  安全规则

  涉及以下内容必须安全审查：

  - 登录、注册、认证、授权
  - 用户输入处理
  - API endpoint
  - 数据库查询
  - 文件上传/下载
  - 外部 API 调用
  - Webhook
  - 加密、签名、token
  - 支付或金融逻辑
  - 敏感数据、PHI、PII

  安全要求：

  - 禁止硬编码 API key、密码、token、私钥。
  - 所有用户输入必须在系统边界验证。
  - SQL 必须参数化。
  - 禁止注入未净化 HTML。
  - 错误信息不能泄露敏感细节。
  - 文件路径必须防路径穿越。
  - 权限逻辑必须显式验证。
  - 涉及 PHI/医疗数据时，必须使用 HIPAA/PHI 相关检查或 healthcare-reviewer agent。
  - 如果当前环境新增了更适合当前风险类型的安全 Skill，应优先考虑新 Skill。

  ---
  AI / ML / Andrej Karpathy Skill 规则

  涉及以下内容时，应优先考虑 `/andrej-karpathy-skills`（如果当前环境可用且适合）：

  - 神经网络、深度学习、Transformer、LLM、tokenizer
  - PyTorch、JAX、训练循环、梯度、优化器
  - 模型调试、loss 异常、过拟合、欠拟合
  - 从零实现算法或教学式解释
  - 需要第一性原理推导、简洁代码、可视化理解
  - AI/ML 代码重构成更清晰、更可学习的实现

  推荐组合：

  主：/andrej-karpathy-skills
  辅：/python-patterns、/python-testing
  验：/benchmark 或项目测试
  审：/security-review（涉及外部数据、模型服务、密钥时）

  规则：

  - 教学和原理解释优先清晰、可运行、可验证。
  - 训练相关修改必须关注数据泄漏、随机种子、评估集隔离、指标可信度。
  - 涉及外部模型 API、密钥、用户数据时必须安全审查。
  - 如果 `/andrej-karpathy-skills` 不可用，不得假装调用；使用当前最合适的 Python/ML/测试能力替代。

  ---
  Claude API / SDK 规则

  涉及以下内容时必须使用 /claude-api，或当前环境中更适合 Claude / Anthropic SDK 的最新 Skill：

  - anthropic
  - @anthropic-ai/sdk
  - Claude API
  - Anthropic SDK
  - Managed Agents
  - prompt caching
  - tool use
  - thinking
  - batch
  - files
  - citations
  - memory
  - Claude 模型版本迁移

  规则：

  - 必须查最新官方文档。
  - 默认考虑 prompt caching。
  - 不确定 API 细节时不要凭记忆实现。
  - 涉及用户输入、密钥、外部调用时，额外使用 /security-review。

  ---
  Git 与发布规则

  简单只读 git 命令可直接执行：

  git status
  git diff
  git log
  git branch

  高风险 git 操作必须先确认：

  git commit
  git push
  git push --force
  git reset --hard
  git rebase
  git merge
  git branch -D

  规则：

  - 只有用户明确要求时才 commit。
  - 只有用户明确要求时才 push。
  - 只有用户明确要求时才创建 PR。
  - 不允许跳过 hook。
  - 不允许未经确认 force push。
  - 不允许 force push 到 main/master。
  - commit 前必须检查 diff 和 status。
  - 创建 PR 前必须分析完整 diff 和提交历史。
  - 不要把 .env、密钥、凭据文件加入提交。
  - 发布、部署、合并 PR 前必须获得用户明确确认。
  - 如果当前环境新增了更适合 Git、PR、发布或部署的 Skill，应优先考虑新 Skill，但仍必须遵守确认规则。

  ---
  文档规则

  - 用户明确要求文档时才创建新的 .md 文件。
  - 修改公共 API、CLI、配置、部署流程时应同步更新文档。
  - 项目结构变化较大时可更新 codemap。
  - 文档应简洁准确，不写容易过期的实现细节。
  - 不要把临时计划写成永久文档，除非用户要求。
  - 详细 Skill / Agent 路由表可放在 AGENTS.md 或 SKILL_ROUTING.md，不要把所有路由细节塞进 CLAUDE.md。
  - 如果当前环境新增了更适合文档生成、文档审查或 codemap 的 Skill，应优先考虑新 Skill。

  ---
  冲突处理规则

  优先级从高到低：

  1. 用户当前明确指令。
  2. 安全与危险操作规则。
  3. 删除规则。
  4. 项目 CLAUDE.md。
  5. AGENTS.md 或 SKILL_ROUTING.md 详细路由表。
  6. 当前可用 Skill / Agent 的实际能力。
  7. 项目代码现状。
  8. 记忆和历史经验。

  补充规则：

  - 安全规则优先于开发速度。
  - 删除规则优先于清理效率。
  - 用户显式指定的 Skill 优先。
  - 最适合当前任务的 Skill 优先，而不是机械固定顺序。
  - 本文件列出的 Skill 是默认推荐，不是唯一允许列表。
  - 新增 Skill 如果更适合当前任务，应优先考虑。
  - superpowers 可用且适合时，优先作为流程纪律。
  - /huashu-design 可用且适合时，优先用于 UI、原型、交互 Demo。
  - /andrej-karpathy-skills 可用且适合时，优先用于 AI/ML、深度学习、第一性原理解释和清晰实现。
  - Context7 官方文档优先于记忆。
  - 当前代码状态优先于历史记忆。
  - 不确定时先问用户，不要擅自执行高风险操作。

  ---
  禁止事项

  - 不要在未明确需求时直接写代码。
  - 不要跳过测试、验证、审查后声称完成。
  - 不要为简单任务引入复杂抽象。
  - 不要为了通过检查而删除测试或降低测试强度。
  - 不要用临时兼容 hack 掩盖真实错误。
  - 不要在未查文档的情况下猜测 SDK/API 行为。
  - 不要在用户未要求时创建大量文档。
  - 不要永久删除非缓存文件。
  - 不要未经确认执行 push、merge、release、deploy、force push。
  - 不要把 MCP 工具伪装成 slash Skill。
  - 不要调用当前环境不存在的 Skill。
  - 不要因为 Skill 没写在本文档中就忽略它。
  - 不要因为旧 Skill 写在本文档中就机械优先它。
  - 不要把 Agent 或 Skill 总结当成事实，必须验证实际文件、diff、测试或命令输出。

  ---
  完成定义

  一个开发任务只有同时满足以下条件，才可以声明完成：

  1. 需求已满足。
  2. 相关测试已运行并通过，或已说明为什么无法运行。
  3. 构建、类型检查、lint 已按项目实际情况验证。
  4. 代码已审查，重大问题已处理。
  5. 涉及安全边界时已做安全检查。
  6. UI 改动已进行浏览器或 E2E 验证，或已明确说明无法验证。
  7. 没有遗留未说明的风险。
  8. 没有擅自执行高风险操作。
  9. 没有未完成的关键任务。
  10. 回复中必须简洁说明验证证据。