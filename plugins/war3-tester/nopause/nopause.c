/* ============================================================================
 * nopause.c - war3 防失焦暂停（窗口子类化版，最终版）
 * ============================================================================
 * 机制：war3 失焦暂停靠窗口消息触发--收到 WM_ACTIVATEAPP(FALSE) /
 *   WM_ACTIVATE(WA_INACTIVE) 后进入暂停状态。不是 Sleep，也不是
 *   GetForegroundWindow 轮询（两者均已实测排除）。
 * 做法：子类化 war3 主窗口，吞掉这两个失焦/失活通知，war3 误判始终前台，
 *   失焦不暂停（后台挂机）。
 * 注：WM_KILLFOCUS 经实测不参与触发，不吞--保护输入框/对话框的键盘焦点。
 *
 * 部署链路：dll 编译进地图产物，改 map/nopause.dll 后必须 compile_map 重编地图，
 *   否则运行时仍解包旧 dll 到 Temp。
 * 编译：MinGW i686（PATH 前置 /c/msys64/mingw32/bin），
 *   gcc -O2 -shared -static -o nopause.dll nopause.c -luser32
 *   注意 MinGW 不支持 MSVC 的 __try/__except，用 IsBadReadPtr 替代。
 * ==========================================================================*/

#include <windows.h>
#include <stdint.h>
#include <stdio.h>

typedef struct lua_State lua_State;

static void dbg_file(const char *msg)
{
    FILE *f = fopen("D:\\maps\\wzns\\map\\nopause.log", "a");
    if (f) { fprintf(f, "%s\n", msg); fclose(f); }
}

static WNDPROC g_orig_proc = NULL;

static LRESULT CALLBACK hook_wndproc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp)
{
    /* 吞掉失焦/失活通知，让 war3 以为始终前台。
     * 不吞 WM_KILLFOCUS（实测不参与触发，保护输入框/对话框键盘焦点）。*/
    if (msg == WM_ACTIVATEAPP && wp == FALSE) return 0;
    if (msg == WM_ACTIVATE && LOWORD(wp) == WA_INACTIVE) return 0;
    return CallWindowProc(g_orig_proc, hwnd, msg, wp, lp);
}

__declspec(dllexport) int __cdecl luaopen_nopause(lua_State *L)
{
    (void)L;
    HWND war3 = FindWindowA("Warcraft III", NULL);
    char buf[256];
    sprintf(buf, "nopause: war3_wnd=%p", war3);
    dbg_file(buf);
    if (!war3) { dbg_file("ABORT: war3 window not found"); return 0; }

    g_orig_proc = (WNDPROC)SetWindowLongPtrA(war3, GWLP_WNDPROC, (LONG_PTR)hook_wndproc);
    if (!g_orig_proc) {
        sprintf(buf, "SetWindowLongPtr FAILED err=%lu", GetLastError());
        dbg_file(buf);
        return 0;
    }
    sprintf(buf, "nopause OK: orig_proc=%p -> hook_proc=%p",
            (void *)g_orig_proc, (void *)hook_wndproc);
    dbg_file(buf);
    return 0;
}

BOOL WINAPI DllMain(HINSTANCE h, DWORD r, LPVOID v)
{
    (void)h; (void)r; (void)v;
    return TRUE;
}
