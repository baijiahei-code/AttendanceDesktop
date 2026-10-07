"""从 app/icon.png 生成多尺寸的 app/icon.ico。

为什么需要这个脚本
------------------
Windows 在不同位置取不同尺寸的图标：16（详情/列表）、24（小图标）、32（桌面、任务栏）、
48（中图标）、64、128、256（大图标/缩略图）。ICO 里**预置好每一档**，系统就直接取用；
如果 ICO 只有 256 一帧（旧版就是如此），系统只能自己缩小 → 小图标与中图标糊成一团。

用法
----
    .venv\\Scripts\\python.exe scripts\\make_icon.py            # 生成 app/icon.ico
    .venv\\Scripts\\python.exe scripts\\make_icon.py --crisp    # 小尺寸额外提升对比度（更"重"）
    .venv\\Scripts\\python.exe scripts\\make_icon.py --out x.ico --src app/icon.png

实现说明
--------
* **只用 Qt（PySide6）**，不引入 Pillow —— 项目本来就依赖 Qt，生成图标不必再加依赖。
* 缩放用**精确面积平均**（自己算，不用 ``QImage.scaled``）：双线性对大幅缩小偏软，
  面积平均更接近 GTK/浏览器的高质量缩放（用户实测：这样与 Linux 上的一致、更清楚）。
* 尺寸含 **125%/150% 缩放屏需要的档位**（20/40/60/72/96）—— 否则 Windows 会拿相邻帧
  放大，反而糊。
* 帧用 **32 位 BMP/DIB**（不是 PNG 压缩帧）：兼容性最好 —— Inno Setup / PyInstaller /
  老版资源工具都认，不会出现「打包工具不认 PNG 帧」的坑。
* 默认**不做对比度提升**（保持原图干净）；需要更"重"的小图标时加 ``--crisp``。
"""
from __future__ import annotations

import argparse
import math
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SRC = ROOT / "app" / "icon.png"
DEFAULT_OUT = ROOT / "app" / "icon.ico"
# 需要预置的尺寸：Windows 常用档位 + 125%/150% 缩放档位（100%~200% 全覆盖）
SIZES = (16, 20, 24, 32, 40, 48, 60, 64, 72, 96, 128, 256)


def _qimage(src: Path):
    from PySide6.QtGui import QImage
    img = QImage(str(src))
    if img.isNull():
        raise SystemExit(f"无法读取源图：{src}")
    return img.convertToFormat(QImage.Format_ARGB32)


def _ensure_app():
    """建一个（离屏的）Qt 应用实例，保证图像插件可用（无显示器也能跑）。"""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication
    if QGuiApplication.instance() is None:
        QGuiApplication([])


def _resize(src, size: int):
    """缩到 size×size：**精确面积平均**（每个目标像素 = 其覆盖区域的加权平均）。

    为什么不用 QImage.scaled：Qt 的 SmoothTransformation 是双线性，对大幅缩小偏软；
    面积平均不糊也不锯齿，效果与 GTK/浏览器的高质量缩放一致。
    """
    from PySide6.QtGui import QColor, QImage
    w, h = src.width(), src.height()
    if size == w and size == h:
        return src.copy()
    px = [[src.pixelColor(x, y).getRgb() for x in range(w)] for y in range(h)]
    out = QImage(size, size, QImage.Format_ARGB32)
    for oy in range(size):
        y0, y1 = oy * h / size, (oy + 1) * h / size
        for ox in range(size):
            x0, x1 = ox * w / size, (ox + 1) * w / size
            r = g = b = a = wsum = 0.0
            for y in range(int(y0), min(h, math.ceil(y1))):
                wy = min(y + 1, y1) - max(y, y0)
                if wy <= 0:
                    continue
                for x in range(int(x0), min(w, math.ceil(x1))):
                    wx = min(x + 1, x1) - max(x, x0)
                    weight = wx * wy
                    if weight <= 0:
                        continue
                    c = px[y][x]
                    r += c[0] * weight
                    g += c[1] * weight
                    b += c[2] * weight
                    a += c[3] * weight
                    wsum += weight
            out.setPixelColor(ox, oy, QColor(round(r / wsum), round(g / wsum),
                                             round(b / wsum), round(a / wsum)))
    return out


