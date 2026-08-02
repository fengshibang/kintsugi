"""ffmpeg 包装接口与实现。

- FfmpegWrapper:Protocol(deps 注入位)
- FfmpegCliWrapper:真实实现,subprocess 调 ffmpeg(探测用 `ffmpeg -i` 解析 stderr,
  避免对 ffprobe 的硬依赖;有 ffprobe 时也可换用)
- MockFfmpegWrapper:无 ffmpeg 环境的 mock(轨有无/抽帧可配)
"""
from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
import tempfile
from typing import Protocol


def ensure_ffmpeg_on_path() -> None:
    """确保 ffmpeg 在 PATH(供 subprocess 调用)。

    优先级:已在 PATH > 环境变量 VIE_FFMPEG_BIN > WinGet Packages 下 *FFmpeg* 包。
    winget 装的或本机已有的 ffmpeg.exe 未必在当前进程 PATH(进程启动早于安装/未配 PATH),
    故提供 VIE_FFMPEG_BIN 供显式指定 ffmpeg.exe 所在目录。
    """
    if shutil.which("ffmpeg"):
        return
    env_bin = os.environ.get("VIE_FFMPEG_BIN")
    if env_bin and os.path.isfile(os.path.join(env_bin, "ffmpeg.exe")):
        os.environ["PATH"] = env_bin + os.pathsep + os.environ.get("PATH", "")
        return
    localappdata = os.environ.get("LOCALAPPDATA", "")
    base = os.path.join(localappdata, "Microsoft", "WinGet", "Packages")
    candidates = glob.glob(os.path.join(base, "*FFmpeg*", "*", "bin"))
    candidates += glob.glob(os.path.join(base, "*FFmpeg*", "bin"))
    for d in candidates:
        if os.path.isfile(os.path.join(d, "ffmpeg.exe")):
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
            return


class FfmpegWrapper(Protocol):
    """ffmpeg 包装:探测时长 / 视频音频轨 / 抽帧 / 切片段。"""

    def get_duration(self, video_path: str) -> float: ...

    def has_video_track(self, video_path: str) -> bool: ...

    def has_audio_track(self, video_path: str) -> bool: ...

    def extract_frames(self, video_path: str) -> list[str]: ...

    def slice_segment(
        self, video_path: str, start: float, duration: float, out_path: str
    ) -> None: ...


def _run(cmd: list[str]) -> str:
    """跑命令返回 stdout;非 0 退出码抛 RuntimeError 含 stderr。"""
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"命令失败(returncode={proc.returncode}): {' '.join(cmd)}\nstderr: {proc.stderr}"
        )
    return proc.stdout


class FfmpegCliWrapper:
    """真实 ffmpeg 包装:subprocess 调 ffmpeg。需 ffmpeg 在 PATH。

    探测(时长 / 轨有无)用 `ffmpeg -i <path>`,解析其 stderr(无输出参数时 ffmpeg
    退出码非 0,但 stderr 含 Input/Duration/Stream 信息)。仅需 ffmpeg,不依赖 ffprobe。
    """

    _DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")

    def __init__(self) -> None:
        ensure_ffmpeg_on_path()

    def _probe(self, video_path: str) -> str:
        """返回 `ffmpeg -i <path>` 的 stderr(含探测信息)。"""
        proc = subprocess.run(
            ["ffmpeg", "-i", video_path], capture_output=True, text=True, check=False
        )
        # ffmpeg -i 无输出参数时退出码非 0,属正常;stderr 即探测结果
        return proc.stderr

    def get_duration(self, video_path: str) -> float:
        stderr = self._probe(video_path)
        m = self._DURATION_RE.search(stderr)
        if not m:
            raise RuntimeError(f"无法从 ffmpeg 输出解析时长: {video_path}\n{stderr}")
        h, mi, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
        return h * 3600 + mi * 60 + s

    def has_video_track(self, video_path: str) -> bool:
        # Stream 行形如 "Stream #0:0: Video: h264, ..."
        return "Video:" in self._probe(video_path)

    def has_audio_track(self, video_path: str) -> bool:
        return "Audio:" in self._probe(video_path)

    def extract_frames(self, video_path: str) -> list[str]:
        """1 fps 抽帧到临时目录,返回帧路径(有序)。

        注:work_dir 生命周期待 04 接真实模型走 C 路径时统一管理(当前用 mkdtemp)。
        """
        out_dir = tempfile.mkdtemp(prefix="vie_frames_")
        _run([
            "ffmpeg", "-y", "-i", video_path,
            "-vf", "fps=1",
            os.path.join(out_dir, "frame_%04d.jpg"),
        ])
        return sorted(glob.glob(os.path.join(out_dir, "frame_*.jpg")))

    def slice_segment(
        self, video_path: str, start: float, duration: float, out_path: str
    ) -> None:
        """从 video_path 的 start 秒起切 duration 秒到 out_path(-c copy,快)。"""
        _run([
            "ffmpeg", "-y",
            "-ss", str(start), "-t", str(duration),
            "-i", video_path,
            "-c", "copy",
            out_path,
        ])


class MockFfmpegWrapper:
    """mock ffmpeg:返回预设时长 / 轨有无 / 抽帧结果(供无 ffmpeg 环境测试)。

    默认 has_video=has_audio=True(典型视频);纯音频 fixture 传 has_video=False;
    纯画面 fixture 传 has_audio=False。frames 默认占位两张,可配。
    slice_segment 写一个空占位文件到 out_path(供路径存在性)。
    """

    def __init__(
        self,
        *,
        duration: float,
        has_video: bool = True,
        has_audio: bool = True,
        frames: list[str] | None = None,
    ) -> None:
        self.duration = duration
        self.has_video = has_video
        self.has_audio = has_audio
        self._frames = frames if frames is not None else ["frame_0.jpg", "frame_1.jpg"]
        self.extract_frames_calls: list[str] = []
        self.slice_calls: list[tuple[str, float, float, str]] = []

    def get_duration(self, video_path: str) -> float:
        return self.duration

    def has_video_track(self, video_path: str) -> bool:
        return self.has_video

    def has_audio_track(self, video_path: str) -> bool:
        return self.has_audio

    def extract_frames(self, video_path: str) -> list[str]:
        self.extract_frames_calls.append(video_path)
        return list(self._frames)

    def slice_segment(
        self, video_path: str, start: float, duration: float, out_path: str
    ) -> None:
        self.slice_calls.append((video_path, start, duration, out_path))
        # 写占位文件,模拟切片产物存在(供真实模型/路径检查)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("")
