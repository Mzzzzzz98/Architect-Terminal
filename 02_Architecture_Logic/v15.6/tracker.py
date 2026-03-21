import os
import sys
import json
import ctypes
import ctypes.wintypes
import time
import pystray
from PIL import ImageDraw  # 用于在内存中凭空画出一个赛博图标
import psutil
import winreg
import calendar
import requests
from datetime import datetime, timedelta
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, colorchooser, font, messagebox
import threading
import glob
import random
from PIL import Image, ImageTk, ImageGrab
import traceback

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
APP_NAME = "ArchitectTerminal"
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
        target = os.path.join(base, "ArchitectTerminal").encode('utf-8').decode('utf-8')
        
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

def load_sys_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                if not isinstance(cfg, dict): cfg = {}
                if "timers" not in cfg or not isinstance(cfg.get("timers"), dict): cfg["timers"] = {}
                cfg["timers"].setdefault("study_break_sec", 2 * 3600)
                cfg["timers"].setdefault("game_limit_sec", int(2.5 * 3600))
                return cfg
        except: pass
    return {"is_setup": False, "study": {}, "game": {}, "music": {}, "timers": {"study_break_sec": 2 * 3600, "game_limit_sec": int(2.5 * 3600)}}

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
        if os.path.exists(temp_file): os.remove(temp_file)
        print(f"数据固化失败: {e}")

def save_data(data): atomic_save(DATA_FILE, data)
def save_sys_config(cfg): atomic_save(CONFIG_FILE, cfg)

