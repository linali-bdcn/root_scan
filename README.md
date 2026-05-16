# 💽 Disk Space Analyzer Pro (磁盘空间智能分析专家)

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg) ![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg) ![Plotly.js](https://img.shields.io/badge/Plotly.js-Interactive-orange.svg) ![License](https://img.shields.io/badge/License-MIT-blue.svg)

## 📖 项目简介

**Disk Space Analyzer Pro** 是一款轻量、极速、基于 Web 架构的系统级磁盘空间分析与清理工具。
它彻底抛弃了臃肿的传统桌面 GUI 框架，采用 **Python FastAPI 后端 + 原生 JS/HTML/CSS 前端** 的纯净前后端分离架构。不仅提供了极具视觉冲击力的**深色模式双向联动分析视图**，更内置了强大的正则筛选、数据分析以及带有多重安全预判的物理文件管理系统。

---

## ✨ 核心特性

🚀 **极速扫描与物理剪枝**
基于操作系统底层 `os.scandir` 实现高并发遍历。首创“碎片文件合并算法”，自动过滤并合并极小文件，彻底杜绝前端 DOM 与内存爆炸，支持 TB 级别硬盘秒级扫描与渲染。

🎨 **沉浸式双模联动视图**
左侧原生树状目录，右侧 Plotly 交互式色块图（Treemap）。**点击左侧树瞬间重绘右侧图表（0延迟）**，支持深海蓝、高级灰、赛博紫等多套暗黑主题无缝热切换。

🧠 **严密的树状状态引擎**
拥有完美的复选框状态机（全选/半选/取消）。无论目录深达多少层，底层算法都能极其精准地计算出真实勾选的字节数，拒绝“虚假全选”引起的数据丢失。

🔍 **极客级匹配与分析**
支持正则表达式、扩展名、大小范围多条件组合查找。匹配结果独立成表，支持二次核对后**完美同步勾选至主视图**。提供 Top 10 文件类型占比分析。

🛡️ **企业级物理安全操作**
支持对选中的文件进行**物理删除、打包压缩、跨盘转移**。
* **空间预判**：转移/压缩前自动探测目标磁盘剩余容量。
* **异步防卡死**：后台轮询机制，前端展示实时进度条，支持**紧急停止**。
* **三重防误删**：删除大于 1GB 数据时触发防呆警告，操作全程记录至 `logs/` 目录供灾难恢复参考。

---

## 💻 快速开始

### 1. 环境要求
* Python 3.8+
* 现代浏览器 (Chrome / Edge / Firefox)

### 2. 安装依赖
```bash
pip install fastapi uvicorn
