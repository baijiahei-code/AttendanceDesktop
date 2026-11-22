# 第三方组件许可声明（Third-Party Notices）

本文件说明「工作考勤表」（Attendance Desktop / Attendance HarmonyOS）**发行包内含的第三方组件**
及其许可条款。安装包 / 免安装目录 / deb / rpm 中都会附带两份文件的副本：
本文件（Windows：`安装目录\THIRD_PARTY_NOTICES.md`；deb：`/usr/share/doc/attendance-desktop/`；
rpm：`/usr/share/licenses/attendance-desktop/`），以及 **`LICENSE.Python.txt`**
（构建所用 CPython 自带的 LICENSE，其中汇总了 CPython 内嵌组件如 OpenSSL / zlib /
expat / libffi / bzip2 / liblzma / libzstd 的版权与许可）。

> 本项目自身的代码由 **柯一鸣** 开发，以 **GPL-3.0-or-later** 发布，全文见仓库根目录 [`LICENSE`](LICENSE)。
> 第三方组件仍归各自作者所有、按各自许可授权；本项目未修改它们的源码。

---

## 1. 随桌面版发行包分发的第三方组件

桌面版用 PyInstaller 打成单个目录（`_internal/` 下即这些组件的实体文件），因此构成“分发”，
需履行各自的许可义务。

| 组件 | 版本 | 许可 | 版权方 | 许可全文 |
|---|---|---|---|---|
| PySide6 / PySide6-Essentials / PySide6-Addons | 6.11.2 | LGPL-3.0-only（另可选 GPL-2.0-only / GPL-3.0-only / 商业许可），**本项目按 LGPL-3.0 使用** | The Qt Company Ltd. 及贡献者 | 附录 A（LGPL-3.0）+ [`LICENSE`](LICENSE)（GPL-3.0） |
| shiboken6 | 6.11.2 | 同上 | The Qt Company Ltd. 及贡献者 | 同上 |
| Qt 6（随 PySide6 附带，位于 `_internal/PySide6/Qt/`；Linux 下 `_internal/` 根目录还有一份运行时副本） | 6.11.x | LGPL-3.0 | The Qt Company Ltd. 及贡献者 | 同上 |
| openpyxl | 3.1.5 | MIT | Copyright (c) 2010 openpyxl | 附录 B |
| gmssl | 3.2.2 | 宽松许可（PyPI 元数据标 BSD；上游仓库 `License` 文件为 MIT） | duanhongyi / Nemo | 附录 C |
| pycryptodomex（PyCryptodome） | 3.23.0 | BSD-2-Clause + 部分 Public Domain | 各自作者 | 附录 D |
| Python 运行时（CPython，`python3*.dll` / `libpython*` / `python3.*/lib-dynload`） | 3.14.x（Windows）/ 3.12.x（Linux） | PSF-2.0 | Python Software Foundation | `LICENSE.Python.txt`（随包） |
| OpenSSL（`libssl.so*` / `libcrypto*.dll`） | 3.x | Apache-2.0 | The OpenSSL Project Authors | 见 `LICENSE.Python.txt` |
| libffi（`libffi.so*` / `libffi-*.dll`） | 3.x | MIT | Anthony Green 及贡献者 | 见 `LICENSE.Python.txt` |
| GTK / GLib / Pango / ATK / Cairo / libgcrypt | 随构建机 | LGPL-2.1-or-later（cairo 亦可用 MPL-1.1） | GNOME / freedesktop 各项目 | deb `copyright` 对应段落 |
| X11 / XCB / xkbcommon | 随构建机 | MIT | X.Org Foundation 及贡献者 | deb `copyright` 对应段落 |
| GCC 运行时（`libstdc++.so*` / `libgcc_s.so*`） | 随构建机 | GPL-3.0-or-later **+ GCC 运行时例外 3.1** | Free Software Foundation, Inc. | libstdc++ 的 `COPYING.RUNTIME` |
| ICU（`libicu*`，Qt 依赖） | 73.x | Unicode-3.0 | Unicode, Inc. | <https://www.unicode.org/license.txt> |
| Microsoft VC++ 运行库（`VCRUNTIME140*.dll` / `api-ms-win-*.dll` / `ucrtbase.dll`，**仅 Windows**） | 随 CPython | Microsoft Visual C++ Redistributable 许可 | Microsoft Corporation | Microsoft 的再分发条款 |
| PyInstaller 引导器（`AttendanceDesktop.exe` 的启动部分） | 6.22.3 | GPL-2.0-or-later + 允许打包异许可程序的特别例外 | PyInstaller Development Team | <https://github.com/pyinstaller/pyinstaller/blob/develop/COPYING.txt> |