# 软件快捷启动路径
NETEASE_MUSIC_PATH = r"E:\CloudMusic\cloudmusic.exe"
WEGAME_PATH = r"F:\Program Files (x86)\WeGame\wegame.exe"

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
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return {}

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

        # 2. 窗口UI设定 (加宽以容纳双边栏)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = int(sw / 2.2), int(sh / 1.6)
        self.geometry(f"{w}x{h}+{int((sw-w)/2)}+{int((sh-h)/2)}")
        self.configure(fg_color="#09090b")
        self.attributes("-topmost", True)
        
        # 3. 布局：左侧日历侧边栏，右侧编辑区
        self.left_panel = ctk.CTkFrame(self, width=280, fg_color="#111111", corner_radius=0, border_width=1, border_color="#27272a")
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
        
        # 🚀 体验强化：立刻冻结（禁用）主窗口的点击交互，防止用户在等待的 1.6 秒内误触
        self.attributes("-disabled", True)
        self.after(750, lambda: (toast.destroy(), self.destroy()))

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
        try:
            modified = bool(self.text_area.edit_modified())
        except Exception:
            modified = False

        if modified and not getattr(self, "is_dirty", False):
            self._set_dirty(True)

        try:
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
        self.text_area.image_create(tk.INSERT, image=photo)
        self.text_area.insert(tk.INSERT, "\n")

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
            self.after(2600, lambda: self.btn_save.configure(text="💾 SYNC MATRIX", fg_color="#10b981"))
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
# ⚙️ 神经网络初次校准向导 (V2 智能拖拽捕获版)
# ==========================================
class SetupWizard(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("SYSTEM CALIBRATION (首次部署校准)")
        self.geometry("600x680")
        self.attributes("-topmost", True)
        self.configure(fg_color="#09090b")
        # 👇 解锁右上角关闭按钮，指向安全中断协议
        self.protocol("WM_DELETE_WINDOW", self.abort_setup)

        self.cfg = {"is_setup": True, "study": {}, "game": {}, "music": {}}
        self.section_frames = {} # 用于存储三个区域的容器引用，方便拖拽后动态渲染

        ctk.CTkLabel(self, text="NEURAL PATHWAY CALIBRATION", font=("Impact", 24), text_color="#00f2ff").pack(pady=(25, 5))
        # 👇 动态提示文字更新
        ctk.CTkLabel(self, text="请点击添加或【直接拖入 .exe 文件】进行自动识别", font=("Consolas", 12), text_color="#10b981").pack(pady=(0, 15))

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="#111111", corner_radius=10, border_width=1, border_color="#27272a")
        self.scroll.pack(fill="both", expand=True, padx=25, pady=10)

        self.build_section("💻 STUDIO (生产力 / 学习软件)", "study", "#00f2ff")
        self.build_section("🎮 GAMING (娱乐 / 游戏软件)", "game", "#ef4444")
        self.build_section("🎵 MUSIC (音乐播放器)", "music", "#f59e0b")

        self.btn_deploy = ctk.CTkButton(self, text="✅ DEPLOY SYSTEM (部署架构矩阵)", font=("Impact", 20), 
                                        fg_color="#10b981", hover_color="#059669", height=50, command=self.finish_setup)
        self.btn_deploy.pack(pady=20, fill="x", padx=25)

        # 👇 拖拽：优先使用 tkinterdnd2（更稳）；不可用则仅支持“点击添加”
        _bind_tkdnd_drop(self, self._on_files_dropped)

    def _on_files_dropped(self, paths):
        self.handle_drop(paths)

    def build_section(self, title, key, color):
        frame = ctk.CTkFrame(self.scroll, fg_color="#18181b", corner_radius=8)
        frame.pack(fill="x", pady=10)
        self.section_frames[key] = frame # 保存引用以便拖拽后动态添加 UI
        
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=10)
        ctk.CTkLabel(header, text=title, font=("Microsoft YaHei", 14, "bold"), text_color=color).pack(side="left")
        ctk.CTkButton(header, text="+ 添加 .exe", width=80, fg_color="#27272a", hover_color="#3f3f46", 
                      command=lambda: self.add_exe(key)).pack(side="right")

    def add_exe(self, key):
        """传统的点击选择文件流"""
        try:
            # 关键修复：显式指定 parent，避免对话框被置顶窗挡在后面导致“没反应”
            self.lift()
            self.focus_force()
            file_path = filedialog.askopenfilename(
                parent=self,
                title="选择核心启动文件",
                filetypes=[("Executable", "*.exe")],
            )
            if file_path:
                self._register_exe(key, file_path)
        except Exception as e:
            self.show_error(f"❌ 打开文件对话框失败\n{e}")

    # ==========================================
    # 🌟 以下为全新的拖拽处理系统
    # ==========================================
    # ==========================================
    # 🌟 修复版拖拽系统 (解决线程冲突与崩溃)
    # ==========================================
    def handle_drop(self, files):
        for f in files:
            try:
                # 兼容处理：将字节流转为字符串路径
                file_path = f.decode('gbk') if isinstance(f, bytes) else str(f)
            except:
                continue
            
            # 🚀 绝招：所有涉及到 UI 的操作 (弹窗/报错)，全部通过 after 抛给主线程
            if file_path.lower().endswith('.exe'):
                self.after(0, lambda p=file_path: self.ask_drop_category(p))
            elif file_path.lower().endswith('.lnk'):
                self.after(0, lambda: self.show_error("❌ 拒绝快捷方式\n请拖入本体 .exe 文件！"))
            else:
                self.after(0, lambda: self.show_error("❌ 格式错误\n仅支持 .exe 程序！"))

    def _register_exe(self, key, file_path):
        """底层注册：安全更新 UI"""
        exe_name = os.path.basename(file_path).lower()
        self.cfg[key][exe_name] = file_path
        
        # 🚀 【核心修复2】：确保 UI 更新也在主线程安全队列中
        def update_ui():
            parent_frame = self.section_frames[key]
            ctk.CTkLabel(parent_frame, text=f"✔️ {exe_name}", 
                         font=("Consolas", 12), text_color="#e4e4e7").pack(anchor="w", padx=20, pady=2)
        
        self.after(0, update_ui)

    def ask_drop_category(self, file_path):
        """弹出动态悬浮窗，询问文件归属分类"""
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
            prompt.destroy() # 分配完毕后销毁询问窗

        # 分配选项卡
        ctk.CTkButton(btn_frame, text="💻 STUDIO", width=90, fg_color="#082f49", hover_color="#0284c7", command=lambda: assign("study")).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="🎮 GAMING", width=90, fg_color="#450a0a", hover_color="#dc2626", command=lambda: assign("game")).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="🎵 MUSIC", width=90, fg_color="#78350f", hover_color="#d97706", command=lambda: assign("music")).pack(side="left", padx=5)

    def _register_exe(self, key, file_path):
        """底层注册引擎：将路径写入配置并更新 UI"""
        exe_name = os.path.basename(file_path).lower()
        self.cfg[key][exe_name] = file_path
        parent_frame = self.section_frames[key]
        ctk.CTkLabel(parent_frame, text=f"✔️ {exe_name}", font=("Consolas", 12), text_color="#e4e4e7").pack(anchor="w", padx=20, pady=5)

    def show_error(self, msg):
        err = ctk.CTkToplevel(self)
        err.title("WARNING")
        err.geometry("380x150")
        err.attributes("-topmost", True)
        err.configure(fg_color="#450a0a")
        ctk.CTkLabel(err, text=msg, text_color="#fca5a5", font=("Microsoft YaHei", 11, "bold"), justify="center").pack(expand=True)

    def finish_setup(self):
        """部署协议：确保文件生成后再关闭"""
        # 检查是否至少选了一个
        if not any(self.cfg[k] for k in ["study", "game", "music"]):
            self.show_error("💡 架构为空: 请至少录入一个程序！")
            return

        try:
            # 打印调试信息，你可以通过控制台看到文件准备写到哪
            print(f">>> 正在部署架构至: {CONFIG_FILE}")
            
            # 确保文件夹存在
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            
            # 固化保存
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cfg, f, indent=4, ensure_ascii=False)
            
            print(">>> 部署成功！正在启动主矩阵...")
            
            # 给系统一点响应时间
            self.after(100, self.destroy)
        except Exception as e:
            self.show_error(f"❌ 部署失败: {e}")

    def safe_destroy(self):
        # 销毁向导，让主窗口继续 __init__ 的后续逻辑
        self.destroy()

    def abort_setup(self):
        """关闭向导：不再强制杀进程，避免“弹窗突然消失”"""
        try:
            self.destroy()
        except Exception:
            pass


