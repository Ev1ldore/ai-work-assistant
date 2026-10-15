# AGENTS.md — 给接手本项目的 AI / 工程师

> **动代码之前先读完本文。** 本文记录环境事实、红线、已定决策与当前状态。
> 本文只写实测与已决内容，不含推测。

最后更新：2026-10-15

---

## 0. 项目 TDD Skill 与交接约束

本节是已确定的项目执行规范，不代表下列测试或功能已经完成。

- 实现、修复、测试或交付微信 Agent 时，先阅读 [.agents/skills/wechat-agent-tdd/SKILL.md](.agents/skills/wechat-agent-tdd/SKILL.md)，按需读取其测试计划。仅要求审阅或编写文档时，不自动实施代码。
- 即使当前 Agent 不支持自动发现 Skill，也须遵守该入口规定的项目约束；支持 Skill 的 Agent 可用 `$wechat-agent-tdd` 调用。
- 先核对源码与实际测试，再选择最小未完成行为，完成红灯、绿灯、重构。空测试、未收集到测试和缺依赖均不能算行为验证通过。
- 所有自动化 LLM 调用均 mock；真实收发另行验收。发送未知须暂停、不重发；群 @ 只进入人工队列；重启不能解除熔断或补发积压。
- 每次实施结束更新 [docs/tdd-progress.md](docs/tdd-progress.md)，记录测试编号、实际命令和结果、阻塞、下一步。不能伪造历史红灯或沿用过时的“已完成”结论。
- Skill 不扩大当前任务授权，不自动授予微信操作、系统权限、真实数据上传、Git 提交、推送或公开仓库的权限。

## 1. 项目是什么

macOS 上运行的个人微信**私聊**自动回复 Agent（招聘笔试 MVP）：监听消息 → 过滤 → 意图识别 → LLM 回复 → 发送确认，带短期与长期记忆，支持知识库查询与受控工具接口。

**不是**：企业微信 / 公众号方案（不得擅自改用）；不是群聊机器人（群消息一律跳过）；不读微信本地数据库。

## 2. 本机实测环境（2026-10-15 实测，非推断）

| 项 | 实测值 | 备注 |
| --- | --- | --- |
| macOS | 26.6.2 (build 25G83) | |
| 芯片 | Apple M5, arm64 | |
| Python（默认 `python3`） | anaconda3 **3.14.6** | ⚠️ **pyobjc 在此环境下不可用**（`import objc` 报 dyld 错误：找不到 `libffi.8.dylib`）。**不要用它。** |
| Python（应使用） | `~/.local/bin/python3.11` → **3.11.15** | ✅ 统一用这个建 venv |
| 微信 | **4.1.13**（CFBundleVersion 269602），`com.tencent.xinWeChat` | 实测版本，目前正在运行 |
| 电源策略 | `sleep 0`（系统不休眠）、`displaysleep 60` | 便于测试熄屏场景 |

## 3. 红线（不得违反）

1. 不读取或解密微信本地数据库，不提取登录凭证，不 hook / 注入客户端，不使用已失效的网页版协议，不绕过安全限制。
2. 本项目自建的 SQLite 记忆库**不属于**微信本地数据库，可以正常使用。
3. 开发、测试、演示**只用备用测试小号**，禁止日常主号。
4. 新增系统权限必须先说明用途并征得同意。
5. **不得编造**准确率、性能、测试通过记录或兼容范围。只对实测版本给结论，其余一律「未验证」。
6. mock 测试通过**不能**代替真实微信验收。
7. 不伪造 commit 历史，不擅自推送或公开仓库。
8. 敏感信息只走 `.env`，代码中不硬编码。

## 4. 关键决策与理由

| # | 决策 | 理由 / 备选 |
| --- | --- | --- |
| D1 | 接入默认走 **macOS Accessibility（AX）UI 自动化** | 不注入、不 hook、不改微信本体，封号风险最低；跨版本差异收敛到 `selectors.py` 一层。备选 A′：截图 + Apple Vision OCR |
| D2 | **微信 4.1.13 的 AX 可读性是最大未知** | 微信 Mac 4.0 是重写版本（进程模块名 `xwechat_mac`）。**未实测前不得假设可读**，Day 0 必须先 spike |
| D3 | FAQ 匹配用 **jieba + BM25 / 字符 n-gram**，不用 embedding | 纯本地、确定性、零 API 依赖，保住「自动化测试全 mock、结果确定」；embedding 会引入外部依赖 |
| D4 | 合成消息 ID = hash(会话 ID + 发送者 + 文本 + 时间桶) | UI 取不到内部消息 ID。**同桶完全相同消息仍会碰撞**，README 须照实声明 |
| D5 | 去重 = 合成 ID + 滑动时间窗 + **顺序感知增量比对** | 只处理上一轮已见消息的有序列表的尾部增量，降低碰撞率；**但仍不能归零** |
| D6 | 提示注入防线在**架构**，不在 prompt | 白名单 / 运行模式 / 权限均来自 `.env` 与本地配置，LLM 输出只作为「候选回复文本」流入发送策略，无权触达控制状态；工具走白名单注册表 |
| D7 | 发送结果三态：成功 / 失败 / **未知** | 发送后重读同一窗口确认消息在列表中 → 本地发送成功；无法确认 → 未知，暂停该会话并要求人工核查，不盲目重发 |
| D8 | LLM 只做兜底生成 | 关键词规则与 FAQ 匹配能处理时不调用 LLM |
| D9 | 短期记忆只做**有界近期窗口** | LLM 对话摘要属扩展项，本阶段不实现，不要在实现中偷偷加上 |