补充说明：

- **Linux 包（deb / rpm）的依赖链更宽**：PyInstaller 还会带入 Kerberos、systemd、selinux、
  zlib / zstd / bzip2 / xz、libpng / libjpeg、freetype / fontconfig、pcre2、expat 等系统级库。
  它们均为宽松许可或 LGPL，**不属于本项目作品**；deb 的 `copyright` 已把这些目录统一切入
  “三方运行时（mixed）”段落并指向本文件，Windows 侧则由上述组件或 CPython 的 LICENSE 覆盖。
- **Qt 自身还包含若干第三方库**（例如 zlib、PCRE2、ICU、FreeType 等，视启用的模块而定），
  其版权与许可随 Qt 源码树提供；如需逐项清单，可查阅 Qt 源码中的 `LICENSES/` 目录或
  <https://code.qt.io/cgit/qt/>。
- 上述组件均**未经修改**。若你替换其中某个组件的文件，相关许可义务随之转移到你身上。

## 2. 仅构建期使用、不随发行包分发

以下依赖只参与构建 / 测试，不会被 PyInstaller 打入发行包，因此不构成对外分发：

- PyInstaller 6.22.3（GPL-2.0+ 特别例外）、pyinstaller-hooks-contrib（Apache-2.0）
- 鸿蒙版工具链：TypeScript、Vitest、`@types/node` 等 devDependencies（Apache-2.0 / MIT）
- 打包脚本用到的系统工具（Inno Setup、dpkg-deb、rpmbuild、openssl）

## 3. 鸿蒙版（HarmonyOS）

- 应用代码（`harmony-app/core`、`harmony/entry/src/main/ets`）为本项目原创，GPL-3.0-or-later。
- ArkUI / ArkTS 运行时与系统库由 **HarmonyOS 设备系统自身提供**，不随 HAP 分发；
  开发所用的 HarmonyOS SDK 条款见 [`harmony-app/harmony/licenses/HarmonyOS-SDK`](harmony-app/harmony/licenses/HarmonyOS-SDK)。
- HAP 包内 `resources/rawfile/LICENSE` 为 GPL-3.0 全文，与仓库根目录 `LICENSE` 完全一致。

## 4. LGPL-3.0 合规说明（PySide6 / Qt）

本项目按 **LGPL-3.0** 使用 PySide6 与 Qt（未修改其源代码），满足 LGPL-3.0 第 4 条的方式如下：

1. **显著声明**：即本文件（随包分发），并在程序「关于」对话框与 `README` 中说明使用了 Qt / PySide6。
2. **附带许可全文**：LGPL-3.0 全文见附录 A，GPL-3.0 全文见仓库 `LICENSE`（随包附带）。
3. **可替换 / 可重新链接**：发行包中的 Qt / PySide6 为**独立目录中的独立文件**（不是静态链入主程序），
   你可以用自行编译或自行下载的同版本（主次版本兼容即可）替换：
   - Windows：替换 `安装目录\_internal\PySide6\` 整个目录（可用 `pip install PySide6==6.11.2` 得到的同名目录覆盖）；
   - Linux（deb / rpm）：替换 `/usr/lib/attendance-desktop/_internal/PySide6/` 整个目录，
     以及 `/usr/lib/attendance-desktop/_internal/libQt6*.so.6`、`libpyside6*`、`libshiboken6*`
     这些 Qt 运行时库（Linux 下 PyInstaller 把它们复制到了 `_internal/` 根下）；
   - 或直接以源码运行：`python main.py`（此时使用你环境中安装的 PySide6）。
4. **对应源码**：本项目源码公开于
   <https://github.com/baijiahei-code/AttendanceDesktop>（镜像：<https://gitee.com/white-and-black-code/AttendanceDesktop>），
   可据此重新构建、重新链接。Qt / PySide6 的源码见 <https://code.qt.io/> 与 <https://download.qt.io/official_releases/QtForPython/>。

> 说明：Qt 采用“LGPL-3.0 / GPL-2.0 / GPL-3.0 / 商业许可”多选授权，本项目选择 LGPL-3.0。
> 由于本项目本身以 GPL-3.0-or-later 发布，组合后的整体分发亦符合 GPLv3 的相关要求。

---

## 附录 A：GNU Lesser General Public License v3.0 全文

```text
                   GNU LESSER GENERAL PUBLIC LICENSE
                       Version 3, 29 June 2007

 Copyright (C) 2007 Free Software Foundation, Inc. <https://fsf.org/>
 Everyone is permitted to copy and distribute verbatim copies
 of this license document, but changing it is not allowed.


  This version of the GNU Lesser General Public License incorporates