# ==========================================
# ⚙️ 运行时设置面板：编辑已部署的软件路径
# ==========================================
class SettingsPanel(ctk.CTkToplevel):
    def __init__(self, master, initial_cfg, on_save):
        super().__init__(master)
        self.title("SYSTEM SETTINGS (软件路径矩阵)")
        self.geometry("720x560")
        self.attributes("-topmost", True)
        self.configure(fg_color="#09090b")

        self._on_save = on_save
        # 深拷贝，避免边改边影响主进程
        self.cfg = {
            "is_setup": True,
            "study": dict((initial_cfg or {}).get("study") or {}),
            "game": dict((initial_cfg or {}).get("game") or {}),
            "music": dict((initial_cfg or {}).get("music") or {}),
            "timers": dict((initial_cfg or {}).get("timers") or {}),
        }
        self.cfg.setdefault("timers", {})
        self.cfg["timers"].setdefault("study_break_sec", 2 * 3600)
        self.cfg["timers"].setdefault("game_limit_sec", int(2.5 * 3600))

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
        }

        self.list_frames = {}
        for key in ["study", "game", "music"]:
            self._build_tab(key)
        self._build_timers_tab()

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
        ctk.CTkEntry(row1, width=70, textvariable=self.study_h_var).pack(side="right")
        ctk.CTkLabel(row1, text="小时", font=("Microsoft YaHei", 11), text_color="#a1a1aa").pack(side="right", padx=(6, 12))
        ctk.CTkEntry(row1, width=70, textvariable=self.study_m_var).pack(side="right")
        ctk.CTkLabel(row1, text="分钟", font=("Microsoft YaHei", 11), text_color="#a1a1aa").pack(side="right", padx=(6, 12))

        # 游戏防沉迷阈值
        game_sec = (self.cfg.get("timers") or {}).get("game_limit_sec", int(2.5 * 3600))
        gh, gm = self._sec_to_hm(game_sec)

        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill="x", padx=14, pady=(0, 14))
        ctk.CTkLabel(row2, text="游戏弹窗阈值", font=("Consolas", 12, "bold"), text_color="#ef4444").pack(side="left")

        self.game_h_var = tk.StringVar(value=str(gh))
        self.game_m_var = tk.StringVar(value=str(gm))
        ctk.CTkEntry(row2, width=70, textvariable=self.game_h_var).pack(side="right")
        ctk.CTkLabel(row2, text="小时", font=("Microsoft YaHei", 11), text_color="#a1a1aa").pack(side="right", padx=(6, 12))
        ctk.CTkEntry(row2, width=70, textvariable=self.game_m_var).pack(side="right")
        ctk.CTkLabel(row2, text="分钟", font=("Microsoft YaHei", 11), text_color="#a1a1aa").pack(side="right", padx=(6, 12))

        self.timers_err = ctk.CTkLabel(wrap, text="", font=("Microsoft YaHei", 11, "bold"), text_color="#ef4444")
        self.timers_err.pack(anchor="w")

        hint = (
            "提示：分钟范围 0-59；可填 0 小时。\n"
            "学习提醒：到达间隔时弹出休息提示。\n"
            "游戏弹窗：到达阈值后触发全屏警告（并有 60 秒冷却）。"
        )
        ctk.CTkLabel(wrap, text=hint, font=("Consolas", 11), text_color="#71717a", justify="left").pack(anchor="w", pady=(8, 0))

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
            # Timers：先校验再保存，避免写入坏配置
            if hasattr(self, "study_h_var") and hasattr(self, "game_h_var"):
                try:
                    study_sec = self._parse_hm_to_sec(self.study_h_var.get(), self.study_m_var.get())
                    game_sec = self._parse_hm_to_sec(self.game_h_var.get(), self.game_m_var.get())
                    if study_sec <= 0:
                        raise ValueError("study interval must be > 0")
                    if game_sec <= 0:
                        raise ValueError("game limit must be > 0")
                    self.cfg.setdefault("timers", {})
                    self.cfg["timers"]["study_break_sec"] = int(study_sec)
                    self.cfg["timers"]["game_limit_sec"] = int(game_sec)
                    if hasattr(self, "timers_err") and self.timers_err.winfo_exists():
                        self.timers_err.configure(text="")
                except Exception:
                    if hasattr(self, "timers_err") and self.timers_err.winfo_exists():
                        self.timers_err.configure(text="⚠ 时长输入无效：请填整数，分钟 0-59，且总时长必须 > 0")
                    return

            save_sys_config(self.cfg)
            if callable(self._on_save):
                self._on_save(self.cfg)

            # 体验优化：展示保存成功再关闭
            ok = ctk.CTkToplevel(self)
            ok.title("保存成功")
            ok.geometry("320x120")
            ok.attributes("-topmost", True)
            ok.configure(fg_color="#111111")
            ctk.CTkLabel(ok, text="✅ SETTINGS SAVED", font=("Consolas", 16, "bold"), text_color="#10b981").pack(expand=True)
            self.after(900, lambda: (ok.destroy(), self.destroy()))
        except Exception as e:
            ctypes.windll.user32.MessageBoxW(0, f"保存设置失败：\n{e}", "Settings Save Failed", 0x10)

