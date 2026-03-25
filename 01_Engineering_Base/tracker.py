import requests
import os
import re  
import sys
import json
import logging
import gc
import ctypes
import ctypes.wintypes
import time
import winsound
import pystray
from PIL import ImageDraw  # 用于在内存中凭空画出一个赛博图标
import shutil
from tkinter import filedialog 
import psutil
import platform
import winreg
import calendar
from datetime import datetime, timedelta
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, colorchooser, font, messagebox
import threading
import glob
import random
from PIL import Image, ImageTk, ImageGrab
import traceback
import webbrowser  # 新增：用于呼叫系统默认浏览器打开下载链接

# ==========================================
# ⚙️ 全局配置与路径初始化 (V16.0 路径安全升级)
# ==========================================
APP_NAME = "Nebula"
CURRENT_VERSION = "1.0.0"  # 🚀 你的星云终端当前生命周期版本号

# 下面是你原本定义 APPDATA_PATH 的代码...

# ==========================================
# 📦 工业级资源寻路引擎 (兼容 PyInstaller 打包)
# ==========================================
def resource_path(relative_path):
    """获取资源的绝对路径，完美兼容开发环境与 PyInstaller 单文件打包环境"""
    try:
        # PyInstaller 打包后，会将资源解压到一个名为 _MEIPASS 的临时目录
        base_path = sys._MEIPASS
    except Exception:
        # 如果是在 VS Code 里直接运行代码，就用当前文件所在目录
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

try:
    # optional dependency (pylance/pyright may not resolve in env)
    from tkinterdnd2 import DND_FILES  # type: ignore
    _TKDND_AVAILABLE = True
except Exception:
    DND_FILES = None
    _TKDND_AVAILABLE = False

def _bind_tkdnd_drop(widget: tk.Misc, on_files):
    """用 tkinterdnd2 绑定文件拖拽；不可用则返回 False。"""
    if not _TKDND_AVAILABLE:
        return False
    try:
        widget.drop_target_register(DND_FILES)
        def _on_drop(event):
            try:
                # event.data 可能是带 {} 的路径列表，用 Tk 的 splitlist 最稳
                paths = [p.strip("{}") for p in widget.tk.splitlist(event.data)]
                paths = [p for p in paths if p]
                if paths and callable(on_files):
                    on_files(paths)
            except Exception:
                pass
        widget.dnd_bind("<<Drop>>", _on_drop)
        return True
    except Exception as e:
        print(f"tkdnd bind failed: {e}")
        return False

# ==========================================
# ⚙️ 全局配置与路径初始化 (V16.0 路径安全升级)
# ==========================================
APP_NAME = "Nebula"
# 获取 Windows 标准应用数据路径 (AppData/Roaming)
# 这样即使安装在 C 盘，读写数据也永远拥有合法权限
APPDATA_PATH = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_NAME)
def get_safe_path():
    try:
        # 优先获取 AppData，如果获取失败则退回到当前程序目录
        base = os.environ.get("APPDATA")
        if not base:
            base = os.path.dirname(os.path.abspath(__file__))
        
        # 强制处理编码，防止中文用户名导致的 Extension modules 崩溃
        target = os.path.join(base, "Nebula").encode('utf-8').decode('utf-8')
        
        # 递归创建所有依赖目录
        notes_p = os.path.join(target, "Notes")
        imgs_p = os.path.join(notes_p, "Images")
        
        for d in [target, notes_p, imgs_p]:
            if not os.path.exists(d):
                os.makedirs(d, exist_ok=True)
        return target, notes_p, imgs_p
    except Exception as e:
        # 如果这里都崩了，用最原始的 MessageBox 报警
        ctypes.windll.user32.MessageBoxW(0, f"FATAL: 路径初始化失败\n{e}", "核心坍塌", 0x10)
        os._exit(1)

# 执行初始化并锁定常量
APP_DIR, NOTES_DIR, IMAGE_DIR = get_safe_path()
# ==========================================
# 📡 工业级黑匣子日志引擎 (Telemetry System V2)
# ==========================================
LOG_FILE = os.path.join(APP_DIR, "terminal_core.log") # 改名：不再只记录 error

# 配置全局分级日志记录器
logger = logging.getLogger("Nebula")
logger.setLevel(logging.INFO) # 基础过滤级别设为 INFO

if not logger.handlers:
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - [%(levelname)s] - <%(funcName)s> : %(message)s")
    fh.setFormatter(formatter)
    logger.addHandler(fh)

# 🚀 捕获全局未处理的致命崩溃 (终极容灾救生舱版)
def global_exception_handler(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    # 1. 第一时间将报错堆栈写入黑匣子
    logger.error("🔴 发生未捕获的全局致命异常！", exc_info=(exc_type, exc_value, exc_traceback))

    # 2. 召唤独立于主循环的纯净 Tkinter 容灾弹窗 (保证在任何情况下都能弹出来)
    try:
        import tkinter as tk
        import os
        
        crash_win = tk.Tk()
        crash_win.title("SYSTEM FAILURE")
        crash_win.geometry("450x220")
        crash_win.attributes("-topmost", True)
        crash_win.configure(bg="#09090b") # 极黑底色
        
        # 居中算法
        crash_win.update_idletasks()
        sw, sh = crash_win.winfo_screenwidth(), crash_win.winfo_screenheight()
        crash_win.geometry(f"+{(sw-450)//2}+{(sh-220)//2}")

        tk.Label(crash_win, text="⚠️ 核心矩阵发生坍塌 (Fatal Error)", font=("Microsoft YaHei", 16, "bold"), bg="#09090b", fg="#ef4444").pack(pady=(25, 10))
        tk.Label(crash_win, text="程序遇到了无法恢复的系统级错误，必须终止运行。\n崩溃快照已加密写入黑匣子日志。", font=("Microsoft YaHei", 11), bg="#09090b", fg="#a1a1aa").pack(pady=(0, 20))

        btn_frame = tk.Frame(crash_win, bg="#09090b")
        btn_frame.pack()

        def open_log():
            try: os.startfile(APP_DIR)
            except: pass

        def close_app():
            crash_win.destroy()
            os._exit(1) # 物理级断电，防止僵尸线程残留

        # 模拟极客风原生按钮
        tk.Button(btn_frame, text="📂 提取黑匣子 (打开日志)", font=("Microsoft YaHei", 11, "bold"), bg="#27272a", fg="#00f2ff", relief="flat", cursor="hand2", command=open_log).pack(side="left", padx=10, ipadx=10, ipady=5)
        tk.Button(btn_frame, text="❌ 强行拔管 (退出程序)", font=("Microsoft YaHei", 11, "bold"), bg="#450a0a", fg="#ef4444", relief="flat", cursor="hand2", command=close_app).pack(side="left", padx=10, ipadx=10, ipady=5)

        crash_win.protocol("WM_DELETE_WINDOW", close_app)
        crash_win.mainloop()
        
    except Exception:
        # 兜底防御：如果连内存都没了导致 Tkinter 都弹不出，直接用 Windows 最底层的 C 语言弹窗报警
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, "发生严重错误！\n日志已保存在 AppData 目录中。", "Nebula Crash", 0x10)
        except: pass
    finally:
        os._exit(1)

sys.excepthook = global_exception_handler

# 记录系统点火日志
logger.info(f"=== TERMINAL INITIALIZED | OS: {platform.system()} {platform.release()} ===")

sys.excepthook = global_exception_handler
DATA_FILE = os.path.join(APP_DIR, "daily_logs.json")
CONFIG_FILE = os.path.join(APP_DIR, "system_config.json")
QUOTES_FILE = os.path.join(APP_DIR, "quotes.txt")

# 自动构建生态目录 (加入更严密的目录校验)
for d in [APP_DIR, NOTES_DIR, IMAGE_DIR]:
    if not os.path.exists(d):
        try:
            os.makedirs(d, exist_ok=True)
        except Exception as e:
            ctypes.windll.user32.MessageBoxW(0, f"权限初始化失败: {e}\n请尝试以管理员权限运行。", "系统错误", 0x10)
            sys.exit(1)

# ==========================================
# 🧬 核心数据洗练与迁移引擎 (Schema Migration)
# ==========================================
CURRENT_SCHEMA_VERSION = 2.0  # 定义当前系统的最新架构版本

def migrate_sys_config(cfg):
    """时空隧道：将旧版 JSON 数据平滑升级到最新版本"""
    if not isinstance(cfg, dict): 
        cfg = {}

    # 如果没有版本号，说明是 V1.0 的远古旧数据
    current_ver = cfg.get("schema_version", 1.0)

    # 🚀 向上迁移通道：V1.0 -> V2.0
    if current_ver < 2.0:
        print(f">>> 发现旧版矩阵数据 (V{current_ver})，正在执行平滑升级至 V2.0...")
        
        # 1. 补齐 V2.0 新增的底层字段，防止未来报 KeyError
        cfg.setdefault("timers", {"study_break_sec": 2 * 3600, "game_limit_sec": int(2.5 * 3600)})
        cfg.setdefault("ui_scale", "1.0")
        cfg.setdefault("retention_days", "30")
        cfg.setdefault("auto_start", False)
        
        # 2. 补齐矩阵核心分类
        cfg.setdefault("study", {})
        cfg.setdefault("game", {})
        cfg.setdefault("music", {})
        
        # 3. 升级完成，打上最新版本思想钢印
        cfg["schema_version"] = 2.0
        
        # 4. 立即将升级后的健康数据固化到硬盘
        save_sys_config(cfg)
        print(">>> 矩阵平滑升级完成！")

    # 未来如果升级到 V3.0，就在这里继续加：
    # if current_ver < 3.0:
    #     ... 执行 V2 到 V3 的转换逻辑 ...
    #     cfg["schema_version"] = 3.0

    return cfg

def load_sys_config():
    """读取并自动洗练配置矩阵 (解除文件死锁 + 注入开箱演示版)"""
    cfg_data = None
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg_data = json.load(f)
        except Exception as e:
            if 'logger' in globals(): logger.error(f"⚠️ 配置读取异常: {e}", exc_info=True)
            pass
            
    # 👇 核心修复：退出 with 块，释放文件锁后，再执行升级重写
    if cfg_data is not None:
        return migrate_sys_config(cfg_data)
            
    # 🚀 如果文件不存在（全新安装），生成携带最新版本号与【极其酷炫的演示占位符】的初始矩阵
    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "is_setup": False, 
        # 预先塞入假数据，让主界面一打开就充满赛博感，而不是丑陋的空白
        "study": {"VSCode": "#DEMO_STUDY"}, 
        "game": {"Cyberpunk": "#DEMO_GAME", "Valorant": "#DEMO_GAME", "Steam": "#DEMO_GAME"}, 
        "music": {"网易云音乐": "#DEMO_MUSIC"}, 
        "timers": {
            "study_break_sec": 2 * 3600, 
            "game_limit_sec": int(2.5 * 3600),
            "weekly_goal_sec": 20 * 3600  # 🚀 新增：每周专注目标默认 20 小时
        },
        "ui_scale": "1.0",
        "retention_days": "30",
        "auto_start": False,
        "allow_network": True
    }

def atomic_save(file_path, data):
    """原子化写入引擎"""
    folder = os.path.dirname(file_path)
    if not os.path.exists(folder): os.makedirs(folder, exist_ok=True)
    temp_file = file_path + ".tmp"
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        if os.path.exists(file_path): os.replace(temp_file, file_path)
        else: os.rename(temp_file, file_path)
    except Exception as e:
        if os.path.exists(temp_file): 
            try: os.remove(temp_file)
            except: pass
        # 写入黑匣子，并保留完整报错堆栈
        logger.error(f"💾 数据固化失败 [目标: {file_path}]", exc_info=True)
        # 弹窗提示用户
        try:
            ctypes.windll.user32.MessageBoxW(0, f"数据保存失败，请检查 C 盘空间或权限！\n详情请查看日志。", "写入异常", 0x10)
        except: pass
def save_data(data): atomic_save(DATA_FILE, data)
def save_sys_config(cfg): atomic_save(CONFIG_FILE, cfg)

# ==========================================
# ⚡ 注册表双向控制引擎 (合规版开机自启)
# ==========================================
def set_autostart(enable: bool):
    """安全地向 Windows 注册表写入或擦除自启项"""
    try:
        if getattr(sys, 'frozen', False): 
            app_path = sys.executable
        else: 
            app_path = os.path.abspath(__file__)
            
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
        
        if enable:
            winreg.SetValueEx(key, "Nebula", 0, winreg.REG_SZ, f'"{app_path}"')
            print("🚀 系统矩阵注入成功：已开启开机自启")
        else:
            try: 
                winreg.DeleteValue(key, "Nebula")
                print("🛑 系统矩阵剥离成功：已关闭开机自启")
            except FileNotFoundError: 
                pass # 本来就没有，安全忽略
                
        winreg.CloseKey(key)
    except Exception as e: 
        logger.error("⚙️ 注册表注入被拒绝（可能被杀毒软件拦截）", exc_info=True)
        # 如果是界面操作导致的，通过 ctypes 弹个友好的系统原生弹窗
        ctypes.windll.user32.MessageBoxW(0, "开机自启设置失败！\n这通常是因为 Windows Defender 或杀毒软件拦截了注册表写入。\n请将本软件加入白名单后重试。", "权限被拒绝", 0x30)
# ==========================================
# 0. 悬停提示引擎 (Tooltip)
# ==========================================
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tipwindow or not self.text: return
        x, y, _, cy = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() + 20
        y = y + cy + self.widget.winfo_rooty() + 20
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.attributes("-topmost", True)
        tk.Label(tw, text=self.text, justify="left", background="#27272a", foreground="white", 
                 relief="solid", borderwidth=1, font=("Microsoft YaHei", 9)).pack(ipadx=4, ipady=2)

    def hide_tip(self, event=None):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None

# ==========================================
# 1. 底层数据流转逻辑
# ==========================================
# ==========================================
# 🧬 核心业务数据洗练引擎 (Data Schema Migration)
# ==========================================
CURRENT_DATA_VERSION = 2.0

def migrate_daily_logs(db):
    """时空隧道：对历史日志进行深度洗练，修补远古数据的结构空洞"""
    if not isinstance(db, dict):
        return {"schema_version": CURRENT_DATA_VERSION}

    current_ver = db.get("schema_version", 1.0)

    # 🚀 向上迁移通道：V1.0 -> V2.0
    if current_ver < 2.0:
        print(f">>> 发现旧版核心日志矩阵 (V{current_ver})，正在执行结构重组至 V2.0...")
        
        # 遍历所有历史日期，填补过去可能缺失的新维度（比如以前没写睡眠、没统计音乐）
        for key, day_data in db.items():
            # 跳过非日期的元数据字段 (如 schema_version, last_heartbeat)
            if not key.replace("-", "").isdigit():
                continue
            
            if isinstance(day_data, dict):
                day_data.setdefault("study_total", 0)
                day_data.setdefault("study_apps", {"vscode": 0, "chrome": 0, "bilibili": 0})
                day_data.setdefault("game_total", 0)
                day_data.setdefault("game_apps", {})
                day_data.setdefault("music_total", 0)
                day_data.setdefault("sleep", {"pc_shutdown": "", "sleep_time": "", "duration": "未记录"})

        # 升级完成，打上最新版本思想钢印
        db["schema_version"] = 2.0
        
        # 立即将洗练后的数据固化到硬盘
        save_data(db)
        print(">>> 核心日志矩阵平滑升级完成！")

    return db

def load_data():
    """读取并自动洗练日志矩阵 (解除文件死锁版)"""
    db_data = None
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                db_data = json.load(f)
        except Exception as e:
            if 'logger' in globals(): logger.error(f"⚠️ 核心数据读取异常: {e}", exc_info=True)
            pass
            
    # 👇 核心修复：退出 with 块，释放文件锁后，再执行升级重写
    if db_data is not None:
        return migrate_daily_logs(db_data)
            
    # 全新初始状态
    return {"schema_version": CURRENT_DATA_VERSION}

def init_today_data(data, date_str):
    if date_str not in data: data[date_str] = {}
    if "study_total" not in data[date_str]:
        data[date_str] = {
            "study_total": 0, "study_apps": {"vscode": 0, "chrome": 0, "bilibili": 0},
            "game_total": 0, "game_apps": {},
            "music_total": 0,
            "sleep": {"pc_shutdown": "", "sleep_time": "", "duration": "未记录"}
        }
    if "music_total" not in data[date_str]: data[date_str]["music_total"] = 0
    return data


