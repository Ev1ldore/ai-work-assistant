"""微信适配器统一协议。

职责：定义 WeChatAdapter 抽象接口 —— receive()（拉取新消息）、send()（发送）、
     status()（连接与窗口可用性）、readback()（重读窗口用于发送确认）。
约束：实现可替换（mock / macOS AX），上层只依赖此协议。
TODO: 待实现。
"""