# ==========================================
# 🚀 核心控制中枢 (极限悬浮窗)
# ==========================================
class FloatingTracker(ctk.CTk):
    def __init__(self):
        super().__init__()
        # 🚀 注入主窗口和任务栏的星云图标
        try:
            self.iconbitmap(resource_path("app_icon.ico"))
        except Exception as e:
            print(f"图标加载失败: {e}")
            
        # 👇 调试用：运行后弹窗告诉你配置文件夹的绝对路径
        print(f"--- 架构坐标: {CONFIG_FILE} ---")
        # 👇 调试用：运行后弹窗告诉你配置文件夹的绝对路径
        print(f"--- 架构坐标: {CONFIG_FILE} ---")
        # 甚至可以加一行代码直接自动打开这个文件夹
        # os.startfile(APPDATA_PATH) 
        
        # 启动时先隐藏主窗，避免无边框切换导致“闪一下”
        self.withdraw()

        # 预设基础状态（在任何 UI 渲染前）
        self.mode = "STUDY"
        self.is_collapsed = False
        self.menu = None
        self.music_active = False

        self.sys_config = load_sys_config()
        
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
        
        # 窗口设定（保持隐藏状态下完成，避免闪烁）
        self.geometry("260x150+100+100") 
        # 先用普通窗口确保能显示；稍后再切换为无边框（某些 Win11/驱动组合下，启动即无边框会“看不见”）
        self.overrideredirect(False)
        # 关键修复：`overrideredirect(True)` + `-toolwindow` 在部分 Windows 环境下会导致窗口“存在但不可见/不可切换”
        # 注意：全窗 alpha 会在边缘产生混色“矩形黑框”（尤其是圆角裁剪后）
        # 若你需要透明效果，建议改为仅内容控件视觉透明（或改用 transparentcolor 方案）
        self.attributes("-topmost", True, "-alpha", 1.0)
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
                self.lift()
                self.attributes("-topmost", True)
                self.focus_force()
                # 无边框后再做一次真实圆角裁剪（Win11 DWM 圆角对部分无边框窗不生效）
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
                self.geometry("260x150+100+100")
        except Exception:
            pass

        # 系统自启动注入
        self.inject_to_registry()

        # 数据初始化
        self.db = load_data()
        self.today = datetime.now().strftime("%Y-%m-%d")
        self.db = init_today_data(self.db, self.today)

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
        # 👇 修复：纠正父级容器为 main_frame，收缩折行宽度至 240，修改引力为居中填充
        self.lbl_quote = ctk.CTkLabel(self.inner_frame, text="正在同步思维矩阵...", 
                                      font=("Microsoft YaHei", 12, "italic"), text_color="#a1a1aa", 
                                      wraplength=240, cursor="hand2") 
        self.lbl_quote.pack(side="top", expand=True, fill="both", pady=(2, 2))
        
        # 绑定鼠标左键点击事件 (<Button-1>)
        self.lbl_quote.bind("<Button-1>", lambda e: self.refresh_quote())
