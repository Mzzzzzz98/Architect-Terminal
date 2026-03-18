import os
import sys
import json
import ctypes
import time
import psutil
import winreg
import calendar
from datetime import datetime, timedelta
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, colorchooser, font
import threading
import glob
import random
from PIL import Image, ImageTk, ImageGrab

# ==========================================
# ⚙️ 全局配置与路径中枢 (随时在这里修改你的软件路径)
# ==========================================
# ==========================================
# ⚙️ 全局配置与路径初始化 (V15.2 防弹版)
# ==========================================
# 这一步是为了确保 .exe 运行在它所在的文件夹，而不是系统的临时文件夹
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

APP_DIR = os.path.join(BASE_DIR, "Architect_Terminal")
NOTES_DIR = os.path.join(APP_DIR, "Notes")
IMAGE_DIR = os.path.join(NOTES_DIR, "Images")
DATA_FILE = os.path.join(APP_DIR, "daily_logs.json")

# 自动构建生态目录 (加入异常捕获，防止 WinError 5 崩溃)
for d in [APP_DIR, NOTES_DIR, IMAGE_DIR]:
    try:
        os.makedirs(d, exist_ok=True)
    except PermissionError:
        # 如果权限报错，直接弹出一个 Windows 原生提示框告诉你
        ctypes.windll.user32.MessageBoxW(0, f"权限受阻！\n请不要在系统保护文件夹运行。\n建议将程序移动到 D 盘或 E 盘的新文件夹中。\n报错路径: {d}", "系统权限错误", 0x10)
        sys.exit(1)

# 下面接着你的快捷启动路径配置...
NETEASE_MUSIC_PATH = r"E:\CloudMusic\cloudmusic.exe"
# ... 后面保持不变
# 自动构建生态目录
for d in [APP_DIR, NOTES_DIR, IMAGE_DIR]:
    if not os.path.exists(d): os.makedirs(d)

# 软件快捷启动路径
NETEASE_MUSIC_PATH = r"E:\CloudMusic\cloudmusic.exe"
WEGAME_PATH = r"F:\Program Files (x86)\WeGame\wegame.exe"

