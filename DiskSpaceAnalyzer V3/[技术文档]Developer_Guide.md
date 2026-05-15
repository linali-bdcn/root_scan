# 💽 DiskSpaceAnalyzer V3 技术文档

---

# 🛠️ Disk Space Analyzer Pro 技术架构与开发指南

## 1. 架构概述 (Architecture Overview)

本项目经历过从 GUI（PySide6/Qt）到 B/S（Browser/Server）架构的彻底重构。
当前采用 **Python FastAPI (后端) + Vanilla JS/HTML/CSS (前端)** 的纯净分离架构。

**架构优势**：
1. **零构建依赖**：前端抛弃了 Webpack/Vue/React 等重型框架，采用原生 JS 编写，即开即用，极大地降低了二次开发门槛。
2. **渲染极限突破**：基于 Chromium/Webkit 原生的 DOM 渲染能力与 Plotly.js 结合，完美解决了桌面 GUI 引擎（如 Qt WebEngine）带来的黑边、透明度穿透及内存泄漏问题。
3. **高内聚低耦合**：Python 仅负责底层系统 API 调用（IO 遍历、物理操作）和计算；前端仅负责状态机维护和图表渲染，通过 RESTful API 进行 JSON 数据握手。

---

## 2. 核心模块与算法剖析 (Core Algorithms)

### 2.1 后端：极速扫描与物理剪枝算法 (`DiskScanner`)
为了应对动辄数百万个文件的 C 盘，后端放弃了传统的 `os.walk`，采用了底层的 `os.scandir`。
* **物理剪枝 (Pruning)**：前端 Plotly 渲染的极限大约在 1~2 万个节点。我们在后端设定了 `threshold_bytes`，过滤掉极小的碎文件，并将它们合并为 `其他小文件(合并)` 虚拟节点。
* **收益**：将传输的 JSON 数据体积从几十 MB 压缩至几百 KB，彻底避免了浏览器“DOM 爆炸”导致卡死。

### 2.2 后端：异步轮询任务引擎 (Job Polling)
在执行大规模物理删除或压缩时，直接使用 HTTP 阻塞请求会导致浏览器超时。我们自行实现了一套轻量级的异步任务队列：
* **数据结构**：维护一个全局字典 `jobs_db`，以 `uuid` 作为 Job ID。
* **执行线程**：`background_job_runner` 作为守护线程 (Daemon Thread) 运行。
* **非阻塞中断**：在 `for` 循环操作物理文件时，每处理一个文件校验一次 `if job.get('cancel')`，并在循环中插入 `time.sleep(0.01)`，使线程能够瞬间响应前端发来的中断信号，防止 CPU 满载卡死。

### 2.3 前端：完美树状状态机 (State Machine)
这是整个前端最复杂、最具含金量的部分。为了解决“父文件夹假全选导致误删子文件”的致命 BUG，我们设计了严格的**双标记状态机**：
* `checked` (Boolean)：标识该节点是否被勾选（包含半选）。只要子项有勾选，父级必然为 `true`。
* `fullSelected` (Boolean)：**严格全选标记**。只有当该目录下的**所有子节点（无论文件还是文件夹）都为 `fullSelected = true` 时**，父级才会被标记为 `true`。
* **状态收集算法 (`updateSelectionSize` / `getSelectedPaths`)**：在提取导出或删除路径时，算法遇到 `fullSelected = true` 的目录直接整包推入数组；遇到 `checked = true` 但 `fullSelected = false` 的半选目录，则剥开外层，继续向子级递归，**做到了绝对精准的差值读取**。

### 2.4 前端：Plotly 渲染劫持与降级容错
* **精度丢失危机**：由于后端剪枝合并了碎文件，再加上操作系统的簇大小误差，导致树结构传到前端时：`子节点体积之和 != 父节点总体积`。
* **解决方案**：
  1. 将 Plotly 的渲染模式从 `branchvalues: 'total'` 修改为 `branchvalues: 'remainder'`，强制引擎容忍误差。
  2. 放弃 Plotly 原生的 `% {percentParent}`，在 `buildPlotlyData` 扁平化数据时，自己手写递归除法，算好真实百分比并硬编码塞入 `customdata` 数组中供悬浮窗读取。

