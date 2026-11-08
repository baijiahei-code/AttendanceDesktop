"""用桌面版的 app/icon.png 生成鸿蒙端的分层图标（background / foreground / startIcon）。

为什么需要这个脚本：
  DevEco 新建工程自带的是**模板默认图标**（蓝色方块），和桌面版的「Money where?」完全不是一回事。
  鸿蒙的分层图标要求「背景 + 前景」两张 1024×1024，且主体要落在中间的安全区内，
  直接拿原图改个文件名是会被系统裁掉的，所以统一由本脚本生成，保持两端外观一致。

产出（5 个文件，都是覆盖写）：
  harmony/AppScope/resources/base/media/background.png        纯底色（取原图四角颜色）
  harmony/AppScope/resources/base/media/foreground.png        主体（居中，占 60% 安全区）
  harmony/entry/src/main/resources/base/media/background.png  同上
  harmony/entry/src/main/resources/base/media/foreground.png  同上
  harmony/entry/src/main/resources/base/media/startIcon.png   启动窗口图标 152×152

用法（在仓库根目录）：
  .venv\\Scripts\\python.exe harmony-app\\scripts\\make_harmony_icon.py
  ... --src app/icon.png --safe 0.6

只依赖 PySide6（桌面版已装），不引入新依赖；只读 app/icon.png，不碰桌面版其他文件。
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent            # harmony-app/
DESKTOP = ROOT.parent         # 仓库根（桌面版在 DESKTOP/app/）
if not (DESKTOP / "app" / "icon.png").exists():
    raise SystemExit(
        "[ERROR] 找不到桌面版图标：%s\n"
        "        本脚本必须在完整仓库里运行（app/ 与 harmony-app/ 同级）。"
        % (DESKTOP / "app" / "icon.png")
    )

MEDIA = ROOT / "harmony" / "entry" / "src" / "main" / "resources" / "base" / "media"
APPSCOPE = ROOT / "harmony" / "AppScope" / "resources" / "base" / "media"

CANVAS = 1024                 # 鸿蒙分层图标画布
START_ICON = 152              # startWindowIcon 尺寸
SAFE_RATIO = 0.60             # 前景主体占画布比例（鸿蒙安全区约 60%）


def corner_color(img: QImage) -> QColor:
    """取四角颜色的平均，作为分层图标的背景底色。"""
    w, h = img.width(), img.height()
    pts = [(1, 1), (w - 2, 1), (1, h - 2), (w - 2, h - 2)]
    cols = [img.pixelColor(x, y) for x, y in pts]
    r = sum(c.red() for c in cols) // len(cols)
    g = sum(c.green() for c in cols) // len(cols)
    b = sum(c.blue() for c in cols) // len(cols)
    a = sum(c.alpha() for c in cols) // len(cols)
    return QColor(r, g, b, a)


def make_background(color: QColor) -> QImage:
    img = QImage(CANVAS, CANVAS, QImage.Format_ARGB32)
    img.fill(color)
    return img


def make_foreground(src: QImage, safe: float) -> QImage:
    """透明画布 + 居中主体；主体本身带底色，和背景同色时接缝不可见。"""
    img = QImage(CANVAS, CANVAS, QImage.Format_ARGB32)
    img.fill(Qt.transparent)

    side = int(round(CANVAS * safe))
    # 先按整段裁剪缩放，避免放大后出现阶梯
    scaled = src.scaled(side, side, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    p = QPainter(img)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    x = (CANVAS - scaled.width()) // 2
    y = (CANVAS - scaled.height()) // 2
    p.drawImage(QRect(x, y, scaled.width(), scaled.height()), scaled)
    p.end()
    return img


def make_start_icon(src: QImage) -> QImage:
    return src.scaled(START_ICON, START_ICON, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def save(img: QImage, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not img.save(str(path), "PNG"):
        raise SystemExit("[ERROR] 写不出去：%s" % path)
    print("  %-58s %5.1f KB  %dx%d"
          % (path.relative_to(DESKTOP), path.stat().st_size / 1024,
             img.width(), img.height()))


def main(argv: list[str]) -> int:
    src_path = DESKTOP / "app" / "icon.png"
    safe = SAFE_RATIO
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--src" and i + 1 < len(argv):
            src_path = Path(argv[i + 1]).resolve()
            i += 2
        elif a == "--safe" and i + 1 < len(argv):
            safe = float(argv[i + 1])
            i += 2
        elif a in ("-h", "--help"):
            print(__doc__)
            return 0
        else:
            sys.stderr.write("[ERROR] 未知参数：%s（用 --help 看用法）\n" % a)
            return 2

    if not src_path.exists():
        sys.stderr.write("[ERROR] 找不到源图：%s\n" % src_path)
        return 2

    src = QImage(str(src_path))
    if src.isNull():
        sys.stderr.write("[ERROR] 读不出来（不是有效图片）：%s\n" % src_path)
        return 2

    color = corner_color(src)
    print("源图：%s  %dx%d  底色 %s" % (src_path.name, src.width(), src.height(), color.name()))
    print("输出：")

    bg = make_background(color)
    fg = make_foreground(src, safe)
    st = make_start_icon(src)

    for base in (APPSCOPE, MEDIA):
        save(bg, base / "background.png")
        save(fg, base / "foreground.png")
    save(st, MEDIA / "startIcon.png")

    print("\n完成。重新打包即可（一键打包.bat harmony）。")
    return 0


if __name__ == "__main__":
    _app = QGuiApplication.instance() or QGuiApplication([])
    raise SystemExit(main(sys.argv[1:]))