# 进程监控特征码 (全小写)
MUSIC_PROCESS_NAME = "netease cloud music.exe"
GAME_NAMES = ["leagueclientuxrender.exe", "wegame.exe", "deltaforceclient-win64-shipping.exe"]

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

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"数据保存失败: {e}")

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
class NoteWindow(ctk.CTkToplevel):
    def __init__(self, master, category_name):
        super().__init__(master)
        self.category = category_name
        self.title(f"架构师文献 - {category_name}")
        
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = int(sw / 3.5), int(sh / 1.8)
        self.geometry(f"{w}x{h}+{int((sw-w)/2)}+{int((sh-h)/2)}")
        self.configure(fg_color="#18181b")
        self.attributes("-topmost", True)
        
        # 顶层栏
        self.top_bar = ctk.CTkFrame(self, fg_color="#27272a", height=35, corner_radius=0)
        self.top_bar.pack(fill="x", side="top")
        ctk.CTkLabel(self.top_bar, text=f"📂 {category_name}", font=("Microsoft YaHei", 12, "bold"), text_color="#10b981").pack(side="left", padx=10)
        self.btn_save = ctk.CTkButton(self.top_bar, text="💾 封存笔记", width=70, height=24, fg_color="#10b981", hover_color="#059669", command=self.save_content)
        self.btn_save.pack(side="right", padx=10)

        # 富文本工具栏 (修复了字体大小和格式调整失效的问题)
        self.format_bar = ctk.CTkFrame(self, fg_color="#18181b", height=30, corner_radius=0)
        self.format_bar.pack(fill="x", padx=5, pady=5)
        
        self.font_family = ctk.CTkOptionMenu(self.format_bar, values=["Microsoft YaHei", "Consolas", "SimHei", "KaiTi"], width=110, height=24, command=self.apply_font_family)
        self.font_family.pack(side="left", padx=2)
        
        self.font_size = ctk.CTkOptionMenu(self.format_bar, values=["10", "12", "14", "16", "18", "20", "24"], width=60, height=24, command=self.apply_font_size)
        self.font_size.set("14")
        self.font_size.pack(side="left", padx=2)
        
        ctk.CTkButton(self.format_bar, text="B", width=28, height=24, font=("Arial", 12, "bold"), fg_color="#3f3f46", command=self.apply_bold).pack(side="left", padx=2)
        ctk.CTkButton(self.format_bar, text="I", width=28, height=24, font=("Arial", 12, "italic"), fg_color="#3f3f46", command=self.apply_italic).pack(side="left", padx=2)
        ctk.CTkButton(self.format_bar, text="🎨", width=28, height=24, fg_color="#3f3f46", command=self.apply_color).pack(side="left", padx=2)

        # 文本编辑区
        self.text_frame = ctk.CTkFrame(self, fg_color="#09090b", corner_radius=0)
        self.text_frame.pack(fill="both", expand=True, padx=2, pady=2)

        self.scrollbar = tk.Scrollbar(self.text_frame)
        self.scrollbar.pack(side="right", fill="y")

        self.text_area = tk.Text(self.text_frame, bg="#09090b", fg="#e4e4e7", insertbackground="#10b981", 
                                 font=("Microsoft YaHei", 14), padx=15, pady=15, borderwidth=0, highlightthickness=0,
                                 yscrollcommand=self.scrollbar.set, wrap="word")
        self.text_area.pack(fill="both", expand=True)
        self.scrollbar.config(command=self.text_area.yview)
        
        self.image_refs = [] 
        self.load_content()
        self.text_area.bind('<Control-v>', self.paste_image)

    # --- 富文本核心逻辑 ---
    def apply_tag(self, tag_name, **kwargs):
        try:
            self.text_area.tag_add(tag_name, "sel.first", "sel.last")
            self.text_area.tag_config(tag_name, **kwargs)
        except tk.TclError: pass 

    def apply_font_family(self, choice):
        f = font.Font(self.text_area, self.text_area.cget("font"))
        f.configure(family=choice)
        self.apply_tag(f"family_{choice}", font=f)

    def apply_font_size(self, choice):
        f = font.Font(self.text_area, self.text_area.cget("font"))
        f.configure(size=int(choice))
        self.apply_tag(f"size_{choice}", font=f)

    def apply_bold(self):
        f = font.Font(self.text_area, self.text_area.cget("font"))
        f.configure(weight="bold")
        self.apply_tag("bold", font=f)

    def apply_italic(self):
        f = font.Font(self.text_area, self.text_area.cget("font"))
        f.configure(slant="italic")
        self.apply_tag("italic", font=f)

    def apply_color(self):
        color = colorchooser.askcolor(title="选择字体颜色")[1]
        if color: self.apply_tag(f"color_{color}", foreground=color)

    # --- 图片处理与存储 ---
    def process_and_insert_image(self, img):
        max_width = int(self.winfo_width() * 0.8)
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

    def save_content(self):
        content = self.text_area.get("1.0", tk.END)
        with open(os.path.join(NOTES_DIR, f"{self.category}.txt"), "w", encoding="utf-8") as f:
            f.write(content)
        self.btn_save.configure(text="✅ 已保存")
        self.after(1500, lambda: self.btn_save.configure(text="💾 封存笔记"))

    def load_content(self):
        path = os.path.join(NOTES_DIR, f"{self.category}.txt")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f: self.text_area.insert("1.0", f.read())

