# nopause-dll - war3 防失焦暂停 DLL

> 目标：war3 1.27 切窗口/最小化时不暂停游戏（后台挂机）。
> 方案：窗口子类化，吞掉 war3 的失焦/失活窗口消息。

## 机制（已实测确认）

war3 失焦暂停靠**窗口消息**触发--不是 Sleep，也不是 GetForegroundWindow 轮询：
- 失焦时 war3 窗口收到 `WM_ACTIVATEAPP(FALSE)` / `WM_ACTIVATE(WA_INACTIVE)`，据此进入暂停/降帧状态。
- 子类化 war3 主窗口，吞掉这两个消息，war3 误判始终前台，失焦不暂停。
- `WM_KILLFOCUS` 经实测不参与触发，不吞--保护输入框/对话框的键盘焦点。

排过的坑（都无效）：
- ❌ 全禁 Sleep（IAT patch `Sleep -> ret4 空函数`）：失焦仍暂停，Sleep 非根因。
- ❌ hook `GetForegroundWindow` 返回 war3 窗口：失焦仍暂停，war3 不轮询前台。
- ❌ 只吞 `WM_ACTIVATEAPP` 一个：仍暂停，`WM_ACTIVATE(WA_INACTIVE)` 也参与触发。
- ❌ 早期 `E8 -> (51 FF 15 + IAT->kernelbase.Sleep)` 模式匹配：war3 的 IAT 指向 `kernel32.Sleep`（地址与 `kernelbase.Sleep` 不同），且 war3 不通过 Sleep wrapper 降帧，模式全错。

## 编译（MinGW 32 位）

war3 是 32 位进程，DLL 必须 32 位。MSYS2 mingw32：

```bash
export PATH="/c/msys64/mingw32/bin:$PATH"
cd D:/maps/wzns/tools/nopause-dll
gcc -O2 -shared -static -o nopause.dll nopause.c -luser32
```

- **PATH 必须前置 mingw32/bin**，否则 gcc 找不到 as/ld/cc1 子进程，静默失败（exit=1 无输出）。
- `-static` 静态链 libgcc，避免依赖 `libgcc_s_dw2-1.dll`。
- MinGW 不支持 MSVC 的 `__try/__except`，用 `IsBadReadPtr` 替代（本版子类化用不到，IAT 扫描版需要）。
- MSVC `cl.exe` 在本机缺 Windows SDK 10（`C:\Program Files (x86)\Windows Kits\10` 不存在），编不了含 `windows.h` 的程序；要用 MSVC 得先装 SDK 组件。
- 警告：`cmd /c ... | head` 会让 `$?` 变成 head 的退出码，掩盖编译失败。判断编译成败看 dll 是否生成。

## 部署

dll 被编译进地图产物 `MoeHero.w3x`，运行时解包到 `%TEMP%\nopause.dll`。
所以改 `map/nopause.dll` 后**必须 `compile_map` 重编地图**，否则运行时仍解包 Temp 里的旧 dll。
`map/plugin_main.lua:23` 的 `require'nopause'` 加载它。

## 加载验证

`require'nopause'` 触发 `luaopen_nopause`，写日志到 `D:\maps\wzns\map\nopause.log`：

```
nopause: war3_wnd=05b21064
nopause OK: orig_proc=30472760 -> hook_proc=77ce1480
```

成功后 Alt+Tab 切窗口，游戏不暂停。

## 副作用

- 只吞 `WM_ACTIVATEAPP` / `WM_ACTIVATE`，不吞 `WM_KILLFOCUS`，输入框/对话框的键盘焦点行为正常。
- 单机挂机可接受。

## 风险

DLL 注入性质：对战平台会判外挂。单机/测试用 OK，**别上平台**。