# 👇 ========= 在这里插入 ENV 标签 ========= 👇
        self.lbl_env = ctk.CTkLabel(self.inner_frame, text="ENV SCAN: INITIALIZING SYSTEM...", 
                                    font=("Consolas", 10, "bold"), text_color="#00f2ff")
        self.lbl_env.pack(side="bottom", pady=(0, 2))
        # 👆 ===================================== 👆
        # 在 __init__ 的最后一行加上调用
        self.fetch_daily_quote()

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
        threading.Thread(target=self.fetch_daily_quote, daemon=True).start()
        self.update_ui()
        self.after(1500, self.check_sleep_log) 
        # 👇 新增这一行，启动天气定位引擎 👇
        self.fetch_env_data()
        # 👇 启动右下角托盘引擎
        self.setup_tray()
    def _fetch_soup_text(self, kind: str = "game") -> str:
        """联网获取鸡汤/金句（失败则返回空字符串，由调用方兜底）"""
        try:
            # hitokoto: https://v1.hitokoto.cn/
            # c=k(哲学) c=d(文学) c=i(诗词) —— 尽量偏“提醒自律”方向
            params = {"c": ["k", "d", "i"]}
            resp = requests.get("https://v1.hitokoto.cn/", params=params, timeout=4)
            if resp.status_code != 200:
                return ""
            data = resp.json() if resp.content else {}
            quote = (data or {}).get("hitokoto") or ""
            if not quote:
                return ""
            author = (data or {}).get("from_who") or (data or {}).get("from") or "System"
            return f"{quote} —— {author}"
        except Exception:
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
            try:
                self.settings_win.lift()
                self.settings_win.focus_force()
            except Exception:
                pass
            return

        def on_save(new_cfg):
            # 运行时热更新：刷新监控列表
            self.sys_config = new_cfg or load_sys_config()
            study_cfg = self.sys_config.get("study") or {}
            game_cfg = self.sys_config.get("game") or {}
            music_cfg = self.sys_config.get("music") or {}
            self.study_procs = list(study_cfg.keys())
            self.game_procs = list(game_cfg.keys())
            self.music_procs = list(music_cfg.keys())

            timers = (self.sys_config or {}).get("timers") or {}
            try:
                self.study_break_sec = int(timers.get("study_break_sec", 2 * 3600))
            except Exception:
                self.study_break_sec = 2 * 3600
            try:
                self.game_limit_sec = int(timers.get("game_limit_sec", int(2.5 * 3600)))
            except Exception:
                self.game_limit_sec = int(2.5 * 3600)
            if self.study_break_sec <= 0:
                self.study_break_sec = 2 * 3600
            if self.game_limit_sec <= 0:
                self.game_limit_sec = int(2.5 * 3600)

        self.settings_win = SettingsPanel(self, self.sys_config, on_save=on_save)
    # ==========================================
    # 🛸 隐形托盘矩阵 (System Tray Engine)
    # ==========================================
    def create_tray_icon(self):
        """读取真实的 .ico 实体作为托盘图标"""
        icon_path = resource_path("app_icon.ico")
        if os.path.exists(icon_path):
            return Image.open(icon_path)
        else:
            # 兜底方案：如果万一没找到图标，画个绿边黑框防崩溃
            img = Image.new('RGB', (64, 64), color=(17, 17, 17))
            draw = ImageDraw.Draw(img)
            draw.rectangle((8, 8, 56, 56), outline=(0, 242, 255), width=4)
            return img

    def setup_tray(self):
        """配置托盘右键菜单与双击事件"""
        menu = pystray.Menu(
            # default=True 代表双击托盘图标时触发这个动作
            pystray.MenuItem('🖥️ 唤醒终端', self._tray_show, default=True),
            pystray.MenuItem('⚙️ 系统设置', self._tray_settings),
            pystray.MenuItem('❌ 彻底拔管 (退出)', self._tray_exit)
        )
        self.tray_icon = pystray.Icon("ArchitectTerminal", self.create_tray_icon(), "Starry Sky(运行中)", menu)
        # 必须把托盘扔到后台线程去跑，否则会和 Tkinter 死锁
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def hide_to_tray(self):
        """点击右上角 ✕ 时调用：彻底隐藏主窗口"""
        # 如果是猫咪状态，先还原，防止出现渲染 BUG
        if self.is_collapsed:
            self.restore_window()
        self.withdraw()

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
        """安全拔管销毁一切进程"""
        self.tray_icon.stop()
        os._exit(0)
    # 👇 把这两个函数加在 __init__ 的下方，和 __init__ 保持相同的缩进级别！

    def fetch_env_data(self):
        """后台静默获取干净的城市名与天气 (过滤恶心坐标)"""
        def task():
            try:
                import requests
                
                # 1. 第一步：精准截获当前 IP 所在的城市名 (返回干净的英文，如 Shanghai)
                ip_info = requests.get("http://ip-api.com/json/", timeout=5).json()
                city = ip_info.get("city", "UNKNOWN").upper() # 转为全大写，更有赛博感
                
                # 2. 第二步：带着城市名去查天气，并只要求返回 图标+温度+湿度
                # 注意这里去掉了 %l，我们自己用拼装的 city
                weather_url = f"https://wttr.in/{city}?format=%c+%t+|+HUM:%h"
                w_resp = requests.get(weather_url, timeout=5) 
                
                if w_resp.status_code == 200:
                    weather_data = w_resp.text.strip()
                    # 组装出终极完美格式：ENV SCAN: SHANGHAI | ⛅️ +22°C | HUM:60%
                    env_text = f"ENV SCAN: {city} | {weather_data}"
                else:
                    env_text = f"ENV SCAN: {city} | SENSOR OFFLINE"
                    
            except Exception as e:
                env_text = "ENV SCAN: CONNECTION LOST"
            
            # 回到主线程安全地更新 UI
            self.after(0, lambda: self.update_env_ui(env_text))
            
        # 开启守护线程
        threading.Thread(target=task, daemon=True).start()
    def update_env_ui(self, text):
        """主线程更新天气标签，并同步当前模式颜色"""
        if hasattr(self, 'lbl_env') and self.lbl_env.winfo_exists():
            self.lbl_env.configure(text=text)
            # 根据当前模式变色（蓝/红）
            color = "#00f2ff" if self.mode == "STUDY" else "#ef4444"
            self.lbl_env.configure(text_color=color)

    # 👆 ======================================================== 👆
    # --- ⚡ 注册表注入引擎 (开机自启) ---
    def inject_to_registry(self):
        try:
            if getattr(sys, 'frozen', False): app_path = sys.executable
            else: app_path = os.path.abspath(__file__)
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            winreg.SetValueEx(key, "ArchitectTerminal", 0, winreg.REG_SZ, f'"{app_path}"')
            winreg.CloseKey(key)
        except Exception as e: print(f"自启注入失败: {e}")
    # --- 🌐 云端金句获取引擎 (方案 B: Hitokoto API) ---
    # --- 🔄 手动触发灵感刷新 ---
    def refresh_quote(self):
        # 瞬间给出一个视觉反馈，告诉用户系统正在运转
        self.lbl_quote.configure(text="[ 正在接入思维矩阵，获取新坐标... ]")
        # 开启一条全新的隐形后台线程去拉取数据，绝对不卡主界面！
        threading.Thread(target=self.fetch_daily_quote, daemon=True).start()

    def fetch_daily_quote(self):
        try:
            # 调用 Hitokoto (一言) 极客/哲学类接口
            response = requests.get("https://v1.hitokoto.cn/?c=k&c=d&c=i", timeout=5)
            if response.status_code == 200:
                data = response.json()
                quote = data.get("hitokoto", "Logic is the soul of every agent.")
                
                # 智能提取作者或来源
                author = data.get("from_who")
                if not author:
                    author = data.get("from", "System")
                
                # 极简排版 (去除了引号装饰)
                final_text = f"{quote} —— {author}"
                
                # 安全地在主线程更新 UI
                self.after(0, lambda: self.lbl_quote.configure(text=final_text))
                
                # 缓存到本地，作为断网时的“防弹装甲”
                with open(os.path.join(APP_DIR, "quotes.txt"), "w", encoding="utf-8") as f:
                    f.write(final_text)
        except Exception as e:
            # 触发断网回退机制：读取昨天的缓存，如果连缓存都没有，就用保底名言
            fallback_text = "The quieter you become, the more you are able to hear."
            try:
                with open(os.path.join(APP_DIR, "quotes.txt"), "r", encoding="utf-8") as f:
                    fallback_text = f.read().strip() or fallback_text
            except:
                pass
            self.after(0, lambda: self.lbl_quote.configure(text=fallback_text))
    # --- 快捷启动与工具 ---
    def launch_music(self):
        try: os.startfile(NETEASE_MUSIC_PATH)
        except: pass

    def launch_wegame(self):
        try: os.startfile(WEGAME_PATH)
        except: pass

    def clean_memory(self):
        """🚀 灭霸级内存释放引擎：精准猎杀高耗能进程"""
        # 🔪 升级版猎杀名单 (涵盖高耗能浏览器、开发工具、办公软件)
        target_list = [
            # 浏览器家族 (最吃内存的怪物)
            'chrome.exe', 'msedge.exe', 'firefox.exe', 'safari.exe', '360se.exe', 'sogouexplorer.exe',
            # 开发与设计工具 (架构师专属)
            'code.exe', 'idea64.exe', 'pycharm64.exe', 'java.exe', 'node.exe', 'navicat.exe', 'postman.exe',
            # 办公与通讯软件
            'wps.exe', 'winword.exe', 'excel.exe', 'powerpnt.exe', 'bilibili.exe', 'wechat.exe', 'qq.exe', 'dingtalk.exe'
        ]
        
        freed_mb = 0
        killed_count = 0
        
        # 扫描系统所有进程
        for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
            try:
                p_name = proc.info['name']
                if p_name and p_name.lower() in target_list:
                    # ⚠️ 安全锁：绝对不要杀掉程序自己 (防止你调试时叫 python.exe)
                    if proc.pid == os.getpid():
                        continue
                    
                    # 累加即将释放的内存
                    freed_mb += proc.info['memory_info'].rss / (1024 * 1024)
                    
                    # 从温柔的 terminate 升级为暴力的 kill，系统内核强制终止，绝不拖泥带水
                    proc.kill() 
                    killed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                # 遇到权限不够的系统级同名进程，优雅跳过
                continue
        
        # ⚡ UX 视觉冲击反馈
        if freed_mb > 0:
            # 爆出金色的释放数字
            self.lbl_mode_txt.configure(text=f"-{int(freed_mb)}MB!", font=("Impact", 16), text_color="#facc15")
            print(f"🧹 猎杀完毕！共清理 {killed_count} 个进程，瞬间释放 {int(freed_mb)} MB 内存。")
        else:
            self.lbl_mode_txt.configure(text="Clean!", font=("Impact", 16), text_color="#10b981")
        
        # 2秒后，状态指示器自动冷却，恢复成暴躁的战斗红标志
        self.after(2000, lambda: self.lbl_mode_txt.configure(text="GAME", font=("Impact", 20), text_color="#ef4444"))

    def switch_mode(self):
        """核心协议：物理级重构界面主题，修复组件渲染坍塌"""
        # 1. 切换内部状态
        if self.mode == "STUDY":
            self.mode = "GAME"
        else:
            self.mode = "STUDY"
        
        # 2. 清除所有常规的主界面组件 (让容器彻底干净)
        for w in self.inner_frame.winfo_children():
            w.pack_forget()

        # 3. 🚀 仅恢复顶部栏的“容器”，绝对不要去碰它内部的子按钮！
        self.top_row.pack(side="top", fill="x", padx=10, pady=(8, 2))

        # 4. 如果之前有因为最小化产生的猫咪状态，直接解除
        if getattr(self, "is_collapsed", False):
            self.restore_window()

        # 5. 调用核心重建引擎
        if self.mode == "STUDY":
            self._rebuild_study_interface()
        elif self.mode == "GAME":
            self._rebuild_gaming_interface()


    # ==========================================
    # 🔴 战斗终端：游戏主题重建引擎 (Thematic Redesign)
    # ==========================================
    def _rebuild_gaming_interface(self):
        """激进大改：暴躁战斗红，遵守底部优先渲染法则"""
        # 0. 强行修改主悬浮窗底色和标题文字颜色
        try:
            self.configure(fg_color="#0a0a0c") 
            self.inner_frame.configure(fg_color="#0a0a0c")
            self.lbl_mode_txt.configure(text="GAME", text_color="#ef4444")
            self.lbl_time.configure(text_color="#ef4444")
            self.current_eye_color = "#ef4444"
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
    def _rebuild_study_interface(self):
        """宁静大改：赛博禅修蓝，恢复经典的金句与极简模式"""
        # 0. 强行恢复经典颜色
        try:
            self.configure(fg_color="#111111")
            self.inner_frame.configure(fg_color="#111111")
            self.lbl_mode_txt.configure(text="STUDY", text_color="#00f2ff")
            self.lbl_time.configure(text_color="#00f2ff")
            self.current_eye_color = "#00f2ff"
        except Exception: pass

        # 1. 优先 Pack 底部逃生舱
        self.bot_row.pack(side="bottom", fill="x", padx=10, pady=(2, 5))
        
        # 隐藏游戏模式专属按钮
        if hasattr(self, 'btn_clean'): self.btn_clean.pack_forget()
        if hasattr(self, 'btn_wegame'): self.btn_wegame.pack_forget()
        
        # 恢复学习模式的四大金刚
        self.btn_switch.pack(side="left")
        self.music_container.pack(side="right", padx=(10, 5))
        self.btn_data.pack(side="right", padx=1)
        self.btn_note.pack(side="right", padx=1)

        # 2. 恢复底部天气雷达
        if hasattr(self, 'lbl_env'): self.lbl_env.pack(side="bottom", pady=(0, 2))

        # 3. 🚀 核心修复：把每日金句请回来！铺满中间剩余的全部空间
        if hasattr(self, 'lbl_quote'): 
            self.lbl_quote.pack(side="top", expand=True, fill="both", pady=(2, 2))
            
        # 4. 🔪 彻底物理销毁那个带有“DEEP FOCUS TOOLS”的啰嗦列表
        if hasattr(self, 'mode_frame') and self.mode_frame.winfo_exists():
            self.mode_frame.destroy()
    def show_note_menu(self):
        if self.menu and self.menu.winfo_exists(): return
        self.menu = ctk.CTkToplevel(self)
        self.menu.geometry("160x130")
        self.menu.overrideredirect(True)
        self.menu.attributes("-topmost", True)
        self.menu.configure(fg_color="#18181b")
        
        x, y = self.winfo_rootx() + 40, self.winfo_rooty() + 85
        self.menu.geometry(f"+{x}+{y}")
        
        ctk.CTkButton(self.menu, text="×", width=20, height=20, fg_color="transparent", text_color="#ef4444", 
                      command=self.menu.destroy).pack(anchor="ne")

        for opt in ["代码架构知识", "大数据模型使用", "随笔"]:
            ctk.CTkButton(self.menu, text=opt, fg_color="transparent", hover_color="#27272a", font=("Microsoft YaHei", 12), anchor="w",
                          command=lambda c=opt: [NoteWindow(self, c), self.menu.destroy()]).pack(fill="x", padx=5, pady=2)

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

        self.current_eye_color = "#00f2ff" if self.mode == "STUDY" else "#ef4444"
        head_fill = "#18181b"
        border = "#3f3f46"
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

        self.eye_open_h = 10
        self.eye_closed_h = 2
        self.eye_base_y = 24
        self.eye_l_id = self.cat_canvas.create_oval(21, self.eye_base_y, 31, self.eye_base_y + self.eye_open_h, fill=self.current_eye_color, outline="", tags=("eye_l",))
        self.eye_r_id = self.cat_canvas.create_oval(49, self.eye_base_y, 59, self.eye_base_y + self.eye_open_h, fill=self.current_eye_color, outline="", tags=("eye_r",))

        # 🚀 调用正规的类方法
        self.blink_timer = self.after(3000, self._do_cat_blink)
        
        for w in [self.cat_container, self.cat_canvas]:
            w.bind("<Double-Button-1>", self.restore_window)
            w.bind("<ButtonPress-1>", self.start_move)
            w.bind("<B1-Motion>", self.do_move)

    def restore_window(self, event=None):
        if not self.is_collapsed: return

        if hasattr(self, 'blink_timer') and self.blink_timer:
            try:
                self.after_cancel(self.blink_timer)
                self.blink_timer = None
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
        if hasattr(self, 'bot_row'): self.bot_row.pack(side="bottom", fill="x", padx=10, pady=(2, 5))
        if hasattr(self, 'lbl_env'): self.lbl_env.pack(side="bottom", pady=(0, 2))
        if hasattr(self, 'lbl_quote'): self.lbl_quote.pack(side="top", expand=True, fill="both", pady=(2, 2))

        self.is_collapsed = False
        self.after(0, self._apply_windows_round_corners)


    def start_move(self, event):
        self.x = event.x; self.y = event.y
    def do_move(self, event):
        self.geometry(f"+{self.winfo_x() + (event.x - self.x)}+{self.winfo_y() + (event.y - self.y)}")
    def _do_cat_blink(self):
        """🚀 核心修复：独立的眨眼引擎，免疫内存回收"""
        if not self.is_collapsed: 
            return
            
        if hasattr(self, "cat_canvas") and self.cat_canvas.winfo_exists():
            try:
                # 闭眼
                self._set_canvas_eyes(opened=False)
                # 150ms 后睁眼
                self.after(150, lambda: self._set_canvas_eyes(opened=True))
                # 再次安排下一次随机眨眼
                self.blink_timer = self.after(random.randint(3000, 7000), self._do_cat_blink)
            except Exception:
                pass
    def _set_canvas_eyes(self, opened: bool):
        try:
            if not (hasattr(self, "cat_canvas") and self.cat_canvas.winfo_exists()):
                return
            h = self.eye_open_h if opened else self.eye_closed_h
            # 固定 top=self.eye_base_y，调整 bottom 来模拟眨眼
            y = getattr(self, "eye_base_y", 24)
            self.cat_canvas.coords(self.eye_l_id, 21, y, 31, y + h)
            self.cat_canvas.coords(self.eye_r_id, 49, y, 59, y + h)
        except Exception:
            pass


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
        """主线程定时监控：替代 monitor_loop 的后台线程版本。"""
        if not getattr(self, "running", False):
            return

        try:
            # 配置未就绪则延迟
            if not hasattr(self, "study_procs") or not self.study_procs:
                self.after(1000, self._monitor_tick)
                return

            user32 = ctypes.windll.user32
            self._monitor_loop_counter = int(getattr(self, "_monitor_loop_counter", 0)) + 1
            self.db["last_heartbeat"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 抓取当前电脑上所有正在运行的进程名 (转小写)
            active_procs = []
            for p in psutil.process_iter(['name']):
                try:
                    if p.info['name']:
                        active_procs.append(p.info['name'].lower())
                except Exception:
                    continue

            # 1) 🎵 听歌统计
            music_active = False
            for m in getattr(self, "music_procs", []) or []:
                if m in active_procs:
                    music_active = True
                    break
            self.music_active = music_active
            if music_active:
                self.db[self.today]["music_total"] += 1

            # 2) 💻 学习统计
            if self.mode == "STUDY":
                is_study = False
                for s in getattr(self, "study_procs", []) or []:
                    if s in active_procs:
                        is_study = True
                        if s not in self.db[self.today]["study_apps"]:
                            self.db[self.today]["study_apps"][s] = 0
                        self.db[self.today]["study_apps"][s] += 1

                if not is_study:
                    hwnd = user32.GetForegroundWindow()
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buff, length + 1)
                        title = buff.value.lower()
                        if "visual studio code" in title or "vscode" in title:
                            self.db[self.today]["study_apps"]["vscode"] = self.db[self.today]["study_apps"].get("vscode", 0) + 1
                            is_study = True
                        elif "chrome" in title or "bilibili" in title or "哔哩哔哩" in title:
                            is_study = True

                if is_study:
                    self.db[self.today]["study_total"] += 1
                    if self.study_break_sec > 0 and (self.db[self.today]["study_total"] % self.study_break_sec == 0):
                        self.trigger_study_break()

            # 3) 🎮 游戏统计
            elif self.mode == "GAME":
                game_active = False
                for game in getattr(self, "game_procs", []) or []:
                    if game in active_procs:
                        game_active = True
                        if game not in self.db[self.today]["game_apps"]:
                            self.db[self.today]["game_apps"][game] = 0
                        self.db[self.today]["game_apps"][game] += 1
                        break

                if game_active:
                    self.db[self.today]["game_total"] += 1
                    if self.game_limit_sec > 0 and self.db[self.today]["game_total"] >= self.game_limit_sec:
                        if not self.warning_active and (time.time() - self.last_warning_time > 60):
                            self.trigger_game_warning()

            # 4) 💾 自动存盘 (每 10 秒)
            if self._monitor_loop_counter % 10 == 0:
                save_data(self.db)
        except Exception as e:
            print(f"监测异常: {e}")
        finally:
            self.after(1000, self._monitor_tick)
    def update_ui(self):
        if not self.is_collapsed:
            # 1. 更新主专注/游戏时间
            sec = self.db[self.today]["study_total"] if self.mode == "STUDY" else self.db[self.today]["game_total"]
            self.lbl_time.configure(text=f"{sec//3600:02d}:{(sec%3600)//60:02d}:{sec%60:02d}")
            
            # 2. 更新独立的音乐时长标签（只在“正在听歌”时显示，且用极简 3h/45m）
            m_sec = self.db[self.today].get("music_total", 0)
            if hasattr(self, 'lbl_music_time'):
                if getattr(self, "music_active", False) and m_sec > 0:
                    if m_sec >= 3600:
                        self.lbl_music_time.configure(text=f"{m_sec//3600}h")
                    else:
                        self.lbl_music_time.configure(text=f"{m_sec//60}m")
                else:
                    self.lbl_music_time.configure(text="")
                
        self.after(1000, self.update_ui)

    # --- 📊 日历与全景数据矩阵 ---
    def show_data_module(self):
        """双核数据中枢：融合 7 天全息矩阵、软件耗时追踪与历史月历"""
        if hasattr(self, 'data_win') and self.data_win.winfo_exists():
            self.data_win.focus()
            return

        # 1. 初始化扩容后的数据终端
        self.data_win = ctk.CTkToplevel(self)
        self.data_win.title("SYSTEM ANALYTICS & ARCHIVE")
        self.data_win.geometry("750x620")  # 扩容以容纳所有数据
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
        
        cal_right = ctk.CTkFrame(tab_cal, fg_color="#18181b", width=220, corner_radius=10)
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
        win = ctk.CTkToplevel(self)
        win.geometry("500x280")
        win.attributes("-topmost", True)
        win.overrideredirect(True)
        win.configure(fg_color="#18181b")
        win.geometry(f"+{(self.winfo_screenwidth()-500)//2}+{(self.winfo_screenheight()-280)//2}")
        
        ctk.CTkLabel(win, text="☕ 架构师休息站", font=("Microsoft YaHei", 24, "bold"), text_color="#10b981").pack(pady=30)
        text = "你离那个‘有价值而发光’的自己又近了一步。\n两个小时的高频算力已经达成。\n把眼睛从代码上移开，去听首《珊瑚海》或者《爱错》。\n真正的成长，是在平静中积蓄力量。"
        ctk.CTkLabel(win, text=text, font=("Microsoft YaHei", 13), text_color="#d1d5db", justify="center").pack(pady=10)
        ctk.CTkButton(win, text="听会歌，休息一下", command=win.destroy, fg_color="#10b981", hover_color="#059669").pack(pady=20)

    def trigger_game_warning(self):
        """游戏提醒窗：更克制的置顶提示 + 联网鸡汤"""
        if self.warning_active: return # 状态锁检查
        self.warning_active = True     # 立即上锁
            
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

        soup_lbl = ctk.CTkLabel(
            body,
            text="正在从网络获取鸡汤...",
            font=("Microsoft YaHei", 14, "italic"),
            text_color="#a1a1aa",
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
    try:
        app = FloatingTracker()
        app.mainloop()
    except Exception:
        err = traceback.format_exc()
        try:
            ctypes.windll.user32.MessageBoxW(0, f"程序启动失败（异常信息如下）：\n\n{err}", "ArchitectTerminal Crash", 0x10)
        except Exception:
            pass
        raise