# ==========================================
# 📝 富文本架构师笔记引擎
# ==========================================
# ==========================================
# 📝 富文本架构师笔记引擎 (V2 极客日历版)
# ==========================================
class NoteWindow(ctk.CTkToplevel):
    def __init__(self, master, category_name):
        super().__init__(master)
        self.category = category_name
        # 分类名可能包含特殊字符，做最小安全化，防止路径冲突
        self.category_slug = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(category_name)).strip("_") or "notes"
        self.title(f"ARCHIVE TERMINAL - {category_name}")
        
        # 1. 初始化时间系统与兼容旧数据
        today = datetime.now()
        self.current_date = today.strftime("%Y-%m-%d")
        self.cal_year = today.year
        self.cal_month = today.month
        self.image_refs = [] 

        # 新版目录结构：Notes/<category>/<YYYY-MM>/<YYYY-MM-DD>.txt
        self.category_dir = os.path.join(NOTES_DIR, self.category_slug)
        os.makedirs(self.category_dir, exist_ok=True)

        # 自动迁移旧版本单文件到“当天文件”
        old_path = os.path.join(NOTES_DIR, f"{self.category}.txt")
        new_path = self._note_path(self.current_date)
        if os.path.exists(old_path) and not os.path.exists(new_path):
            os.makedirs(os.path.dirname(new_path), exist_ok=True)
            os.rename(old_path, new_path)

        # 2. 窗口UI设定 (加入动态物理倍率)
        scale = float(master.sys_config.get("ui_scale", "1.0")) # 读取设置中的倍率
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = int((sw / 2.2) * scale), int((sh / 1.6) * scale) # 乘上倍率
        
        self.geometry(f"{w}x{h}+{int((sw-w)/2)}+{int((sh-h)/2)}")
        self.configure(fg_color="#09090b")
        self.attributes("-topmost", True)
        
        # 3. 布局：左侧日历侧边栏，右侧编辑区 (侧边栏宽度同步等比放大)
        self.left_panel = ctk.CTkFrame(self, width=int(280 * scale), fg_color="#111111", corner_radius=0, border_width=1, border_color="#27272a")
        self.left_panel.pack(side="left", fill="y")
        self.left_panel.pack_propagate(False) # 锁定侧边栏宽度
        
        self.right_panel = ctk.CTkFrame(self, fg_color="#18181b", corner_radius=0)
        self.right_panel.pack(side="right", fill="both", expand=True)

        self.build_calendar()
        self.build_editor()
        self._update_path_hint()
        self.load_content(self.current_date)

        # 关闭窗口兜底保存
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # --- 左侧：日历侧边栏模块 ---
    def build_calendar(self):
        # 清理旧组件
        for widget in self.left_panel.winfo_children(): widget.destroy()

        # 头部：分类名称
        header = ctk.CTkFrame(self.left_panel, fg_color="#18181b", corner_radius=0, border_width=1, border_color="#27272a")
        header.pack(fill="x")
        ctk.CTkLabel(header, text=f"📂 {self.category}", font=("Microsoft YaHei", 16, "bold"), text_color="#10b981").pack(pady=15)

        # 导航：月份切换
        nav_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        nav_frame.pack(fill="x", pady=(15, 5), padx=15)
        ctk.CTkButton(nav_frame, text="<", width=30, fg_color="#27272a", hover_color="#3f3f46", command=self.prev_month).pack(side="left")
        ctk.CTkLabel(nav_frame, text=f"{self.cal_year} - {self.cal_month:02d}", font=("Impact", 18), text_color="#00f2ff").pack(side="left", expand=True)
        ctk.CTkButton(nav_frame, text=">", width=30, fg_color="#27272a", hover_color="#3f3f46", command=self.next_month).pack(side="right")

        # 网格：日历主体
        grid_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        grid_frame.pack(expand=True, fill="both", padx=15, pady=10)

        for i, wd in enumerate(["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]):
            ctk.CTkLabel(grid_frame, text=wd, font=("Consolas", 11, "bold"), text_color="#52525b").grid(row=0, column=i, padx=4, pady=8)

        cal_matrix = calendar.monthcalendar(self.cal_year, self.cal_month)
        for r, week in enumerate(cal_matrix):
            for c, day in enumerate(week):
                if day != 0:
                    d_str = f"{self.cal_year}-{self.cal_month:02d}-{day:02d}"
                    new_path = self._note_path(d_str)
                    old_path = self._legacy_note_path(d_str)
                    has_note = (
                        (os.path.exists(new_path) and os.path.getsize(new_path) > 0)
                        or (os.path.exists(old_path) and os.path.getsize(old_path) > 0)
                    )

                    # 视觉逻辑：选中日=绿色，有笔记日=蓝色，空白日=暗色
                    btn_color = "#10b981" if d_str == self.current_date else ("#082f49" if has_note else "#18181b")
                    text_color = "#ffffff" if d_str == self.current_date else ("#00f2ff" if has_note else "#a1a1aa")

                    btn = ctk.CTkButton(grid_frame, text=str(day), width=32, height=32, corner_radius=8,
                                        fg_color=btn_color, hover_color="#3f3f46", text_color=text_color,
                                        command=lambda d=d_str: self.switch_date(d))
                    btn.grid(row=r+1, column=c, padx=2, pady=2)

    def prev_month(self):
        self.cal_month = 12 if self.cal_month == 1 else self.cal_month - 1
        if self.cal_month == 12: self.cal_year -= 1
        self.build_calendar()

    def next_month(self):
        self.cal_month = 1 if self.cal_month == 12 else self.cal_month + 1
        if self.cal_month == 1: self.cal_year += 1
        self.build_calendar()

    def _normalize_date_str(self, date_str: str) -> str:
        """标准化日期字符串，确保始终为 YYYY-MM-DD。无效输入不回退到今天，避免串写到同一天。"""
        raw = str(date_str).strip()
        try:
            return datetime.strptime(raw, "%Y-%m-%d").strftime("%Y-%m-%d")
        except Exception:
            # 关键：优先维持当前日期，避免所有内容被误写到“今天”
            cur = getattr(self, "current_date", "")
            if isinstance(cur, str) and len(cur) == 10:
                return cur
            return datetime.now().strftime("%Y-%m-%d")

    def _note_path(self, date_str: str) -> str:
        """按日路径：Notes/<category>/<YYYY-MM>/<YYYY-MM-DD>.txt（每天独立文件）"""
        date_str = self._normalize_date_str(date_str)
        month_dir = os.path.join(self.category_dir, date_str[:7])
        return os.path.join(month_dir, f"{date_str}.txt")

    def _legacy_note_path(self, date_str: str) -> str:
        """旧版路径：Notes/<category>_<YYYY-MM-DD>.txt"""
        date_str = self._normalize_date_str(date_str)
        return os.path.join(NOTES_DIR, f"{self.category}_{date_str}.txt")

    def _resolve_note_path(self, date_str: str) -> str:
        """优先新版；若存在旧版则自动迁移到新版后返回新版路径。"""
        date_str = self._normalize_date_str(date_str)
        new_path = self._note_path(date_str)
        old_path = self._legacy_note_path(date_str)

        if os.path.exists(new_path):
            return new_path

        if os.path.exists(old_path):
            try:
                os.makedirs(os.path.dirname(new_path), exist_ok=True)
                os.replace(old_path, new_path)
            except Exception:
                # 迁移失败时仍然返回当日新路径，避免不同日期意外写入同一旧文件
                return new_path

        return new_path

    def migrate_legacy_notes(self):
        """一键迁移当前分类下的旧笔记：
        1) Notes/<分类>_YYYY-MM-DD.txt -> Notes/<分类>/<YYYY-MM>/<YYYY-MM-DD>.txt
        2) Notes/<分类>.txt -> 当天文件
        """
        migrated = 0
        skipped = 0
        failed = 0

        # 迁移旧的“单文件分类笔记”到当天
        old_single = os.path.join(NOTES_DIR, f"{self.category}.txt")
        if os.path.exists(old_single):
            target = self._note_path(self.current_date)
            try:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                if os.path.exists(target):
                    with open(old_single, "r", encoding="utf-8") as f_old, open(target, "a", encoding="utf-8") as f_new:
                        old_content = f_old.read().strip()
                        if old_content:
                            sep = "\n\n" if os.path.getsize(target) > 0 else ""
                            f_new.write(sep + old_content)
                    os.remove(old_single)
                    migrated += 1
                else:
                    os.replace(old_single, target)
                    migrated += 1
            except Exception:
                failed += 1

        # 迁移旧的“按日扁平文件”
        pattern = os.path.join(NOTES_DIR, f"{self.category}_*.txt")
        for old_path in glob.glob(pattern):
            name = os.path.basename(old_path)
            prefix = f"{self.category}_"
            if not name.startswith(prefix):
                continue

            date_part = name[len(prefix):-4]  # 去掉 .txt
            try:
                datetime.strptime(date_part, "%Y-%m-%d")
            except Exception:
                continue

            new_path = self._note_path(date_part)
            try:
                os.makedirs(os.path.dirname(new_path), exist_ok=True)
                if os.path.exists(new_path):
                    # 已存在同日文件：合并，避免覆盖
                    with open(old_path, "r", encoding="utf-8") as f_old, open(new_path, "a", encoding="utf-8") as f_new:
                        old_content = f_old.read().strip()
                        if old_content:
                            sep = "\n\n" if os.path.getsize(new_path) > 0 else ""
                            f_new.write(sep + old_content)
                    os.remove(old_path)
                    migrated += 1
                else:
                    os.replace(old_path, new_path)
                    migrated += 1
            except Exception:
                failed += 1

        if migrated == 0 and failed == 0:
            msg = "没有检测到需要迁移的旧笔记文件。"
        else:
            msg = f"迁移完成：成功 {migrated}，失败 {failed}。"

        messagebox.showinfo("迁移结果", msg, parent=self)

        # 刷新当前视图
        self.build_calendar()
        self.load_content(self.current_date)

    def switch_date(self, date_str):
        self.save_content(show_feedback=True, feedback_text="✅ AUTO-SAVED") # 切换前自动保存
        self.current_date = self._normalize_date_str(date_str)
        self.build_calendar() # 刷新日历高亮状态
        self._set_dirty(False)
        self._update_date_title()
        self._update_path_hint()
        self.load_content(self.current_date)

    def on_close(self):
        # 🚀 核心修复：加一把防抖锁，只要进入关闭流程，立刻屏蔽后续的所有关闭信号
        if getattr(self, "_is_closing", False):
            return
        self._is_closing = True

        try:
            self.save_content(show_feedback=False)
        except Exception:
            pass

        toast = ctk.CTkToplevel(self)
        toast.title("已保存")
        toast.geometry("280x110")
        toast.attributes("-topmost", True)
        toast.configure(fg_color="#111111")
        ctk.CTkLabel(toast, text="✅ NOTE SAVED", font=("Consolas", 15, "bold"), text_color="#10b981").pack(expand=True)
        self.attributes("-disabled", True)
        # 🚀 注入存在性校验：安全销毁吐司和主窗体
        def _safe_destroy():
            if toast.winfo_exists(): toast.destroy()
            if self.winfo_exists(): self.destroy()
            
        self.after(750, _safe_destroy)

    # --- 右侧：富文本编辑模块 ---
    # --- 右侧：富文本编辑模块 (V2 沉浸式美学升级) ---
    def build_editor(self):
        self.top_bar = ctk.CTkFrame(self.right_panel, fg_color="#18181b", height=60, corner_radius=0, border_width=1, border_color="#27272a")
        self.top_bar.pack(fill="x", side="top")
        
        self.is_dirty = False
        self.lbl_date_title = ctk.CTkLabel(self.top_bar, text="", font=("Consolas", 18, "bold"), text_color="#00f2ff")
        self.lbl_date_title.pack(side="left", padx=30, pady=15)
        self._update_date_title()
        
        self.btn_save = ctk.CTkButton(self.top_bar, text="💾 SYNC MATRIX", width=130, height=34, font=("Consolas", 12, "bold"), fg_color="#10b981", hover_color="#059669", corner_radius=6, command=self.save_content)
        self.btn_save.pack(side="right", padx=(8, 30))

        self.btn_gallery = ctk.CTkButton(self.top_bar, text="🖼️ 图库", width=70, height=34, font=("Microsoft YaHei", 12, "bold"), fg_color="#27272a", hover_color="#3f3f46", corner_radius=6, command=lambda: GalleryWindow(self.master))
        self.btn_gallery.pack(side="right", padx=(0, 6))
        
        self.btn_migrate = ctk.CTkButton(self.top_bar, text="🗂 MIGRATE", width=115, height=34, font=("Consolas", 11, "bold"), fg_color="#27272a", hover_color="#3f3f46", corner_radius=6, command=self.migrate_legacy_notes)
        self.btn_migrate.pack(side="right", padx=(0, 6))

        self.btn_copy_yesterday = ctk.CTkButton(self.top_bar, text="📅 COPY YESTERDAY", width=140, height=34, font=("Consolas", 11, "bold"), fg_color="#27272a", hover_color="#3f3f46", corner_radius=6, command=self.copy_yesterday_to_today)
        self.btn_copy_yesterday.pack(side="right", padx=(0, 6))

        self.btn_delete_day = ctk.CTkButton(self.top_bar, text="🗑 DELETE DAY", width=120, height=34, font=("Consolas", 11, "bold"), fg_color="#450a0a", hover_color="#7f1d1d", corner_radius=6, command=self.delete_current_day_note)
        self.btn_delete_day.pack(side="right", padx=(0, 6))

        self.path_hint_var = tk.StringVar(value="")
        self.lbl_path_hint = ctk.CTkLabel(self.top_bar, textvariable=self.path_hint_var, font=("Consolas", 10), text_color="#71717a")
        self.lbl_path_hint.pack(side="left", padx=(10, 0), pady=15)

        self.format_bar = ctk.CTkFrame(self.right_panel, fg_color="#111111", height=45, corner_radius=0, border_width=1, border_color="#27272a")
        self.format_bar.pack(fill="x")
        
        self.font_family = ctk.CTkOptionMenu(self.format_bar, values=["Microsoft YaHei", "Consolas", "SimHei", "KaiTi"], width=140, height=28, fg_color="#18181b", button_color="#27272a", button_hover_color="#3f3f46", font=("Consolas", 12), command=self.apply_font_family)
        self.font_family.pack(side="left", padx=(30, 10), pady=8)
        
        self.font_size = ctk.CTkOptionMenu(self.format_bar, values=["12", "14", "16", "18", "20", "24", "32"], width=80, height=28, fg_color="#18181b", button_color="#27272a", button_hover_color="#3f3f46", font=("Consolas", 12), command=self.apply_font_size)
        self.font_size.set("14")
        self.font_size.pack(side="left", padx=(0, 15))
        
        btn_kwargs = {"width": 36, "height": 28, "fg_color": "#18181b", "hover_color": "#27272a", "corner_radius": 4}
        ctk.CTkButton(self.format_bar, text="B", font=("Arial", 14, "bold"), command=self.apply_bold, **btn_kwargs).pack(side="left", padx=4)
        ctk.CTkButton(self.format_bar, text="I", font=("Arial", 14, "italic"), command=self.apply_italic, **btn_kwargs).pack(side="left", padx=4)
        ctk.CTkButton(self.format_bar, text="🎨", font=("Arial", 14), command=self.apply_color, **btn_kwargs).pack(side="left", padx=4)
        ctk.CTkButton(self.format_bar, text="🔍", font=("Arial", 14), command=self.open_search_panel, **btn_kwargs).pack(side="left", padx=4)

        # 🚀 核心修复：只保留这一个文本渲染层，彻底解决保存读取错位问题
        self.text_frame = ctk.CTkFrame(self.right_panel, fg_color="#09090b", corner_radius=0)
        self.text_frame.pack(fill="both", expand=True)

        self.scrollbar = ctk.CTkScrollbar(self.text_frame, width=12, fg_color="transparent", button_color="#27272a", button_hover_color="#3f3f46")
        self.scrollbar.pack(side="right", fill="y", padx=(0, 2), pady=2)

        self.text_area = tk.Text(self.text_frame, bg="#09090b", fg="#e4e4e7", insertbackground="#10b981", 
                                 selectbackground="#059669", selectforeground="#ffffff", font=("Microsoft YaHei", 14), 
                                 padx=40, pady=35, borderwidth=0, highlightthickness=0,
                                 spacing1=10, spacing2=6, spacing3=10, yscrollcommand=self.scrollbar.set, wrap="word")
        self.text_area.pack(fill="both", expand=True)
        self.scrollbar.configure(command=self.text_area.yview)
        
        self.text_area.bind('<Control-v>', self.paste_image)
        self.text_area.bind('<<Modified>>', self.on_text_modified)

    def _set_dirty(self, dirty: bool):
        self.is_dirty = bool(dirty)
        self._update_date_title()

    def _update_date_title(self):
        if not hasattr(self, "lbl_date_title") or not self.lbl_date_title.winfo_exists():
            return
        star = " *" if getattr(self, "is_dirty", False) else ""
        self.lbl_date_title.configure(text=f"DATE // {self.current_date}{star}")

    def on_text_modified(self, _event=None):
        """🚀 终极修复：彻底斩断 Tkinter 文本框的无限死循环"""
        try:
            # 1. 关键防御：检查标志位，如果是 False 立刻退出，绝不往下走！
            if not self.text_area.edit_modified():
                return

            # 2. 标记标题栏小星星
            if not getattr(self, "is_dirty", False):
                self._set_dirty(True)

            # 3. 复位标志位 (此操作会再次触发事件，但会被上面的 if 成功拦截)
            self.text_area.edit_modified(False)
        except Exception:
            pass

    def _update_path_hint(self):
        path = self._resolve_note_path(self.current_date)
        self.path_hint_var.set(f"PATH // {path}")

    def copy_yesterday_to_today(self):
        today = self._normalize_date_str(self.current_date)
        y_day = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")

        today_path = self._resolve_note_path(today)
        y_path = self._resolve_note_path(y_day)

        if not os.path.exists(y_path):
            messagebox.showwarning("复制失败", f"未找到昨天笔记：{y_day}", parent=self)
            return

        try:
            with open(y_path, "r", encoding="utf-8") as f:
                y_content = f.read().strip()
            if not y_content:
                messagebox.showwarning("复制失败", f"昨天笔记为空：{y_day}", parent=self)
                return

            # 🚀 正确的复制日记逻辑
            os.makedirs(os.path.dirname(today_path), exist_ok=True)
            with open(today_path, "w", encoding="utf-8") as f:
                f.write(y_content)

            self.load_content(today)
            self.save_content(show_feedback=True, feedback_text="✅ COPIED")
            messagebox.showinfo("复制成功", f"已把 {y_day} 内容复制到 {today}", parent=self)
        except Exception as e:
            messagebox.showerror("复制失败", f"操作异常：{e}", parent=self)

    def delete_current_day_note(self):
        date_str = self._normalize_date_str(self.current_date)
        path = self._resolve_note_path(date_str)

        if not os.path.exists(path) and not self.text_area.get("1.0", tk.END).strip():
            messagebox.showinfo("无需删除", f"{date_str} 没有可删除内容", parent=self)
            return

        ok = messagebox.askyesno("确认删除", f"确定删除 {date_str} 的日记内容吗？\n此操作不可撤销。", parent=self)
        if not ok:
            return

        try:
            if os.path.exists(path):
                os.remove(path)
            self.text_area.delete("1.0", tk.END)
            self.save_content(show_feedback=True, feedback_text="🗑 DELETED")
        except Exception as e:
            messagebox.showerror("删除失败", f"操作异常：{e}", parent=self)

    # --- 富文本渲染逻辑 ---
    def apply_tag(self, tag_name, **kwargs):
        try:
            self.text_area.tag_add(tag_name, "sel.first", "sel.last")
            self.text_area.tag_config(tag_name, **kwargs)
        except tk.TclError: pass 

    def apply_font_family(self, choice):
        f = font.Font(self.text_area, self.text_area.cget("font")); f.configure(family=choice)
        self.apply_tag(f"family_{choice}", font=f)

    def apply_font_size(self, choice):
        f = font.Font(self.text_area, self.text_area.cget("font")); f.configure(size=int(choice))
        self.apply_tag(f"size_{choice}", font=f)

    def apply_bold(self):
        f = font.Font(self.text_area, self.text_area.cget("font")); f.configure(weight="bold")
        self.apply_tag("bold", font=f)

    def apply_italic(self):
        f = font.Font(self.text_area, self.text_area.cget("font")); f.configure(slant="italic")
        self.apply_tag("italic", font=f)

    def apply_color(self):
        color = colorchooser.askcolor(title="选择字体颜色")[1]
        if color: self.apply_tag(f"color_{color}", foreground=color)

    def process_and_insert_image(self, img):
        max_width = int(self.winfo_width() * 0.5)
        if img.size[0] > max_width:
            w_percent = (max_width / float(img.size[0]))
            img = img.resize((max_width, int(float(img.size[1]) * float(w_percent))), Image.Resampling.LANCZOS)
        
        img_name = f"img_{int(time.time())}.png"
        img.save(os.path.join(IMAGE_DIR, img_name))
        
        photo = ImageTk.PhotoImage(img)
        self.image_refs.append(photo)
        
        # 🚀 限制内存池最大图片引用数量 (保留最近 20 张防撑爆内存)
        if len(self.image_refs) > 20:
            self.image_refs.pop(0) 

        self.text_area.image_create(tk.INSERT, image=photo)
        self.text_area.insert(tk.INSERT, "\n")
        
        # 🚀 致命一击：物理释放底层 PIL 原图的 C 语言内存块！
        try: img.close()
        except: pass
    def paste_image(self, event):
        img = ImageGrab.grabclipboard()
        if img:
            self.process_and_insert_image(img)
            return "break"

    def open_search_panel(self):
        if hasattr(self, "search_win") and self.search_win and self.search_win.winfo_exists():
            self.search_win.lift()
            self.search_win.focus_force()
            return

        self.search_win = ctk.CTkToplevel(self)
        self.search_win.title("搜索日记")
        self.search_win.geometry("780x520")
        self.search_win.attributes("-topmost", True)
        self.search_win.configure(fg_color="#111111")

        top = ctk.CTkFrame(self.search_win, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(14, 8))

        self.search_var = tk.StringVar(value="")
        self.search_entry = ctk.CTkEntry(top, textvariable=self.search_var, placeholder_text="输入关键词（搜索日期和内容）")
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(top, text="搜索", width=90, command=self._perform_search).pack(side="left")
        self.search_entry.bind("<Return>", lambda _e: self._search_and_jump_first())

        self.search_result_box = tk.Listbox(self.search_win, bg="#09090b", fg="#e4e4e7", selectbackground="#27272a", borderwidth=0, highlightthickness=0)
        self.search_result_box.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        self.search_result_box.bind("<Double-Button-1>", self._open_selected_search_result)
        self.search_result_box.bind("<Return>", self._open_selected_search_result)

        # Esc 快速关闭
        self.search_win.bind("<Escape>", lambda _e: self.search_win.destroy())
        self.search_entry.bind("<Escape>", lambda _e: self.search_win.destroy())
        self.search_result_box.bind("<Escape>", lambda _e: self.search_win.destroy())

        hint = ctk.CTkLabel(self.search_win, text="回车：搜索并跳到第一条；双击/回车：打开选中结果；Esc：关闭", font=("Microsoft YaHei", 11), text_color="#71717a")
        hint.pack(pady=(0, 12))

        self.search_entry.focus_force()

    def _iter_all_note_files(self):
        for root, _dirs, files in os.walk(self.category_dir):
            for fn in files:
                if fn.lower().endswith(".txt"):
                    yield os.path.join(root, fn)

    def _highlight_kw(self, text: str, kw: str) -> str:
        if not kw:
            return text
        low_text = text.lower()
        low_kw = kw.lower()
        i = low_text.find(low_kw)
        if i < 0:
            return text
        j = i + len(kw)
        return f"{text[:i]}【{text[i:j]}】{text[j:]}"

    def _perform_search(self):
        kw_raw = (self.search_var.get() or "").strip()
        kw = kw_raw.lower()
        self.search_result_box.delete(0, tk.END)
        self._search_results = []

        if not kw:
            self.search_result_box.insert(tk.END, "请输入关键词")
            return

        results = []
        for p in self._iter_all_note_files():
            try:
                date_str = os.path.basename(p).replace(".txt", "")
                with open(p, "r", encoding="utf-8") as f:
                    content = f.read()
                if kw in date_str.lower() or kw in content.lower():
                    preview = content.replace("\n", " ").strip()[:80]
                    preview = self._highlight_kw(preview, kw_raw)
                    date_show = self._highlight_kw(date_str, kw_raw)
                    results.append((date_str, p, preview, date_show))
            except Exception:
                continue

        if not results:
            self.search_result_box.insert(tk.END, "未找到匹配结果")
            return

        results.sort(key=lambda x: x[0], reverse=True)
        self._search_results = results
        for idx, (_date_sort, _p, preview, date_show) in enumerate(results, 1):
            self.search_result_box.insert(tk.END, f"{idx:03d} | {date_show} | {preview}")

    def _search_and_jump_first(self):
        self._perform_search()
        if not hasattr(self, "_search_results") or not self._search_results:
            return
        self.search_result_box.selection_clear(0, tk.END)
        self.search_result_box.selection_set(0)
        self.search_result_box.activate(0)
        self._open_selected_search_result()

    def _open_selected_search_result(self, _event=None):
        if not hasattr(self, "_search_results"):
            return
        sel = self.search_result_box.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < 0 or idx >= len(self._search_results):
            return

        date_str = self._search_results[idx][0]
        self.switch_date(date_str)
        if hasattr(self, "search_win") and self.search_win and self.search_win.winfo_exists():
            self.search_win.destroy()

    # --- IO 数据读写 (支持按日规整) ---
    def save_content(self, show_feedback=True, feedback_text="✅ SYNCED"):
        content = self.text_area.get("1.0", tk.END).strip()
        path = self._resolve_note_path(self.current_date)

        if content:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        else:
            if os.path.exists(path):
                os.remove(path) # 内容清空则删除文件，保持整洁

        self._set_dirty(False)
        if show_feedback:
            self.btn_save.configure(text=feedback_text, fg_color="#3b82f6")
            # 🚀 注入存在性校验：如果按钮还没死，才给它变色
            def _reset_btn():
                if hasattr(self, "btn_save") and self.btn_save.winfo_exists():
                    self.btn_save.configure(text="💾 SYNC MATRIX", fg_color="#10b981")
            self.after(2600, _reset_btn)
            
        self.build_calendar() # 刷新日历上的蓝点指示器
        self._update_path_hint()

    def load_content(self, date_str):
        self.text_area.delete("1.0", tk.END)
        self.image_refs.clear()
        date_str = self._normalize_date_str(date_str)
        path = self._resolve_note_path(date_str)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self.text_area.insert("1.0", f.read())

        try:
            self.text_area.edit_modified(False)
        except Exception:
            pass
        self._set_dirty(False)

# ==========================================
# 🖼️ 全息图库管理矩阵 (Image Gallery Panel)
# ==========================================
class GalleryWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("ASSET ARCHIVE (图库矩阵)")
        
        scale = float(master.sys_config.get("ui_scale", "1.0"))
        w, h = int(800 * scale), int(600 * scale)
        self.geometry(f"{w}x{h}")
        self.attributes("-topmost", True)
        self.configure(fg_color="#09090b")
        self.gallery_refs = [] # 保护图片不被回收

        top_bar = ctk.CTkFrame(self, fg_color="#18181b", corner_radius=0, height=60, border_width=1, border_color="#27272a")
        top_bar.pack(fill="x")
        
        ctk.CTkLabel(top_bar, text="🖼️ ASSET ARCHIVE", font=("Impact", 22), text_color="#10b981").pack(side="left", padx=20, pady=15)
        
        btn_export = ctk.CTkButton(top_bar, text="📦 批量导出全部影像", font=("Microsoft YaHei", 12, "bold"), 
                                   fg_color="#2563eb", hover_color="#1d4ed8", command=self.export_all_images)
        btn_export.pack(side="right", padx=20)

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="#111111", corner_radius=0)
        self.scroll.pack(fill="both", expand=True, padx=10, pady=10)

        self.load_images()

    def load_images(self):
        """扫描 Images 目录，以网格形式瀑布流渲染"""
        if not os.path.exists(IMAGE_DIR):
            return
            
        # 按时间倒序排列图片
        img_files = sorted([f for f in os.listdir(IMAGE_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg'))], reverse=True)
        
        if not img_files:
            ctk.CTkLabel(self.scroll, text="图库中暂无影像资料", font=("Consolas", 14), text_color="#71717a").pack(pady=50)
            return

        # 动态网格计算 (每行 4 张图)
        COLUMNS = 4
        for idx, filename in enumerate(img_files):
            filepath = os.path.join(IMAGE_DIR, filename)
            try:
                # 缩略图引擎
                img = Image.open(filepath)
                img.thumbnail((160, 160), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.gallery_refs.append(photo)

                row, col = idx // COLUMNS, idx % COLUMNS
                
                card = ctk.CTkFrame(self.scroll, fg_color="#18181b", corner_radius=8, border_width=1, border_color="#27272a")
                card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
                
                # 图片
                lbl_img = tk.Label(card, image=photo, bg="#18181b", cursor="hand2")
                lbl_img.pack(padx=10, pady=(10, 5))
                
                # 文件名 (去除时间戳前缀，尽量美观)
                display_name = filename.replace("img_", "")
                if len(display_name) > 15: display_name = display_name[:12] + "..."
                ctk.CTkLabel(card, text=display_name, font=("Consolas", 10), text_color="#a1a1aa").pack(pady=(0, 5))
                
                # 点击图片调用系统默认查看器打开原图
                lbl_img.bind("<Button-1>", lambda e, p=filepath: os.startfile(p))
                
            except Exception as e:
                pass

    def export_all_images(self):
        """一键打包图库"""
        dest_dir = filedialog.askdirectory(parent=self, title="选择影像导出目标文件夹")
        if not dest_dir: return
        
        try:
            export_folder = os.path.join(dest_dir, f"Nebula_Images_Export_{int(time.time())}")
            shutil.copytree(IMAGE_DIR, export_folder)
            messagebox.showinfo("导出成功", f"图库已全部导出至：\n{export_folder}", parent=self)
            os.startfile(export_folder) # 自动打开文件夹
        except Exception as e:
            messagebox.showerror("导出失败", f"发生了未知错误：\n{e}", parent=self)

# ==========================================
# ⚙️ 神经网络初次校准向导 (V4 合规隐私引导版)
# ==========================================
class SetupWizard(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("SYSTEM CALIBRATION (首次部署协议)")
        self.geometry("650x700")
        self.attributes("-topmost", True)
        self.configure(fg_color="#09090b")
        
        # 🚀 物理级合规拦截：如果用户不同意隐私协议直接关闭窗口，程序必须断电，绝不静默运行！
        self.protocol("WM_DELETE_WINDOW", self.abort_setup)

        self.cfg = {"is_setup": True, "study": {}, "game": {}, "music": {}}
        self.section_frames = {} 
        self.current_step = 1  # 引导流进度控制：现已扩展为 4 步

        # 核心内容容器 (动态替换内容)
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True, padx=35, pady=30)

        # 底部导航容器
        self.footer_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.footer_frame.pack(fill="x", side="bottom", padx=35, pady=25)

        self.btn_next = ctk.CTkButton(self.footer_frame, text="AGREE & CONTINUE >", font=("Impact", 18), 
                                      fg_color="#10b981", hover_color="#059669", height=45, command=self.next_step)
        self.btn_next.pack(side="right")

        # 初始化渲染第一步
        self.render_step()
        _bind_tkdnd_drop(self, self._on_files_dropped)

    def render_step(self):
        """渲染当前引导步骤的 UI"""
        # 清空当前画布
        for w in self.content_frame.winfo_children():
            w.destroy()

        if self.current_step == 1:
            # === 🚀 STEP 1: 隐私主权协议 (Privacy Protocol) ===
            ctk.CTkLabel(self.content_frame, text="PRIVACY PROTOCOL", font=("Impact", 32), text_color="#10b981").pack(pady=(40, 20))
            
            privacy_text = (
                "【绝对的数据主权声明】\n\n"
                "在正式接入 Nebula 矩阵之前，我们向您作出最高级别的隐私承诺：\n\n"
                "1. 物理本地封存：您的所有应用时长、焦点记录、架构日记及偏好配置，均采取【纯本地闭环存储】，牢牢封锁在您的私人硬盘中。\n\n"
                "2. 零隐私收集：本系统【绝对不会】向任何外部服务器收集、上传、分析或售卖您的使用痕迹。\n\n"
                "3. 最低网络交互：系统仅在您主动授权的情况下，请求极少量的公开 API 服务（如获取当地天气、拉取每日金句）。\n\n"
                "在此按下同意，即代表您充分知晓并授权 Nebula 在本地设备上追踪进程时长以守护您的算力。"
            )
            ctk.CTkLabel(self.content_frame, text=privacy_text, font=("Microsoft YaHei", 14), text_color="#d1d5db", justify="left", wraplength=550).pack(pady=15)
            
            # 进度指示器
            ctk.CTkLabel(self.content_frame, text="● ○ ○ ○", font=("Consolas", 16), text_color="#71717a").pack(side="bottom", pady=20)
            
            self.btn_next.configure(text="AGREE & CONTINUE (同意并继续) >", fg_color="#10b981", hover_color="#059669")
            self.btn_next.pack(side="right")

        elif self.current_step == 2:
            # === STEP 2: 概念与使命 (What is this?) ===
            ctk.CTkLabel(self.content_frame, text="INITIATING NEBULA", font=("Impact", 32), text_color="#00f2ff").pack(pady=(50, 20))
            
            intro_text = (
                "欢迎接入 Nebula (星云) 终端。\n\n"
                "这不是一个普通的番茄钟，而是一个伴随你成长的【赛博监控矩阵】。\n"
                "它将在本地静默追踪你的代码算力（专注时长）与娱乐消耗（游戏时长），\n"
                "生成全景数据面板，并在你过度沉迷时，触发强制的视觉拦截屏障。"
            )
            ctk.CTkLabel(self.content_frame, text=intro_text, font=("Microsoft YaHei", 15), text_color="#d1d5db", justify="center", wraplength=550).pack(pady=20)
            
            # 进度指示器
            ctk.CTkLabel(self.content_frame, text="○ ● ○ ○", font=("Consolas", 16), text_color="#71717a").pack(side="bottom", pady=20)
            
            self.btn_next.configure(text="NEXT PROTOCOL >", fg_color="#2563eb", hover_color="#1d4ed8")

        elif self.current_step == 3:
            # === STEP 3: 交互与退出协议 (How to exit?) ===
            ctk.CTkLabel(self.content_frame, text="SYSTEM INTERACTION", font=("Impact", 32), text_color="#f59e0b").pack(pady=(40, 20))
            
            interact_text = (
                "【双重形态与呼出】\n"
                "在主界面点击右上角「—」，终端将缩小为桌面悬浮宠物（极客学霸猫 / 狂暴游戏猫）。\n"
                "双击猫咪即可将其重新展开为主面板。\n\n"
                "【如何彻底退出？】\n"
                "点击主面板右上角的「✕」只会将终端隐蔽至电脑右下角的【系统托盘】（任务栏小箭头内）。\n"
                "若需彻底拔管（完全退出软件），请右键点击系统托盘的 星云图标，选择「❌ 彻底拔管」。"
            )
            ctk.CTkLabel(self.content_frame, text=interact_text, font=("Microsoft YaHei", 14), text_color="#d1d5db", justify="left", wraplength=550).pack(pady=15)
            
            # 进度指示器
            ctk.CTkLabel(self.content_frame, text="○ ○ ● ○", font=("Consolas", 16), text_color="#71717a").pack(side="bottom", pady=20)

        elif self.current_step == 4:
            # === STEP 4: 神经校准 (拖拽添加路径) ===
            self.btn_next.pack_forget() # 隐藏 Next 按钮，展示终极 Deploy 和 Skip 按钮
            self.build_calibration_ui()

    def next_step(self):
        """流转到下一步"""
        if self.current_step < 4:
            self.current_step += 1
            self.render_step()

    def build_calibration_ui(self):
        """Step 4 的实体界面 (拖拽添加 UI)"""
        ctk.CTkLabel(self.content_frame, text="NEURAL PATHWAY CALIBRATION", font=("Impact", 24), text_color="#00f2ff").pack(pady=(0, 5))
        ctk.CTkLabel(
            self.content_frame, 
            text="请点击添加或【直接拖入 .exe 文件】进行自动识别\n💡 建议拖入你最常用的 学习、音乐、游戏等程序，建立快捷矩阵", 
            font=("Microsoft YaHei", 12), text_color="#10b981", justify="center"
        ).pack(pady=(0, 15))

        self.scroll = ctk.CTkScrollableFrame(self.content_frame, fg_color="#111111", corner_radius=10, border_width=1, border_color="#27272a")
        self.scroll.pack(fill="both", expand=True, padx=5, pady=5)

        self.build_section("💻 STUDIO (生产力 / 学习软件)", "study", "#00f2ff")
        self.build_section("🎮 GAMING (娱乐 / 游戏软件)", "game", "#ef4444")
        self.build_section("🎵 MUSIC (音乐播放器)", "music", "#f59e0b")

        # 进度指示器
        ctk.CTkLabel(self.content_frame, text="○ ○ ○ ●", font=("Consolas", 16), text_color="#71717a").pack(side="bottom", pady=(10, 0))

        # 部署按钮区域 (使用横向排列容纳两个按钮)
        btn_area = ctk.CTkFrame(self.footer_frame, fg_color="transparent")
        btn_area.pack(fill="x", expand=True)

        self.btn_skip = ctk.CTkButton(btn_area, text="跳过配置 (直接体验)", font=("Microsoft YaHei", 13, "bold"), 
                                      fg_color="#27272a", hover_color="#3f3f46", text_color="#a1a1aa", height=45, 
                                      command=self.skip_setup)
        self.btn_skip.pack(side="left", padx=(0, 10))

        self.btn_deploy = ctk.CTkButton(btn_area, text="✅ DEPLOY SYSTEM (部署架构)", font=("Impact", 20), 
                                        fg_color="#10b981", hover_color="#059669", height=45, command=self.finish_setup)
        self.btn_deploy.pack(side="right", fill="x", expand=True)

    def build_section(self, title, key, color):
        frame = ctk.CTkFrame(self.scroll, fg_color="#18181b", corner_radius=8)
        frame.pack(fill="x", pady=10)
        self.section_frames[key] = frame 
        
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=10)
        ctk.CTkLabel(header, text=title, font=("Microsoft YaHei", 14, "bold"), text_color=color).pack(side="left")
        ctk.CTkButton(header, text="+ 添加 .exe", width=80, fg_color="#27272a", hover_color="#3f3f46", 
                      command=lambda: self.add_exe(key)).pack(side="right")

    def add_exe(self, key):
        try:
            self.lift()
            self.focus_force()
            file_path = filedialog.askopenfilename(parent=self, title="选择核心启动文件", filetypes=[("Executable", "*.exe")])
            if file_path: self._register_exe(key, file_path)
        except Exception as e:
            self.show_error(f"❌ 打开文件对话框失败\n{e}")

    def handle_drop(self, files):
        for f in files:
            try:
                file_path = f.decode('gbk') if isinstance(f, bytes) else str(f)
            except: continue
            
            if file_path.lower().endswith('.exe'):
                self.after(0, lambda p=file_path: self.ask_drop_category(p))
            elif file_path.lower().endswith('.lnk'):
                self.after(0, lambda: self.show_error("❌ 拒绝快捷方式\n请拖入本体 .exe 文件！"))
            else:
                self.after(0, lambda: self.show_error("❌ 格式错误\n仅支持 .exe 程序！"))

    def ask_drop_category(self, file_path):
        exe_name = os.path.basename(file_path).lower()
        prompt = ctk.CTkToplevel(self)
        prompt.title("分类确认")
        prompt.geometry("380x200")
        prompt.attributes("-topmost", True)
        prompt.configure(fg_color="#18181b")
        
        ctk.CTkLabel(prompt, text=f"📥 成功捕获实体: {exe_name}", font=("Consolas", 14, "bold"), text_color="#00f2ff").pack(pady=(25, 10))
        ctk.CTkLabel(prompt, text="请指示该进程所属的架构象限：", font=("Microsoft YaHei", 12), text_color="#a1a1aa").pack(pady=5)
        
        btn_frame = ctk.CTkFrame(prompt, fg_color="transparent")
        btn_frame.pack(pady=15)

        def assign(key):
            self._register_exe(key, file_path)
            prompt.destroy()

        ctk.CTkButton(btn_frame, text="💻 STUDIO", width=90, fg_color="#082f49", hover_color="#0284c7", command=lambda: assign("study")).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="🎮 GAMING", width=90, fg_color="#450a0a", hover_color="#dc2626", command=lambda: assign("game")).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="🎵 MUSIC", width=90, fg_color="#78350f", hover_color="#d97706", command=lambda: assign("music")).pack(side="left", padx=5)

    def _register_exe(self, key, file_path):
        exe_name = os.path.basename(file_path).lower()
        self.cfg[key][exe_name] = file_path
        def update_ui():
            parent_frame = self.section_frames[key]
            ctk.CTkLabel(parent_frame, text=f"✔️ {exe_name}", font=("Consolas", 12), text_color="#e4e4e7").pack(anchor="w", padx=20, pady=2)
        self.after(0, update_ui)

    def show_error(self, msg):
        err = ctk.CTkToplevel(self)
        err.title("WARNING")
        err.geometry("380x150")
        err.attributes("-topmost", True)
        err.configure(fg_color="#450a0a")
        ctk.CTkLabel(err, text=msg, text_color="#fca5a5", font=("Microsoft YaHei", 11, "bold"), justify="center").pack(expand=True)

    def finish_setup(self):
        if not any(self.cfg[k] for k in ["study", "game", "music"]):
            self.show_error("💡 架构为空: 请至少录入一个程序！")
            return
        try:
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cfg, f, indent=4, ensure_ascii=False)
            self.after(100, self.destroy)
        except Exception as e:
            self.show_error(f"❌ 部署失败: {e}")

    def skip_setup(self):
        """🚀 极客级开箱体验：生成带有占位符的临时矩阵"""
        demo_cfg = {
            "schema_version": 2.0,
            "is_setup": True, 
            "study": {"VSCode": "#DEMO_STUDY"}, 
            "game": {"Cyberpunk": "#DEMO_GAME", "Valorant": "#DEMO_GAME", "Steam": "#DEMO_GAME"}, 
            "music": {"网易云音乐": "#DEMO_MUSIC"},
            "timers": {"study_break_sec": 2 * 3600, "game_limit_sec": int(2.5 * 3600)},
            "ui_scale": "1.0",
            "retention_days": "30",
            "auto_start": False,
            "allow_network": True,
            "auto_backup": False,
            "backup_path": ""
        }
        try:
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(demo_cfg, f, indent=4, ensure_ascii=False)
            self.after(100, self.destroy)
        except Exception as e:
            self.show_error(f"❌ 跳过失败: {e}")

    def _on_files_dropped(self, paths):
        self.handle_drop(paths)
        
    def abort_setup(self):
        """物理级合规拦截：如果用户拒绝隐私协议，直接断电退出"""
        try: 
            self.destroy()
        except: 
            pass
        # 强行终止 Python 进程，防止后台引擎被非法拉起
        import os
        os._exit(0)

# ==========================================
# ⚙️ 运行时设置面板：编辑已部署的软件路径
# ==========================================
class SettingsPanel(ctk.CTkToplevel):
    def __init__(self, master, initial_cfg, on_save):
        super().__init__(master)
        self.title("SYSTEM SETTINGS (软件路径矩阵)")
        
        # 记录初始缩放，用于保存时比对是否需要重启
        self._initial_scale = str((initial_cfg or {}).get("ui_scale", "1.0"))
        
        # 🚀 物理级扩容：读取当前倍率，同步放大系统设置面板
        scale = float(self._initial_scale)
        w, h = int(820 * scale), int(680 * scale)
        self.geometry(f"{w}x{h}") 
        
        self.attributes("-topmost", True)
        self.configure(fg_color="#09090b")

        self._on_save = on_save
        # 🚀 记录初始缩放，用于保存时比对是否需要重启！
        self._initial_scale = str((initial_cfg or {}).get("ui_scale", "1.0"))
        
        # 深拷贝，避免边改边影响主进程
        self.cfg = {
            "is_setup": True,
            "study": dict((initial_cfg or {}).get("study") or {}),
            "game": dict((initial_cfg or {}).get("game") or {}),
            "music": dict((initial_cfg or {}).get("music") or {}),
            "timers": dict((initial_cfg or {}).get("timers") or {}),
            "auto_start": bool((initial_cfg or {}).get("auto_start", False)),
            # 👇 新增：读取联网权限，默认为 True
            "allow_network": bool((initial_cfg or {}).get("allow_network", True)),
            
            # 👇 核心新增：自动备份配置的记忆锚点
            "auto_backup": bool((initial_cfg or {}).get("auto_backup", False)),
            "backup_path": str((initial_cfg or {}).get("backup_path", "")),
            # 👇 新增：注入霓虹光效引擎的初始色
            "theme_study": str((initial_cfg or {}).get("theme_study", "#00f2ff")),
            "theme_game": str((initial_cfg or {}).get("theme_game", "#ef4444")),
        }
        
        self.cfg.setdefault("timers", {})
        self.cfg["timers"].setdefault("study_break_sec", 2 * 3600)
        self.cfg["timers"].setdefault("game_limit_sec", int(2.5 * 3600))
        # 🚀 新增：初始化时注入每周目标默认值 (20小时)
        self.cfg["timers"].setdefault("weekly_goal_sec", 20 * 3600)

        ctk.CTkLabel(
            self,
            text="SYSTEM SETTINGS",
            font=("Impact", 26),
            text_color="#00f2ff",
        ).pack(pady=(18, 6))
        ctk.CTkLabel(
            self,
            text="在这里维护学习/游戏/音乐软件路径（新增 / 替换 / 删除）",
            font=("Consolas", 12),
            text_color="#10b981",
        ).pack(pady=(0, 12))
        ctk.CTkLabel(
            self,
            text="支持拖拽：将 .exe 直接拖入此窗口即可自动添加（在当前标签页归类）",
            font=("Consolas", 11),
            text_color="#71717a",
        ).pack(pady=(0, 10))

        self.tabview = ctk.CTkTabview(
            self,
            fg_color="#111111",
            segmented_button_fg_color="#18181b",
            segmented_button_selected_color="#27272a",
            text_color="#00f2ff",
        )
        self.tabview.pack(expand=True, fill="both", padx=18, pady=12)

        self.tabs = {
            "study": self.tabview.add("STUDIO / 学习"),
            "game": self.tabview.add("GAMING / 游戏"),
            "music": self.tabview.add("MUSIC / 音乐"),
            "timers": self.tabview.add("TIMERS / 时长"),
            "system": self.tabview.add("SYSTEM / 系统"),
        }

        self.list_frames = {}
        for key in ["study", "game", "music"]:
            self._build_tab(key)
        self._build_timers_tab()
        self._build_system_tab(self.tabs["system"])
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=18, pady=(0, 16))

        ctk.CTkButton(
            bottom,
            text="💾 SAVE SETTINGS",
            height=38,
            fg_color="#10b981",
            hover_color="#059669",
            font=("Consolas", 14, "bold"),
            command=self._save,
        ).pack(side="right")

        # 拖拽：优先使用 tkinterdnd2（更稳）；不可用则仅支持“点击添加”
        _bind_tkdnd_drop(self, self._on_files_dropped)

    def _on_files_dropped(self, paths):
        # 与旧回调保持一致：逐个路径进入处理逻辑
        for p in (paths or []):
            try:
                self._handle_dropped_path(str(p))
            except Exception:
                pass

    def _decode_drop_path(self, f):
        try:
            if isinstance(f, bytes):
                # Windows 常见为 gbk，也兼容 utf-8
                try:
                    return f.decode("gbk")
                except Exception:
                    return f.decode("utf-8", errors="ignore")
            return str(f)
        except Exception:
            return ""

    def _current_category_key(self):
        try:
            tab_name = self.tabview.get()  # e.g. "STUDIO / 学习"
        except Exception:
            tab_name = ""
        name = (tab_name or "").upper()
        if "STUDIO" in name:
            return "study"
        if "GAMING" in name or "GAME" in name:
            return "game"
        if "MUSIC" in name:
            return "music"
        return ""

    def _handle_dropped_path(self, file_path: str):
        low = (file_path or "").lower()
        if low.endswith(".lnk"):
            self._show_drop_error("❌ 拒绝快捷方式\n请拖入本体 .exe 文件！")
            return
        if not low.endswith(".exe"):
            self._show_drop_error("❌ 格式错误\n仅支持拖入 .exe 程序！")
            return

        key = self._current_category_key()
        if key in ["study", "game", "music"]:
            exe_name = os.path.basename(file_path).lower()
            self.cfg[key][exe_name] = file_path
            self._render_list(key)
            return

        # 若当前不在三类标签页（比如 TIMERS），则询问归类
        self._ask_drop_category(file_path)
    def _export_data(self):
        """将深藏在 AppData 的数据导出到用户桌面"""
        from tkinter import filedialog
        import shutil
        
        # 假设你的数据文件保存在 DATA_FILE 变量中
        save_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON 数据文件", "*.json")],
            title="导出赛博终端数据",
            initialfile=f"CyberTerminal_Data_{datetime.now().strftime('%Y%m%d')}.json"
        )
        if save_path:
            try:
                shutil.copy(DATA_FILE, save_path)
                messagebox.showinfo("导出成功", f"数据已安全备份至：\n{save_path}", parent=self)
            except Exception as e:
                messagebox.showerror("导出失败", f"发生了未知错误：\n{e}", parent=self)

    def _clear_data(self):
        """物理级数据销毁"""
        confirm = messagebox.askyesno(
            "⚠️ 终极警告", 
            "此操作将永久抹除所有使用时长、日记和历史矩阵数据！\n且无法恢复（建议先导出备份）。\n\n确认执行物理清空吗？", 
            icon='warning', parent=self
        )
        if confirm:
            try:
                # 覆盖为空字典并保存
                save_data({}) 
                messagebox.showinfo("抹除完毕", "所有本地数据矩阵已物理清空。\n重启软件后生效。", parent=self)
            except Exception as e:
                pass
    def _copy_diagnostics(self):
        """🚀 一键生成并复制系统全景诊断报告"""
        import platform
        try:
            # 提取最后 8 行日志 (用于捕捉最近的报错)
            log_summary = "No recent logs found."
            log_path = os.path.join(APP_DIR, "terminal_core.log")
            if os.path.exists(log_path):
                with open(log_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    log_summary = "".join(lines[-8:]) if lines else "Log file is empty."

            # 组装极客风诊断报告
            schema_ver = self.cfg.get("schema_version", "Unknown")
            report = (
                "=== Nebula Diagnostic Report ===\n"
                f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"OS: {platform.system()} {platform.release()} ({platform.version()})\n"
                f"Architecture: {platform.machine()}\n"
                f"Python Version: {platform.python_version()}\n"
                f"Schema Version: {schema_ver}\n"
                f"UI Scale: {self.cfg.get('ui_scale', '1.0')}\n"
                f"Auto Start: {self.cfg.get('auto_start', False)}\n"
                "--- Recent Core Logs ---\n"
                f"{log_summary}\n"
                "============================================"
            )

            # 注入剪贴板
            self.clipboard_clear()
            self.clipboard_append(report)
            self.update() # 强制刷新，确保 Windows 剪贴板同步成功

            messagebox.showinfo("诊断报告已生成", "✅ 诊断信息已复制到剪贴板！\n你可以直接使用 Ctrl+V 粘贴给开发者排错。", parent=self)
            logger.info("用户主动提取了系统诊断报告。")
        except Exception as e:
            logger.error("生成诊断报告失败", exc_info=True)
            messagebox.showerror("生成失败", f"获取诊断信息失败: {e}", parent=self)
    def _ask_drop_category(self, file_path: str):
        exe_name = os.path.basename(file_path).lower()
        prompt = ctk.CTkToplevel(self)
        prompt.title("分类确认")
        prompt.geometry("380x200")
        prompt.attributes("-topmost", True)
        prompt.configure(fg_color="#18181b")

        ctk.CTkLabel(prompt, text=f"📥 捕获实体: {exe_name}", font=("Consolas", 14, "bold"), text_color="#00f2ff").pack(pady=(25, 10))
        ctk.CTkLabel(prompt, text="请指示该进程所属分类：", font=("Microsoft YaHei", 12), text_color="#a1a1aa").pack(pady=5)

        btn_frame = ctk.CTkFrame(prompt, fg_color="transparent")
        btn_frame.pack(pady=15)

        def assign(k):
            self.cfg[k][exe_name] = file_path
            self._render_list(k)
            prompt.destroy()

        ctk.CTkButton(btn_frame, text="💻 STUDIO", width=90, fg_color="#082f49", hover_color="#0284c7", command=lambda: assign("study")).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="🎮 GAMING", width=90, fg_color="#450a0a", hover_color="#dc2626", command=lambda: assign("game")).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="🎵 MUSIC", width=90, fg_color="#78350f", hover_color="#d97706", command=lambda: assign("music")).pack(side="left", padx=5)

    def _show_drop_error(self, msg: str):
        win = ctk.CTkToplevel(self)
        win.title("WARNING")
        win.geometry("380x150")
        win.attributes("-topmost", True)
        win.configure(fg_color="#450a0a")
        ctk.CTkLabel(win, text=msg, text_color="#fca5a5", font=("Microsoft YaHei", 11, "bold"), justify="center").pack(expand=True)

    def _build_tab(self, key):
        tab = self.tabs[key]

        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(14, 8))

        ctk.CTkButton(
            header,
            text="+ 添加 .exe",
            width=110,
            fg_color="#27272a",
            hover_color="#3f3f46",
            font=("Microsoft YaHei", 11, "bold"),
            command=lambda k=key: self._add_exe(k),
        ).pack(side="left")

        # 快速输入：支持粘贴 exe 路径（拖拽在 CTk 上不稳定时作为替代）
        self._quick_path_vars = getattr(self, "_quick_path_vars", {})
        self._quick_path_vars.setdefault(key, tk.StringVar(value=""))
        quick_entry = ctk.CTkEntry(
            header,
            width=320,
            textvariable=self._quick_path_vars[key],
            placeholder_text="在此粘贴 .exe 完整路径，然后回车添加",
        )
        quick_entry.pack(side="left", padx=(10, 6))
        def _submit_quick(_evt=None, k=key):
            p = (self._quick_path_vars[k].get() or "").strip().strip('"')
            if p:
                self._handle_dropped_path(p)  # 复用校验与归类逻辑
                self._quick_path_vars[k].set("")
        quick_entry.bind("<Return>", _submit_quick)

        def _paste_quick(k=key):
            try:
                p = (self.clipboard_get() or "").strip().strip('"')
            except Exception:
                p = ""
            if p:
                self._quick_path_vars[k].set(p)
                _submit_quick(k=k)

        ctk.CTkButton(
            header,
            text="📋 粘贴添加",
            width=90,
            fg_color="#27272a",
            hover_color="#3f3f46",
            font=("Microsoft YaHei", 11, "bold"),
            command=_paste_quick,
        ).pack(side="left")

        ctk.CTkLabel(
            header,
            text="提示：点击条目可“替换路径”，右侧可删除",
            font=("Consolas", 11),
            text_color="#a1a1aa",
        ).pack(side="left", padx=12)

        lst = ctk.CTkScrollableFrame(tab, fg_color="#18181b", corner_radius=10)
        lst.pack(expand=True, fill="both", padx=14, pady=(0, 14))
        self.list_frames[key] = lst

        self._render_list(key)

    def _sec_to_hm(self, sec: int):
        try:
            sec = int(sec or 0)
        except Exception:
            sec = 0
        if sec < 0:
            sec = 0
        h = sec // 3600
        m = (sec % 3600) // 60
        return h, m
    
    def _build_system_tab(self, parent_frame):
        """🚀 全新的系统与数据控制中心 (包含隐私与网络隔离)"""
        wrap = ctk.CTkScrollableFrame(parent_frame, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=10, pady=10)

        # ==========================================
        # 1. 👁️ 视觉与主题 (UI & Scaling)
        # ==========================================
        ctk.CTkLabel(wrap, text=">>> VISUAL & THEME / 视觉控制", font=("Consolas", 12, "bold"), text_color="#10b981").pack(anchor="w", pady=(0, 5))
        
        scale_frame = ctk.CTkFrame(wrap, fg_color="transparent")
        scale_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(scale_frame, text="面板物理放大倍率 (仅日记与数据窗)", font=("Microsoft YaHei", 12), text_color="#a1a1aa").pack(side="left")
        
        # 🚀 替换为 DoubleVar 以支持平滑过渡
        self.scale_var = ctk.DoubleVar(value=float(self.cfg.get("ui_scale", "1.0")))
        
        # 实时数值显示标签
        self.lbl_scale_val = ctk.CTkLabel(scale_frame, text=f"{self.scale_var.get():.2f}x", font=("Consolas", 13, "bold"), text_color="#00f2ff", width=45)
        self.lbl_scale_val.pack(side="right", padx=(5, 0))

        # 🚀 替换为 DoubleVar 以支持平滑过渡
        self.scale_var = ctk.DoubleVar(value=float(self.cfg.get("ui_scale", "1.0")))
        
        # 实时数值显示标签
        self.lbl_scale_val = ctk.CTkLabel(scale_frame, text=f"{self.scale_var.get():.2f}x", font=("Consolas", 13, "bold"), text_color="#00f2ff", width=45)
        self.lbl_scale_val.pack(side="right", padx=(5, 0))

        # 🛡️ 初始化防抖缓冲池
        self._scale_timer = None

        # 🚀 核心动态形变引擎 (加入 200ms 防抖算法)
        def on_scale_change(value):
            # 1. 轻量级操作：瞬间更新数字，保证滑块跟手的丝滑感
            rounded_val = round(value, 2)
            self.scale_var.set(rounded_val)
            self.lbl_scale_val.configure(text=f"{rounded_val}x")
            
            # 2. 拦截并取消上一次还没来得及执行的重绘任务
            if self._scale_timer is not None:
                self.after_cancel(self._scale_timer)
                
            # 3. 延时重绘：等用户停下鼠标 200 毫秒后，才执行沉重的全局形变
            def apply_scale():
                try:
                    ctk.set_widget_scaling(rounded_val)
                    ctk.set_window_scaling(rounded_val)
                except Exception:
                    pass
                    
            self._scale_timer = self.after(200, apply_scale)

        # 工业级阻尼滑块 (范围 0.8 到 1.5，划分为 14 个刻度，步长 0.05)
        scale_slider = ctk.CTkSlider(
            scale_frame, from_=0.8, to=1.5, number_of_steps=14, 
            variable=self.scale_var, command=on_scale_change,
            button_color="#10b981", button_hover_color="#059669", progress_color="#10b981"
        )
        scale_slider.pack(side="right", fill="x", expand=True, padx=(10, 5))
        # --- 🚀 新增：霓虹光效调色盘 (Neon Accent Palette) ---
        ctk.CTkFrame(wrap, height=1, fg_color="#27272a").pack(fill="x", pady=(15, 10))
        
        theme_frame = ctk.CTkFrame(wrap, fg_color="transparent")
        theme_frame.pack(fill="x", pady=5)
        
        # 预设赛博朋克光效字典
        self.color_map = {
            "赛博蓝": "#00f2ff", "霓虹粉": "#f472b6", 
            "极客绿": "#4ade80", "初号机紫": "#a855f7",
            "太阳神黄": "#facc15", "狂暴红": "#ef4444"
        }
        # 反向映射用于在 UI 上显示中文名字
        self.reverse_color_map = {v: k for k, v in self.color_map.items()}

        current_s_color = self.cfg.get("theme_study", "#00f2ff")
        current_g_color = self.cfg.get("theme_game", "#ef4444")
        
        # 学习模式光效选择
        row_s = ctk.CTkFrame(theme_frame, fg_color="transparent")
        row_s.pack(fill="x", pady=5)
        ctk.CTkLabel(row_s, text="STUDIO (学习模式) 主光效", font=("Microsoft YaHei", 12, "bold"), text_color=current_s_color).pack(side="left")
        
        self.theme_study_var = ctk.StringVar(value=self.reverse_color_map.get(current_s_color, "赛博蓝"))
        ctk.CTkOptionMenu(row_s, values=list(self.color_map.keys()), variable=self.theme_study_var, 
                          fg_color="#18181b", button_color="#27272a", font=("Microsoft YaHei", 12)).pack(side="right")

        # 游戏模式光效选择
        row_g = ctk.CTkFrame(theme_frame, fg_color="transparent")
        row_g.pack(fill="x", pady=5)
        ctk.CTkLabel(row_g, text="GAMING (游戏模式) 警告光效", font=("Microsoft YaHei", 12, "bold"), text_color=current_g_color).pack(side="left")
        
        self.theme_game_var = ctk.StringVar(value=self.reverse_color_map.get(current_g_color, "狂暴红"))
        ctk.CTkOptionMenu(row_g, values=list(self.color_map.keys()), variable=self.theme_game_var, 
                          fg_color="#18181b", button_color="#27272a", font=("Microsoft YaHei", 12)).pack(side="right")
        # ==========================================
        # 2. 🛡️ 隐私与网络 (Privacy & Network)
        # ==========================================
        ctk.CTkLabel(wrap, text=">>> PRIVACY & NETWORK / 隐私与网络", font=("Consolas", 12, "bold"), text_color="#10b981").pack(anchor="w", pady=(20, 5))
        
        self.network_var = ctk.BooleanVar(value=self.cfg.get("allow_network", True))
        ctk.CTkSwitch(
            wrap, text="允许软件联网 (获取当地天气与每日金句)", variable=self.network_var,
            font=("Microsoft YaHei", 12, "bold"), text_color="#e4e4e7", button_color="#10b981", progress_color="#059669"
        ).pack(anchor="w", pady=(5, 5))

        # 核心声明文字：给用户吃定心丸
        privacy_text = "🔒 隐私承诺：您的所有使用时长、进程记录及架构日记【仅完全加密保存在本地硬盘】，本软件在任何情况下绝不会向外部服务器上传您的任何隐私数据。"
        ctk.CTkLabel(wrap, text=privacy_text, font=("Microsoft YaHei", 11), text_color="#71717a", justify="left", wraplength=720).pack(anchor="w", pady=(0, 15))

        # ==========================================
        # 3. 💾 数据保留与清理 (Data Matrix)
        # ==========================================
        ctk.CTkLabel(wrap, text=">>> DATA MATRIX / 数据矩阵", font=("Consolas", 12, "bold"), text_color="#10b981").pack(anchor="w", pady=(10, 5))

        # --- 🚀 新增：幽灵自动备份系统 ---
        backup_frame = ctk.CTkFrame(wrap, fg_color="transparent")
        backup_frame.pack(fill="x", pady=5)
        
        self.auto_backup_var = ctk.BooleanVar(value=self.cfg.get("auto_backup", False))
        ctk.CTkSwitch(backup_frame, text="开启幽灵静默备份 (每 7 天)", variable=self.auto_backup_var, 
                      font=("Microsoft YaHei", 12, "bold"), text_color="#e4e4e7", 
                      button_color="#2563eb", progress_color="#1d4ed8").pack(side="left")

        self.backup_path_var = ctk.StringVar(value=self.cfg.get("backup_path", ""))
        display_path = self.backup_path_var.get() if self.backup_path_var.get() else "未设置备份目录"
        self.lbl_backup_path = ctk.CTkLabel(wrap, text=f"安全舱坐标: {display_path}", font=("Consolas", 11), text_color="#71717a", justify="left")
        
        def choose_backup_dir():
            d = filedialog.askdirectory(parent=self, title="选择自动备份存放的安全舱 (强烈建议选 D 盘或云盘目录)")
            if d:
                self.backup_path_var.set(d)
                self.lbl_backup_path.configure(text=f"安全舱坐标: {d}")
                
        ctk.CTkButton(backup_frame, text="📂 选择坐标", width=90, fg_color="#27272a", hover_color="#3f3f46", command=choose_backup_dir).pack(side="right", padx=(10, 0))
        self.lbl_backup_path.pack(anchor="w", pady=(0, 10))
        # ----------------------------------------

        retention_frame = ctk.CTkFrame(wrap, fg_color="transparent")
        retention_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(retention_frame, text="数据保留期限 (天)", font=("Microsoft YaHei", 12), text_color="#a1a1aa").pack(side="left")
        
        self.retention_var = ctk.StringVar(value=str(self.cfg.get("retention_days", "30")).replace(" (永久)", ""))
        retention_menu = ctk.CTkSegmentedButton(
            retention_frame, values=["7", "15", "30", "90", "999"], 
            variable=self.retention_var, selected_color="#2563eb", selected_hover_color="#1d4ed8"
        )
        retention_menu.pack(side="right")

        # 导出与清空按钮
        btn_frame = ctk.CTkFrame(wrap, fg_color="transparent")
        btn_frame.pack(fill="x", pady=10)
        
        btn_export = ctk.CTkButton(btn_frame, text="📥 一键导出数据备份", fg_color="#2563eb", hover_color="#1d4ed8", font=("Microsoft YaHei", 12, "bold"), command=self._export_data)
        btn_export.pack(side="left", expand=True, fill="x", padx=(0, 5))
        
        btn_clear = ctk.CTkButton(btn_frame, text="💥 永久抹除本地数据", fg_color="#ef4444", hover_color="#b91c1c", font=("Microsoft YaHei", 12, "bold"), command=self._clear_data)
        btn_clear.pack(side="right", expand=True, fill="x", padx=(5, 0))

        # ==========================================
        # 4. 🚀 系统权限 (Boot & Protocol)
        # ==========================================
        ctk.CTkLabel(wrap, text=">>> SYSTEM PROTOCOL / 系统权限", font=("Consolas", 12, "bold"), text_color="#10b981").pack(anchor="w", pady=(20, 5))
        
        self.auto_start_var = ctk.BooleanVar(value=self.cfg.get("auto_start", False))
        ctk.CTkSwitch(
            wrap, text="随 Windows 启动 (隐蔽常驻)", variable=self.auto_start_var,
            font=("Microsoft YaHei", 12), text_color="#a1a1aa", button_color="#10b981", progress_color="#059669"
        ).pack(anchor="w", pady=(5, 10))

        # ==========================================
        # 5. 🛠️ 诊断与反馈 (Diagnostics)
        # ==========================================
        ctk.CTkFrame(wrap, height=1, fg_color="#27272a").pack(fill="x", pady=(15, 15))
        ctk.CTkLabel(wrap, text=">>> DIAGNOSTICS / 诊断与反馈", font=("Consolas", 12, "bold"), text_color="#10b981").pack(anchor="w", pady=(0, 5))

        btn_diag = ctk.CTkButton(
            wrap, text="📋 复制诊断报告 (供提交 Bug 使用)",
            fg_color="#4c1d95", hover_color="#5b21b6", font=("Microsoft YaHei", 12, "bold"), command=self._copy_diagnostics
        )
        btn_diag.pack(anchor="w", pady=(5, 10))
    def _build_timers_tab(self):
        tab = self.tabs["timers"]

        wrap = ctk.CTkFrame(tab, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(
            wrap,
            text="时长阈值（修改后立即生效）",
            font=("Microsoft YaHei", 13, "bold"),
            text_color="#e4e4e7",
        ).pack(anchor="w", pady=(0, 10))

        card = ctk.CTkFrame(wrap, fg_color="#18181b", corner_radius=10, border_width=1, border_color="#27272a")
        card.pack(fill="x", pady=(0, 12))

        # 学习休息提醒
        study_sec = (self.cfg.get("timers") or {}).get("study_break_sec", 2 * 3600)
        sh, sm = self._sec_to_hm(study_sec)

        row1 = ctk.CTkFrame(card, fg_color="transparent")
        row1.pack(fill="x", padx=14, pady=(14, 10))
        ctk.CTkLabel(row1, text="学习提醒间隔", font=("Consolas", 12, "bold"), text_color="#00f2ff").pack(side="left")

        self.study_h_var = tk.StringVar(value=str(sh))
        self.study_m_var = tk.StringVar(value=str(sm))
        # 建立右对齐透明容器，内部从左往右排列
        r_frame1 = ctk.CTkFrame(row1, fg_color="transparent")
        r_frame1.pack(side="right")
        ctk.CTkEntry(r_frame1, width=70, textvariable=self.study_h_var).pack(side="left")
        ctk.CTkLabel(r_frame1, text="小时", font=("Microsoft YaHei", 11), text_color="#a1a1aa").pack(side="left", padx=(6, 12))
        ctk.CTkEntry(r_frame1, width=70, textvariable=self.study_m_var).pack(side="left")
        ctk.CTkLabel(r_frame1, text="分钟", font=("Microsoft YaHei", 11), text_color="#a1a1aa").pack(side="left", padx=(6, 0))
        # 游戏防沉迷阈值
        game_sec = (self.cfg.get("timers") or {}).get("game_limit_sec", int(2.5 * 3600))
        gh, gm = self._sec_to_hm(game_sec)

        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill="x", padx=14, pady=(0, 14))
        ctk.CTkLabel(row2, text="游戏弹窗阈值", font=("Consolas", 12, "bold"), text_color="#ef4444").pack(side="left")

        self.game_h_var = tk.StringVar(value=str(gh))
        self.game_m_var = tk.StringVar(value=str(gm))
        # 建立右对齐透明容器，内部从左往右排列
        r_frame2 = ctk.CTkFrame(row2, fg_color="transparent")
        r_frame2.pack(side="right")
        ctk.CTkEntry(r_frame2, width=70, textvariable=self.game_h_var).pack(side="left")
        ctk.CTkLabel(r_frame2, text="小时", font=("Microsoft YaHei", 11), text_color="#a1a1aa").pack(side="left", padx=(6, 12))
        ctk.CTkEntry(r_frame2, width=70, textvariable=self.game_m_var).pack(side="left")
        ctk.CTkLabel(r_frame2, text="分钟", font=("Microsoft YaHei", 11), text_color="#a1a1aa").pack(side="left", padx=(6, 0))
        # 🚀 新增：每周专注总目标
        weekly_sec = (self.cfg.get("timers") or {}).get("weekly_goal_sec", 20 * 3600)
        wh, wm = self._sec_to_hm(weekly_sec)

        row3 = ctk.CTkFrame(card, fg_color="transparent")
        row3.pack(fill="x", padx=14, pady=(0, 14))
        ctk.CTkLabel(row3, text="每周专注目标", font=("Consolas", 12, "bold"), text_color="#10b981").pack(side="left")

        self.weekly_h_var = tk.StringVar(value=str(wh))
        self.weekly_m_var = tk.StringVar(value=str(wm))
        
        r_frame3 = ctk.CTkFrame(row3, fg_color="transparent")
        r_frame3.pack(side="right")
        ctk.CTkEntry(r_frame3, width=70, textvariable=self.weekly_h_var).pack(side="left")
        ctk.CTkLabel(r_frame3, text="小时", font=("Microsoft YaHei", 11), text_color="#a1a1aa").pack(side="left", padx=(6, 12))
        ctk.CTkEntry(r_frame3, width=70, textvariable=self.weekly_m_var).pack(side="left")
        ctk.CTkLabel(r_frame3, text="分钟", font=("Microsoft YaHei", 11), text_color="#a1a1aa").pack(side="left", padx=(6, 0))

        self.timers_err = ctk.CTkLabel(wrap, text="", font=("Microsoft YaHei", 11, "bold"), text_color="#ef4444")
        self.timers_err.pack(anchor="w")

        hint = (
            "提示：分钟范围 0-59；可填 0 小时。\n"
            "学习提醒：到达间隔时弹出休息提示。\n"
            "游戏弹窗：到达阈值后触发全屏警告（并有 60 秒冷却）。\n"
            "每周目标：设定你的黄金算力周目标，主界面将实时反馈进度。"
        )
        ctk.CTkLabel(wrap, text=hint, font=("Consolas", 11), text_color="#71717a", justify="left").pack(anchor="w", pady=(8, 0))
        
        # 👇 在这个函数的末尾，加入极其酷炫的自启开关：
        ctk.CTkFrame(wrap, height=1, fg_color="#27272a").pack(fill="x", pady=(20, 15)) # 视觉分割线
        
        self.auto_start_var = ctk.BooleanVar(value=self.cfg.get("auto_start", False))
        ctk.CTkSwitch(
            wrap, 
            text="🚀 随 Windows 启动 (开机自启)",
            variable=self.auto_start_var,
            font=("Microsoft YaHei", 13, "bold"),
            text_color="#00f2ff",
            button_color="#10b981",
            progress_color="#059669"
        ).pack(anchor="w", pady=(0, 10))
    def _parse_hm_to_sec(self, h_str: str, m_str: str):
        h_str = (h_str or "").strip()
        m_str = (m_str or "").strip()
        if h_str == "":
            h_str = "0"
        if m_str == "":
            m_str = "0"
        h = int(h_str)
        m = int(m_str)
        if h < 0 or m < 0 or m > 59:
            raise ValueError("invalid hm")
        return h * 3600 + m * 60

    def _render_list(self, key):
        frame = self.list_frames[key]
        for w in frame.winfo_children():
            w.destroy()

        items = self.cfg.get(key) or {}
        if not items:
            ctk.CTkLabel(
                frame,
                text="（空）还没有录入任何程序",
                font=("Consolas", 12),
                text_color="#71717a",
            ).pack(anchor="w", padx=12, pady=12)
            return

        for exe_name, path in sorted(items.items(), key=lambda x: x[0]):
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=6)

            btn = ctk.CTkButton(
                row,
                text=f"{exe_name}",
                fg_color="#111111",
                hover_color="#27272a",
                corner_radius=8,
                font=("Consolas", 12, "bold"),
                anchor="w",
                command=lambda k=key, e=exe_name: self._replace_exe(k, e),
            )
            btn.pack(side="left", expand=True, fill="x", padx=(0, 8))
            ToolTip(btn, path)

            ctk.CTkButton(
                row,
                text="🗑",
                width=36,
                height=30,
                fg_color="transparent",
                hover_color="#27272a",
                font=("Segoe UI Emoji", 12),
                text_color="#ef4444",
                command=lambda k=key, e=exe_name: self._remove_exe(k, e),
            ).pack(side="right")

    def _pick_exe(self, title):
        self.lift()
        self.focus_force()
        return filedialog.askopenfilename(
            parent=self,
            title=title,
            filetypes=[("Executable", "*.exe")],
        )

    def _add_exe(self, key):
        try:
            file_path = self._pick_exe("选择 .exe 文件")
            if not file_path:
                return
            if not str(file_path).lower().endswith(".exe"):
                return
            exe_name = os.path.basename(file_path).lower()
            self.cfg[key][exe_name] = file_path
            self._render_list(key)
        except Exception as e:
            win = ctk.CTkToplevel(self)
            win.title("WARNING")
            win.geometry("420x160")
            win.attributes("-topmost", True)
            win.configure(fg_color="#450a0a")
            ctk.CTkLabel(win, text=f"❌ 添加失败\n{e}", text_color="#fca5a5", font=("Microsoft YaHei", 11, "bold"), justify="center").pack(expand=True)

    def _replace_exe(self, key, exe_name):
        try:
            file_path = self._pick_exe(f"替换路径：{exe_name}")
            if not file_path:
                return
            if not str(file_path).lower().endswith(".exe"):
                return
            new_name = os.path.basename(file_path).lower()
            # 替换策略：允许更名（exe 名变了就按新名存）
            if new_name != exe_name:
                self.cfg[key].pop(exe_name, None)
            self.cfg[key][new_name] = file_path
            self._render_list(key)
        except Exception:
            pass

    def _remove_exe(self, key, exe_name):
        self.cfg[key].pop(exe_name, None)
        self._render_list(key)

    def _save(self):
        try:
            logger.info("SettingsPanel._save started")
            # --- 1. 时长参数校验 (防御空输入) ---
            if hasattr(self, "study_h_var"):
                try:
                    s_h = self.study_h_var.get().strip() or "0"
                    s_m = self.study_m_var.get().strip() or "0"
                    g_h = self.game_h_var.get().strip() or "0"
                    g_m = self.game_m_var.get().strip() or "0"
                    
                    # 🚀 提取每周目标输入框的值
                    w_h = getattr(self, "weekly_h_var", tk.StringVar(value="20")).get().strip() or "0"
                    w_m = getattr(self, "weekly_m_var", tk.StringVar(value="0")).get().strip() or "0"
                    
                    study_sec = self._parse_hm_to_sec(s_h, s_m)
                    game_sec = self._parse_hm_to_sec(g_h, g_m)
                    weekly_sec = self._parse_hm_to_sec(w_h, w_m) # 🚀 转换为秒
                    
                    self.cfg.setdefault("timers", {})
                    self.cfg["timers"]["study_break_sec"] = int(study_sec)
                    self.cfg["timers"]["game_limit_sec"] = int(game_sec)
                    self.cfg["timers"]["weekly_goal_sec"] = int(weekly_sec) # 🚀 写入物理配置矩阵
                except Exception as e:
                    if hasattr(self, "timers_err"):
                        self.timers_err.configure(text=f"⚠ 输入无效: {e}")
                    return

            if hasattr(self, "network_var"):
                self.cfg["allow_network"] = self.network_var.get()
                
            # 👇 核心：将选中的中文名字转换为 Hex 色值并打入硬盘钢印
            if hasattr(self, "theme_study_var"):
                self.cfg["theme_study"] = self.color_map.get(self.theme_study_var.get(), "#00f2ff")
                self.cfg["theme_game"] = self.color_map.get(self.theme_game_var.get(), "#ef4444")
            # --- 2. 状态比对 (防止字符串格式导致的误杀) ---
            # 使用 float 比对而非字符串，避免 "1.0" != "1" 的悲剧
            try:
                old_s = float(getattr(self, "_initial_scale", "1.0"))
                new_s = float(self.scale_var.get())
                self.cfg["ui_scale"] = str(new_s)
                scale_changed = abs(old_s - new_s) > 0.01
            except:
                scale_changed = False

            if hasattr(self, "network_var"):
                self.cfg["allow_network"] = self.network_var.get()
                
            # 👇 将自动备份设置打入思想钢印
            if hasattr(self, "auto_backup_var"):
                self.cfg["auto_backup"] = self.auto_backup_var.get()
                self.cfg["backup_path"] = self.backup_path_var.get()
                
            if hasattr(self, "auto_start_var"):
                self.cfg["auto_start"] = self.auto_start_var.get()
                set_autostart(self.cfg["auto_start"])

            save_sys_config(self.cfg)
            logger.info("SettingsPanel._save config persisted")
            
            if callable(self._on_save):
                self._on_save(self.cfg)
                logger.info("SettingsPanel._save on_save callback done")

            # --- 3. 动态形变 vs 强制重启 ---
            if scale_changed:
                # 之前商定的物理形变逻辑 (不闪退版)
                new_w, new_h = int(820 * new_s), int(680 * new_s)
                self.geometry(f"{new_w}x{new_h}")
                self._initial_scale = str(new_s) # 更新基准
                # 这里不执行 os._exit，除非你确定需要底层缩放

            # 体验优化：安全展示保存成功
            self._show_success_toast()
            
        except Exception as e:
            logger.error(f"Save crash: {e}", exc_info=True)
            messagebox.showerror("Save Failed", f"系统保存出错: {e}")

    def _show_success_toast(self):
        """安全弹窗并关闭"""
        ok = ctk.CTkToplevel(self)
        ok.title("SUCCESS")
        ok.geometry("300x100")
        ok.attributes("-topmost", True)
        ctk.CTkLabel(ok, text="✅ SETTINGS SYNCED", font=("Consolas", 14, "bold"), text_color="#10b981").pack(expand=True)
        
        def _close():
            if ok.winfo_exists(): ok.destroy()
            # 不再自动关闭设置窗口，避免用户误以为“闪退”
            #（主窗口配置会在 on_save 回调里热更新）
        self.after(800, _close)

