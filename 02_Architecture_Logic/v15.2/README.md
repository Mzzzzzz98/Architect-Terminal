# 🏗️ Architect-Terminal (架构师中枢终端)

> **"在嘈杂的现实中，建立属于自己的逻辑堡垒。"**
[![Download](https://github.com/Mzzzzzz98/Architect-Terminal/releases/download/v15.2/default.exe)]
这是一个由 **AI 协作驱动** 的个人生产力管理系统（V15.2 终极稳定版）。它诞生的初衷是为了在碎片化的环境中，通过底层系统级的监控与强制反馈，重塑个人的专注力与算力分配。

---

## 🚀 核心功能 (Core Features)

* **⚡ 注册表级冷启动**：通过 Python 自动注入 Windows 注册表，实现系统原生级的开机自启，优先级高于常规启动项。
* **🧠 严格防作弊监控**：动态抓取系统顶层窗口句柄。只有当视线停留在 VS Code、Chrome 或 Bilibili（学习模式）时才计入专注时长。
* **🧹 游戏模式内存斩杀**：一键清理非关键后台进程（白名单机制），为 3A 游戏或高负载开发腾出物理算力。
* **📝 富文本架构文献库**：内置支持图片粘贴（Ctrl+V）和格式化排版的笔记系统，所有数据本地持久化存储。
* **📊 全景数据矩阵**：热力图式日历统计，精准回溯过去一个月的学习、游戏及睡眠作息曲线。

---

## 🛠️ 技术栈 (Tech Stack)

- **Language**: Python 3.x
- **GUI Framework**: `CustomTkinter` (Modern UI)
- **System API**: `ctypes`, `winreg`, `psutil`
- **Engine**: `Pillow` for Image Processing
- **Deployment**: `PyInstaller` (Standalone Executable)

---

## 📅 进化路径 (Roadmap)

- [x] **V1.0 - V10.0**: 基础计时逻辑与悬浮窗原型开发。
- [x] **V11.0 - V13.0**: 引入本地 JSON 数据库、富文本笔记与图片存储。
- [x] **V14.0 - V15.2**: 攻克 Windows 权限报错 (WinError 5)，实现注册表自启与热力日历。
- [ ] **Next**: 接入深度学习模型，实现自动化学习周报生成。

---

## 🖋️ 开发者随笔 (Architect's Note)

这是我用ai辅助开发的一个项目，它的目标是帮助我更好地管理时间，高效学习

> *"真正的成长，是在平静中积蓄力量。"*

---

### 💡 如何运行
1. `pip install -r requirements.txt`
2. `python tracker.py`
3. 或直接下载 `dist/` 下的 `.exe` 部署。