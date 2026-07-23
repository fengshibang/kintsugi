# 通信协议继续 HTTP,不升级自定义 TCP

war3-tester 的 AI↔游戏通信基于 HTTP(`socket.dll` = LuaSocket,`http_socket.lua` 在原始 TCP 上手写 HTTP 协议)。评估过升级为自定义 TCP 长连接(降延迟 / 省 connect 开销),**决定继续用 HTTP**:`exec_game` / `inspect_game` 复用现有 inspect HTTP 通道(pending 队列 + `/inspect/pending` `/inspect/result`)。

## 理由

war3 单线程 + LuaSocket 同步阻塞,自定义协议本质上**还是要轮询**(游戏端 `ac.loop` non-blocking recv),主要收益只是省 connect 开销 + 把 200ms 轮询压到 `ac.loop` 间隔(可 50ms)。当前 TDD 场景(AI 操控造测试条件,非实时对战)200ms 轮询够用,无实打实痛点(用户确认)。HTTP 已工作且有熔断保护(`auto-test/init.lua` 的 `_safe_post`,8766 不可用不拖死游戏)。协议升级是独立的性能优化,不该阻塞主体需求。

## 何时推翻

若 `exec_game` 操控延迟在真实 TDD 闭环里成瓶颈,升级方向是长连接 TCP(`ac.loop` non-blocking recv),届时用 `/prototype` 验证 war3 长连接稳定性再定。

_Status: accepted(当前)。未来若痛点出现,由新 ADR supersede。_
