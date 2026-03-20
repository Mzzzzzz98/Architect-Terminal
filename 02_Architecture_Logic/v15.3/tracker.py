import os
import sys
import json
import ctypes
import time
import psutil
import winreg
import calendar
import requests
import windnd
from datetime import datetime, timedelta
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, colorchooser, font
import threading
import glob
import random
from PIL import Image, ImageTk, ImageGrab
import traceback

# ==========================================
# ⚙️ 全局配置与路径初始化 (V16.0 路径安全升级)
# ==========================================
APP_NAME = "ArchitectTerminal"
# 获取 Windows 标准应用数据路径 (AppData/Roaming)
# 这样即使安装在 C 盘，读写数据也永远拥有合法权限
APPDATA_PATH = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_NAME)
# ==========================================
# ⚙️ 核心路径矩阵 (V16.5 绝对防御版)
# ==========================================
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

# 👇 新增：系统配置文件路径与读写引擎
CONFIG_FILE = os.path.join(APP_DIR, "system_config.json")

def load_sys_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {"is_setup": False, "study": {}, "game": {}, "music": {}}

def atomic_save(file_path, data):
    """原子化写入：增加自动补全目录功能"""
    # 🚀 核心补丁：确保文件夹存在，否则保存必崩
    folder = os.path.dirname(file_path)
    if not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)

    temp_file = file_path + ".tmp"
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        
        if os.path.exists(file_path):
            os.replace(temp_file, file_path)
        else:
            os.rename(temp_file, file_path)
    except Exception as e:
        if os.path.exists(temp_file): os.remove(temp_file)
        print(f"数据固化失败: {e}")

# 重新链接函数
def save_data(data): atomic_save(DATA_FILE, data)
def save_sys_config(cfg): atomic_save(CONFIG_FILE, cfg)


# 自动构建生态目录 (加入异常捕获)
for d in [APP_DIR, NOTES_DIR, IMAGE_DIR]:
    try:
        os.makedirs(d, exist_ok=True)
    except PermissionError:
        ctypes.windll.user32.MessageBoxW(0, f"权限受阻！\n请不要在系统保护文件夹运行。\n报错路径: {d}", "系统权限错误", 0x10)
        sys.exit(1)

# 软件快捷启动路径
NETEASE_MUSIC_PATH = r"E:\CloudMusic\cloudmusic.exe"
WEGAME_PATH = r"F:\Program Files (x86)\WeGame\wegame.exe"

# 进程监控特征码 (全小写)
MUSIC_PROCESS_NAME = "cloudmusic.exe"
GAME_NAMES = ["leagueclientuxrender.exe", "wegame.exe", "deltaforceclient-win64-shipping.exe"]
STUDIO_TOOLS = ["cherrystudio.exe", "chatbox.exe", "anythingllm.exe"]
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