**待确认的边界**：跨时间桶边界的那条消息，会因桶号不同生成两个合成 ID，可能被处理两次。拟按「桶宽可配 + 边界消息二次确认」实现，语义写入 README —— 此为待确认项，非最终结论。

## 5. 目录结构与模块职责

```
ai-work-assistant/
├── .env.example            # 全部可配置项（敏感信息与阈值唯一入口）
├── pyproject.toml          # 依赖与打包的唯一事实来源（版本号待 Day 0 锁定）
├── requirements*.txt       # 供不使用 package install 的场景
├── AGENTS.md               # 本文档
├── README.md               # 交付文档（骨架，待填）
├── docs/
│   ├── decisions.md        # 决策记录（ADR）
│   ├── acceptance.md       # 真实验收记录表（待实测填写）
│   ├── demo-script.md      # 演示视频脚本与检查表
│   └── extensions.md       # 语音 / 文件扩展思路（本阶段不实现）
├── scripts/
│   ├── check_env.py        # 环境与版本采集
│   ├── spike_ax_dump.py    # Day 0：dump AX 元素树，判定可读性
│   └── spike_ocr.py        # Day 0：截图 + OCR 备选方案验证
├── src/wxagent/
│   ├── config.py           # 配置加载与校验（唯一读 os.environ 处）
│   ├── models.py           # 统一消息结构 Message / Direction / MessageType
│   ├── ids.py              # 合成消息 ID 生成
│   ├── logging_setup.py    # 日志与脱敏
│   ├── cli.py              # 命令行入口
│   ├── adapters/
│   │   ├── base.py         # WeChatAdapter 协议：receive / send / status / readback
│   │   ├── mock.py         # Mock 适配器（离线测试与开发）
│   │   └── macos_ax/
│   │       ├── adapter.py      # AX 适配器实现
│   │       ├── tree.py         # AX 元素树遍历
│   │       ├── selectors.py    # 微信版本选择器适配层
│   │       └── window.py       # 窗口 / 锁屏 / 最小化状态检测
│   ├── pipeline/
│   │   ├── filter.py       # 白名单 / 垃圾 / 自发消息 / 非文本 / 群消息
│   │   ├── dedup.py        # 合成 ID + 滑动窗口 + 顺序感知
│   │   ├── dispatcher.py   # 同会话有序，跨会话有限并发
│   │   └── runner.py       # 主循环（可配置轮询间隔）
│   ├── agent/
│   │   ├── core.py         # 编排：路由 → 知识 → LLM 兜底 → 记忆
│   │   ├── intent.py       # 三类意图：闲聊 / FAQ / 人工接管
│   │   ├── llm.py          # 可替换供应商的客户端，异常归一化
│   │   ├── prompt.py       # 提示模板 + 不可信输入隔离
│   │   └── knowledge/
│   │       ├── faq.py      # 本地确定性 FAQ 检索
│   │       └── data/faq.yaml  # 虚构 FAQ 数据
│   ├── memory/
│   │   ├── short_term.py   # 有界近期窗口
│   │   ├── long_term.py    # SQLite，按联系人隔离 + TTL
│   │   └── schema.sql      # 表结构（待定义）
│   ├── sending/
│   │   ├── policy.py       # dry_run / confirm / auto
│   │   ├── limiter.py      # 限速 / 超时 / 长度
│   │   ├── circuit_breaker.py  # 每小时上限 + 连续上限
│   │   └── verify.py       # 发送后读回确认
│   ├── handoff/queue.py    # 人工确认队列与接管
│   └── tools/registry.py   # 受控工具白名单注册表
├── tests/                  # 18 个文件，按验收条目切分，LLM 全部 mock
└── var/                    # 运行时数据（记忆库 / 日志），.gitignore 忽略
```

## 6. 当前状态

**已完成**：目录结构、包标记、各模块占位文件（仅含职责 docstring 与 TODO）、配置文件、文档骨架。

**未完成**：全部实现代码、全部测试、Day 0 验证、真实验收、演示视频、README 正文。

**注意**：`src/` 下所有 `.py` 均为仅含 docstring 的占位文件，**尚未实现任何逻辑**。

## 7. 待出题方确认（禁止代填）

1. 允许的微信接入方式及目标版本 —— 未确认前按 D1 的 AX 方案推进。
2. 独立机器人 vs 代个人账号回复现有联系人。
3. 全自动 vs 人工确认。
4. **截止日期** —— 影响范围裁剪。

## 8. Day 0 待办（最高优先级，结论决定后续）

1. 用 `~/.local/bin/python3.11` 建 venv，实装 pyobjc 并验证 `import objc` 可用。
2. 开设辅助功能权限，运行 `scripts/spike_ax_dump.py` dump 微信 4.1.13 的 AX 树 → **判定消息列表能否被读取**。
3. 运行 `scripts/spike_ocr.py` 作为 A′ 对照。
4. 实测三项能力：读取新私聊文本 / 定位正确会话 / 发送后重读确认。
5. 收发验证优先用**文件传输助手**（不需要第二个账号）。

## 9. 变更记录

| 日期 | 变更 |
| --- | --- |
| 2026-10-15 | 初始化项目骨架：目录结构、模块占位、配置文件、文档骨架。无实现代码。 |
| 2026-10-15 | 补 `docs/extensions.md`（语音 / 文件扩展思路），补 `var/` 子目录占位与 `.gitignore` 规则。 |
| 2026-10-15 | 增加项目 TDD Skill 入口与交接记录；只新增开发约束和测试方案，未实现业务功能。 |