---

## 3. 核心 API 接口定义 (RESTful API Spec)

| 接口路径 | 方法 | 参数 | 功能描述 |
| :--- | :--- | :--- | :--- |
| `/` | GET | 无 | 挂载点，返回前端 `index.html` 骨架 |
| `/api/drives` | GET | 无 | 获取操作系统挂载的所有可用盘符 |
| `/api/scan` | GET | `target` (str), `threshold_mb` (int) | 发起深度扫描，返回带有层级的完整 JSON 树 |
| `/api/action/open` | GET | `path` (str) | 调用操作系统底层资源管理器打开指定路径 |
| `/api/jobs/start` | POST | `BatchActionReq` (JSON) | 提交物理操作任务 (delete/move/compress) |
| `/api/jobs/status` | GET | `job_id` (str) | 轮询查询任务进度、成功/失败数量 |
| `/api/jobs/cancel` | POST | `job_id` (str) | 向后端发送中断信号，阻断物理操作循环 |
| `/api/action/export` | POST| `target` (str), `data` (dict) | 将 JSON 数据落盘至本地物理存储 |

---

## 4. UI 与交互逻辑层 (DOM & Event Engine)

### 4.1 动态换肤与 CSS 变量注入
项目未采用 SASS/LESS，直接利用现代浏览器的 CSS Variables (`--bg-color` 等)。
通过 JavaScript 的 `document.documentElement.style.setProperty` 实现秒级换肤。为确保 Plotly 图表底色一致，每次换肤后会自动调用 `Plotly.newPlot` 的增量重绘功能。

### 4.2 事件代理与键盘劫持 (Keybinding)
* 全局监听 `keydown` 事件。
* 通过 `.node-row.active` 类的漂移模拟操作系统的焦点移动。
* 使用 `scrollIntoView({ block: "nearest" })` 确保在使用键盘 `↓` 键长列表滚动时，焦点元素始终停留在浏览器的可视区域内，提供不输于原生客户端的沉浸体验。

### 4.3 筛选器视图隔离策略
为了不破坏主视图的树状结构状态，**高级匹配与统计**功能采用了“视图隔离”：
1. 匹配结果存储在独立的 `matchedListNodes` 数组中。
2. 渲染在右侧独立列表中，拥有单独的 `listChecked` 状态。
3. 只有当用户显式点击【同步至主视图】时，系统才会读取 `listChecked`，并调用核心的 `recalculateEntireTree` 函数，自下而上一次性校准主树结构，确保数据原子性（Atomicity）。

---

## 5. 维护与二次开发备忘 (Troubleshooting)

1. **为什么在终端能扫到文件，但在 Web 树状图上没显示？**
   👉 检查左侧侧边栏的 **“过滤碎文件(MB)”** 阈值。如果阈值过高，小文件会被合并为“其他小文件”。如果需要绝对完整结构，请将阈值设为 `0` 重扫。
2. **如果要增加一种全新的批量操作（例如：上传云端），该怎么改？**
   👉 **后端**：在 `backend.py` 的 `background_job_runner` 函数内增加 `elif req.action == 'upload':` 的逻辑处理块。
   👉 **前端**：在 `index.html` 添加一个按钮，在 `app.js` 中为其绑定点击事件，调用 `startJob('upload', 目标参数)` 即可直接复用现有的进度条和日志系统。
3. **安全审计警告**
   👉 物理删除功能没有接入操作系统回收站（直接使用了 `os.remove` 和 `shutil.rmtree`）。为了防止用户误触，在 `app.js` 的 `startJob` 函数内设定了超过 1GB 容量时的**三重强制 Confirm 拦截**。修改时切勿移除此防线！

---
*(End of Technical Architecture Document)*