def get_diary_reflection():
    try:
        files = glob.glob("Processed_Diaries/*.md")
        if not files: return "当下的逃避，会透支明天的念头通达。"
        with open(random.choice(files), 'r', encoding='utf-8') as f:
            content = [l.strip() for l in f.readlines() if len(l.strip()) > 15]
        return f"“{random.choice(content)[:80]}...”" if content else "回归现实需要一个承诺。"
    except: return "回归现实需要一个承诺。"

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
        self.title(f"ARCHIVE TERMINAL - {category_name}")
        
        # 1. 初始化时间系统与兼容旧数据
        today = datetime.now()
        self.current_date = today.strftime("%Y-%m-%d")
        self.cal_year = today.year
        self.cal_month = today.month
        self.image_refs = [] 
        
        # 自动迁移旧版本笔记到今天
        old_path = os.path.join(NOTES_DIR, f"{self.category}.txt")
        new_path = os.path.join(NOTES_DIR, f"{self.category}_{self.current_date}.txt")
        if os.path.exists(old_path) and not os.path.exists(new_path):
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
        self.load_content(self.current_date)

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
                    path = os.path.join(NOTES_DIR, f"{self.category}_{d_str}.txt")
                    has_note = os.path.exists(path) and os.path.getsize(path) > 0

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

    def switch_date(self, date_str):
        self.save_content() # 切换前自动保存
        self.current_date = date_str
        self.build_calendar() # 刷新日历高亮状态
        self.lbl_date_title.configure(text=f"DATE: {self.current_date}")
        self.load_content(date_str)

    # --- 右侧：富文本编辑模块 ---
    # --- 右侧：富文本编辑模块 (V2 沉浸式美学升级) ---
    def build_editor(self):
        # 1. 顶层状态与同步栏 (增加底部边框分割线)
        self.top_bar = ctk.CTkFrame(self.right_panel, fg_color="#18181b", height=60, corner_radius=0, 
                                    border_width=1, border_color="#27272a")
        self.top_bar.pack(fill="x", side="top")
        
        # 日期标题：使用更优雅的排版
        self.lbl_date_title = ctk.CTkLabel(self.top_bar, text=f"DATE // {self.current_date}", 
                                           font=("Consolas", 18, "bold"), text_color="#00f2ff")
        self.lbl_date_title.pack(side="left", padx=30, pady=15)
        
        self.btn_save = ctk.CTkButton(self.top_bar, text="💾 SYNC MATRIX", width=130, height=34, 
                                      font=("Consolas", 12, "bold"), fg_color="#10b981", hover_color="#059669", 
                                      corner_radius=6, command=self.save_content)
        self.btn_save.pack(side="right", padx=30)

        # 2. 极简富文本工具栏 (调整间距与按钮质感)
        self.format_bar = ctk.CTkFrame(self.right_panel, fg_color="#111111", height=45, corner_radius=0,
                                       border_width=1, border_color="#27272a")
        self.format_bar.pack(fill="x")
        
        self.font_family = ctk.CTkOptionMenu(self.format_bar, values=["Microsoft YaHei", "Consolas", "SimHei", "KaiTi"], 
                                             width=140, height=28, fg_color="#18181b", button_color="#27272a", 
                                             button_hover_color="#3f3f46", font=("Consolas", 12), command=self.apply_font_family)
        self.font_family.pack(side="left", padx=(30, 10), pady=8)
        
        self.font_size = ctk.CTkOptionMenu(self.format_bar, values=["12", "14", "16", "18", "20", "24", "32"], 
                                           width=80, height=28, fg_color="#18181b", button_color="#27272a", 
                                           button_hover_color="#3f3f46", font=("Consolas", 12), command=self.apply_font_size)
        self.font_size.set("14")
        self.font_size.pack(side="left", padx=(0, 15))
        
        # 样式按钮组
        btn_kwargs = {"width": 36, "height": 28, "fg_color": "#18181b", "hover_color": "#27272a", "corner_radius": 4}
        ctk.CTkButton(self.format_bar, text="B", font=("Arial", 14, "bold"), command=self.apply_bold, **btn_kwargs).pack(side="left", padx=4)
        ctk.CTkButton(self.format_bar, text="I", font=("Arial", 14, "italic"), command=self.apply_italic, **btn_kwargs).pack(side="left", padx=4)
        ctk.CTkButton(self.format_bar, text="🎨", font=("Arial", 14), command=self.apply_color, **btn_kwargs).pack(side="left", padx=4)

        # 3. 核心文本区 (引入呼吸感与赛博定制色)
        self.text_frame = ctk.CTkFrame(self.right_panel, fg_color="#09090b", corner_radius=0)
        self.text_frame.pack(fill="both", expand=True)

        # 【升级】使用 CTkScrollbar 替代丑陋的 Windows 默认滚动条
        self.scrollbar = ctk.CTkScrollbar(self.text_frame, width=12, fg_color="transparent", 
                                          button_color="#27272a", button_hover_color="#3f3f46")
        self.scrollbar.pack(side="right", fill="y", padx=(0, 2), pady=2)

        # 【核心美化】增加行间距 (spacing)、增加四周留白 (padx/pady)、定制选中高亮色
        self.text_area = tk.Text(self.text_frame, bg="#09090b", fg="#e4e4e7", 
                                 insertbackground="#10b981", # 光标颜色：薄荷绿
                                 selectbackground="#059669", selectforeground="#ffffff", # 选中文字的背景色
                                 font=("Microsoft YaHei", 14), 
                                 padx=40, pady=35, # 超大内部呼吸留白
                                 borderwidth=0, highlightthickness=0,
                                 spacing1=10, spacing2=6, spacing3=10, # 段落与行间距优化
                                 yscrollcommand=self.scrollbar.set, wrap="word")
        self.text_area.pack(fill="both", expand=True)
        self.scrollbar.configure(command=self.text_area.yview)
        
        # 绑定快捷键
        self.text_area.bind('<Control-v>', self.paste_image)

        # 核心文本区
        self.text_frame = ctk.CTkFrame(self.right_panel, fg_color="#09090b", corner_radius=0)
        self.text_frame.pack(fill="both", expand=True, padx=2, pady=2)

        self.scrollbar = tk.Scrollbar(self.text_frame, bg="#111111", borderwidth=0)
        self.scrollbar.pack(side="right", fill="y")

        self.text_area = tk.Text(self.text_frame, bg="#09090b", fg="#e4e4e7", insertbackground="#10b981", 
                                 font=("Microsoft YaHei", 14), padx=30, pady=25, borderwidth=0, highlightthickness=0,
                                 yscrollcommand=self.scrollbar.set, wrap="word")
        self.text_area.pack(fill="both", expand=True)
        self.scrollbar.config(command=self.text_area.yview)
        
        self.text_area.bind('<Control-v>', self.paste_image)

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

    # --- IO 数据读写 (支持按日规整) ---
    def save_content(self):
        content = self.text_area.get("1.0", tk.END).strip()
        path = os.path.join(NOTES_DIR, f"{self.category}_{self.current_date}.txt")
        
        if content:
            with open(path, "w", encoding="utf-8") as f: f.write(content)
        else:
            if os.path.exists(path): os.remove(path) # 内容清空则删除文件，保持整洁
            
        self.btn_save.configure(text="✅ SYNCED", fg_color="#3b82f6")
        self.after(1500, lambda: self.btn_save.configure(text="💾 SYNC MATRIX", fg_color="#10b981"))
        self.build_calendar() # 刷新日历上的蓝点指示器

    def load_content(self, date_str):
        self.text_area.delete("1.0", tk.END)
        self.image_refs.clear()
        path = os.path.join(NOTES_DIR, f"{self.category}_{date_str}.txt")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f: 
                self.text_area.insert("1.0", f.read())
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

        # 👇 核心黑科技：向 Windows 底层注入全局拖拽监听钩子
        try:
            windnd.hook_dropfiles(self, func=self.handle_drop)
        except Exception as e:
            print(f"拖拽引擎注入失败: {e}")

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
        }

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
        }

        self.list_frames = {}
        for key in ["study", "game", "music"]:
            self._build_tab(key)

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
            save_sys_config(self.cfg)
            if callable(self._on_save):
                self._on_save(self.cfg)
            self.destroy()
        except Exception as e:
            ctypes.windll.user32.MessageBoxW(0, f"保存设置失败：\n{e}", "Settings Save Failed", 0x10)