the terms and conditions of version 3 of the GNU General Public
License, supplemented by the additional permissions listed below.

  0. Additional Definitions.

  As used herein, "this License" refers to version 3 of the GNU Lesser
General Public License, and the "GNU GPL" refers to version 3 of the GNU
General Public License.

  "The Library" refers to a covered work governed by this License,
other than an Application or a Combined Work as defined below.

  An "Application" is any work that makes use of an interface provided
by the Library, but which is not otherwise based on the Library.
Defining a subclass of a class defined by the Library is deemed a mode
of using an interface provided by the Library.

  A "Combined Work" is a work produced by combining or linking an
Application with the Library.  The particular version of the Library
with which the Combined Work was made is also called the "Linked
Version".

  The "Minimal Corresponding Source" for a Combined Work means the
Corresponding Source for the Combined Work, excluding any source code
for portions of the Combined Work that, considered in isolation, are
based on the Application, and not on the Linked Version.

  The "Corresponding Application Code" for a Combined Work means the
object code and/or source code for the Application, including any data
and utility programs needed for reproducing the Combined Work from the
Application, but excluding the System Libraries of the Combined Work.

  1. Exception to Section 3 of the GNU GPL.

  You may convey a covered work under sections 3 and 4 of this License
without being bound by section 3 of the GNU GPL.

  2. Conveying Modified Versions.

  If you modify a copy of the Library, and, in your modifications, a
facility refers to a function or data to be supplied by an Application
that uses the facility (other than as an argument passed when the
facility is invoked), then you may convey a copy of the modified
version:

   a) under this License, provided that you make a good faith effort to
   ensure that, in the event an Application does not supply the
   function or data, the facility still operates, and performs
   whatever part of its purpose remains meaningful, or

   b) under the GNU GPL, with none of the additional permissions of
   this License applicable to that copy.

  3. Object Code Incorporating Material from Library Header Files.

  The object code form of an Application may incorporate material from
a header file that is part of the Library.  You may convey such object
code under terms of your choice, provided that, if the incorporated
material is not limited to numerical parameters, data structure
layouts and accessors, or small macros, inline functions and templates
(ten or fewer lines in length), you do both of the following:

   a) Give prominent notice with each copy of the object code that the
   Library is used in it and that the Library and its use are
   covered by this License.

   b) Accompany the object code with a copy of the GNU GPL and this license
   document.

  4. Combined Works.

  You may convey a Combined Work under terms of your choice that,
taken together, effectively do not restrict modification of the
portions of the Library contained in the Combined Work and reverse
engineering for debugging such modifications, if you also do each of
the following:

   a) Give prominent notice with each copy of the Combined Work that
   the Library is used in it and that the Library and its use are
   covered by this License.

   b) Accompany the Combined Work with a copy of the GNU GPL and this license
   document.

   c) For a Combined Work that displays copyright notices during
   execution, include the copyright notice for the Library among
   these notices, as well as a reference directing the user to the
   copies of the GNU GPL and this license document.

   d) Do one of the following:

       0) Convey the Minimal Corresponding Source under the terms of this
       License, and the Corresponding Application Code in a form
       suitable for, and under terms that permit, the user to
       recombine or relink the Application with a modified version of
       the Linked Version to produce a modified Combined Work, in the
       manner specified by section 6 of the GNU GPL for conveying
       Corresponding Source.

       1) Use a suitable shared library mechanism for linking with the
       Library.  A suitable mechanism is one that (a) uses at run time
       a copy of the Library already present on the user's computer
       system, and (b) will operate properly with a modified version
       of the Library that is interface-compatible with the Linked
       Version.

   e) Provide Installation Information, but only if you would otherwise
   be required to provide such information under section 6 of the
   GNU GPL, and only to the extent that such information is
   necessary to install and execute a modified version of the
   Combined Work produced by recombining or relinking the
   Application with a modified version of the Linked Version. (If
   you use option 4d0, the Installation Information must accompany
   the Minimal Corresponding Source and Corresponding Application
   Code. If you use option 4d1, you must provide the Installation
   Information in the manner specified by section 6 of the GNU GPL
   for conveying Corresponding Source.)

  5. Combined Libraries.

  You may place library facilities that are a work based on the
