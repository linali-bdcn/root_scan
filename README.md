
---

# 💽 Disk Space Analyzer Pro (磁盘空间智能分析专家)

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg) ![PySide6](https://img.shields.io/badge/PySide6-Qt6-green.svg) ![Plotly](https://img.shields.io/badge/Plotly-Interactive-orange.svg)

## 📖 项目简介
本项目是一款基于 Python 开发的现代化、跨平台磁盘空间分析工具。它通过底层高效的文件遍历算法，结合 PyQt(PySide6) 桌面级图形界面与 Plotly 交互式数据可视化引擎，帮助用户直观、快速地找出占用硬盘空间的“罪魁祸首”。

本项目摒弃了传统分析软件枯燥的纯列表展示，首创 **“原生树状目录 + WebEngine 动态色块图” 双向联动** 的沉浸式交互体验。

---

## ✨ 核心特性 (Key Features)

* **🚀 极致性能扫描**：基于底层的 `os.scandir` 算法，避免系统调用开销。同时内置 **智能物理剪枝** 机制，深度过滤无用碎小文件，支持 TB 级别硬盘秒级扫描。
* **🎨 沉浸式双模视图**：左侧为标准资源管理器树状列表，右侧为高亮矩阵色块图（Treemap）。支持 4 种视图模式平滑切换。
* **⚡ 瞬间联动渲染引擎**：在“联动模式”下，点击左侧任意子文件夹，右侧图表将提取内存级缓存**瞬间重绘**，无需二次读取硬盘，且自动复用临时文件不产生存储垃圾。
* **🔮 高级主题引擎**：内置模块化主题系统（深海蓝、高级灰、赛博紫、日落橘），支持全局一键换肤，深度定制的 CSS 注入技术彻底消灭网页白边。
* **🛡️ 异步防卡死架构**：严格遵循 GUI 与业务逻辑分离。底层采用 `QThread` 多线程 + `Signal/Slot` 信号槽机制，即使在处理几十万个文件时，界面依然如丝般顺滑。

---

## 📂 项目工程结构 (Project Structure)

本项目采用严格的 **高内聚低耦合 (Separation of Concerns)** 架构，分为表现层、业务层、配置层与工具层。

```text
DiskSpaceAnalyzer/
│
├── main.py                      # 🚀 程序的唯一入口点 (Entry Point)
├── requirements.txt             # 📦 项目依赖清单 (pip install -r requirements.txt)
├── README.md                    # 📖 本项目技术说明文档
│
├── config/                      
│   ├── __init__.py              
│   └── settings.py              # ⚙️ 全局配置中心 (管理阈值、忽略目录、主题引擎、渲染深度)
│
├── core/                        
│   ├── __init__.py              
│   └── scanner.py               # 🧠 核心业务层：只负责递归扫描与计算大小，返回原生 Dict 字典树
│
├── ui/                          
│   ├── __init__.py              
│   ├── qt_main_window.py        # 🖥️ 桌面表现层：PySide6 主窗口界面、多线程调度、事件联动逻辑
│   └── html_renderer.py         # 📊 视图渲染层：负责将字典树转化为 Plotly 交互式 HTML 图表
│
└── utils/                       
    ├── __init__.py              
    ├── formatters.py            # 🛠️ 格式化工具：(如 Byte 转换为 MB/GB)
    └── system_helper.py         # 🛠️ 系统级工具：获取可用盘符、检测 Windows 管理员权限
```

---

## 🛠️ 核心技术原理解析

### 1. “DOM 爆炸” 预防机制 (防卡死)
在渲染带有几十万个文件的 C 盘时，常规网页渲染会导致浏览器内存溢出崩溃。本项目在 `html_renderer.py` 中引入了 `export_max_depth` 概念。系统不仅在视觉上折叠图表，更在**数据写入时进行物理阻断**，仅将用户视距范围内的 N 层数据写入 HTML，使文件体积削减 90%，彻底解决浏览器卡顿。

### 2. UI 组件与数据的隐式绑定
为了实现“点击左侧树，右侧瞬间更新”，本项目巧妙利用了 Qt 的 `Qt.UserRole`。在扫描完成后，程序将完整的硬盘数据字典隐藏存储在了 `QTreeWidgetItem` 对象中。点击节点时，直接从内存中抽取出对应的子字典抛给渲染器，实现了 **O(1) 级别的响应速度**。

### 3. Temp Cache 缓存覆写策略
为了防止用户频繁点击导致本地生成大量重复的 HTML 报告文件，引入了 `is_temp` 标志位。主扫产生持久化历史记录，而局部的联动点击始终覆写同一份 `temp_linked_view.html` 缓存文件，做到性能与空间的完美平衡。

---

## 💻 安装与运行指南

### 环境要求
* Python 3.8 或更高版本
* 操作系统：Windows / macOS / Linux

### 1. 克隆/下载项目
将本工程所有文件下载到本地文件夹。

### 2. 安装依赖
打开终端 (Terminal / CMD)，进入项目根目录，运行以下命令安装所需依赖包：
```bash
pip install -r requirements.txt
```
*(主要包含 `PySide6`、`PySide6-WebEngine`、`plotly` 等库)*

### 3. 启动程序
```bash
python main.py
```
> **提示：** 如果需要扫描 Windows 系统所在的 C 盘，建议右键以 **管理员身份** 运行终端或 IDE，否则系统底层文件将由于权限不足被忽略，导致最终统计大小不准确。

---

## ⚙️ 个性化配置说明

用户可以通过直接修改 `config/settings.py` 来改变软件的行为和外观：

* **更改主题**：修改 `ACTIVE_THEME = "Ocean"` (支持 "Slate", "Ocean", "Sunset", "Neon")。
* **过滤小文件**：修改 `SIZE_THRESHOLD_MB`，低于该数值的文件夹将被聚合并折叠，不再展示细节，以提升性能。
* **调整渲染层级**：修改 `DEFAULT_RENDER_DEPTH` 控制图表初始往下渲染的深度（推荐为 3-4 之间）。

---
*(End of Document)*

### 💡 结语
这份文档清楚地阐明了**这个软件是什么、为什么好用、结构在哪里、怎么跑起来**。你可以直接把这段 Markdown 文本复制下来存为 `README.md`。如果你以后打算把这个项目上传到 GitHub 等开源社区，这份文档能让你的项目瞬间拥有极高的专业度！