# ==========================================
# 🚀 核心控制中枢 (极限悬浮窗)
# ==========================================
class FloatingTracker(ctk.CTk):
    def __init__(self):
        super().__init__()
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
        self.overrideredirect(True)      
        # 关键修复：`overrideredirect(True)` + `-toolwindow` 在部分 Windows 环境下会导致窗口“存在但不可见/不可切换”
        self.attributes("-topmost", True, "-alpha", 0.92)
        ctk.set_appearance_mode("dark")

        # 配置完成，主窗口登场（在无边框/置顶属性设置之后）
        self.deiconify()

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
        self.game_limit = int(2.5 * 3600)  
        self.quote_file = os.path.join(APP_DIR, "quotes.txt")
        self.current_quote = "Logic is the soul of every agent." # 默认金句

        # 主框架
        self.main_frame = ctk.CTkFrame(self, corner_radius=12, fg_color="#111111", border_width=1, border_color="#27272a")
        self.main_frame.pack(fill="both", expand=True, padx=1, pady=1)
        
        # --- 第一行：状态指示 ---
        self.top_row = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.top_row.pack(side="top", fill="x", padx=10, pady=(8, 2))
        
        # 学习模式初始色应为赛博蓝（避免启动时“Study 变绿”）
        self.lbl_mode_txt = ctk.CTkLabel(self.top_row, text="Study", font=("Impact", 20), text_color="#00f2ff")
        self.lbl_mode_txt.pack(side="left")

        self.lbl_time = ctk.CTkLabel(self.top_row, text="00:00:00", font=("Consolas", 22, "bold"), text_color="#00f2ff")
        self.lbl_time.pack(side="left", padx=15)
        # 👇 修复：纠正父级容器为 main_frame，收缩折行宽度至 240，修改引力为居中填充
        self.lbl_quote = ctk.CTkLabel(self.main_frame, text="正在同步思维矩阵...", 
                                      font=("Microsoft YaHei", 12, "italic"), text_color="#a1a1aa", 
                                      wraplength=240, cursor="hand2") 
        self.lbl_quote.pack(side="top", expand=True, fill="both", pady=(2, 2))
        
        # 绑定鼠标左键点击事件 (<Button-1>)
        self.lbl_quote.bind("<Button-1>", lambda e: self.refresh_quote())
        
        # 绑定鼠标左键点击事件 (<Button-1>)
        self.lbl_quote.bind("<Button-1>", lambda e: self.refresh_quote())