Library side by side in a single library together with other library
facilities that are not Applications and are not covered by this
License, and convey such a combined library under terms of your
choice, if you do both of the following:

   a) Accompany the combined library with a copy of the same work based
   on the Library, uncombined with any other library facilities,
   conveyed under the terms of this License.

   b) Give prominent notice with the combined library that part of it
   is a work based on the Library, and explaining where to find the
   accompanying uncombined form of the same work.

  6. Revised Versions of the GNU Lesser General Public License.

  The Free Software Foundation may publish revised and/or new versions
of the GNU Lesser General Public License from time to time. Such new
versions will be similar in spirit to the present version, but may
differ in detail to address new problems or concerns.

  Each version is given a distinguishing version number. If the
Library as you received it specifies that a certain numbered version
of the GNU Lesser General Public License "or any later version"
applies to it, you have the option of following the terms and
conditions either of that published version or of any later version
published by the Free Software Foundation. If the Library as you
received it does not specify a version number of the GNU Lesser
General Public License, you may choose any version of the GNU Lesser
General Public License ever published by the Free Software Foundation.

  If the Library as you received it specifies that a proxy can decide
whether future versions of the GNU Lesser General Public License shall
apply, that proxy's public statement of acceptance of any version is
permanent authorization for you to choose that version for the
Library.
```

（LGPL-3.0 以 GPL-3.0 为基础，GPL-3.0 全文见仓库根目录 [`LICENSE`](LICENSE)。）

## 附录 B：MIT（openpyxl）

```text
This software is under the MIT Licence
======================================

Copyright (c) 2010 openpyxl

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be included
in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
```

## 附录 C：MIT（gmssl）

> gmssl 3.2.2 的 PyPI 元数据把许可标为 `BSD`，而其上游仓库中的 `License` 文件为下面的 MIT 文本
> （Copyright (c) 2022 Nemo）。两者同属宽松许可，义务一致：保留版权与许可声明。此处收录上游原文。

```text
MIT License

Copyright (c) 2022 Nemo

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## 附录 D：BSD-2-Clause + Public Domain（PyCryptodome / pycryptodomex）

```text
The source code in PyCryptodome is partially in the public domain
and partially released under the BSD 2-Clause license.

In either case, there are minimal if no restrictions on the redistribution,
modification and usage of the software.

Public domain
=============

All code originating from  PyCrypto is free and unencumbered software
released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or
distribute this software, either in source code form or as a compiled
binary, for any purpose, commercial or non-commercial, and by any
means.

In jurisdictions that recognize copyright laws, the author or authors
of this software dedicate any and all copyright interest in the
software to the public domain. We make this dedication for the benefit
of the public at large and to the detriment of our heirs and
successors. We intend this dedication to be an overt act of
relinquishment in perpetuity of all present and future rights to this
software under copyright law.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

For more information, please refer to <http://unlicense.org>

BSD license
===========

All direct contributions to PyCryptodome are released under the following
license. The copyright of each piece belongs to the respective author.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice,
   this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

---

## 附：本文件自身的维护

- 依赖升级（`requirements.txt` / `package.json`）或打包方式变化时，请同步更新第 1 节的版本号与许可。
- 检查是否漏带：`scripts/verify_deb.sh` 与 `scripts/verify_rpm.sh` 会验证包内存在本文件与
  `LICENSE.Python.txt` 的副本。
- **版权年份自动覆盖**：deb 的 `copyright` 年份由 `scripts/pack_deb.py` 的
  `COPYRIGHT_START_YEAR`（首年 2026）+ 构建当年自动生成（同年写 `2026`，跨年写 `2026-2027`），
  发新版本时不需要手工改；其它平台使用 `2026-present`，本身已覆盖后续年份。