def _crisp(img, strength: float = 1.7):
    """小尺寸下缩放会把笔画糊成灰调 —— 以图像均值为中心做一次对比度拉伸。

    均值（背景色）不动，笔画颜色被推得更深，16/24 下更容易辨认。
    """
    from PySide6.QtGui import QColor
    w, h = img.width(), img.height()
    px = [[img.pixelColor(x, y) for x in range(w)] for y in range(h)]
    flat = [c for row in px for c in row]
    mr = sum(c.red() for c in flat) / len(flat)
    mg = sum(c.green() for c in flat) / len(flat)
    mb = sum(c.blue() for c in flat) / len(flat)

    def cvt(v: float, m: float) -> int:
        return max(0, min(255, round(m + (v - m) * strength)))

    out = img.copy()
    for y in range(h):
        for x in range(w):
            c = px[y][x]
            out.setPixelColor(x, y, QColor(cvt(c.red(), mr), cvt(c.green(), mg),
                                           cvt(c.blue(), mb), c.alpha()))
    return out


def _dib(img) -> bytes:
    """把 QImage 编码成 ICO 里的 32 位 DIB 帧（BITMAPINFOHEADER + BGRA 倒序 + AND 掩码）。"""
    w, h = img.width(), img.height()
    # Qt 的 Format_ARGB32 在内存里就是 BGRA（小端），正是 DIB 需要的字节序
    buf = bytes(img.constBits())
    stride = img.bytesPerLine()
    rows = [buf[y * stride: y * stride + w * 4] for y in range(h - 1, -1, -1)]  # 自下而上
    # BITMAPINFOHEADER：biHeight 要写 XOR+AND 两张图的总高
    header = struct.pack("<IiiHHIIiiII", 40, w, h * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    mask_stride = ((w + 31) // 32) * 4
    and_mask = b"\x00" * (mask_stride * h)   # 32bpp 用 alpha 通道，掩码全 0 即可
    return header + b"".join(rows) + and_mask


def write_ico(frames: list[tuple[int, bytes]], out_path: Path) -> Path:
    """把 (尺寸, DIB 数据) 列表写成 ICO 文件。"""
    n = len(frames)
    head = struct.pack("<HHH", 0, 1, n)
    entries = b""
    offset = 6 + 16 * n
    for size, data in frames:
        b = 0 if size >= 256 else size      # 256 要写 0（字节装不下）
        entries += struct.pack("<BBBBHHII", b, b, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    out_path.write_bytes(head + entries + b"".join(d for _s, d in frames))
    return out_path


def build(src_path: Path, out_path: Path, crisp: bool = False,
          sizes=SIZES) -> Path:
    _ensure_app()
    src = _qimage(src_path)
    frames: list[tuple[int, bytes]] = []
    for size in sizes:
        img = _resize(src, size)
        if crisp and size <= 48:
            img = _crisp(img)
        frames.append((size, _dib(img)))

    write_ico(frames, out_path)
    print(f"源图：{src_path} ({src.width()}x{src.height()})")
    print(f"输出：{out_path}  {out_path.stat().st_size / 1024:.1f} KB  帧数 {len(frames)}")
    for (size, data) in frames:
        print(f"   {size:3d}x{size:<3d} DIB {len(data):>7d} 字节")
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser(description="生成多尺寸 icon.ico")
    ap.add_argument("--src", default=str(DEFAULT_SRC))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--crisp", action="store_true",
                    help="16~48 尺寸额外做一次对比度提升（笔画更深，但放大看会有点毛）")
    args = ap.parse_args()
    build(Path(args.src), Path(args.out), crisp=args.crisp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