# 👇 ========= 在这里插入 ENV 标签 ========= 👇
        self.lbl_env = ctk.CTkLabel(self.main_frame, text="ENV SCAN: INITIALIZING SYSTEM...", 
                                    font=("Consolas", 10, "bold"), text_color="#00f2ff")
        self.lbl_env.pack(side="bottom", pady=(0, 2))
        # 👆 ===================================== 👆
        # 在 __init__ 的最后一行加上调用
        self.fetch_daily_quote()

        self.btn_min = ctk.CTkButton(self.top_row, text="—", width=20, height=20, fg_color="transparent", 
                                     hover_color="#27272a", text_color="#a1a1aa", font=("Consolas", 14, "bold"), command=self.toggle_collapse)
        self.btn_min.pack(side="right")
        ToolTip(self.btn_min, "smaller")

        # ⚙ 设置按钮：同音乐图标的字体/尺寸风格
        self.btn_settings = ctk.CTkButton(
            self.top_row,
            text="⚙",
            width=20,
            height=20,
            fg_color="transparent",
            hover_color="#27272a",
            text_color="#a1a1aa",
            font=("Segoe UI Emoji", 12),
            command=self.open_settings,
        )
        self.btn_settings.pack(side="right", padx=(0, 6))
        ToolTip(self.btn_settings, "Settings")

        # --- 第二行：快捷工具栏 ---
        self.bot_row = ctk.CTkFrame(self.main_frame, fg_color="transparent")
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
        self.main_frame.bind("<ButtonPress-1>", self.start_move)
        self.main_frame.bind("<B1-Motion>", self.do_move)
        
        self.warning_active = False         
        self.last_warning_time = 0  # 建议顺便加上这个，用于留出 60 秒关闭时间
        # 线程启动
        self.running = True
        # 核心监控线程（原先未启动会导致学习/游戏/音乐时长都不增长）
        threading.Thread(target=self.monitor_loop, daemon=True).start()
        threading.Thread(target=self.fetch_daily_quote, daemon=True).start()
        self.update_ui()
        self.after(1500, self.check_sleep_log) 
        # 👇 新增这一行，启动天气定位引擎 👇
        self.fetch_env_data()

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

        self.settings_win = SettingsPanel(self, self.sys_config, on_save=on_save)
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
        target_list = ['chrome.exe', 'msedge.exe', 'bilibili.exe', 'wechat.exe', 'qq.exe', 'wps.exe', 'winword.exe', 'excel.exe']
        freed_mb = 0
        for proc in psutil.process_iter(['name', 'memory_info']):
            try:
                if proc.info['name'] and proc.info['name'].lower() in target_list:
                    freed_mb += proc.info['memory_info'].rss / (1024 * 1024)
                    proc.terminate() 
            except: pass
        
        if freed_mb > 0:
            self.lbl_mode_txt.configure(text=f"-{int(freed_mb)}MB!", font=("Impact", 16), text_color="#facc15")
        else:
            self.lbl_mode_txt.configure(text="Clean!", font=("Impact", 16), text_color="#10b981")
        self.after(2000, lambda: self.lbl_mode_txt.configure(text="Game", font=("Impact", 20), text_color="#ef4444"))   

    def switch_mode(self):
        """模式切换：增加对眼睛颜色的即时控制与专属按钮显示"""
        if self.mode == "STUDY":
            self.mode = "GAME"
            accent_color = "#ef4444" # 警告红
            self.lbl_mode_txt.configure(text="Game", font=("Impact", 20), text_color=accent_color)
            self.lbl_time.configure(text_color=accent_color)
            
            # 👇 核心修复：切到游戏模式时，显示清理内存按钮
            if hasattr(self, 'btn_clean'):
                self.btn_clean.pack(side="left", padx=5)
        else:
            self.mode = "STUDY"
            accent_color = "#00f2ff" # 赛博蓝
            self.lbl_mode_txt.configure(text="Study", font=("Impact", 20), text_color=accent_color)
            self.lbl_time.configure(text_color=accent_color)
            
            # 👇 核心修复：切回学习模式时，隐藏清理内存按钮
            if hasattr(self, 'btn_clean'):
                self.btn_clean.pack_forget()

        # 如果已经最小化，瞬间改变眼睛颜色
        if self.is_collapsed and hasattr(self, 'eye_l') and self.eye_l.winfo_exists():
            self.eye_l.configure(fg_color=accent_color)
            self.eye_r.configure(fg_color=accent_color)
            self.current_eye_color = accent_color
        #让天气标签也同步变色   
        if hasattr(self, 'lbl_env') and self.lbl_env.winfo_exists():
            self.lbl_env.configure(text_color=accent_color)

        # 注意：`btn_note` 在 __init__ 里已创建并 pack；这里不要重复创建/pack，否则会越点越多
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
        """最小化：进化为极简赛博核心 (无耳、圆润、防卡死)"""
        if self.is_collapsed: return 
        
        # 1. 立即强制停止计时器，确保主线程洁净
        if hasattr(self, 'blink_timer') and self.blink_timer:
            try: self.after_cancel(self.blink_timer)
            except: pass
            self.blink_timer = None

        self.is_collapsed = True
        self.old_geom = self.geometry()
        
        # 2. 隐藏主 UI 组件
        self.top_row.pack_forget()
        if hasattr(self, 'mid_row'): self.mid_row.pack_forget()
        self.bot_row.pack_forget()
        if hasattr(self, 'lbl_quote'): self.lbl_quote.pack_forget()
        if hasattr(self, 'lbl_env'): self.lbl_env.pack_forget()

        # 3. 窗口形态变换 (先改透明属性，再改尺寸)
        # 使用 #000001 作为穿透色，实现真正的无边框圆角
        self.attributes("-transparentcolor", "#000001")
        self.configure(fg_color="#000001")
        self.main_frame.configure(fg_color="#000001", border_width=0)
        self.geometry("80x50") 

        # 4. 构建核心容器
        if hasattr(self, 'cat_container'):
            try: self.cat_container.destroy()
            except: pass
            
        self.cat_container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.cat_container.pack(expand=True, fill="both")

        # 5. 【核心主体】 - 一个圆润的深色底座
        self.eye_orb = ctk.CTkFrame(self.cat_container, 
                                   width=70, height=38, 
                                   fg_color="#18181b", 
                                   corner_radius=19, 
                                   border_width=1, 
                                   border_color="#3f3f46")
        self.eye_orb.place(relx=0.5, rely=0.5, anchor="center")

        # 6. 【核心修复】：将 STUDIO 改为 STUDY，并使用 self.current_eye_color
        self.current_eye_color = "#00f2ff" if self.mode == "STUDY" else "#ef4444"
        
        self.eye_l = ctk.CTkFrame(self.eye_orb, width=11, height=11, corner_radius=6, fg_color=self.current_eye_color)
        self.eye_l.place(relx=0.3, rely=0.5, anchor="center")
        self.eye_r = ctk.CTkFrame(self.eye_orb, width=11, height=11, corner_radius=6, fg_color=self.current_eye_color)
        self.eye_r.place(relx=0.7, rely=0.5, anchor="center")
        # 7. 安全眨眼算法
        def safe_blink():
            if self.is_collapsed and hasattr(self, 'eye_l') and self.eye_l.winfo_exists():
                try:
                    self.eye_l.configure(height=1)
                    self.eye_r.configure(height=1)
                    # 150ms 后恢复睁眼
                    self.after(150, self.safe_open_eyes)
                    # 随机 3-7 秒眨一次
                    self.blink_timer = self.after(random.randint(3000, 7000), safe_blink)
                except: pass

        self.blink_timer = self.after(3000, safe_blink)
        
        # 8. 绑定交互 (双击恢复，拖动移动)
        for w in [self.cat_container, self.eye_orb, self.eye_l, self.eye_r]:
            w.bind("<Double-Button-1>", self.restore_window)
            w.bind("<ButtonPress-1>", self.start_move)
            w.bind("<B1-Motion>", self.do_move)

    def safe_open_eyes(self):
        """眨眼辅助：确保组件存在时才睁眼"""
        if hasattr(self, 'eye_l') and self.eye_l.winfo_exists():
            self.eye_l.configure(height=11)
            self.eye_r.configure(height=11)

    def restore_window(self, event=None):
        """展开窗口：核心步骤是先清理计时器，防止卡死"""
        if not self.is_collapsed: return
        
        # 1. 彻底清理计时器
        if hasattr(self, 'blink_timer') and self.blink_timer:
            try:
                self.after_cancel(self.blink_timer)
                self.blink_timer = None
            except: pass
            
        # 2. 还原透明度属性 (必须在 geometry 改变前执行)
        self.attributes("-transparentcolor", "") 
        self.configure(fg_color="#111111")
        self.main_frame.configure(fg_color="#111111", border_width=1, corner_radius=12)

        # 3. 物理销毁核心容器
        if hasattr(self, 'cat_container'):
            try: self.cat_container.destroy()
            except: pass
            
        # 4. 恢复原始尺寸与组件布局        
            self.geometry(self.old_geom)            
            # 按照“两头向中间”的引力锚点顺序恢复组件
            self.top_row.pack(side="top", fill="x", padx=10, pady=(8, 2))
            
            if hasattr(self, 'bot_row'): 
                self.bot_row.pack(side="bottom", fill="x", padx=10, pady=(2, 5))
                
            if hasattr(self, 'lbl_env'): 
                self.lbl_env.pack(side="bottom", pady=(0, 2))
                
            if hasattr(self, 'lbl_quote'): 
                # expand=True 保证长文本即便溢出也只会自己裁剪，不影响全局
                self.lbl_quote.pack(side="top", expand=True, fill="both", pady=(2, 2))
            
            self.is_collapsed = False


    def start_move(self, event):
        self.x = event.x; self.y = event.y
    def do_move(self, event):
        self.geometry(f"+{self.winfo_x() + (event.x - self.x)}+{self.winfo_y() + (event.y - self.y)}")

    # --- 🧠 算力监控核心引擎 (严格防作弊模式) ---
    def monitor_loop(self):
        """核心监测引擎：加入变量安全锁"""
        user32 = ctypes.windll.user32
        loop_counter = 0
        
        while self.running:
            # 🚀 【核心修复3】：如果配置还没部署好，雷达保持静默，不往下执行
            if not hasattr(self, 'study_procs') or not self.study_procs:
                time.sleep(1)
                continue
                
            try:
                time.sleep(1) 
                loop_counter += 1
                self.db["last_heartbeat"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # 抓取当前电脑上所有正在运行的进程名 (转小写)
                active_procs = []
                for p in psutil.process_iter(['name']):
                    try:
                        if p.info['name']: 
                            active_procs.append(p.info['name'].lower())
                    except: 
                        continue

                # ==========================================
                # 1. 🎵 听歌统计 (读取动态配置的音乐软件)
                # ==========================================
                music_active = False
                for m in self.music_procs:
                    if m in active_procs:
                        music_active = True
                        break
                # 让 UI 可以决定是否显示“🎵 + 时长”
                self.music_active = music_active
                if music_active:
                    self.db[self.today]["music_total"] += 1

                # ==========================================
                # 2. 💻 学习/架构模式统计
                # ==========================================
                if self.mode == "STUDY":
                    is_study = False
                    
                    # 判定 A: 检查你配置的生产力软件是否在后台运行
                    for s in self.study_procs:
                        if s in active_procs:
                            is_study = True
                            # 记录单个软件的使用时长
                            if s not in self.db[self.today]["study_apps"]:
                                self.db[self.today]["study_apps"][s] = 0
                            self.db[self.today]["study_apps"][s] += 1
                    
                    # 判定 B: 如果配置的工具没开，则检查前台活动窗口 (防止用浏览器查资料时漏计时)
                    if not is_study:
                        hwnd = user32.GetForegroundWindow()
                        length = user32.GetWindowTextLengthW(hwnd)
                        if length > 0:
                            buff = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(hwnd, buff, length + 1)
                            title = buff.value.lower()
                            if "visual studio code" in title or "vscode" in title:
                                # 兼容保底机制
                                self.db[self.today]["study_apps"]["vscode"] = self.db[self.today]["study_apps"].get("vscode", 0) + 1
                                is_study = True
                            elif "chrome" in title or "bilibili" in title or "哔哩哔哩" in title:
                                is_study = True
                    
                    # 如果判定在学习，累加总时间
                    if is_study:
                        self.db[self.today]["study_total"] += 1
                        if self.db[self.today]["study_total"] % 7200 == 0: # 每 2 小时提醒
                            self.after(0, self.trigger_study_break)

                # ==========================================
                # 3. 🎮 游戏模式统计
                # ==========================================
                elif self.mode == "GAME":
                    game_active = False
                    
                    # 遍历你动态配置的游戏软件
                    for game in self.game_procs:
                        if game in active_procs:
                            game_active = True
                            # 记录单个游戏的使用时长
                            if game not in self.db[self.today]["game_apps"]: 
                                self.db[self.today]["game_apps"][game] = 0
                            self.db[self.today]["game_apps"][game] += 1
                            break # 找到一个在运行的游戏，就跳出循环
                    
                    # 如果判定在打游戏，累加总时间
                    if game_active:
                        self.db[self.today]["game_total"] += 1
                        if self.db[self.today]["game_total"] >= 9000: # 达到 2.5 小时防沉迷阈值
                            if not self.warning_active and (time.time() - self.last_warning_time > 60):
                                self.after(0, self.trigger_game_warning)

                # ==========================================
                # 4. 💾 自动存盘 (每 10 秒)
                # ==========================================
                if loop_counter % 10 == 0:
                    save_data(self.db)

            except Exception as e:
                print(f"监测异常: {e}")
                continue
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
        """震撼弹窗修复版：修正了执行顺序"""
        if self.warning_active: return # 状态锁检查
        self.warning_active = True     # 立即上锁
            
        # 1. 先创建窗口
        win = ctk.CTkToplevel(self)
        win.attributes("-fullscreen", True, "-topmost", True)
        win.configure(fg_color="#000000") 

        # 2. 定义关闭逻辑
        def on_acknowledge():
            self.warning_active = False      # 解锁
            self.last_warning_time = time.time() # 记录时间开始 60 秒冷却
            win.destroy()

        # 3. 布局 UI 组件
        # 赛博警戒线
        line = ctk.CTkFrame(win, fg_color="#ef4444", height=10, corner_radius=0)
        line.pack(fill="x", pady=(150, 0))

        # 主标题
        ctk.CTkLabel(win, text="SYSTEM OVERRIDE", 
                     font=("Impact", 85), text_color="#ef4444").pack(pady=(50, 10))
        
        ctk.CTkLabel(win, text="LIMIT REACHED: 2.5 HOURS EXCEEDED", 
                     font=("Consolas", 28, "bold"), text_color="#ffffff").pack()

        # 文案
        text_content = (
            "游戏里再高的段位，也填补不了你感受到的那种‘平淡的刺痛’。\n"
            "不要在这个虚拟的副本里当一个逃避的 NPC 了。\n"
            "Architecture requires sacrifice. SHUT DOWN THE CLIENT NOW."
        )
        ctk.CTkLabel(win, text=text_content, font=("Microsoft YaHei", 20, "italic"), 
                     text_color="#a1a1aa", justify="center", wraplength=1000).pack(pady=40)

        # 4. 创建按钮 (这次它能找到 win 了)
        btn_exit = ctk.CTkButton(win, text="执行退出协议 & 部署架构矩阵", 
                                font=("Microsoft YaHei", 24, "bold"), 
                                fg_color="#ef4444", hover_color="#b91c1c",
                                width=450, height=70,
                                command=on_acknowledge)
        btn_exit.pack(pady=50)

        # 5. 启动闪烁动画
        def flash():
            if win.winfo_exists():
                current_color = btn_exit.cget("fg_color")
                next_color = "#991b1b" if current_color == "#ef4444" else "#ef4444"
                btn_exit.configure(fg_color=next_color)
                win.after(500, flash)

        flash()
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