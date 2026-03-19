🌌 Architect Terminal - V15.3 迭代更新日志 (Release Notes)
Date: 2026-03-19
Author: 孟哲 (Chief Architect)

🚀 一、 核心架构新增 (New Core Features)
🌍 环境扫描雷达 (ENV SCAN Module)

实装了基于双重接口 (ip-api.com + wttr.in) 的全自动物理环境感知系统。

支持后台异步解析精准城市定位与气象数据（滤除冗余经纬度坐标），并以全大写赛博极客格式（如 ENV SCAN: SHANGHAI | ⛅️ +22°C | HUM:60%）注入主终端界面。

📊 双核全息数据矩阵 (Dual-Core Data Matrix)

弃用简易文本展示，重构为具备 CTkTabview 双页签的图形化分析中枢。

Tab 1 - Neural Matrix: 纯 UI 手工渲染 7 天红蓝堆叠柱状图（无需外部图表库），新增总能效比 (Efficiency) 面板，以及当日 App Trace (生产力/游戏软件精细耗时清单)。

Tab 2 - Archive Calendar: 实装互动式历史热力月历。通过红蓝底色直观反映单日状态，点击任意网格即可侧边展开该日的详细复盘数据。

⚙️ 生产力全天候追踪引擎 (Omni-Tracking Engine)

重构底层 monitor_loop，引入 STUDIO_TOOLS 白名单机制（包含 Cherry Studio, Chatbox, AnythingLLM）。

实现“非前台静默判定”：只要生产力工具进程存活，系统即刻进行专注计费，完美适配查阅资料与 AI 辅助并行的多任务工作流。

新增网易云音乐 (cloudmusic.exe) 后台静默使用时长统计。

👁️ 二、 视觉与交互重构 (UI/UX Upgrades)
✨ 赛博核心动态视觉 (Dynamic Cyber Core)

打通主控台与最小化“小猫模式”的视觉神经。现在进行模式切换时，核心眼部 UI 会实时且瞬间完成 电光蓝 (Study) 与 警告红 (Game) 的状态同步。

📐 引力锚点自适应布局 (Gravity Anchoring Layout)

重构主界面高度预设（扩容至 155px）与 pack 空间分配逻辑。

采用两端引力锚定策略，彻底解决长篇“每日金句”导致的 UI 容器溢出、底部工具栏被吞噬的渲染 Bug。

🔧 三、 系统级修复与防弹优化 (System Fixes)
Bug Fix: 统一全系统状态机变量，修复因 "STUDY" 与 "STUDIO" 命名空间错位导致的颜色判定死锁。

Bug Fix: 将进程轮询逻辑与 UI 按钮事件彻底解耦，清除了点击切换时触发的 NameError (active_procs) 崩溃隐患。

Performance: 优化后台守护线程结构，确保 2.5 小时游戏防沉迷警报机制、每 10 秒数据库自动存盘机制、以及异步网络请求互不阻塞，主线程零卡顿。