# ==========================================
# 🚀 核心控制中枢 (极限悬浮窗)
# ==========================================
class FloatingTracker(ctk.CTk):
    def __init__(self):
        super().__init__()

        # 🚀 拦截 Tkinter 按钮点击引发的所有静默异常
        self.last_err_time = 0

        def tk_exception_handler(exc_type, exc_value, exc_traceback):
            err_msg = str(exc_value)
            
            # 🛡️ 架构师核心补丁：静默过滤掉 Tkinter 内部无害的“幽灵组件”报错
            if "bad window path name" in err_msg or "invalid command name" in err_msg:
                return
                
            logger.error("🖱️ UI 交互事件引发了异常", exc_info=(exc_type, exc_value, exc_traceback))
            
            # 🛡️ 终极防御：防抖冷却 (如果1秒内疯狂报错，直接拦截)
            if time.time() - getattr(self, "last_err_time", 0) < 1:
                return
            self.last_err_time = time.time()
            
            try:
                if len(err_msg) > 100: err_msg = err_msg[:100] + "..."
                ctypes.windll.user32.MessageBoxW(0, f"系统遇到局部阻碍，但不影响主体运行。\n错误: {err_msg}\n\n已自动记录至黑匣子。", "UI 交互异常", 0x30)
            except: pass
            
        self.report_callback_exception = tk_exception_handler
        
        
        # 🚀 工业级：注入主窗口和任务栏的星云图标
        try:
            self.iconbitmap(resource_path("app_icon.ico"))
        except Exception as e:
            print(f"图标加载失败: {e}")
            
        # 启动时先隐藏主窗，避免无边框切换导致“闪一下”
        self.withdraw()

        # ==========================================
        # 💥 赛博终端：视觉级启动加载动画 (Splash Screen)
        # ==========================================
        splash = ctk.CTkToplevel(self)
        splash.overrideredirect(True) # 无边框沉浸模式
        splash.attributes("-topmost", True)
        splash.configure(fg_color="#0a0a0c") # 极深黑底色
        
        # 居中算法
        w, h = 420, 220
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        splash.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        # 动画 UI 元素 (🚀 正式命名：NEBULA)
        ctk.CTkLabel(splash, text="NEBULA TERMINAL", font=("Impact", 34), text_color="#00f2ff").pack(pady=(50, 10))
        lbl_status = ctk.CTkLabel(splash, text="INITIALIZING NEBULA CORE...", font=("Consolas", 12), text_color="#10b981")
        lbl_status.pack(pady=(0, 20))
        
        # 红色赛博进度条
        bar = ctk.CTkProgressBar(splash, width=300, height=4, progress_color="#ef4444", fg_color="#27272a")
        bar.pack()
        bar.set(0)

        # ⚡ 模拟系统自检动画 (阻塞式刷新)
        status_texts = [
            "CONNECTING TO NEBULA MATRIX...",
            "LOADING ASSETS AND PROTOCOLS...",
            "BYPASSING SECURITY FIREWALL...",
            "NEBULA SYSTEM READY."
        ]
        
        for i in range(1, 21):
            bar.set(i / 20.0) # 更新进度条
            if i % 5 == 0:
                # 每跑 25% 换一句炫酷的自检文案
                lbl_status.configure(text=status_texts[(i//5)-1])
            splash.update() # 强制刷新 UI 渲染
            time.sleep(0.06) # 控制动画速度（总计约 1.2 秒的高级停顿）

        splash.destroy() # 动画结束，销毁加载屏
        # ==========================================

        # 👇 调试用：运行后弹窗告诉你配置文件夹的绝对路径
        print(f"--- 架构坐标: {CONFIG_FILE} ---")
        
        # ... 后面的 self.mode = "STUDY" 等全部代码保持不变 ...

        # 预设基础状态（在任何 UI 渲染前）
        self.mode = "STUDY"
        self.is_collapsed = False
        self.menu = None
        self.music_active = False

        self.sys_config = load_sys_config()
        
        # 🚀 启动拦截：系统点火前，优先装载全局缩放倍率！
        try:
            saved_scale = float(self.sys_config.get("ui_scale", "1.0"))
            ctk.set_widget_scaling(saved_scale)
            ctk.set_window_scaling(saved_scale)
        except Exception:
            pass
        
        if not self.sys_config.get("is_setup"):
            wizard = SetupWizard(self)
            self.wait_window(wizard) # 挂起主线程，死死等待用户在弹窗中点完配置
            self.sys_config = load_sys_config() # 用户点完部署后，重新读取最新配置
            
        # 将提取出的 .exe 名字存入系统动态列表
        study_cfg = self.sys_config.get("study") or {}
        game_cfg = self.sys_config.get("game") or {}
        music_cfg = self.sys_config.get("music") or {}
        self.study_procs = list(study_cfg.keys())
        self.game_procs = list(game_cfg.keys())
        self.music_procs = list(music_cfg.keys())
        # 👆 新增结束
        
        # 窗口设定（横向拉宽到 320，高度拉高到 185，终结高度窒息）
        self.geometry("320x185+100+100")
        # 先用普通窗口确保能显示；稍后再切换为无边框（某些 Win11/驱动组合下，启动即无边框会“看不见”）
        self.overrideredirect(False)
        # 关键修复：`overrideredirect(True)` + `-toolwindow` 在部分 Windows 环境下会导致窗口“存在但不可见/不可切换”
        # 注意：全窗 alpha 会在边缘产生混色“矩形黑框”（尤其是圆角裁剪后）
        # 若你需要透明效果，建议改为仅内容控件视觉透明（或改用 transparentcolor 方案）
        self.attributes("-topmost", True, "-alpha", 1.0)
        self.attributes("-toolwindow", True) # 🚀 第一重保险：Tkinter 原生剥离任务栏
        ctk.set_appearance_mode("dark")
        # 根窗口背景与主面板一致，避免圆角裁剪后出现“黑边/黑底”
        try:
            self.configure(fg_color="#111111")
        except Exception:
            pass

        # 配置完成，主窗口登场（在无边框/置顶属性设置之后）
        self.deiconify()

        # 延迟切换为无边框，提升兼容性
        def _enable_borderless():
            try:
                self.overrideredirect(True)
                # 👇 在这里调用我们刚刚写的物理隐身引擎 👇
                self._hide_from_taskbar() # 🚀 第二重保险：底层内核隐身
                self.lift()
                self.attributes("-topmost", True)
                self.focus_force()
                self.after(0, self._apply_windows_round_corners)
            except Exception:
                pass
        self.after(80, _enable_borderless)

        # Windows：初始化圆角（并在后续尺寸变化时重算 region）
        self._round_radius = 14
        self._round_job = None
        self.bind("<Configure>", self._on_configure_apply_round, add="+")
        self.after(0, self._apply_windows_round_corners)

        # 兜底：如果窗口被系统/其它置顶窗压到后台，强制拉回
        self.after(200, self._ensure_visible)
    def _enforce_data_retention(self):
        """根据用户的保留天数设置，自动抹除过期数据"""
        try:
            retention_str = str(self.sys_config.get("retention_days", "30"))
            if "999" in retention_str:
                return # 永久保留，不执行清理

            retention_days = int(retention_str)
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            
            keys_to_delete = []
            for date_str in self.db.keys():
                # 跳过非日期格式的键 (比如 "last_heartbeat")
                if not date_str.replace("-", "").isdigit(): continue
                
                try:
                    record_date = datetime.strptime(date_str, "%Y-%m-%d")
                    if record_date < cutoff_date:
                        keys_to_delete.append(date_str)
                except ValueError:
                    pass
            
            # 执行物理删除
            if keys_to_delete:
                for k in keys_to_delete:
                    del self.db[k]
                save_data(self.db)
                print(f"🧹 内存矩阵已自动清理 {len(keys_to_delete)} 天前的过期数据。")
        except Exception as e:
            print(f"数据清理引擎异常: {e}")
    def _check_auto_backup(self):
        """静默的幽灵备份引擎：每 7 天自动向安全舱投递一次数据快照"""
        if not getattr(self, "sys_config", {}).get("auto_backup", False):
            return
            
        backup_path = self.sys_config.get("backup_path", "")
        if not backup_path or not os.path.exists(backup_path):
            return

        today_str = datetime.now().strftime("%Y-%m-%d")
        last_backup = self.db.get("last_auto_backup", "")

        # 检查是否超过 7 天
        if last_backup:
            try:
                last_date = datetime.strptime(last_backup, "%Y-%m-%d")
                if (datetime.now() - last_date).days < 7:
                    return # 时间未到，继续潜伏
            except Exception:
                pass

        # 🚀 触发时机已到，执行物理级镜像拷贝
        try:
            import shutil
            file_name = f"Nebula_Matrix_Backup_{today_str}.json"
            dest = os.path.join(backup_path, file_name)
            
            if os.path.exists(DATA_FILE):
                shutil.copy2(DATA_FILE, dest)
                
            # 打上时间戳钢印
            self.db["last_auto_backup"] = today_str
            save_data(self.db)
            
            if 'logger' in globals(): logger.info(f"📦 幽灵备份完成: 数据已安全固化至 {dest}")
            
            # 顺便弹个低调的雷达通知给架构师
            self.after(3000, lambda: self._update_env_or_quote(f"📦 AUTO-BACKUP: 矩阵快照已送达安全舱"))
        except Exception as e:
            if 'logger' in globals(): logger.error(f"❌ 幽灵备份失败: {e}", exc_info=True)
    def _ensure_visible(self):
        try:
            self.deiconify()
            self.lift()
            self.attributes("-topmost", True)
            self.focus_force()
            self.update_idletasks()
            # 避免意外跑到屏幕外
            x, y = self.winfo_x(), self.winfo_y()
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            if x < -2000 or y < -2000 or x > sw + 2000 or y > sh + 2000:
                self.geometry("320x185+100+100")
        except Exception:
            pass

        # 系统自启动注入
        #self.inject_to_registry()

        # 数据初始化
        self.db = load_data()
        self.today = datetime.now().strftime("%Y-%m-%d")
        self.db = init_today_data(self.db, self.today)
        self._enforce_data_retention()
        
        # 👇 核心点火：每次系统拉起时，触发幽灵备份检测
        self._check_auto_backup()

        # Timers（可配置）
        timers = (self.sys_config or {}).get("timers") or {}
        self.study_break_sec = int(timers.get("study_break_sec", 2 * 3600))
        self.game_limit_sec = int(timers.get("game_limit_sec", int(2.5 * 3600)))
        if self.study_break_sec <= 0:
            self.study_break_sec = 2 * 3600
        if self.game_limit_sec <= 0:
            self.game_limit_sec = int(2.5 * 3600)

        self.quote_file = os.path.join(APP_DIR, "quotes.txt")
        self.current_quote = "Logic is the soul of every agent." # 默认金句

        # 主框架（外层只负责圆角/背景；边框改为“内边框”避免溢出到圆角外）
        self.main_frame = ctk.CTkFrame(self, corner_radius=12, fg_color="#111111", border_width=0)
        self.main_frame.pack(fill="both", expand=True, padx=0, pady=0)

        # 内边框层：真正的边框绘制发生在这里
        self.inner_frame = ctk.CTkFrame(
            self.main_frame,
            corner_radius=12,
            fg_color="#111111",
            border_width=0,
        )
        # padx/pady=1 让边框在内侧“吃进去”，外沿保持纯圆角
        self.inner_frame.pack(fill="both", expand=True, padx=0, pady=0)
        
        # --- 第一行：状态指示 ---
        self.top_row = ctk.CTkFrame(self.inner_frame, fg_color="transparent")
        self.top_row.pack(side="top", fill="x", padx=10, pady=(8, 2))
        
        # 学习模式初始色应为赛博蓝（避免启动时“Study 变绿”）
        self.lbl_mode_txt = ctk.CTkLabel(self.top_row, text="Study", font=("Impact", 20), text_color="#00f2ff")
        self.lbl_mode_txt.pack(side="left")

        self.lbl_time = ctk.CTkLabel(self.top_row, text="00:00:00", font=("Consolas", 22, "bold"), text_color="#00f2ff")
        self.lbl_time.pack(side="left", padx=15)
        # 🚀 极限美学方案：恢复斜体！通过设置 width > wraplength，强行制造 40px 的内部安全区防切边
        self.lbl_quote = ctk.CTkLabel(self.inner_frame, text="正在同步思维矩阵...   ", 
                                      font=("Microsoft YaHei", 12, "italic"), text_color="#a1a1aa", 
                                      width=300, wraplength=260, cursor="hand2") 
        self.lbl_quote.pack(side="top", expand=True, fill="both", padx=10, pady=(2, 2))
        
        # 绑定鼠标左键点击事件 (<Button-1>)
        self.lbl_quote.bind("<Button-1>", lambda e: self.refresh_quote())
        # 👇 更改初始颜色为科技灰 #a1a1aa (或者你喜欢的颜色)
        self.lbl_env = ctk.CTkLabel(self.inner_frame, text="ENV SCAN: INITIALIZING SYSTEM...", 
                                    font=("Microsoft YaHei", 11, "bold"), text_color="#facc15")
        self.lbl_env.pack(side="bottom", pady=(0, 2))

        # --- 🚀 重新排版的右上角控制台：[设置] [猫咪] [隐藏到托盘] ---
        # 1. 隐藏到托盘 ✕ (修改为统一的低调灰)
        self.btn_hide = ctk.CTkButton(self.top_row, text="✕", width=20, height=20, fg_color="transparent", 
                                     hover_color="#27272a", text_color="#a1a1aa", font=("Consolas", 14, "bold"), 
                                     command=self.hide_to_tray)
        self.btn_hide.pack(side="right", padx=(0, 2))
        ToolTip(self.btn_hide, "隐蔽驻留 (Hide to Tray)")

        # 2. 缩小为猫咪 —
        self.btn_min = ctk.CTkButton(self.top_row, text="—", width=20, height=20, fg_color="transparent", 
                                     hover_color="#27272a", text_color="#a1a1aa", font=("Consolas", 14, "bold"), 
                                     command=self.toggle_collapse)
        self.btn_min.pack(side="right", padx=(0, 2))
        ToolTip(self.btn_min, "迷你形态 (Cat Mode)")


        # --- 第二行：快捷工具栏 ---
        self.bot_row = ctk.CTkFrame(self.inner_frame, fg_color="transparent")
        self.bot_row.pack(side="bottom", fill="x", padx=10, pady=(2, 5))

        # 天气显示应在小图标栏上方
        try:
            self.lbl_env.pack_forget()
            self.lbl_env.pack(before=self.bot_row, side="bottom", pady=(0, 2))
        except Exception:
            pass

        self.btn_switch = ctk.CTkButton(self.bot_row, text="🔄 切换", width=60, height=24, fg_color="#27272a", hover_color="#3f3f46", font=("Microsoft YaHei", 10, "bold"), command=self.switch_mode)
        self.btn_switch.pack(side="left")
        ToolTip(self.btn_switch, "CHANGE MODE")

        # 统一图标按钮视觉规范：尺寸/字体/交互一致
        icon_btn_kwargs = {
            "width": 24,
            "height": 24,
            "fg_color": "transparent",
            "hover_color": "#27272a",
            "font": ("Segoe UI Emoji", 12),
        }

        # 游戏模式专属按钮 (默认隐藏)
        self.btn_clean = ctk.CTkButton(self.bot_row, text="🧹", text_color="#facc15", command=self.clean_memory, **icon_btn_kwargs)
        ToolTip(self.btn_clean, "一键释放！！")

        self.btn_wegame = ctk.CTkButton(self.bot_row, text="🎮", command=self.launch_wegame, **icon_btn_kwargs)
        ToolTip(self.btn_wegame, "启动！")
        
        # 常驻按钮
        # 👇 ==========================================
        # 🎵 重构音乐组件 (Music Component V2: Grid 呼吸感)
        # ==========================================
        self.music_container = ctk.CTkFrame(self.bot_row, fg_color="transparent")
        self.music_container.pack(side="right", padx=(10, 5)) # 给右侧按钮留出呼吸空间

        # A. 独立的图标按钮 (只显示图标，点击启动)
        self.btn_music_icon = ctk.CTkButton(self.music_container, text="🎵", command=self.launch_music, **icon_btn_kwargs)
        self.btn_music_icon.grid(row=0, column=0, padx=(0, 5)) # 图标放在第0列，居中
        ToolTip(self.btn_music_icon, "听歌去！")

        # B. 独立的时长标签 (使用 Consolas 律动橙，精准对齐时间)
        self.lbl_music_time = ctk.CTkLabel(self.music_container, text="", 
                                         font=("Consolas", 12, "bold"), text_color="#f59e0b") # Consolas 律动橙
        self.lbl_music_time.grid(row=0, column=1) # 时长放在第1列

        # (为了兼容旧代码，将 icon_button 赋值给 old_name，防止其它地方崩溃)
        self.btn_music = self.btn_music_icon

        self.btn_data = ctk.CTkButton(self.bot_row, text="📊", command=self.show_data_module, **icon_btn_kwargs)
        self.btn_data.pack(side="right", padx=1)
        ToolTip(self.btn_data, "数据矩阵与日历")

        self.btn_note = ctk.CTkButton(self.bot_row, text="📝", command=self.show_note_menu, **icon_btn_kwargs)
        self.btn_note.pack(side="right", padx=1)
        ToolTip(self.btn_note, "奇思妙想")

        # 事件绑定
        # 拖动绑定放在内层（边框/内容区域）更符合直觉
        self.inner_frame.bind("<ButtonPress-1>", self.start_move)
        self.inner_frame.bind("<B1-Motion>", self.do_move)
        
        self.warning_active = False         
        self.last_warning_time = 0  # 建议顺便加上这个，用于留出 60 秒关闭时间
        # 监控循环：不要用后台线程跑 psutil（Python 3.14 下可能触发 GIL 致命崩溃）
        self.running = True
        self._monitor_loop_counter = 0
        
        self.after(1000, self._monitor_tick)
        self.update_ui()
        self.after(1500, self.check_sleep_log) 
        
        # 🚀 核心修复：先清空初始杂乱的挂载，严格按照自上而下的重力顺序重新组装！
        for w in self.inner_frame.winfo_children():
            w.pack_forget()
        
        # 1. 优先固定最顶部的状态栏
        self.top_row.pack(side="top", fill="x", padx=10, pady=(8, 2))
        # 2. 呼叫重构引擎，按完美比例塞入金句、进度条和底部图标
        self._rebuild_study_interface()
        
        # 👇 优先启动底层托盘引擎
        self.setup_tray()

        # 🚀 核心修复：网络引擎“错峰点火 (Staggered Ignition)”序列
        self.after(500, self.fetch_env_data)
        # 👇 优先启动底层托盘引擎
        self.setup_tray()

        # 🚀 核心修复：网络引擎“错峰点火 (Staggered Ignition)”序列
        # 绝对不能让多个网络线程在同一毫秒内并发启动，否则断网时会触发 Windows 底层注册表死锁！
        # 因为被调用的函数内部已经自带了 threading 隔离，所以这里直接用 after 触发即可
        self.after(500, self.fetch_env_data)       # 0.5 秒后：数据库已加载，拉取天气
        self.after(1200, self.fetch_daily_quote)   # 1.2 秒后：拉取金句
        self.after(3500, self.check_for_updates)   # 3.5 秒后：低优先级云端探针
    def _fetch_soup_text(self, kind: str = "game") -> str:
        """获取弹窗鸡汤（已接入网络装甲）"""
        # 这里的调用本身就是在各自的 daemon Thread 里，所以可以直接阻塞执行
        data = self.safe_get("https://v1.hitokoto.cn/", params={"c": ["k", "d", "i"]}, 
                             timeout=3, max_retries=1, cache_key="raw_quote_data", as_json=True)
        
        if isinstance(data, dict):
            quote = data.get("hitokoto")
            if quote:
                author = data.get("from_who") or data.get("from", "System")
                return f"{quote} —— {author}"
        return ""

    def _apply_center_geometry(self, win: tk.Toplevel, w: int, h: int):
        try:
            sw = win.winfo_screenwidth()
            sh = win.winfo_screenheight()
            x = int((sw - w) / 2)
            y = int((sh - h) / 2)
            win.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

    def open_settings(self):
        if hasattr(self, "settings_win") and self.settings_win and self.settings_win.winfo_exists():
            self.settings_win.lift()
            return

        def on_save(new_cfg):
            try:
                # 🚀 关键：所有的热更新逻辑都包在 try-except 里，防止任何转换错误拉垮整个程序
                self.sys_config = new_cfg
                
                # 刷新监控列表
                study_cfg = self.sys_config.get("study", {})
                game_cfg = self.sys_config.get("game", {})
                music_cfg = self.sys_config.get("music", {})
                
                self.study_procs = list(study_cfg.keys())
                self.game_procs = list(game_cfg.keys())
                self.music_procs = list(music_cfg.keys())

                # 刷新时长阈值 (防御式转换)
                timers = self.sys_config.get("timers", {})
                self.study_break_sec = int(float(timers.get("study_break_sec", 7200)))
                self.game_limit_sec = int(float(timers.get("game_limit_sec", 9000)))
                
                logger.info("系统矩阵热更新成功")
            except Exception as e:
                logger.error(f"Settings hot-reload failed: {e}", exc_info=True)

        self.settings_win = SettingsPanel(self, self.sys_config, on_save=on_save)
    # ==========================================
    # 🛸 隐形托盘矩阵 (System Tray Engine) + 警报闪烁
    # ==========================================
    def create_tray_icon(self, alert=False):
        """读取真实的 .ico 实体作为托盘图标。如果是 alert 模式，强行渲染一层血红色警报滤镜"""
        icon_path = resource_path("app_icon.ico")
        if os.path.exists(icon_path):
            img = Image.open(icon_path).convert("RGBA")
            if alert:
                # 🚀 视觉特效：在原图标上盖一层半透明的战斗红滤镜
                red_layer = Image.new("RGBA", img.size, (239, 68, 68, 120)) # #ef4444 附带透明度
                img = Image.alpha_composite(img, red_layer)
            return img
        else:
            # 兜底方案：画个绿边/红边黑框防崩溃
            img = Image.new('RGB', (64, 64), color=(17, 17, 17))
            draw = ImageDraw.Draw(img)
            color = (239, 68, 68) if alert else (0, 242, 255)
            draw.rectangle((8, 8, 56, 56), outline=color, width=4)
            return img

    def start_tray_flash(self):
        """点燃托盘闪烁引擎"""
        if getattr(self, "is_tray_flashing", False): return
        self.is_tray_flashing = True
        self._tray_flash_state = False
        self._tray_flash_loop()

    def stop_tray_flash(self):
        """熄灭托盘闪烁引擎"""
        self.is_tray_flashing = False
        if hasattr(self, "tray_icon") and self.tray_icon:
            # 恢复默认的星云蓝图标
            self.tray_icon.icon = self.create_tray_icon(alert=False)

    def _tray_flash_loop(self):
        """跨线程高频脉冲重绘 (每 500 毫秒心跳一次)"""
        if not getattr(self, "is_tray_flashing", False):
            return
        if hasattr(self, "tray_icon") and self.tray_icon:
            # 状态翻转：红 / 正常 交替
            self._tray_flash_state = not self._tray_flash_state
            self.tray_icon.icon = self.create_tray_icon(alert=self._tray_flash_state)
        # 🚀 每 500 毫秒递归一次，形成警报闪烁！
        self.after(500, self._tray_flash_loop)

    def setup_tray(self):
        """配置托盘右键菜单与双击事件 (自带终极单例防御锁)"""
        # 🚀 物理级单例锁：如果系统已经侦测到托盘存活，直接拦截后续所有生成请求！防双黄蛋！
        if getattr(self, "_tray_initialized", False):
            return
        self._tray_initialized = True

        menu = pystray.Menu(
            # default=True 代表双击托盘图标时触发这个动作
            pystray.MenuItem('🖥️ 唤醒终端', self._tray_show, default=True),
            pystray.MenuItem('⚙️ 系统设置', self._tray_settings),
            pystray.MenuItem('❌ 彻底拔管 (退出)', self._tray_exit)
        )
        self.tray_icon = pystray.Icon("Nebula", self.create_tray_icon(), "Nebula(运行中)", menu)
        # 必须把托盘扔到后台线程去跑，否则会和 Tkinter 死锁
        import threading
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def hide_to_tray(self):
        """点击右上角 ✕ 时调用：彻底隐藏主窗口并执行内存大扫除"""
        # 如果是猫咪状态，先还原，防止出现渲染 BUG
        if getattr(self, "is_collapsed", False):
            self.restore_window()
            
        self.withdraw()
        
        # 🚀 召唤深度休眠策略：强制垃圾回收，释放所有无用变量与 GUI 碎片
        import gc
        gc.collect()
        
        if 'logger' in globals():
            logger.info("系统隐蔽驻留，已执行底层内存 GC 清理。")


    def _tray_show(self, icon, item):
        """托盘回调：必须通过 after 抛给主线程执行 UI 操作！"""
        self.after(0, self._safe_deiconify)

    def _safe_deiconify(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def _tray_settings(self, icon, item):
        self.after(0, self.open_settings)

    def _tray_exit(self, icon, item):
        """接收系统托盘的拔管指令 (需转交主线程处理)"""
        # 1. 托盘图标可以在它自己的后台线程里先停掉
        icon.stop()
        
        # 🚀 核心修复：绝不能在后台线程直接销毁主窗口，必须用 after 抛回 UI 主线程
        self.after(0, self._graceful_shutdown)

    def _graceful_shutdown(self):
        """优雅关闭序列：数据落盘 -> 停循环 -> 终结进程"""
        try:
            if 'logger' in globals(): 
                logger.info(">>> 收到拔管指令，开始执行优雅关闭协议...")
            
            # 1. 掐断焦点监控引擎的动力源
            self.running = False
            
            # 2. 强制将内存中可能尚未写入硬盘的脏数据 (Dirty Data) 固化
            if hasattr(self, 'db'):
                save_data(self.db)
                if 'logger' in globals(): 
                    logger.info(">>> 数据矩阵已安全落盘。")
            
            # 3. 强制保存最新的系统配置 (确保最后的状态不丢失)
            if hasattr(self, 'sys_config'):
                save_sys_config(self.sys_config)
            
            # 4. 优雅销毁主窗体，正常结束 Tkinter 的 mainloop
            self.destroy()
            
            # 5. 使用标准温和的 sys.exit 代替暴力的 os._exit
            sys.exit(0)
            
        except Exception as e:
            if 'logger' in globals(): 
                logger.error(f"优雅关闭序列崩溃: {e}", exc_info=True)
            # 如果连安全清理都报错了，只能触发最后的物理断电兜底
            os._exit(1)
  
    # 👇 把这两个函数加在 __init__ 的下方，和 __init__ 保持相同的缩进级别！

    def fetch_env_data(self):
        """后台静默获取天气 (绝对物理隔离防卡死版)"""
        if not getattr(self, "sys_config", {}).get("allow_network", True):
            if hasattr(self, "update_env_ui"):
                self.update_env_ui("ENV SCAN: OFFLINE MODE (断网模式)")
            return

        def network_task():
            try:
                # 1. 查询 IP 归属地
                ip_info = self.safe_get("http://ip-api.com/json/", timeout=3, cache_key="ip_info", as_json=True)
                city = "UNKNOWN"
                if isinstance(ip_info, dict):
                    city = ip_info.get("city", "UNKNOWN").upper()
                
                # 2. 如果定位失败，直接放弃查天气，避免 wttr.in 挂起
                if city == "UNKNOWN":
                    env_text = "ENV SCAN: SENSOR OFFLINE (定位失败)"
                else:
                    # 3. 查询天气
                    weather_url = f"https://wttr.in/{city}?format=%c+%t+|+HUM:%h"
                    w_data = self.safe_get(weather_url, timeout=3, cache_key=f"weather_{city}", as_json=False)
                    
                    if w_data and not w_data.startswith("<"): # 防止返回 HTML 报错页
                        env_text = f"ENV SCAN: {city} | {w_data.strip()}"
                    else:
                        env_text = f"ENV SCAN: {city} | SENSOR OFFLINE"
                        
            except Exception:
                env_text = "ENV SCAN: SENSOR OFFLINE (网络未连接)"

            # 🚀 将文本安全送回主线程，使用 e=env_text 锁定变量防丢失
            if hasattr(self, "update_env_ui"):
                self.after(0, lambda e=env_text: self.update_env_ui(e))
            elif hasattr(self, "lbl_env"):
                self.after(0, lambda e=env_text: self.lbl_env.configure(text=e))

        import threading
        threading.Thread(target=network_task, daemon=True).start()

        # 4. 启动守护线程 (Daemon Thread)，把任务扔进后台，让主界面瞬间弹出来
        import threading
        threading.Thread(target=network_task, daemon=True).start()
    def update_env_ui(self, text):
        """主线程更新天气标签"""
        # 🚀 核心：给底层天气数据打上记忆钢印，防止被永久覆写
        self._cached_env_text = text 
        
        if hasattr(self, 'lbl_env') and self.lbl_env.winfo_exists():
            self.lbl_env.configure(text=text)
            # 解除随模式变色，统一锁定为你设定的专属颜色 (如 #facc15)
            self.lbl_env.configure(text_color="#facc15")
    # ==========================================
    # 📡 OTA 云端神经同步协议 (Update Checker)
    # ==========================================
    def check_for_updates(self):
        """后台静默探测云端版本，绝不阻塞主进程"""
        if not getattr(self, "sys_config", {}).get("allow_network", True):
            return

        def task():
            try:
                update_url = "https://gitee.com/Mzzzzzz98/Nebula-Releases/releases" 
                # 🚀 统一使用原生 safe_get，绝不单独再碰 requests！
                data = self.safe_get(update_url, timeout=3, as_json=True)
                if isinstance(data, dict):
                    latest_version = data.get("latest_version", CURRENT_VERSION)
                    if self._is_newer_version(CURRENT_VERSION, latest_version):
                        self.after(2000, lambda d=data: self.show_update_dialog(d))
            except Exception:
                pass
                
        import threading
        threading.Thread(target=task, daemon=True).start()

    def _is_newer_version(self, current: str, latest: str) -> bool:
        """解析版本号矩阵，判断是否需要跃迁"""
        try:
            cur_parts = [int(x) for x in current.split(".")]
            lat_parts = [int(x) for x in latest.split(".")]
            return lat_parts > cur_parts
        except Exception:
            return False

    def show_update_dialog(self, data: dict):
        """🚀 极客风新版本跃迁通知"""
        latest_ver = data.get("latest_version", "Unknown")
        release_notes = data.get("release_notes", "修复了一些系统底层的架构漏洞。")
        download_url = data.get("download_url", "https://github.com/your-repo/releases")

        win = ctk.CTkToplevel(self)
        win.title("SYSTEM OVERRIDE: UPDATE AVAILABLE")
        win.geometry("520x400")
        win.attributes("-topmost", True)
        win.configure(fg_color="#0b0b10")
        self._apply_center_geometry(win, 520, 400)

        outer = ctk.CTkFrame(win, fg_color="#0b0b10", corner_radius=14, border_width=1, border_color="#10b981")
        outer.pack(expand=True, fill="both", padx=14, pady=14)

        ctk.CTkLabel(outer, text="🚀 NEBULA 协议更新可用", font=("Microsoft YaHei", 24, "bold"), text_color="#10b981").pack(pady=(20, 5))
        ctk.CTkLabel(outer, text=f"当前版本: V{CURRENT_VERSION}  >>>  云端版本: V{latest_ver}", font=("Consolas", 14, "bold"), text_color="#00f2ff").pack(pady=(0, 15))

        # 更新日志区
        note_frame = ctk.CTkFrame(outer, fg_color="#111111", corner_radius=8, border_width=1, border_color="#27272a")
        note_frame.pack(fill="both", expand=True, padx=30, pady=5)
        
        ctk.CTkLabel(note_frame, text="[ 跃迁日志 / RELEASE NOTES ]", font=("Consolas", 12), text_color="#71717a").pack(anchor="w", padx=15, pady=(10, 5))
        ctk.CTkLabel(note_frame, text=release_notes, font=("Microsoft YaHei", 12), text_color="#d1d5db", justify="left", wraplength=380).pack(anchor="w", padx=15, pady=(0, 15))

        # 按钮区
        btn_frame = ctk.CTkFrame(outer, fg_color="transparent")
        btn_frame.pack(fill="x", padx=30, pady=20)

        def do_download():
            webbrowser.open(download_url)
            win.destroy()

        ctk.CTkButton(btn_frame, text="稍后同步", width=120, fg_color="#27272a", hover_color="#3f3f46", text_color="#a1a1aa", command=win.destroy).pack(side="left")
        ctk.CTkButton(btn_frame, text="前往云端下载新架构", font=("Microsoft YaHei", 13, "bold"), fg_color="#10b981", hover_color="#059669", command=do_download).pack(side="right", expand=True, fill="x", padx=(10, 0))
    # --- 🌐 云端金句获取引擎 (方案 B: Hitokoto API) ---
    # --- 🔄 手动触发灵感刷新 ---
    def refresh_quote(self):
        # 瞬间给出一个视觉反馈，告诉用户系统正在运转
        self.lbl_quote.configure(text="[ 正在接入思维矩阵，获取新坐标...]  ")
        # 开启一条全新的隐形后台线程去拉取数据，绝对不卡主界面！
        threading.Thread(target=self.fetch_daily_quote, daemon=True).start()

    def fetch_daily_quote(self):
        """获取每日金句 (已修复 db 死锁与代理卡顿)"""
        fallback_quote = "The quieter you become, the more you are able to hear. —— System"
        db_safe = getattr(self, "db", {})
        
        # 断网拦截
        if not getattr(self, "sys_config", {}).get("allow_network", True):
            cached_text = db_safe.get("net_cache", {}).get("daily_quote", fallback_quote)
            if hasattr(self, "lbl_quote") and self.lbl_quote.winfo_exists():
                self.after(0, lambda t=cached_text: self.lbl_quote.configure(text=f"{t} (离线)"))
            return

        def task():
            data = self.safe_get("https://v1.hitokoto.cn/", params={"c": ["k", "d", "i"]}, 
                                 timeout=3, max_retries=1, cache_key="raw_quote_data", as_json=True)
            
            db_ref = getattr(self, "db", {})
            if isinstance(data, dict) and data.get("hitokoto"):
                quote = data.get("hitokoto")
                author = data.get("from_who") or data.get("from", "System")
                # 🚀 在动态生成的文本末尾强行塞入 3 个空格，给最后一行的斜体小尾巴当物理垫背！
                final_text = f"{quote} —— {author}   "
                
                if hasattr(self, "db"):
                    self.db.setdefault("net_cache", {})["daily_quote"] = final_text
                    self._data_dirty = True
            else:
                final_text = db_ref.get("net_cache", {}).get("daily_quote", fallback_quote)
            
            if hasattr(self, "lbl_quote") and self.lbl_quote.winfo_exists():
                self.after(0, lambda t=final_text: self.lbl_quote.configure(text=t))
            
        import threading
        threading.Thread(target=task, daemon=True).start()
    # --- 快捷启动与工具 ---
    def launch_music(self):
        """动态引擎：读取并启动用户配置的第一个音乐软件"""
        music_apps = list(self.sys_config.get("music", {}).values())
        if music_apps and os.path.exists(music_apps[0]):
            try: os.startfile(music_apps[0])
            except Exception as e: print(f"启动失败: {e}")
        else:
            self._show_missing_config_toast("🎵 请先在 ⚙ 设置中配置音乐软件！")

    def launch_wegame(self):
        """动态引擎：读取并启动用户配置的第一个游戏"""
        game_apps = list(self.sys_config.get("game", {}).values())
        if game_apps and os.path.exists(game_apps[0]):
            try: os.startfile(game_apps[0])
            except Exception as e: print(f"启动失败: {e}")
        else:
            self._show_missing_config_toast("🎮 请先在 ⚙ 设置中配置游戏程序！")

    def _show_missing_config_toast(self, msg):
        """专属的极客风报错弹窗"""
        toast = ctk.CTkToplevel(self)
        toast.geometry("320x100")
        toast.attributes("-topmost", True)
        toast.configure(fg_color="#0a0a0c")
        ctk.CTkLabel(toast, text=msg, font=("Microsoft YaHei", 12, "bold"), text_color="#ef4444").pack(expand=True)
        self.after(1600, toast.destroy)

    # ==========================================
    # 🧹 猎杀协议 (安全确认版 Memory Purger)
    # ==========================================
    def clean_memory(self):
        """架构师级内存扫描：精准黑名单探测 -> 授权确认 -> 温和退出"""
        if getattr(self, "_is_cleaning", False):
            return
        self._is_cleaning = True
        
        try:
            import psutil
            
            # 1. 🎯 绝对黑名单矩阵 (只猎杀这些已知的干扰/高耗能进程，全小写)
            # 你可以随时在这里增删你想干掉的摸鱼软件
            BLACKLIST = {
                "chrome.exe", "msedge.exe", "firefox.exe", 
                "wechat.exe", "qq.exe", "discord.exe", 
                "steam.exe", "epicgameslauncher.exe",
                "baidunetdisk.exe", "thunder.exe",
                "wegame.exe"
            }
            my_pid = os.getpid() # 保护 Nebula 自身
            
            targets = []
            total_releasable_mb = 0
            
            # 2. 🔍 资源雷达探测 (仅扫描黑名单)
            if 'logger' in globals(): logger.info(">>> 开始探测黑名单干扰进程...")
            for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
                try:
                    pinfo = proc.info
                    pid = pinfo['pid']
                    name = (pinfo['name'] or "").lower()
                    
                    if pid == my_pid:
                        continue
                        
                    # 猎杀门槛：只要在黑名单里，就直接揪出来，不看内存大小了
                    if name in BLACKLIST:
                        mem_mb = pinfo['memory_info'].rss / (1024 * 1024)
                        targets.append((proc, name, mem_mb))
                        total_releasable_mb += mem_mb
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            
            # 3. 🎯 决策分支
            if not targets:
                self.after(0, lambda: self._update_env_or_quote("✅ 未发现黑名单干扰进程，算力环境极其纯净。"))
                self._is_cleaning = False
                return
                
            # 弹出二次授权清单
            self.after(0, lambda: self._show_purge_confirmation(targets, total_releasable_mb))
            
        except Exception as e:
            if 'logger' in globals(): logger.error(f"探测异常: {e}")
            self._is_cleaning = False

    def _show_purge_confirmation(self, targets, total_mb):
        """🛡️ 二次确认弹窗：向架构师申请猎杀授权"""
        win = ctk.CTkToplevel(self)
        win.title("SYSTEM OVERRIDE: TARGET ACQUIRED")
        win.geometry("450x550")
        win.attributes("-topmost", True)
        win.configure(fg_color="#0b0b10")
        
        # 居中弹窗
        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (450 // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (550 // 2)
        win.geometry(f"+{int(x)}+{int(y)}")
        
        ctk.CTkLabel(win, text="⚠️ 猎杀授权请求", font=("Impact", 24), text_color="#ef4444").pack(pady=(25, 5))
        ctk.CTkLabel(win, text=f"雷达发现 {len(targets)} 个高耗能游离进程\n全部物理拔管预计可释放 {total_mb:.1f} MB 内存\n\n请手动勾选您确定要终止的目标：", 
                     font=("Microsoft YaHei", 12), text_color="#a1a1aa", justify="center").pack(pady=5)
        
        # 猎杀清单滚动区
        scroll = ctk.CTkScrollableFrame(win, fg_color="#111111", corner_radius=8, border_width=1, border_color="#27272a")
        scroll.pack(fill="both", expand=True, padx=25, pady=10)
        
        # 按内存占用从大到小排序
        targets.sort(key=lambda x: x[2], reverse=True)
        
        checkboxes = []
        for proc, name, mem in targets:
            # 🚀 极其关键的安全底线：默认全部不勾选！必须用户主动担责。
            var = ctk.BooleanVar(value=False)
            chk = ctk.CTkCheckBox(scroll, text=f"{name}  [{mem:.1f} MB]", variable=var, 
                                  font=("Consolas", 13), text_color="#e4e4e7", 
                                  fg_color="#ef4444", hover_color="#dc2626")
            chk.pack(anchor="w", pady=8, padx=15)
            checkboxes.append((proc, name, var))
            
        def execute_purge():
            killed_count = 0
            freed_mb = 0
            for proc, name, var in checkboxes:
                if var.get(): # 只有被用户打勾的才会被杀
                    try:
                        mem = proc.memory_info().rss / (1024 * 1024)
                        
                        # 🚀 战术降级：发送温和的关闭信号 (Graceful Close)，代替暴力的 .kill()
                        # 相当于系统按下了软件右上角的 [X] 按钮，允许它们保存数据并体面退出
                        proc.terminate() 
                        
                        freed_mb += mem
                        killed_count += 1
                    except Exception:
                        pass
            
            win.destroy()
            self._is_cleaning = False
            
            if killed_count > 0:
                self._update_env_or_quote(f"⚡ 猎杀完成: 已温和劝退 {killed_count} 个进程，预计释放 {freed_mb:.1f} MB 内存")
            else:
                self._update_env_or_quote("🛡️ 猎杀终止: 架构师未授权任何清理目标。")

        def cancel_purge():
            win.destroy()
            self._is_cleaning = False
            self._update_env_or_quote("🛡️ 猎杀协议已主动撤回。")

        # 确保弹窗关闭时也能重置锁
        win.protocol("WM_DELETE_WINDOW", cancel_purge)

        btn_frame = ctk.CTkFrame(win, fg_color="transparent")
        btn_frame.pack(fill="x", padx=25, pady=20)
        
        ctk.CTkButton(btn_frame, text="撤回指令", width=120, fg_color="#27272a", hover_color="#3f3f46", text_color="#a1a1aa", command=cancel_purge).pack(side="left")
        ctk.CTkButton(btn_frame, text="🔥 执行物理猎杀", font=("Microsoft YaHei", 13, "bold"), fg_color="#ef4444", hover_color="#dc2626", command=execute_purge).pack(side="right", expand=True, fill="x", padx=(15, 0))

    def _update_env_or_quote(self, text: str):
        """UI 渲染层：轻量级消息反馈 (自带 3 秒物理自愈)"""
        try:
            if hasattr(self, 'lbl_env') and self.lbl_env.winfo_exists():
                # 1. 瞬间覆写通知文字
                self.lbl_env.configure(text=text)
                
                # 2. 🚀 斩断永久残留：取消上一秒可能还在倒计时的恢复任务
                if hasattr(self, "_env_restore_timer") and self._env_restore_timer:
                    self.after_cancel(self._env_restore_timer)
                    
                # 3. 🚀 3秒后，自动将记忆深处的天气数据拉回来！
                cached_text = getattr(self, "_cached_env_text", "ENV SCAN: STANDBY")
                self._env_restore_timer = self.after(3000, lambda: self.lbl_env.configure(text=cached_text) if self.lbl_env.winfo_exists() else None)
                
            if 'logger' in globals(): 
                logger.info(f"[UI 状态更新] {text}")
        except Exception:
            pass  
    


    # ==========================================
    # 🔴 战斗终端：游戏主题重建引擎 (Thematic Redesign)
    # ==========================================
    # 0. 强行修改主悬浮窗底色和标题文字颜色 (接入全量霓虹光效引擎)
        accent_color = self.sys_config.get("theme_game", "#ef4444")
        try:
            self.configure(fg_color="#0a0a0c") 
            self.inner_frame.configure(fg_color="#0a0a0c")
            self.lbl_mode_txt.configure(text="GAME", text_color=accent_color)
            self.lbl_time.configure(text_color=accent_color)
            
            self.current_eye_color = accent_color 
            # 🚀 智能几何解析引擎：瞬间同步猫咪
            if hasattr(self, 'cat_canvas'):
                for tag in ["cat", "cat_border", "cat_decor", "eye"]:
                    for item in self.cat_canvas.find_withtag(tag):
                        itype = self.cat_canvas.type(item)
                        if tag == "eye": self.cat_canvas.itemconfig(item, fill=accent_color)
                        elif itype in ["line", "text"]: self.cat_canvas.itemconfig(item, fill=accent_color)
                        elif itype in ["polygon", "arc", "oval"]: self.cat_canvas.itemconfig(item, outline=accent_color)
        except Exception: pass

        # 1. 🚀【核心修复】先 Pack 底部逃生舱！确保它沉在最底下不被挤出去！
        self.bot_row.pack(side="bottom", fill="x", padx=10, pady=(2, 5))
        
        self.btn_switch.pack(side="left")
        if hasattr(self, 'btn_clean'): 
            self.btn_clean.pack(side="left", padx=5)
            
        self.music_container.pack_forget()
        self.btn_data.pack_forget()
        self.btn_note.pack_forget()

        # 2. 销毁旧的模式框，创建新的
        if hasattr(self, 'mode_frame') and self.mode_frame.winfo_exists():
            self.mode_frame.destroy()
            
        self.mode_frame = ctk.CTkFrame(self.inner_frame, fg_color="transparent")
        # 中间的模式区要最后 Pack，让它自动填满“剩余”的中间空间
        self.mode_frame.pack(side="top", fill="both", expand=True, padx=0, pady=0)
        
        # 3. 核心区：三个游戏启动按钮
        btn_container = ctk.CTkFrame(self.mode_frame, fg_color="transparent")
        btn_container.pack(expand=True, padx=10, pady=(5, 5))

        games = list(self.sys_config.get("game", {}).values())
        if not games: games = ["#NO_GAME_CFG", "#NO_GAME_CFG", "#NO_GAME_CFG"]
        elif len(games) < 3: games.extend(["#NO_GAME_CFG"] * (3 - len(games)))

        def launch_game(path):
            if path == "#NO_GAME_CFG": return
            try: os.startfile(path)
            except Exception: pass

        btn_kwargs = {
            "width": 50, "height": 50, 
            "fg_color": "#18181b", 
            "border_width": 2, "border_color": "#ef4444", 
            "corner_radius": 10, 
            "text_color": "#e4e4e7", 
            "hover_color": "#450a0a",
            "font": ("Consolas", 10, "bold")
        }
        
        for g_path in games[:3]:
            g_name = os.path.basename(g_path).replace(".exe", "").lower() if g_path != "#NO_GAME_CFG" else "[待配置]"
            if len(g_name) > 8: g_name = g_name[:6] + ".."
            btn = ctk.CTkButton(btn_container, text=f"🎮\n{g_name}", **btn_kwargs, command=lambda p=g_path: launch_game(p))
            btn.pack(side="left", padx=5)


    # ==========================================
    # 🔵 沉浸终端：学习主题重建引擎 (Thematic Redesign)
    # ==========================================
    def _update_pet_mood(self, mood):
        """情绪渲染器：全量接管猫咪身体与眼睛的霓虹色彩 (智能几何解析版)"""
        # 防止每秒重复渲染
        if getattr(self, "_current_mood", "") == mood: return
        self._current_mood = mood
        
        try:
            s_color = self.sys_config.get("theme_study", "#00f2ff")
            g_color = self.sys_config.get("theme_game", "#ef4444")
            
            if mood == "angry":
                accent_color = "#facc15" # 狂暴黄
            else:
                accent_color = s_color if self.mode == "STUDY" else g_color
            
            # 🚀 智能几何解析引擎：自动判断原件类型，赋予完美光效，绝不报错！
            for tag in ["cat", "cat_border", "cat_decor", "eye"]:
                for item in self.cat_canvas.find_withtag(tag):
                    itype = self.cat_canvas.type(item)
                    if tag == "eye":
                        # 眼睛特殊处理：根据疲惫状态覆盖颜色
                        if mood == "tired": eye_color = "#71717a"
                        elif mood == "sleepy": eye_color = "#3b82f6"
                        else: eye_color = accent_color
                        self.cat_canvas.itemconfig(item, fill=eye_color)
                    elif itype in ["line", "text"]:
                        self.cat_canvas.itemconfig(item, fill=accent_color)
                    elif itype in ["polygon", "arc", "oval"]:
                        self.cat_canvas.itemconfig(item, outline=accent_color)
        except Exception: pass

    def switch_mode(self):
        """核心协议：物理级重构界面主题，修复组件渲染坍塌"""
        if self.mode == "STUDY":
            self.mode = "GAME"
        else:
            self.mode = "STUDY"

        # 🧹 绝对显式清场：精准点名退场，绝不误伤骨架
        for widget_name in ['lbl_quote', 'lbl_env', 'progress_frame', 'mode_frame', 'top_row', 'bot_row']:
            if hasattr(self, widget_name) and getattr(self, widget_name).winfo_exists():
                getattr(self, widget_name).pack_forget()

        # 恢复顶部栏容器
        if hasattr(self, 'top_row'):
            self.top_row.pack(side="top", fill="x", padx=10, pady=(8, 2))

        if getattr(self, "is_collapsed", False):
            self.restore_window()

        if self.mode == "STUDY":
            self._rebuild_study_interface()
        elif self.mode == "GAME":
            self._rebuild_gaming_interface()

    def _rebuild_study_interface(self):
        """宁静大改：赛博禅修蓝，恢复经典的金句与极简模式"""
        accent_color = self.sys_config.get("theme_study", "#00f2ff")

        # 🛡️ 战术解耦 1：背景色独立渲染，报错不蔓延
        try:
            self.configure(fg_color="#111111")
            self.inner_frame.configure(fg_color="#111111")
        except Exception: pass

        # 🛡️ 战术解耦 2：文字色绝对接管
        try:
            if hasattr(self, 'lbl_mode_txt') and self.lbl_mode_txt.winfo_exists():
                self.lbl_mode_txt.configure(text="STUDY", text_color=accent_color)
            if hasattr(self, 'lbl_time') and self.lbl_time.winfo_exists():
                self.lbl_time.configure(text_color=accent_color)
        except Exception: pass

        # 🛡️ 战术解耦 3：猫咪光效智能注入
        self.current_eye_color = accent_color
        try:
            if hasattr(self, 'cat_canvas') and self.cat_canvas.winfo_exists():
                for tag in ["cat", "cat_border", "cat_decor", "eye"]:
                    for item in self.cat_canvas.find_withtag(tag):
                        itype = self.cat_canvas.type(item)
                        if tag == "eye": self.cat_canvas.itemconfig(item, fill=accent_color)
                        elif itype in ["line", "text"]: self.cat_canvas.itemconfig(item, fill=accent_color)
                        elif itype in ["polygon", "arc", "oval"]: self.cat_canvas.itemconfig(item, outline=accent_color)
        except Exception: pass

        # 1. 底部逃生舱防挤压装载
        if hasattr(self, 'bot_row'):
            self.bot_row.pack(side="bottom", fill="x", padx=10, pady=(2, 5))
            for w in self.bot_row.winfo_children():
                w.pack_forget()

            if hasattr(self, 'btn_switch'): self.btn_switch.pack(side="left")
            if hasattr(self, 'music_container'): self.music_container.pack(side="right", padx=(10, 5))
            if hasattr(self, 'btn_data'): self.btn_data.pack(side="right", padx=1)
            if hasattr(self, 'btn_note'): self.btn_note.pack(side="right", padx=1)

        # 2. 天气雷达
        if hasattr(self, 'lbl_env') and self.lbl_env.winfo_exists():
            self.lbl_env.pack(side="bottom", pady=(0, 2))

        # 3. 每周算力进度条
        if hasattr(self, 'progress_frame') and self.progress_frame.winfo_exists():
            self.progress_frame.destroy()

        self.progress_frame = ctk.CTkFrame(self.inner_frame, fg_color="transparent")
        self.progress_frame.pack(side="bottom", fill="x", padx=15, pady=(0, 2), before=self.lbl_env if hasattr(self, 'lbl_env') else None)

        self.lbl_goal_text = ctk.CTkLabel(self.progress_frame, text="WEEKLY GOAL: CALCULATING...", font=("Consolas", 10, "bold"), text_color=accent_color)
        self.lbl_goal_text.pack(anchor="w", pady=(0, 2))

        self.goal_bar = ctk.CTkProgressBar(self.progress_frame, height=4, progress_color=accent_color, fg_color="#27272a")
        self.goal_bar.pack(fill="x")
        self.goal_bar.set(0)

        # 4. 每日金句
        if hasattr(self, 'lbl_quote') and self.lbl_quote.winfo_exists():
            self.lbl_quote.pack(side="top", expand=True, fill="both", pady=(2, 2))


    def _rebuild_gaming_interface(self):
        """激进大改：暴躁战斗红，遵守底部优先法则"""
        accent_color = self.sys_config.get("theme_game", "#ef4444")

        # 🛡️ 战术解耦 1：背景色独立渲染
        try:
            self.configure(fg_color="#0a0a0c")
            self.inner_frame.configure(fg_color="#0a0a0c")
        except Exception: pass

        # 🛡️ 战术解耦 2：文字色绝对接管
        try:
            if hasattr(self, 'lbl_mode_txt') and self.lbl_mode_txt.winfo_exists():
                self.lbl_mode_txt.configure(text="GAME", text_color=accent_color)
            if hasattr(self, 'lbl_time') and self.lbl_time.winfo_exists():
                self.lbl_time.configure(text_color=accent_color)
        except Exception: pass

        # 🛡️ 战术解耦 3：猫咪光效智能注入
        self.current_eye_color = accent_color
        try:
            if hasattr(self, 'cat_canvas') and self.cat_canvas.winfo_exists():
                for tag in ["cat", "cat_border", "cat_decor", "eye"]:
                    for item in self.cat_canvas.find_withtag(tag):
                        itype = self.cat_canvas.type(item)
                        if tag == "eye": self.cat_canvas.itemconfig(item, fill=accent_color)
                        elif itype in ["line", "text"]: self.cat_canvas.itemconfig(item, fill=accent_color)
                        elif itype in ["polygon", "arc", "oval"]: self.cat_canvas.itemconfig(item, outline=accent_color)
        except Exception: pass

        # 1. 底部逃生舱防挤压装载
        if hasattr(self, 'bot_row'):
            self.bot_row.pack(side="bottom", fill="x", padx=10, pady=(2, 5))
            for w in self.bot_row.winfo_children():
                w.pack_forget()

            if hasattr(self, 'btn_switch'): self.btn_switch.pack(side="left")
            if hasattr(self, 'btn_clean'): self.btn_clean.pack(side="left", padx=5)
            if hasattr(self, 'btn_wegame'): self.btn_wegame.pack(side="left", padx=1)

        # 2. 销毁并重建模式框
        if hasattr(self, 'mode_frame') and self.mode_frame.winfo_exists():
            self.mode_frame.destroy()

        self.mode_frame = ctk.CTkFrame(self.inner_frame, fg_color="transparent")
        self.mode_frame.pack(side="top", fill="both", expand=True, padx=0, pady=0)

        # 3. 游戏启动按钮
        btn_container = ctk.CTkFrame(self.mode_frame, fg_color="transparent")
        btn_container.pack(expand=True, padx=10, pady=(5, 5))

        games = list(self.sys_config.get("game", {}).values())
        if not games: games = ["#NO_GAME_CFG", "#NO_GAME_CFG", "#NO_GAME_CFG"]
        elif len(games) < 3: games.extend(["#NO_GAME_CFG"] * (3 - len(games)))

        def launch_game(path):
            if path == "#NO_GAME_CFG": return
            try: os.startfile(path)
            except Exception: pass

        btn_kwargs = {
            "width": 50, "height": 50,
            "fg_color": "#18181b",
            "border_width": 2,
            "border_color": accent_color,
            "corner_radius": 10,
            "text_color": "#e4e4e7",
            "hover_color": "#450a0a",
            "font": ("Consolas", 10, "bold")
        }

        for g_path in games[:3]:
            g_name = os.path.basename(g_path).replace(".exe", "").lower() if g_path != "#NO_GAME_CFG" else "[待配置]"
            if len(g_name) > 8: g_name = g_name[:6] + ".."
            btn = ctk.CTkButton(btn_container, text=f"🎮\n{g_name}", **btn_kwargs, command=lambda p=g_path: launch_game(p))
            btn.pack(side="left", padx=5)
    
    def show_note_menu(self):
        if self.menu and self.menu.winfo_exists(): return
        self.menu = ctk.CTkToplevel(self)
        self.menu.geometry("160x130")
        self.menu.overrideredirect(True)
        self.menu.attributes("-topmost", True)
        self.menu.configure(fg_color="#18181b")
        
        x, y = self.winfo_rootx() + 40, self.winfo_rooty() + 85
        self.menu.geometry(f"+{x}+{y}")
        
        # 👇 修复 1：给关闭按钮加上安全的异步销毁
        ctk.CTkButton(self.menu, text="×", width=20, height=20, fg_color="transparent", text_color="#ef4444", 
                      command=lambda: self.after(10, self.menu.destroy)).pack(anchor="ne")

        # 👇 修复 2：安全的日记打开逻辑 (先开日记，等动画播完再关菜单)
        def _open_diary(c):
            NoteWindow(self, c)
            self.after(20, self.menu.destroy)

        for opt in ["代码架构知识", "大数据模型使用", "随笔"]:
            ctk.CTkButton(self.menu, text=opt, fg_color="transparent", hover_color="#27272a", font=("Microsoft YaHei", 12), anchor="w",
                          command=lambda c=opt: _open_diary(c)).pack(fill="x", padx=5, pady=2)

    def toggle_collapse(self):
        """最小化：进化为纯净绿幕抠图法，绝无黑边"""
        if self.is_collapsed: return

        try:
            if getattr(self, "_round_job", None) is not None:
                self.after_cancel(self._round_job)
                self._round_job = None
        except Exception: pass

        if hasattr(self, 'blink_timer') and self.blink_timer:
            try: self.after_cancel(self.blink_timer)
            except: pass
            self.blink_timer = None

        self.is_collapsed = True
        self.old_geom = self.geometry()
        
        self.top_row.pack_forget()
        if hasattr(self, 'mid_row'): self.mid_row.pack_forget()
        self.bot_row.pack_forget()
        if hasattr(self, 'lbl_quote'): self.lbl_quote.pack_forget()
        if hasattr(self, 'lbl_env'): self.lbl_env.pack_forget()

        # 🚀 核心修复：完全抛弃 WindowRgn，改用纯透明色抠图法！
        self._clear_window_region()
        try:
            self.attributes("-alpha", 1.0) # 必须拉满，否则边缘会半透明发灰
            self.attributes("-transparentcolor", "#000001") # 将特定颜色变为全透明
        except Exception: pass
        
        self.configure(fg_color="#000001")
        if hasattr(self, "inner_frame") and self.inner_frame.winfo_exists():
            self.inner_frame.pack_forget()

        self.main_frame.configure(fg_color="#000001", border_width=0)
        self.geometry("80x50")
        self.update_idletasks()

        if hasattr(self, 'cat_container'):
            try: self.cat_container.destroy()
            except: pass
            
        self.cat_container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.cat_container.pack(expand=True, fill="both")

        # Canvas 背景设为我们的“绿幕色” #000001
        self.cat_canvas = tk.Canvas(self.cat_container, width=80, height=50, bg="#000001", highlightthickness=0, bd=0)
        self.cat_canvas.pack(fill="both", expand=True)

        # 🚀 动态读取主题色，让猫咪诞生的第一秒就拥有光效基因
        s_color = self.sys_config.get("theme_study", "#00f2ff")
        g_color = self.sys_config.get("theme_game", "#ef4444")
        accent_color = s_color if self.mode == "STUDY" else g_color

        self.current_eye_color = accent_color
        head_fill = "#18181b"
        border = accent_color # 身体边框直接上光效
        border_w = 1

        self.cat_canvas.create_polygon(14, 15, 28, 0, 42, 15, fill=head_fill, outline=border, width=border_w, joinstyle="round", smooth=True, tags=("cat",))
        self.cat_canvas.create_polygon(38, 15, 52, 0, 66, 15, fill=head_fill, outline=border, width=border_w, joinstyle="round", smooth=True, tags=("cat",))

        x0, y0, x1, y1 = 5, 10, 75, 48
        r = 19
        self.cat_canvas.create_oval(x0, y0, x0 + 2 * r, y1, fill=head_fill, outline="", tags=("cat_fill",))
        self.cat_canvas.create_oval(x1 - 2 * r, y0, x1, y1, fill=head_fill, outline="", tags=("cat_fill",))
        self.cat_canvas.create_rectangle(x0 + r, y0, x1 - r, y1, fill=head_fill, outline="", tags=("cat_fill",))
        self.cat_canvas.create_arc(x0, y0, x0 + 2 * r, y1, start=90, extent=180, style="arc", outline=border, width=border_w, tags=("cat_border",))
        self.cat_canvas.create_arc(x1 - 2 * r, y0, x1, y1, start=-90, extent=180, style="arc", outline=border, width=border_w, tags=("cat_border",))
        self.cat_canvas.create_line(x0 + r, y0, x1 - r, y0, fill=border, width=border_w, tags=("cat_border",))
        self.cat_canvas.create_line(x0 + r, y1, x1 - r, y1, fill=border, width=border_w, tags=("cat_border",))

        # ==========================================
        # 🎭 双形态猫咪矩阵：学习学霸猫 vs 游戏疯狂猫
        # ==========================================
        self.crazy_cat = (self.mode == "GAME")
        self.study_cat = (self.mode == "STUDY")
        
        if self.crazy_cat:
            # (🔴【游戏形态】：保持不变，保留赤红眉毛獠牙逻辑)
            self.cat_canvas.create_line(16, 20, 32, 26, fill="#ef4444", width=2, tags=("cat_decor",)) 
            self.cat_canvas.create_line(48, 26, 64, 20, fill="#ef4444", width=2, tags=("cat_decor",)) 
            self.cat_canvas.create_line(30, 36, 34, 40, 38, 36, 42, 40, 46, 36, 50, 40, fill="#ef4444", width=1.5, tags=("cat_decor",)) 

            self.eye_open_h = 12
            self.eye_closed_h = 1
            
        elif self.study_cat:
            # 🔵【学习形态】：重铸“全景全息学霸猫”
            visor_color = "#00f2ff" # 专注星云蓝
            
            # 1. 头顶悬浮：专注进度数据环 (不完整弧形)
            self.cat_canvas.create_arc(25, -5, 55, 15, start=45, extent=270, outline=visor_color, width=1.5, style="arc", tags=("cat_decor",))

            # 2. 全景流线眼镜 (从笨重方框改为流畅椭圆)
            # 左镜框
            self.cat_canvas.create_oval(15, 20, 35, 36, outline=visor_color, width=1.5, tags=("cat_decor",))
            # 右镜框
            self.cat_canvas.create_oval(45, 20, 65, 36, outline=visor_color, width=1.5, tags=("cat_decor",))
            # 鼻梁全息流线 (使用 create_line 加上 tags，保证一起抖动)
            self.cat_canvas.create_line(35, 27, 45, 27, fill=visor_color, width=1.5, tags=("cat_decor",))

            # 3. 悬浮数据流挂载 (在眼镜两侧浮动 Σ、∫、π)
            # 使用 tags 将它们归类，确保它们会随抖动一起移动
            self.cat_canvas.create_text(10, 24, text="Σ", font=("Consolas", 9), fill=visor_color, tags=("cat_decor",))
            self.cat_canvas.create_text(12, 32, text="∫", font=("Consolas", 10), fill=visor_color, tags=("cat_decor",))
            self.cat_canvas.create_text(70, 24, text="π", font=("Consolas", 9), fill=visor_color, tags=("cat_decor",))
            self.cat_canvas.create_text(70, 32, text="n", font=("Consolas", 9), fill=visor_color, tags=("cat_decor",))

            self.eye_open_h = 10
            self.eye_closed_h = 2

        # --- 🐱 炸毛形象：仅游戏模式下显示 ---
        self._fur_spike_ids = []
        self._fur_spike_params = []  # (cx, half_w)
        # 炸毛只做“头顶轮廓”，并限制高度，避免和耳朵主轮廓强行重叠
        self._fur_base_y = 14
        self._fur_calm_tip_y = 12
        self._fur_crazy_tip_min = 8
        self._fur_crazy_tip_max = 11

        # 让尖刺集中在头顶中间区域（耳朵绘制在它的上层，视觉上更协调）
        spike_centers = [22, 30, 38, 46, 54]
        half_w = 2
        for cx in spike_centers:
            tip_y = self._fur_crazy_tip_max if self.crazy_cat else self._fur_calm_tip_y
            poly_id = self.cat_canvas.create_polygon(
                cx - half_w, self._fur_base_y,
                cx, tip_y,
                cx + half_w, self._fur_base_y,
                fill=head_fill,
                outline="",
                width=0,
                tags=("cat_fur",),
            )
            self._fur_spike_ids.append(poly_id)
            self._fur_spike_params.append((cx, half_w))

        # 把炸毛压到耳朵后面，减少耳朵/炸毛重叠观感
        try:
            self.cat_canvas.tag_lower("cat_fur", "cat")
        except Exception:
            pass

        if not self.crazy_cat:
            for pid in self._fur_spike_ids:
                self.cat_canvas.itemconfigure(pid, state="hidden")

        self.eye_base_y = 24
        # 🚀 增加 "eye" 标签，让系统能统一操控双眼
        self.eye_l_id = self.cat_canvas.create_oval(21, self.eye_base_y, 31, self.eye_base_y + self.eye_open_h, fill=self.current_eye_color, outline="", tags=("eye_l", "eye"))
        self.eye_r_id = self.cat_canvas.create_oval(49, self.eye_base_y, 59, self.eye_base_y + self.eye_open_h, fill=self.current_eye_color, outline="", tags=("eye_r", "eye"))

        # 🚀 核心点火：双轨制接管动画循环！
        self.blink_timer = None
        self._jitter_timer = None
        
        if getattr(self, "crazy_cat", False):
            # 疯狂模式：眨眼频率加快
            self.blink_timer = self.after(random.randint(120, 450), self._do_cat_blink)
            # 🔥 启动专属的高频物理抽搐引擎！
            self._jitter_timer = self.after(50, self._menacing_jitter_loop)
        else:
            # 学习模式：安静潜伏，只有缓慢眨眼
            self.blink_timer = self.after(random.randint(3000, 7000), self._do_cat_blink)
        # 🚀 终极点火：强制清空情绪缓存，并在变身猫咪的瞬间，强行调用智能上色引擎！
        self._current_mood = ""
        try:
            sec = self.db.get(self.today, {}).get("study_total" if self.mode == "STUDY" else "game_total", 0)
            if self.mode == "STUDY" and sec > 2 * 3600: init_mood = "tired"
            elif self.mode == "STUDY" and sec > 3600: init_mood = "sleepy"
            elif self.mode == "GAME" and sec > getattr(self, "game_limit_sec", 2.5 * 3600): init_mood = "angry"
            else: init_mood = "normal"
            self._update_pet_mood(init_mood)
        except Exception: pass    
        # 事件绑定
        for w in [self.cat_container, self.cat_canvas]:
            w.bind("<Double-Button-1>", self.restore_window)
            w.bind("<ButtonPress-1>", self.start_move)
            w.bind("<B1-Motion>", self.do_move)
            w.bind("<ButtonRelease-1>", self._on_poke_pet) # 🚀 撸猫绑定 (用 Release 防止和拖拽冲突)
            w.configure(cursor="hand2") # 🚀 鼠标放上去变小手

    def restore_window(self, event=None):
        if not self.is_collapsed: return

        if hasattr(self, 'blink_timer') and self.blink_timer:
            try:
                self.after_cancel(self.blink_timer)
                self.blink_timer = None
            except Exception: pass
        # 停止专属的高频抽搐引擎
        if hasattr(self, '_jitter_timer') and self._jitter_timer:
            try:
                self.after_cancel(self._jitter_timer)
                self._jitter_timer = None
            except Exception: pass

        

        # 🚀 恢复正常的 UI 颜色和半透明
        try:
            self.attributes("-transparentcolor", "")
            self.attributes("-alpha", 0.92)
        except Exception: pass

        self.configure(fg_color="#111111")
        self.main_frame.configure(fg_color="#111111", border_width=0, corner_radius=12)

        if hasattr(self, 'cat_container'):
            try: self.cat_container.destroy()
            except Exception: pass

        self.geometry(self.old_geom)

        try:
            if hasattr(self, "inner_frame") and self.inner_frame.winfo_exists():
                self.inner_frame.pack(fill="both", expand=True, padx=1, pady=1)
        except Exception: pass

        self.top_row.pack(side="top", fill="x", padx=10, pady=(8, 2))
        # GAME 模式下金句不要铺满，否则底部按钮/图标会被挤到更靠上
        if hasattr(self, 'lbl_quote'):
            if self.mode == "GAME":
                # GAME 主题重建引擎本身不包含金句区域；这里保持隐藏可确保底部图标位置稳定
                self.lbl_quote.pack_forget()
            else:
                self.lbl_quote.pack(side="top", expand=True, fill="both", pady=(2, 2))
        if hasattr(self, 'bot_row'):
            self.bot_row.pack(side="bottom", fill="x", padx=10, pady=(2, 5))
        if hasattr(self, 'lbl_env'):
            self.lbl_env.pack(side="bottom", pady=(0, 2))

        self.is_collapsed = False
        # GAME 下恢复时需要重建布局：否则 pack 顺序会导致按钮跑到 GAME 文本上方
        try:
            if self.mode == "GAME":
                self._rebuild_gaming_interface()
            else:
                self._rebuild_study_interface()
        except Exception:
            pass
            
        self._hide_from_taskbar() # 🚀 恢复大窗口时，确保它不会“诈尸”回到任务栏
        self.after(0, self._apply_windows_round_corners)


    def start_move(self, event):
        self.x = event.x; self.y = event.y
    def do_move(self, event):
        self.geometry(f"+{self.winfo_x() + (event.x - self.x)}+{self.winfo_y() + (event.y - self.y)}")
    def _do_cat_blink(self):
        """🚀 核心：独立的眨眼引擎"""
        if not getattr(self, "is_collapsed", False): 
            return
            
        if hasattr(self, "cat_canvas") and self.cat_canvas.winfo_exists():
            try:
                self._set_canvas_eyes(opened=False) # 闭眼
                # 睁眼延迟
                open_delay = getattr(self, "cat_eye_open_delay_ms", 150)
                self.after(int(open_delay), lambda: self._set_canvas_eyes(opened=True))
                # 安排下一次眨眼
                lo, hi = getattr(self, "cat_blink_interval_ms", (3000, 7000))
                self.blink_timer = self.after(random.randint(int(lo), int(hi)), self._do_cat_blink)
            except Exception: pass

    def _set_canvas_eyes(self, opened: bool):
        try:
            if not (hasattr(self, "cat_canvas") and self.cat_canvas.winfo_exists()): return
            h = self.eye_open_h if opened else self.eye_closed_h
            
            # 🚀 核心修复：读取眼睛【当前】的真实坐标动态形变，绝不错位！
            l_coords = self.cat_canvas.coords(self.eye_l_id)
            if l_coords and len(l_coords) == 4:
                self.cat_canvas.coords(self.eye_l_id, l_coords[0], l_coords[1], l_coords[2], l_coords[1] + h)
                
            r_coords = self.cat_canvas.coords(self.eye_r_id)
            if r_coords and len(r_coords) == 4:
                self.cat_canvas.coords(self.eye_r_id, r_coords[0], r_coords[1], r_coords[2], r_coords[1] + h)
        except Exception: pass

    def _shake_cat(self):
        """疯狂猫的极度抖动：带有物理窗口撕裂感"""
        if not getattr(self, "is_collapsed", False): return
        if not (hasattr(self, "cat_canvas") and self.cat_canvas.winfo_exists()): return
        try:
            if getattr(self, "crazy_cat", False):
                now_ms = int(time.time() * 1000)
                last_ms = int(getattr(self, "_last_cat_shake_ms", 0))
                if now_ms - last_ms < 90: return
                self._last_cat_shake_ms = now_ms
                
                # 内部元素大幅度撕裂
                dx, dy = random.choice([-4, -3, 3, 4]), random.choice([-3, -2, 2, 3])
                # 🚀 物理级抖动：真正的窗口也跟着发疯 (30%概率)
                if random.random() < 0.3:
                    wx, wy = self.winfo_x(), self.winfo_y()
                    self.geometry(f"+{wx + random.choice([-2, 2])}+{wy + random.choice([-2, 2])}")
            else:
                dx, dy = random.choice([-2, -1, 1, 2]), random.choice([-1, 0, 1])

            tags = ("cat", "cat_fill", "cat_border", "eye_l", "eye_r", "cat_decor", "cat_fur")
            for t in tags: self.cat_canvas.move(t, dx, dy)
            self.after(30, lambda: self._shake_cat_revert(dx, dy))
        except Exception: pass

    def _shake_cat_revert(self, dx: int, dy: int):
        if not (hasattr(self, "cat_canvas") and self.cat_canvas.winfo_exists()): return
        try:
            tags = ("cat", "cat_fill", "cat_border", "eye_l", "eye_r", "cat_decor", "cat_fur")
            for t in tags: self.cat_canvas.move(t, -dx, -dy)
        except Exception: pass

    def _poof_cat_fur(self):
        """疯狂猫炸毛：基于相对坐标抬起尖刺"""
        if not getattr(self, "is_collapsed", False) or not getattr(self, "crazy_cat", False): return
        if not (hasattr(self, "cat_canvas") and self.cat_canvas.winfo_exists()): return
        try:
            tip_offset = random.randint(1, 4) 
            for pid in getattr(self, "_fur_spike_ids", []):
                coords = self.cat_canvas.coords(pid)
                if coords and len(coords) == 6:
                    self.cat_canvas.coords(pid, coords[0], coords[1], coords[2], coords[1] - tip_offset, coords[4], coords[5])
        except Exception: pass

    def _menacing_jitter_loop(self):
        """专门为疯狂小猫设计的独立高频抽搐引擎 (脱离眨眼限制)"""
        if not getattr(self, "is_collapsed", False) or not getattr(self, "crazy_cat", False): return
        try:
            self._shake_cat()
            self._poof_cat_fur()
            if random.random() < 0.6:
                wx, wy = self.winfo_x(), self.winfo_y()
                self.geometry(f"+{wx + random.choice([-1, 1])}+{wy + random.choice([-1, 1])}")
            self._jitter_timer = self.after(random.randint(50, 120), self._menacing_jitter_loop)
        except Exception: pass

    def _on_poke_pet(self, event):
        """赛博撸猫引擎：物理跳跃 + 真实猫叫 + 眼睛微表情"""
        if getattr(self, "_is_poking", False): return
        self._is_poking = True

        # 1. 跨次元声音反馈 (真实猫咪叫声 / 兜底蜂鸣声)
        try:
            # 🚀 寻找真实的猫叫音效文件
            meow_path = resource_path("meow.wav")
            if os.path.exists(meow_path):
                # 🚀 核心架构：SND_ASYNC (异步) | SND_FILENAME (文件模式) 绝对防卡顿！
                winsound.PlaySound(meow_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            else:
                # 降级防御：如果用户忘了放 meow.wav，自动退回赛博蜂鸣声
                self.after(0, lambda: winsound.Beep(1200, 80))
                self.after(100, lambda: winsound.Beep(1800, 150))
        except: pass

        # 2. 物理跳跃与闭眼享受
        try:
            self.cat_canvas.move("all", 0, -5) # 整个画布向上跳 5 像素
            for eye in self.cat_canvas.find_withtag("eye"):
                coords = self.cat_canvas.coords(eye)
                if len(coords) == 4:
                    self.cat_canvas.coords(eye, coords[0], coords[1]+3, coords[2], coords[3]-3)
        except: pass

        # 3. 恢复引力
        def restore():
            try:
                self.cat_canvas.move("all", 0, 5) # 落回地面
                for eye in self.cat_canvas.find_withtag("eye"):
                    coords = self.cat_canvas.coords(eye)
                    if len(coords) == 4:
                        self.cat_canvas.coords(eye, coords[0], coords[1]-3, coords[2], coords[3]+3)
            except: pass
            self._is_poking = False
            
        self.after(300, restore)

    
    def _clear_window_region(self):
        """恢复默认窗口区域（矩形）。"""
        try:
            hwnd = self.winfo_id()
            if not hwnd:
                return
            ctypes.windll.user32.SetWindowRgn(hwnd, 0, True)
            # 强制触发一轮重绘，减少 DWM 残影
            ctypes.windll.user32.RedrawWindow(
                hwnd,
                0,
                0,
                0x0400 | 0x0001 | 0x0004 | 0x0080,  # RDW_FRAME|INVALIDATE|ERASE|ALLCHILDREN
            )
        except Exception:
            pass
    
    def _hide_from_taskbar(self):
        """🚀 物理级隐身：修改 Windows 内核参数，强行将窗口从任务栏抹除"""
        if os.name != 'nt': return
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            if hwnd == 0: hwnd = self.winfo_id()
            
            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000  # 任务栏显示属性
            WS_EX_TOOLWINDOW = 0x00000080 # 工具栏隐藏属性
            
            user32 = ctypes.windll.user32
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            # 强行移除任务栏属性，并贴上工具窗（隐形）标签
            style = (style & ~WS_EX_APPWINDOW) | WS_EX_TOOLWINDOW
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        except Exception:
            pass
    
    def _apply_windows_round_corners(self):
        """在 Windows 上启用圆角：优先 DWM，其次用 Window Region 做真实裁剪（无边框更可靠）。"""
        try:
            hwnd = self.winfo_id()
            if not hwnd:
                return

            # https://learn.microsoft.com/windows/win32/api/dwmapi/nf-dwmapi-dwmsetwindowattribute
            DWMWA_WINDOW_CORNER_PREFERENCE = 33
            DWMCP_ROUND = 2

            dwmapi = ctypes.windll.dwmapi
            pref = ctypes.c_int(DWMCP_ROUND)
            dwmapi.DwmSetWindowAttribute(
                ctypes.wintypes.HWND(hwnd),
                ctypes.wintypes.DWORD(DWMWA_WINDOW_CORNER_PREFERENCE),
                ctypes.byref(pref),
                ctypes.sizeof(pref),
            )
        except Exception:
            # 兼容旧系统/无 DWM 环境，静默失败即可
            pass

        # 尝试禁用 DWM 非客户区渲染（常见于“无边框仍带矩形阴影/边框”的情况）
        try:
            hwnd = self.winfo_id()
            if hwnd:
                DWMWA_NCRENDERING_POLICY = 2
                DWMNCRP_DISABLED = 1
                policy = ctypes.c_int(DWMNCRP_DISABLED)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    ctypes.wintypes.HWND(hwnd),
                    ctypes.wintypes.DWORD(DWMWA_NCRENDERING_POLICY),
                    ctypes.byref(policy),
                    ctypes.sizeof(policy),
                )
        except Exception:
            pass

        # 兜底：对 overrideredirect(True) 的无边框窗，用 region 做真实圆角裁剪
        try:
            self.update_idletasks()
            self._apply_round_region(self._round_radius)
        except Exception:
            pass

    def _on_configure_apply_round(self, _event=None):
        """窗口大小/布局变化时，节流重算圆角 region（避免频繁 GDI 调用）。"""
        if os.name != "nt":
            return
        # 最小化猫形态使用独立 Region，避免与常规圆角 Region 互相覆盖导致黑边
        if getattr(self, "is_collapsed", False):
            return
        try:
            if self._round_job is not None:
                self.after_cancel(self._round_job)
            self._round_job = self.after(16, lambda: self._apply_round_region(self._round_radius))
        except Exception:
            pass

    def _apply_round_region(self, radius: int):
        """使用 SetWindowRgn 对窗口做真实圆角裁剪（适用于无边框）。"""
        if os.name != "nt":
            return
        try:
            hwnd = self.winfo_id()
            if not hwnd:
                return

            w = int(self.winfo_width())
            h = int(self.winfo_height())
            if w <= 0 or h <= 0:
                return

            r = max(0, int(radius))
            r = min(r, w // 2, h // 2)

            gdi32 = ctypes.windll.gdi32
            user32 = ctypes.windll.user32
            # 轻微内缩 1px，减少半透明窗口导致的外沿黑线/矩形边
            inset = 1 if (w > 4 and h > 4) else 0
            hrgn = gdi32.CreateRoundRectRgn(
                inset,
                inset,
                max(inset + 1, w - inset),
                max(inset + 1, h - inset),
                max(0, (r - inset) * 2),
                max(0, (r - inset) * 2),
            )
            if hrgn:
                user32.SetWindowRgn(hwnd, hrgn, True)
        except Exception:
            pass

    def _monitor_tick(self):
        """主线程定时监控：升级为前台焦点追踪引擎 (自带 CPU 与 IO 节流阀)"""
        if not getattr(self, "running", False):
            return

        try:
            if not hasattr(self, "study_procs") or not self.study_procs:
                self.after(1000, self._monitor_tick)
                return

            user32 = ctypes.windll.user32
            self._monitor_loop_counter = int(getattr(self, "_monitor_loop_counter", 0)) + 1
            self.db["last_heartbeat"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # ==========================================
            # 🐢 慢车道：每 5 秒进行一次重量级 psutil 扫描 (音乐监控)
            # ==========================================
            if self._monitor_loop_counter % 5 == 0:
                active_procs = set() # 🚀 使用 set 替代 list，哈希查找将速度提升 O(1)
                for p in psutil.process_iter(['name']):
                    try:
                        if p.info['name']: active_procs.add(p.info['name'].lower())
                    except Exception: continue

                self.music_active = any(m in active_procs for m in (getattr(self, "music_procs", []) or []))
                
            # 音乐时长依然每秒累加（基于慢车道算出的最新状态）
            if getattr(self, "music_active", False):
                self.db[self.today]["music_total"] += 1
                self._data_dirty = True # 标记数据已变脏

            # ==========================================
            # 🚀 快车道：每 1 秒进行一次极其轻量的前台焦点捕获
            # ==========================================
            fg_proc_name = ""
            hwnd = user32.GetForegroundWindow()
            if hwnd:
                pid = ctypes.wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                try:
                    p = psutil.Process(pid.value)
                    fg_proc_name = p.name().lower()
                except Exception: pass

            # --- [模块 C] 💻 学习/游戏：只统计当前焦点窗口 ---
            if self.mode == "STUDY":
                if fg_proc_name in (getattr(self, "study_procs", []) or []):
                    if fg_proc_name not in self.db[self.today]["study_apps"]:
                        self.db[self.today]["study_apps"][fg_proc_name] = 0
                    self.db[self.today]["study_apps"][fg_proc_name] += 1
                    self.db[self.today]["study_total"] += 1
                    self._data_dirty = True # 标记数据已变脏
                    
                    if self.study_break_sec > 0 and (self.db[self.today]["study_total"] % self.study_break_sec == 0):
                        self.trigger_study_break()

            elif self.mode == "GAME":
                if fg_proc_name in (getattr(self, "game_procs", []) or []):
                    if fg_proc_name not in self.db[self.today]["game_apps"]:
                        self.db[self.today]["game_apps"][fg_proc_name] = 0
                    self.db[self.today]["game_apps"][fg_proc_name] += 1
                    self.db[self.today]["game_total"] += 1
                    self._data_dirty = True # 标记数据已变脏
                    
                    if self.game_limit_sec > 0 and self.db[self.today]["game_total"] >= self.game_limit_sec:
                        if not self.warning_active and (time.time() - getattr(self, "last_warning_time", 0) > 60):
                            self.trigger_game_warning()

            # ==========================================
            # 💾 硬盘 IO 节流阀：从 10 秒盲目写，改为 60 秒“脏检测”写入
            # ==========================================
            if getattr(self, "_data_dirty", False) and self._monitor_loop_counter % 60 == 0:
                save_data(self.db)
                self._data_dirty = False # 保存后清洗标记
                
        except Exception as e:
            if 'logger' in globals(): logger.error("🔍 焦点监测引擎内部异常", exc_info=True)
        finally:
            self.after(1000, self._monitor_tick)
    # ==========================================
    # 🌐 工业级网络装甲 (原生底层防御版)
    # ==========================================
    def safe_get(self, url, params=None, timeout=3, max_retries=1, cache_key=None, as_json=True):
        """完全抛弃 requests，使用 Python 原生 urllib，物理切除第三方库引发的 Windows 代理死锁！"""
        import urllib.request
        import urllib.error
        import urllib.parse
        import json
        import time
        
        for attempt in range(max_retries + 1):
            try:
                # 拼接 URL 参数
                req_url = url
                if params:
                    query = urllib.parse.urlencode(params, doseq=True)
                    req_url = f"{url}?{query}"
                
                # 🚀 核心救命代码：创建一个空的代理处理器，强行阻止 Windows 查找底层注册表！
                proxy_handler = urllib.request.ProxyHandler({})
                opener = urllib.request.build_opener(proxy_handler)
                
                # 伪装请求头，防止被 API 拦截
                req = urllib.request.Request(req_url, headers={'User-Agent': 'Mozilla/5.0'})
                
                with opener.open(req, timeout=timeout) as response:
                    raw_data = response.read().decode('utf-8')
                    data = json.loads(raw_data) if as_json else raw_data
                    
                    # 🟢 请求成功：固化到系统数据库缓存中
                    if cache_key and hasattr(self, "db"):
                        self.db.setdefault("net_cache", {})[cache_key] = data
                        self._data_dirty = True
                        
                    return data
                    
            except Exception as e:
                if attempt < max_retries:
                    time.sleep(1.0) # 断网时退避1秒
                else:
                    pass
        
        # 🔴 降级兜底：返回历史缓存
        db_safe = getattr(self, "db", {})
        if cache_key and "net_cache" in db_safe:
            return db_safe["net_cache"].get(cache_key)
            
        return None
    def update_ui(self):
        # 🚀 清除旧的引线，绝对防止定时器叠加造成的 UI 撕裂和内存泄漏
        if hasattr(self, '_ui_job') and self._ui_job:
            try: self.after_cancel(self._ui_job)
            except: pass

        if not getattr(self, "is_collapsed", False):
            # 1. 更新主专注/游戏时间
            sec = self.db[self.today]["study_total"] if self.mode == "STUDY" else self.db[self.today]["game_total"]
            self.lbl_time.configure(text=f"{sec//3600:02d}:{(sec%3600)//60:02d}:{sec%60:02d}")
            
            # 2. 🚀 动态演算每周进度 (仅学习模式)
            if self.mode == "STUDY" and hasattr(self, 'goal_bar') and self.goal_bar.winfo_exists():
                # 算出本周一到今天的总时长
                now = datetime.now()
                monday = now - timedelta(days=now.weekday())
                week_sec = 0
                for i in range(now.weekday() + 1):
                    d_str = (monday + timedelta(days=i)).strftime("%Y-%m-%d")
                    week_sec += self.db.get(d_str, {}).get("study_total", 0)
                
                # 读取目标
                target_sec = self.sys_config.get("timers", {}).get("weekly_goal_sec", 20 * 3600)
                progress = min(week_sec / target_sec, 1.0) if target_sec > 0 else 0
                
                # 更新 UI
                self.goal_bar.set(progress)
                self.lbl_goal_text.configure(
                    text=f"WEEKLY GOAL: {week_sec//3600}H / {target_sec//3600}H ({int(progress*100)}%)",
                    text_color="#10b981" if progress >= 1.0 else "#a1a1aa"
                )
                
                # 💥 达成目标！触发单次庆祝弹窗
                week_str = now.strftime("%Y-W%W") # 获取当前是今年的第几周
                if progress >= 1.0 and getattr(self, "_celebrated_week", "") != week_str:
                    self._celebrated_week = week_str # 烙上思想钢印，本周不再弹窗
                    self.after(500, self._trigger_goal_celebration) # 弹窗！

            # 3. 更新独立的音乐时长标签 (保持你原有的逻辑)
            m_sec = self.db[self.today].get("music_total", 0)
            if hasattr(self, 'lbl_music_time'):
                if getattr(self, "music_active", False) and m_sec > 0:
                    if m_sec >= 3600:
                        self.lbl_music_time.configure(text=f"{m_sec//3600}h")
                    else:
                        self.lbl_music_time.configure(text=f"{m_sec//60}m")
                else:
                    self.lbl_music_time.configure(text="")
        # 🚀 情绪状态机：根据时长动态改变猫咪形态 (仅悬浮窗模式下触发)
        if getattr(self, "is_collapsed", False) and hasattr(self, 'cat_canvas'):
            try:
                sec = self.db[self.today]["study_total"] if self.mode == "STUDY" else self.db[self.today]["game_total"]
                if self.mode == "STUDY":
                    if sec > 2 * 3600:
                        self._update_pet_mood("tired")
                    elif sec > 3600:
                        self._update_pet_mood("sleepy")
                    else:
                        self._update_pet_mood("normal")
                elif self.mode == "GAME":
                    limit = getattr(self, "game_limit_sec", 2.5 * 3600)
                    if sec > limit:
                        self._update_pet_mood("angry")
                    else:
                        self._update_pet_mood("normal")
            except Exception: pass
                    
        # 保存这根新的“引线”，供下一秒拆除
        self._ui_job = self.after(1000, self.update_ui)

    # --- 📊 日历与全景数据矩阵 ---
    def show_data_module(self):
        """双核数据中枢：融合 7 天全息矩阵、软件耗时追踪与历史月历"""
        if hasattr(self, 'data_win') and self.data_win.winfo_exists():
            self.data_win.focus()
            return

        # 1. 初始化扩容后的数据终端
        scale = float(self.sys_config.get("ui_scale", "1.0")) # 读取倍率
        self.data_win = ctk.CTkToplevel(self)
        self.data_win.title("SYSTEM ANALYTICS & ARCHIVE")
        self.data_win.geometry(f"{int(750 * scale)}x{int(620 * scale)}")  # 动态应用宽高
        self.data_win.attributes("-topmost", True)
        self.data_win.configure(fg_color="#09090b")

        # 2. 构建赛博标签页 (Tabview)
        tabview = ctk.CTkTabview(self.data_win, fg_color="#111111", 
                                 segmented_button_fg_color="#18181b", 
                                 segmented_button_selected_color="#27272a",
                                 text_color="#00f2ff")
        tabview.pack(expand=True, fill="both", padx=15, pady=15)
        
        tab_matrix = tabview.add("NEURAL MATRIX (监控矩阵)")
        tab_cal = tabview.add("ARCHIVE CALENDAR (历史月历)")

        # ==========================================
        # ⚡ TAB 1: 监控矩阵 (包含 7天图表 + 今日软件耗时)
        # ==========================================
        
        # --- A. 7 天数据计算 ---
        today_obj = datetime.now()
        study_week_sec, game_week_sec = 0, 0
        days_data = [] 
        for i in range(6, -1, -1):
            d_str = (today_obj - timedelta(days=i)).strftime("%Y-%m-%d")
            s = self.db.get(d_str, {}).get("study_total", 0)
            g = self.db.get(d_str, {}).get("game_total", 0)
            study_week_sec += s
            game_week_sec += g
            days_data.append({"date": d_str[-5:], "study": s, "game": g})

        # --- B. 顶部核心指标卡片 ---
        summary_frame = ctk.CTkFrame(tab_matrix, fg_color="transparent")
        summary_frame.pack(fill="x", padx=10, pady=(5, 10))

        def make_card(parent, title, value_str, color):
            f = ctk.CTkFrame(parent, fg_color="#18181b", corner_radius=8, border_width=1, border_color="#27272a")
            f.pack(side="left", expand=True, fill="x", padx=5)
            ctk.CTkLabel(f, text=title, font=("Consolas", 12), text_color="#a1a1aa").pack(pady=(10, 0))
            ctk.CTkLabel(f, text=value_str, font=("Impact", 20), text_color=color).pack(pady=(0, 10))

        make_card(summary_frame, "7-DAY STUDIO", f"{study_week_sec//3600}H {(study_week_sec%3600)//60}M", "#00f2ff")
        make_card(summary_frame, "7-DAY GAMING", f"{game_week_sec//3600}H {(game_week_sec%3600)//60}M", "#ef4444")

        # --- C. 7天动态柱状图 ---
        chart_frame = ctk.CTkFrame(tab_matrix, fg_color="#18181b", corner_radius=10)
        chart_frame.pack(fill="x", padx=15, pady=5)
        bar_container = ctk.CTkFrame(chart_frame, fg_color="transparent")
        bar_container.pack(expand=True, fill="both", padx=15, pady=15)
        
        max_sec = max(max((d["study"] + d["game"]) for d in days_data), 1)
        for data in days_data:
            col = ctk.CTkFrame(bar_container, fg_color="transparent")
            col.pack(side="left", expand=True, fill="y", padx=4)
            s_height, g_height = int((data["study"]/max_sec)*80), int((data["game"]/max_sec)*80)
            
            ctk.CTkFrame(col, fg_color="transparent", height=100).pack(side="top", expand=True, fill="both")
            if data["game"] > 0: ctk.CTkFrame(col, fg_color="#ef4444", height=max(5, g_height), width=24).pack(side="top", pady=(0, 1))
            if data["study"] > 0: ctk.CTkFrame(col, fg_color="#00f2ff", height=max(5, s_height), width=24).pack(side="top")
            ctk.CTkLabel(col, text=data["date"], font=("Consolas", 10), text_color="#71717a").pack(side="bottom")

        # --- D. 今日软件追踪明细 (Scrollable) ---
        app_frame = ctk.CTkScrollableFrame(tab_matrix, fg_color="#18181b", corner_radius=10, height=130)
        app_frame.pack(fill="both", expand=True, padx=15, pady=(10, 5))
        ctk.CTkLabel(app_frame, text="TODAY'S APP TRACE (今日软件追踪)", font=("Consolas", 12, "bold"), text_color="#71717a").pack(anchor="w", pady=(0, 5))
        
        today_data = self.db.get(self.today, {})
        # 打印学习软件
        for app, sec in today_data.get("study_apps", {}).items():
            if sec > 0:
                ctk.CTkLabel(app_frame, text=f"[STUDIO] {app.upper()}: {sec//3600}h {(sec%3600)//60}m {sec%60}s", font=("Consolas", 12), text_color="#00f2ff").pack(anchor="w", padx=10)
        # 打印游戏软件
        for app, sec in today_data.get("game_apps", {}).items():
            if sec > 0:
                ctk.CTkLabel(app_frame, text=f"[GAMING] {app.upper()}: {sec//3600}h {(sec%3600)//60}m {sec%60}s", font=("Consolas", 12), text_color="#ef4444").pack(anchor="w", padx=10)


        # ==========================================
        # 📅 TAB 2: 历史月历 (全功能存档查阅)
        # ==========================================
        
        cal_left = ctk.CTkFrame(tab_cal, fg_color="transparent")
        cal_left.pack(side="left", fill="both", expand=True, padx=10)
        
        cal_right = ctk.CTkFrame(tab_cal, fg_color="#18181b", width=int(220 * scale), corner_radius=10)
        cal_right.pack(side="right", fill="y", padx=10, pady=10)
        cal_right.pack_propagate(False) # 锁定右侧面板宽度
        
        # -- 右侧：选中日期的详情面板 (终极对齐版) --
        lbl_sel_date = ctk.CTkLabel(cal_right, text="SELECT DATE", font=("Impact", 20), text_color="#ffffff")
        lbl_sel_date.pack(pady=(20, 10))
        
        lbl_sel_s = ctk.CTkLabel(cal_right, text="STUDIO: --", font=("Consolas", 14), text_color="#00f2ff")
        lbl_sel_s.pack(pady=5)
        
        lbl_sel_g = ctk.CTkLabel(cal_right, text="GAMING: --", font=("Consolas", 14), text_color="#ef4444")
        lbl_sel_g.pack(pady=5)
        
        # 🎵 音乐时长 (律动橙 - 代码完美，无需改动)
        lbl_sel_m = ctk.CTkLabel(cal_right, text="MUSIC : --", font=("Consolas", 14), text_color="#f59e0b")
        lbl_sel_m.pack(pady=5)
        
        # 🌙 睡眠时长 (赛博紫)
        lbl_sel_sleep = ctk.CTkLabel(cal_right, text="SLEEP : --", font=("Consolas", 14), text_color="#a855f7")
        lbl_sel_sleep.pack(pady=5)
        
        lbl_sel_apps = ctk.CTkLabel(cal_right, text="", font=("Consolas", 11), text_color="#a1a1aa", justify="left")
        lbl_sel_apps.pack(pady=15, padx=10, anchor="w")

        def _has_meaningful_day_data(d_data: dict) -> bool:
            if not isinstance(d_data, dict):
                return False
            if d_data.get("study_total", 0) > 0:
                return True
            if d_data.get("game_total", 0) > 0:
                return True
            if d_data.get("music_total", 0) > 0:
                return True
            sleep = d_data.get("sleep", {})
            if isinstance(sleep, dict):
                dur = sleep.get("duration", "")
                if dur and dur not in ["未记录", "已记录", "--"]:
                    return True
            if any((sec or 0) > 0 for sec in (d_data.get("study_apps") or {}).values()):
                return True
            if any((sec or 0) > 0 for sec in (d_data.get("game_apps") or {}).values()):
                return True
            return False

        def _date_has_data(date_str: str) -> bool:
            return _has_meaningful_day_data(self.db.get(date_str, {}))

        def _month_has_data(y: int, m: int) -> bool:
            prefix = f"{y}-{m:02d}-"
            for k, v in (self.db or {}).items():
                if isinstance(k, str) and k.startswith(prefix) and _has_meaningful_day_data(v):
                    return True
            return False

        def on_day_click(date_str: str):
            """点击日历更新右侧数据 (自带历史数据兼容与推算引擎)"""
            d_data = self.db.get(date_str, {})
            s_sec = d_data.get("study_total", 0)
            g_sec = d_data.get("game_total", 0)
            m_sec = d_data.get("music_total", 0)

            # --- 🌙 睡眠数据高级解析与历史兼容 ---
            sleep_data = d_data.get("sleep", {})
            sleep_dur = "--"

            if isinstance(sleep_data, dict):
                sleep_dur = sleep_data.get("duration", "--")

                # 旧版“已记录”：尝试用起床/入睡重新推算
                if sleep_dur == "已记录":
                    s_t = sleep_data.get("sleep_time", "")
                    w_t = sleep_data.get("wake_time", "")
                    if s_t and w_t:
                        try:
                            s_h, s_m = map(int, s_t.replace("：", ":").split(':'))
                            w_h, w_m = map(int, w_t.replace("：", ":").split(':'))
                            s_mins, w_mins = s_h * 60 + s_m, w_h * 60 + w_m
                            if w_mins < s_mins:
                                w_mins += 24 * 60
                            total_m = w_mins - s_mins
                            sleep_dur = f"{total_m // 60}H {total_m % 60}M"
                        except Exception:
                            sleep_dur = "--"
                    else:
                        sleep_dur = "--"

            if sleep_dur in ["未记录", "已记录", ""] or not sleep_dur:
                sleep_dur = "--"
            # ----------------------------------------

            lbl_sel_date.configure(text=date_str)
            lbl_sel_s.configure(text=f"STUDIO: {s_sec//3600}H {(s_sec%3600)//60}M")
            lbl_sel_g.configure(text=f"GAMING: {g_sec//3600}H {(g_sec%3600)//60}M")
            lbl_sel_m.configure(text=f"MUSIC : {m_sec//3600}H {(m_sec%3600)//60}M")
            lbl_sel_sleep.configure(text=f"SLEEP : {sleep_dur}")

            app_text = "APPS RECORD:\n"
            for app, sec in d_data.get("study_apps", {}).items():
                if sec > 0:
                    app_text += f"+ {app[:12]}: {sec//60}m\n"
            for app, sec in d_data.get("game_apps", {}).items():
                if sec > 0:
                    app_text += f"- {app[:12]}: {sec//60}m\n"
            if not d_data.get("study_apps") and not d_data.get("game_apps"):
                app_text += "No records."
            lbl_sel_apps.configure(text=app_text)

        # -- 左侧：今年 12 个月总览 + 动态日历网格 --
        year = today_obj.year
        selected_month = today_obj.month

        month_overview = ctk.CTkFrame(cal_left, fg_color="transparent")
        month_overview.pack(fill="x", padx=10, pady=(10, 0))

        ctk.CTkLabel(month_overview, text=f"{year} YEAR OVERVIEW", font=("Impact", 20), text_color="#71717a").pack(anchor="w")

        months_grid = ctk.CTkFrame(month_overview, fg_color="transparent")
        months_grid.pack(fill="x", pady=(8, 0))

        cal_title = ctk.CTkLabel(cal_left, text="", font=("Impact", 24), text_color="#71717a")
        cal_title.pack(pady=(10, 0))

        grid_frame = ctk.CTkFrame(cal_left, fg_color="transparent")
        grid_frame.pack(expand=True, fill="both", padx=10, pady=10)

        month_btns = {}

        def _render_month(y: int, m: int):
            nonlocal selected_month
            selected_month = m
            cal_title.configure(text=f"{y} - {m:02d} ARCHIVE")

            # 更新月份按钮选中态
            for mm, b in month_btns.items():
                if mm == m:
                    b.configure(border_color="#00f2ff")
                else:
                    b.configure(border_color="#27272a")

            # 清空旧网格
            for w in grid_frame.winfo_children():
                try:
                    w.destroy()
                except Exception:
                    pass

            # 表头
            for i, wd in enumerate(["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]):
                ctk.CTkLabel(
                    grid_frame,
                    text=wd,
                    font=("Consolas", 12, "bold"),
                    text_color="#52525b",
                ).grid(row=0, column=i, padx=8, pady=5)

            cal_matrix = calendar.monthcalendar(y, m)
            for r, week in enumerate(cal_matrix):
                for c, day in enumerate(week):
                    if day == 0:
                        continue
                    d_str = f"{y}-{m:02d}-{day:02d}"

                    d_data = self.db.get(d_str, {})
                    s_sec = d_data.get("study_total", 0)
                    g_sec = d_data.get("game_total", 0)
                    has_data = _date_has_data(d_str)

                    # 热力图配色逻辑：无数据=灰且禁用；学习多=暗蓝；游戏多=暗红
                    btn_color = "#18181b"
                    if s_sec > g_sec and s_sec > 0:
                        btn_color = "#082f49"
                    elif g_sec > s_sec and g_sec > 0:
                        btn_color = "#450a0a"

                    state = "normal" if has_data else "disabled"
                    text_color = "#e4e4e7" if has_data else "#52525b"
                    hover_color = "#3f3f46" if has_data else "#18181b"

                    btn = ctk.CTkButton(
                        grid_frame,
                        text=str(day),
                        width=45,
                        height=45,
                        corner_radius=8,
                        fg_color=btn_color if has_data else "#18181b",
                        hover_color=hover_color,
                        text_color=text_color,
                        state=state,
                        command=lambda d=d_str: on_day_click(d),
                    )
                    btn.grid(row=r + 1, column=c, padx=5, pady=5)

        def _on_month_click(m: int):
            _render_month(year, m)

        # 生成 12 个月按钮 (3x4)
        month_names = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
        for idx in range(12):
            m = idx + 1
            has_m = _month_has_data(year, m)

            fg = "#18181b" if not has_m else "transparent"
            hov = "#18181b" if not has_m else "#27272a"
            tcol = "#52525b" if not has_m else "#e4e4e7"
            st = "disabled" if not has_m else "normal"

            b = ctk.CTkButton(
                months_grid,
                text=month_names[idx],
                width=70,
                height=30,
                fg_color=fg,
                hover_color=hov,
                text_color=tcol,
                corner_radius=8,
                border_width=1,
                border_color="#27272a",
                state=st,
                command=(lambda mm=m: _on_month_click(mm)),
            )
            b.grid(row=idx // 4, column=idx % 4, padx=6, pady=6, sticky="ew")
            month_btns[m] = b

        # 初始渲染：如果当月无数据，则跳到今年第一个有数据的月份
        if not _month_has_data(year, selected_month):
            for m in range(1, 13):
                if _month_has_data(year, m):
                    selected_month = m
                    break
        _render_month(year, selected_month)
    
    # --- 🌙 睡眠追踪记录器 ---
    # --- 🌙 睡眠追踪记录器 ---
    def check_sleep_log(self):
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        if yesterday in self.db and self.db[yesterday].get("sleep", {}).get("duration") == "未记录":
            last_hb = self.db.get("last_heartbeat", "未知")
            
            win = ctk.CTkToplevel(self)
            win.geometry("400x340+400+300")
            win.attributes("-topmost", True)
            win.configure(fg_color="#18181b")
            
            ctk.CTkLabel(win, text="🌙 睡眠状态归档", font=("Microsoft YaHei", 18, "bold"), text_color="#a855f7").pack(pady=(20, 10))
            ctk.CTkLabel(win, text=f"昨晚离线: {last_hb}", text_color="#a1a1aa", font=("Consolas", 12)).pack(pady=(0, 15))
            
            # 输入表单容器
            input_frame = ctk.CTkFrame(win, fg_color="transparent")
            input_frame.pack(pady=10)
            
            ctk.CTkLabel(input_frame, text="入睡时间 (如 02:30):", text_color="white").grid(row=0, column=0, padx=10, pady=8, sticky="e")
            entry_sleep = ctk.CTkEntry(input_frame, width=120)
            entry_sleep.grid(row=0, column=1, padx=10, pady=8)
            
            ctk.CTkLabel(input_frame, text="起床时间 (如 10:00):", text_color="white").grid(row=1, column=0, padx=10, pady=8, sticky="e")
            entry_wake = ctk.CTkEntry(input_frame, width=120)
            entry_wake.grid(row=1, column=1, padx=10, pady=8)

            err_lbl = ctk.CTkLabel(win, text="", text_color="#ef4444", font=("Microsoft YaHei", 11))
            err_lbl.pack()
            
            def save_sleep():
                s_time = entry_sleep.get().strip()
                w_time = entry_wake.get().strip()
                
                if not s_time or not w_time:
                    err_lbl.configure(text="⚠ 架构师，请完整输入两个时间点！")
                    return
                
                try:
                    # 容错处理：将中文冒号替换为英文冒号
                    s_h, s_m = map(int, s_time.replace("：", ":").split(':'))
                    w_h, w_m = map(int, w_time.replace("：", ":").split(':'))
                    
                    # 转换为全分钟数
                    s_mins = s_h * 60 + s_m
                    w_mins = w_h * 60 + w_m
                    
                    # 跨夜处理算法 (如果起床分钟数小于入睡分钟数，说明跨了一天)
                    if w_mins < s_mins:
                        w_mins += 24 * 60
                        
                    dur_mins = w_mins - s_mins
                    dur_str = f"{dur_mins // 60}H {dur_mins % 60}M"
                    
                    # 存入数据库
                    self.db[yesterday]["sleep"]["sleep_time"] = s_time
                    self.db[yesterday]["sleep"]["wake_time"] = w_time
                    self.db[yesterday]["sleep"]["duration"] = dur_str
                    save_data(self.db)
                    
                    win.destroy()
                except Exception as e:
                    err_lbl.configure(text="⚠ 时间解析失败！必须是 HH:MM 格式 (例: 08:30)")

            ctk.CTkButton(win, text="💾 提交能量矩阵", command=save_sleep, width=180, height=35, 
                          font=("Microsoft YaHei", 12, "bold"), fg_color="#a855f7", hover_color="#9333ea").pack(pady=15)

    # --- 灵魂弹窗组件 ---
    def trigger_study_break(self):
        """升级版架构师休息站：支持联网金句与随机音乐推荐"""
        # 🚀 启动托盘警报闪烁！
        self.start_tray_flash()
        win = ctk.CTkToplevel(self)
        win.title("RESTING PROTOCOL")
        win.geometry("520x360")
        win.attributes("-topmost", True)
        win.overrideredirect(True)
        win.configure(fg_color="#0b0b10")
        
        # 居中显示
        self._apply_center_geometry(win, 520, 360)
        
        # 装饰性外边框
        outer = ctk.CTkFrame(win, fg_color="#0b0b10", corner_radius=14, border_width=1, border_color="#10b981")
        outer.pack(expand=True, fill="both", padx=10, pady=10)

        # 标题区
        ctk.CTkLabel(outer, text="☕ 架构师休息站", font=("Microsoft YaHei", 26, "bold"), text_color="#10b981").pack(pady=(20, 10))
        
        # 动态内容标签：展示联网获取的金句 (恢复斜体，制造内部安全区)
        quote_lbl = ctk.CTkLabel(outer, text="正在接入思维矩阵，获取宁静指令...   ", 
                                 font=("Microsoft YaHei", 13, "italic"), text_color="#d1d5db", 
                                 width=480, justify="center", wraplength=440)
        quote_lbl.pack(pady=10, padx=20)

        # 音乐推荐区卡片
        music_frame = ctk.CTkFrame(outer, fg_color="#111111", corner_radius=10, border_width=1, border_color="#27272a")
        music_frame.pack(fill="x", padx=40, pady=10)
        
        ctk.CTkLabel(music_frame, text="🎵 推荐今日放松旋律：", font=("Microsoft YaHei", 12, "bold"), text_color="#00f2ff").pack(pady=(8, 2))
        
        # 随机音乐推荐池 (结合了你学习英文的背景)
        relaxing_songs = [
            "《Summer》- 久石让 (清新钢琴)", 
            "《Luv Letter》- DJ Okawari (经典律动)", 
            "《Weightless》- Marconi Union (科学减压)",
            "《Perfect》- Ed Sheeran (英文经典)", 
            "《City of Stars》- La La Land (爵士氛围)",
            "《Always with Me》- 千与千寻 (治愈旋律)",
            "《遇上》- 叶炫清 (宁静国风)",
            "《Thinking Out Loud》- Ed Sheeran (英文抒情)"
        ]
        # 随机抽取两首
        chosen_songs = random.sample(relaxing_songs, 2)
        song_text = f"1. {chosen_songs[0]}\n2. {chosen_songs[1]}"
        
        ctk.CTkLabel(music_frame, text=song_text, font=("Consolas", 12), text_color="#a1a1aa").pack(pady=(0, 10))

        # 🚀 定义一个关闭休息站并熄灭闪烁的联动指令
        def close_break():
            self.stop_tray_flash()
            win.destroy()

        # 确认按钮
        ctk.CTkButton(outer, text="收到，去听首歌休息", command=close_break, 
                       fg_color="#10b981", hover_color="#059669", 
                       font=("Microsoft YaHei", 13, "bold"), height=40).pack(pady=20)

        # 异步加载联网内容
        def load_content():
            # 复用已有的联网获取方法
            text = self._fetch_soup_text("study") 
            if not text:
                text = "真正的成长，是在平静中积蓄力量。\n两个小时的高频算力已经达成，让眼睛休息一下。"
            
            # 回到主线程更新 UI
            self.after(0, lambda: quote_lbl.configure(text=text))

        threading.Thread(target=load_content, daemon=True).start()

    def _trigger_goal_celebration(self):
        """里程碑达成：极客风全息庆祝弹窗"""
        win = ctk.CTkToplevel(self)
        win.title("MILESTONE REACHED")
        win.attributes("-topmost", True)
        win.configure(fg_color="#0b0b10")
        win.overrideredirect(True)
        self._apply_center_geometry(win, 500, 300)
        
        outer = ctk.CTkFrame(win, fg_color="#0b0b10", corner_radius=14, border_width=2, border_color="#10b981")
        outer.pack(expand=True, fill="both", padx=10, pady=10)
        
        ctk.CTkLabel(outer, text="🏆 MILESTONE UNLOCKED", font=("Impact", 36), text_color="#facc15").pack(pady=(30, 10))
        ctk.CTkLabel(outer, text="本周算力目标已达成！", font=("Microsoft YaHei", 18, "bold"), text_color="#10b981").pack(pady=(0, 20))
        ctk.CTkLabel(outer, text="自律与逻辑是你最坚不可摧的武器。\n本周剩余时间的每一次敲击，都是在超越自我。", 
                     font=("Microsoft YaHei", 12), text_color="#a1a1aa", justify="center").pack(pady=(0, 20))
                     
        ctk.CTkButton(outer, text="继续战斗", font=("Microsoft YaHei", 14, "bold"), fg_color="#10b981", hover_color="#059669", 
                      width=180, height=45, command=win.destroy).pack()
    
    def trigger_game_warning(self):
        """游戏提醒窗：更克制的置顶提示 + 联网鸡汤 + 托盘高频闪烁"""
        if self.warning_active: return # 状态锁检查
        self.warning_active = True     # 立即上锁
            
        # 🚀 启动托盘红色警报闪烁！
        self.start_tray_flash()

        # 1. 创建窗口（不再全屏：避免“太粗暴”）
        win = ctk.CTkToplevel(self)
        win.title("SYSTEM OVERRIDE")
        win.attributes("-topmost", True)
        win.configure(fg_color="#0b0b10")
        win.resizable(False, False)
        win.overrideredirect(True)
        self._apply_center_geometry(win, 720, 420)

        # 2. 定义关闭逻辑
        def on_acknowledge():
            self.warning_active = False      # 解锁
            self.last_warning_time = time.time() # 记录时间开始 60 秒冷却
            self.stop_tray_flash()           # 🚀 熄灭托盘闪烁！
            win.destroy()

        # 3. UI 组件（卡片式警告 + 倒计时 + 鸡汤）
        outer = ctk.CTkFrame(win, fg_color="#0b0b10", corner_radius=14, border_width=1, border_color="#27272a")
        outer.pack(expand=True, fill="both", padx=14, pady=14)

        top = ctk.CTkFrame(outer, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=(12, 0))

        btn_close = ctk.CTkButton(
            top,
            text="✕",
            width=28,
            height=28,
            fg_color="transparent",
            hover_color="#27272a",
            text_color="#a1a1aa",
            font=("Consolas", 16, "bold"),
            command=on_acknowledge,
        )
        btn_close.pack(side="right")
        ToolTip(btn_close, "关闭（60秒冷却）")

        line = ctk.CTkFrame(outer, fg_color="#ef4444", height=6, corner_radius=6)
        line.pack(fill="x", padx=18, pady=(10, 0))

        # 主标题
        ctk.CTkLabel(
            outer,
            text="SYSTEM OVERRIDE",
            font=("Impact", 62),
            text_color="#ef4444",
        ).pack(pady=(18, 4))
        
        try:
            lim = int(getattr(self, "game_limit_sec", int(2.5 * 3600)))
        except Exception:
            lim = int(2.5 * 3600)
        lim_h = lim / 3600.0
        lim_txt = f"{lim_h:.1f} HOURS" if abs(lim_h - round(lim_h)) > 1e-9 else f"{int(lim_h)} HOURS"

        ctk.CTkLabel(
            outer,
            text=f"LIMIT REACHED: {lim_txt} EXCEEDED",
            font=("Consolas", 18, "bold"),
            text_color="#e4e4e7",
        ).pack(pady=(0, 14))

        body = ctk.CTkFrame(outer, fg_color="#111111", corner_radius=12, border_width=1, border_color="#27272a")
        body.pack(fill="both", expand=True, padx=18, pady=(0, 14))

        ctk.CTkLabel(
            body,
            text="建议：站起来走两分钟、喝口水、放松眼睛。",
            font=("Microsoft YaHei", 14, "bold"),
            text_color="#10b981",
        ).pack(pady=(16, 8))

        # 警告鸡汤 (恢复斜体，制造内部安全区)
        soup_lbl = ctk.CTkLabel(
            body,
            text="正在从网络获取鸡汤...   ",
            font=("Microsoft YaHei", 14, "italic"),
            text_color="#a1a1aa",
            width=680, 
            justify="center",
            wraplength=640,
        )
        soup_lbl.pack(padx=18, pady=(0, 10))

        countdown_lbl = ctk.CTkLabel(
            body,
            text="此窗口可关闭（关闭后 60 秒冷却）",
            font=("Consolas", 12, "bold"),
            text_color="#71717a",
        )
        countdown_lbl.pack(pady=(0, 14))

        btn_row = ctk.CTkFrame(outer, fg_color="transparent")
        btn_row.pack(fill="x", padx=18, pady=(0, 10))

        btn_ok = ctk.CTkButton(
            btn_row,
            text="我知道了（继续）",
            font=("Microsoft YaHei", 14, "bold"),
            fg_color="#27272a",
            hover_color="#3f3f46",
            height=40,
            command=on_acknowledge,
        )
        btn_ok.pack(side="right")

        # 轻量倒计时：可选自动关闭（不强制）
        ttl_sec = 20
        def tick():
            nonlocal ttl_sec
            if not win.winfo_exists():
                return
            ttl_sec -= 1
            if ttl_sec <= 0:
                on_acknowledge()
                return
            countdown_lbl.configure(text=f"可关闭 / 自动收起倒计时：{ttl_sec}s（关闭后 60 秒冷却）")
            win.after(1000, tick)

        win.after(1000, tick)

        # 4. 联网鸡汤（后台线程拉取，UI 主线程更新）
        def load_soup():
            text = self._fetch_soup_text("game")
            if not text:
                # 兜底：复用本地缓存的 quotes 或默认句
                fallback_text = "你不是缺时间，你是缺一个把自己拉回来的动作。"
                try:
                    with open(os.path.join(APP_DIR, "quotes.txt"), "r", encoding="utf-8") as f:
                        cached = (f.read() or "").strip()
                        if cached:
                            fallback_text = cached
                except Exception:
                    pass
                text = fallback_text
            self.after(0, lambda: soup_lbl.configure(text=text))

        threading.Thread(target=load_soup, daemon=True).start()
if __name__ == "__main__":
    # 所有的崩溃与异常，现在全盘由 sys.excepthook 救生舱接管！
    app = FloatingTracker()
    app.mainloop()