"""统一消息结构。

职责：定义 Message（消息 ID / 会话 ID / 发送者 / 方向 / 时间 / 类型 / 文本），
     以及 Direction、MessageType、会话运行状态（监听 / 暂停 / 熔断）等枚举。
约束：UI 自动化取不到微信内部消息 ID，message_id 为合成 ID，须保留其碰撞限制说明。
TODO: 待实现。
"""