# ==========================================
# 🚀 核心控制中枢 (极限悬浮窗)
# ==========================================
class FloatingTracker(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # 窗口设定
        self.geometry("260x85+100+100") 
        self.overrideredirect(True)      
        self.attributes("-topmost", True, "-alpha", 0.92, "-toolwindow", True)
        ctk.set_appearance_mode("dark")

        # 系统自启动注入
        self.inject_to_registry()

        # 数据初始化
        self.db = load_data()
        self.today = datetime.now().strftime("%Y-%m-%d")
        self.db = init_today_data(self.db, self.today)
        self.game_limit = int(2.5 * 3600)  
        self.mode = "STUDY" 
        self.is_collapsed = False  
        self.menu = None

        # 主框架
        self.main_frame = ctk.CTkFrame(self, corner_radius=12, fg_color="#111111", border_width=1, border_color="#27272a")
        self.main_frame.pack(fill="both", expand=True, padx=1, pady=1)
        
        # --- 第一行：状态指示 ---
        self.top_row = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.top_row.pack(fill="x", padx=10, pady=(8, 2))
        
        self.lbl_mode_txt = ctk.CTkLabel(self.top_row, text="Study", font=("Impact", 20), text_color="#10b981")
        self.lbl_mode_txt.pack(side="left")

        self.lbl_time = ctk.CTkLabel(self.top_row, text="00:00:00", font=("Consolas", 22, "bold"), text_color="#10b981")
        self.lbl_time.pack(side="left", padx=15)

        self.btn_min = ctk.CTkButton(self.top_row, text="—", width=20, height=20, fg_color="transparent", 
                                     hover_color="#27272a", text_color="#a1a1aa", font=("Consolas", 14, "bold"), command=self.toggle_collapse)
        self.btn_min.pack(side="right")
        ToolTip(self.btn_min, "smaller")

        # --- 第二行：快捷工具栏 ---
        self.bot_row = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.bot_row.pack(fill="x", padx=10, pady=(2, 5))

        self.btn_switch = ctk.CTkButton(self.bot_row, text="🔄 切换", width=60, height=24, fg_color="#27272a", hover_color="#3f3f46", font=("Microsoft YaHei", 10, "bold"), command=self.switch_mode)
        self.btn_switch.pack(side="left")
        ToolTip(self.btn_switch, "CHANGE MODE")

        # 游戏模式专属按钮 (默认隐藏)
        self.btn_clean = ctk.CTkButton(self.bot_row, text="🧹", width=28, height=24, fg_color="transparent", hover_color="#27272a", text_color="#facc15", command=self.clean_memory)
        ToolTip(self.btn_clean, "一键释放！！")

        self.btn_wegame = ctk.CTkButton(self.bot_row, text="🎮", width=28, height=24, fg_color="transparent", hover_color="#27272a", command=self.launch_wegame)
        ToolTip(self.btn_wegame, "启动！")
        
        # 常驻按钮
        self.btn_music = ctk.CTkButton(self.bot_row, text="🎵", width=28, height=24, fg_color="transparent", hover_color="#27272a", command=self.launch_music)
        self.btn_music.pack(side="right", padx=1)
        ToolTip(self.btn_music, "听歌去！")

        self.btn_data = ctk.CTkButton(self.bot_row, text="📊", width=28, height=24, fg_color="transparent", hover_color="#27272a", command=self.show_data_module)
        self.btn_data.pack(side="right", padx=1)
        ToolTip(self.btn_data, "数据矩阵与日历")

        self.btn_note = ctk.CTkButton(self.bot_row, text="📝", width=28, height=24, fg_color="transparent", hover_color="#27272a", command=self.show_note_menu)
        self.btn_note.pack(side="right", padx=1)
        ToolTip(self.btn_note, "奇思妙想")

        # 事件绑定
        self.main_frame.bind("<ButtonPress-1>", self.start_move)
        self.main_frame.bind("<B1-Motion>", self.do_move)

        # 线程启动
        self.running = True
        threading.Thread(target=self.monitor_loop, daemon=True).start()
        self.update_ui()
        self.after(1500, self.check_sleep_log) 

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
        if self.mode == "STUDY":
            self.mode = "GAME"
            self.lbl_mode_txt.configure(text="Game", font=("Impact", 20), text_color="#ef4444")
            self.lbl_time.configure(text_color="#ef4444")
            self.btn_wegame.pack(side="right", padx=1, before=self.btn_music)
            self.btn_clean.pack(side="right", padx=1, before=self.btn_wegame)
            self.btn_note.pack_forget() 
            if self.menu: self.menu.destroy()
        else:
            self.mode = "STUDY"
            self.lbl_mode_txt.configure(text="Study", font=("Impact", 20), text_color="#10b981")
            self.lbl_time.configure(text_color="#10b981")
            self.btn_wegame.pack_forget()
            self.btn_clean.pack_forget()
            self.btn_note.pack(side="right", padx=1, after=self.btn_data)

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
        if not self.is_collapsed:
            self.old_geom = self.geometry()
            new_x, new_y = self.winfo_screenwidth() - 80, self.winfo_screenheight() - 80
            self.geometry(f"50x40+{new_x}+{new_y}") 
            
            self.top_row.pack_forget()
            self.bot_row.pack_forget()
            
            self.lbl_min = ctk.CTkLabel(self.main_frame, text="👀", font=("Segoe UI Emoji", 18), cursor="hand2")
            self.lbl_min.pack(expand=True)
            ToolTip(self.lbl_min, "双击恢复终端")
            
            self.lbl_min.bind("<ButtonPress-1>", self.start_move)
            self.lbl_min.bind("<B1-Motion>", self.do_move)
            self.lbl_min.bind("<Double-Button-1>", self.restore_window)
            self.is_collapsed = True

    def restore_window(self, event=None):
        if self.is_collapsed:
            self.lbl_min.destroy()
            if hasattr(self, 'old_geom'): self.geometry(self.old_geom)
            self.top_row.pack(fill="x", padx=10, pady=(8, 2))
            self.bot_row.pack(fill="x", padx=10, pady=(2, 5))
            self.is_collapsed = False

    def start_move(self, event):
        self.x = event.x; self.y = event.y
    def do_move(self, event):
        self.geometry(f"+{self.winfo_x() + (event.x - self.x)}+{self.winfo_y() + (event.y - self.y)}")

    # --- 🧠 算力监控核心引擎 (严格防作弊模式) ---
    def monitor_loop(self):
        user32 = ctypes.windll.user32
        loop_counter = 0
        
        while self.running:
            time.sleep(1) 
            loop_counter += 1
            self.db["last_heartbeat"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            active_procs = []
            try:
                for p in psutil.process_iter(['name']): 
                    if p.info['name']: active_procs.append(p.info['name'].lower())
            except: pass

            if MUSIC_PROCESS_NAME in active_procs:
                self.db[self.today]["music_total"] += 1

            if self.mode == "STUDY":
                try:
                    hwnd = user32.GetForegroundWindow()
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buff, length + 1)
                        active_title = buff.value.lower()
                        
                        is_study = False
                        # 绝对冷酷的严格过滤
                        if "visual studio code" in active_title: 
                            self.db[self.today]["study_apps"]["vscode"] += 1
                            is_study = True
                        elif "bilibili" in active_title or "哔哩哔哩" in active_title: 
                            self.db[self.today]["study_apps"]["bilibili"] += 1
                            is_study = True
                        elif "google chrome" in active_title or "chrome" in active_title: 
                            self.db[self.today]["study_apps"]["chrome"] += 1
                            is_study = True
                        
                        # 只有判定为学习状态，时间才跳动
                        if is_study:
                            self.db[self.today]["study_total"] += 1
                            if self.db[self.today]["study_total"] > 0 and self.db[self.today]["study_total"] % 7200 == 0:
                                self.trigger_study_break()
                except: pass

            elif self.mode == "GAME":
                game_running = False
                for g_name in GAME_NAMES:
                    if g_name in active_procs:
                        game_running = True
                        if g_name not in self.db[self.today]["game_apps"]: self.db[self.today]["game_apps"][g_name] = 0
                        self.db[self.today]["game_apps"][g_name] += 1
                        break
                
                if game_running:
                    self.db[self.today]["game_total"] += 1
                    if self.db[self.today]["game_total"] >= self.game_limit and (self.db[self.today]["game_total"] - self.game_limit) % 300 == 0:
                        self.trigger_game_warning()
            
            if loop_counter % 10 == 0: save_data(self.db)

    def update_ui(self):
        if not self.is_collapsed:
            sec = self.db[self.today]["study_total"] if self.mode == "STUDY" else self.db[self.today]["game_total"]
            self.lbl_time.configure(text=f"{sec//3600:02d}:{(sec%3600)//60:02d}:{sec%60:02d}")
        self.after(1000, self.update_ui)

    # --- 📊 日历与全景数据矩阵 ---
    def show_data_module(self):
        win = ctk.CTkToplevel(self)
        win.title("数据全景矩阵")
        win.geometry("500x450+400+150")
        win.attributes("-topmost", True)
        win.configure(fg_color="#18181b")
        
        tabview = ctk.CTkTabview(win, width=460, height=400, fg_color="#27272a")
        tabview.pack(padx=20, pady=10)
        
        tab_daily = tabview.add("今日细分")
        tab_cal = tabview.add("月度热力日历")
        
        td = self.db[self.today]
        info_frame = ctk.CTkFrame(tab_daily, fg_color="transparent")
        info_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        col1 = ctk.CTkFrame(info_frame, fg_color="#1f2937", corner_radius=8)
        col1.pack(side="left", fill="both", expand=True, padx=5)
        ctk.CTkLabel(col1, text=f"💻 架构专注: {td['study_total']//3600}h {(td['study_total']%3600)//60}m", font=("Microsoft YaHei", 12, "bold"), text_color="#10b981").pack(pady=5)
        for app, sec in td["study_apps"].items():
            if sec > 0: ctk.CTkLabel(col1, text=f"{app}: {sec//60} 分钟", font=("Consolas", 11), text_color="#a1a1aa").pack()

        col2 = ctk.CTkFrame(info_frame, fg_color="#7f1d1d", corner_radius=8)
        col2.pack(side="left", fill="both", expand=True, padx=5)
        ctk.CTkLabel(col2, text=f"🎮 游戏耗时: {td['game_total']//3600}h {(td['game_total']%3600)//60}m", font=("Microsoft YaHei", 12, "bold"), text_color="#fca5a5").pack(pady=5)
        for app, sec in td["game_apps"].items():
            if sec > 0: ctk.CTkLabel(col2, text=f"{app}: {sec//60} 分钟", font=("Consolas", 11), text_color="#fecaca").pack()

        bot_info = ctk.CTkFrame(tab_daily, fg_color="#374151", corner_radius=8)
        bot_info.pack(fill="x", padx=15, pady=10)
        ctk.CTkLabel(bot_info, text=f"🎵 网易云陪伴: {td.get('music_total',0)//60} 分钟   |   🌙 昨夜入睡: {td['sleep'].get('sleep_time', '未记录')}", 
                     font=("Microsoft YaHei", 12), text_color="white").pack(pady=10)

        cal_top = ctk.CTkFrame(tab_cal, fg_color="transparent")
        cal_top.pack(fill="x", pady=5)
        
        now = datetime.now()
        ctk.CTkLabel(cal_top, text=f"{now.year}年 {now.month}月", font=("Microsoft YaHei", 14, "bold")).pack()
        
        cal_grid = ctk.CTkFrame(tab_cal, fg_color="transparent")
        cal_grid.pack(pady=5)
        
        days = ["一", "二", "三", "四", "五", "六", "日"]
        for i, d in enumerate(days): ctk.CTkLabel(cal_grid, text=d, width=40).grid(row=0, column=i, pady=2)
        
        month_days = calendar.monthcalendar(now.year, now.month)
        
        self.cal_detail_lbl = ctk.CTkLabel(tab_cal, text="点击日期查看详细数据", font=("Microsoft YaHei", 12), text_color="#a1a1aa", justify="left")
        self.cal_detail_lbl.pack(pady=10)

        def show_day_detail(day_str):
            if day_str in self.db:
                d = self.db[day_str]
                s, g, m, slp = d.get('study_total', 0), d.get('game_total', 0), d.get('music_total', 0), d.get('sleep', {}).get('sleep_time', '未记录')
                self.cal_detail_lbl.configure(text=f"【{day_str}】\n专注: {s//3600}h {(s%3600)//60}m | 游戏: {g//3600}h {(g%3600)//60}m\n音乐: {m//60}m | 入睡: {slp}", text_color="#10b981")
            else:
                self.cal_detail_lbl.configure(text=f"【{day_str}】\n当天无记录档案", text_color="#ef4444")

        for row, week in enumerate(month_days):
            for col, day in enumerate(week):
                if day != 0:
                    day_str = f"{now.year}-{now.month:02d}-{day:02d}"
                    bg_color = "#059669" if day_str in self.db else "#3f3f46"
                    btn = ctk.CTkButton(cal_grid, text=str(day), width=35, height=35, fg_color=bg_color, corner_radius=18,
                                        command=lambda ds=day_str: show_day_detail(ds))
                    btn.grid(row=row+1, column=col, padx=3, pady=3)

    # --- 🌙 睡眠追踪记录器 ---
    def check_sleep_log(self):
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        if yesterday in self.db and self.db[yesterday].get("sleep", {}).get("duration") == "未记录":
            last_hb = self.db.get("last_heartbeat", "未知")
            win = ctk.CTkToplevel(self)
            win.geometry("380x240+400+300")
            win.attributes("-topmost", True)
            win.configure(fg_color="#18181b")
            
            ctk.CTkLabel(win, text="🌙 睡眠归档", font=("Microsoft YaHei", 16, "bold"), text_color="#3b82f6").pack(pady=15)
            ctk.CTkLabel(win, text=f"昨晚离线: {last_hb}\n实际入睡几点？(如 02:30)", text_color="white").pack()
            
            entry = ctk.CTkEntry(win, width=100)
            entry.pack(pady=10)
            
            def save_sleep():
                if entry.get():
                    self.db[yesterday]["sleep"]["sleep_time"] = entry.get()
                    self.db[yesterday]["sleep"]["duration"] = "已记录"
                    save_data(self.db)
                    win.destroy()
            ctk.CTkButton(win, text="记录", command=save_sleep, width=100).pack()

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
        win = ctk.CTkToplevel(self)
        win.attributes('-fullscreen', True, '-topmost', True)
        win.configure(fg_color="#09090b")
        
        ctk.CTkLabel(win, text="SYSTEM OVERRIDE // LIMIT REACHED", font=("Consolas", 32, "bold"), text_color="#ef4444").pack(pady=120)
        text = "游戏里再高的段位，也填补不了你感受到的那种‘平淡的刺痛’。\n不要在这个虚拟的副本里当一个逃避的 NPC 了。\n软弱没人会买单。关掉它，去面对那个你一直不敢面对的自己！"
        ctk.CTkLabel(win, text=text, font=("Microsoft YaHei", 22, "italic"), text_color="#a1a1aa", justify="center", wraplength=900).pack(pady=50)
        ctk.CTkButton(win, text="执行退出协议", command=win.destroy, fg_color="#b91c1c", hover_color="#991b1b", font=("Microsoft YaHei", 16), width=250, height=50).pack(pady=50)

if __name__ == "__main__":
    app = FloatingTracker()
    app.mainloop()