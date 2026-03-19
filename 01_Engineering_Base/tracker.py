import os
import sys
import json
import ctypes
import time
import psutil
import winreg
import calendar
import requests
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
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

APP_DIR = os.path.join(BASE_DIR, "Architect_Terminal")
NOTES_DIR = os.path.join(APP_DIR, "Notes")
IMAGE_DIR = os.path.join(NOTES_DIR, "Images")
DATA_FILE = os.path.join(APP_DIR, "daily_logs.json")

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
        self.warning_active = False  # 标记弹窗是否正在显示
        self.last_warning_time = 0   # 记录上次关闭弹窗的时间

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
        self.geometry("260x150+100+100") 
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
        self.quote_file = os.path.join(APP_DIR, "quotes.txt")
        self.current_quote = "Logic is the soul of every agent." # 默认金句

        # 主框架
        self.main_frame = ctk.CTkFrame(self, corner_radius=12, fg_color="#111111", border_width=1, border_color="#27272a")
        self.main_frame.pack(fill="both", expand=True, padx=1, pady=1)
        
        # --- 第一行：状态指示 ---
        self.top_row = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.top_row.pack(side="top", fill="x", padx=10, pady=(8, 2))
        
        self.lbl_mode_txt = ctk.CTkLabel(self.top_row, text="Study", font=("Impact", 20), text_color="#10b981")
        self.lbl_mode_txt.pack(side="left")

        self.lbl_time = ctk.CTkLabel(self.top_row, text="00:00:00", font=("Consolas", 22, "bold"), text_color="#10b981")
        self.lbl_time.pack(side="left", padx=15)
        self.lbl_quote = ctk.CTkLabel(self.main_frame, text=self.current_quote, 
                             font=("Segoe UI", 10, "italic"), 
                             text_color="#94a3b8", wraplength=230)
        self.lbl_quote.pack(side="top", expand=True, fill="both", pady=(2, 2))
# 👇 ========= 在这里插入 ENV 标签 ========= 👇
        self.lbl_env = ctk.CTkLabel(self.main_frame, text="ENV SCAN: INITIALIZING SYSTEM...", 
                                    font=("Consolas", 10, "bold"), text_color="#00f2ff")
        self.lbl_env.pack(side="bottom", pady=(0, 2))
        # 👆 ===================================== 👆
        # 在 __init__ 的最后一行加上调用
        self.fetch_deepseek_quote()

        self.btn_min = ctk.CTkButton(self.top_row, text="—", width=20, height=20, fg_color="transparent", 
                                     hover_color="#27272a", text_color="#a1a1aa", font=("Consolas", 14, "bold"), command=self.toggle_collapse)
        self.btn_min.pack(side="right")
        ToolTip(self.btn_min, "smaller")

        # --- 第二行：快捷工具栏 ---
        self.bot_row = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.bot_row.pack(side="bottom", fill="x", padx=10, pady=(2, 5))

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
        
        self.warning_active = False         
        self.last_warning_time = 0  # 建议顺便加上这个，用于留出 60 秒关闭时间
        # 线程启动
        self.running = True
        threading.Thread(target=self.monitor_loop, daemon=True).start()
        self.update_ui()
        self.after(1500, self.check_sleep_log) 
        # 👇 新增这一行，启动天气定位引擎 👇
        self.fetch_env_data()
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
    def fetch_deepseek_quote(self):
        """异步请求本地 Ollama 生成今日架构师语录"""  # 这里必须缩进！
        def task():
            try:
                url = "http://localhost:11434/api/generate"
                payload = {
                    "model": "deepseek-r1:8b", 
                    "prompt": "You are a senior AI Architect. Generate ONE short, powerful English quote about MAS, AI, or Grit. No yapping, just the quote.",
                    "stream": False
                }
                response = requests.post(url, json=payload, timeout=30)
                raw_text = response.json().get("response", "").strip()
                quote = raw_text.split('</think>')[-1].strip()
                if quote:
                    self.current_quote = quote
                    with open(self.quote_file, "w", encoding="utf-8") as f:
                        f.write(quote)
                    self.after(0, lambda: self.lbl_quote.configure(text=quote))
            except:
                if os.path.exists(self.quote_file):
                    with open(self.quote_file, "r", encoding="utf-8") as f:
                        self.after(0, lambda: self.lbl_quote.configure(text=f.read()))

        threading.Thread(target=task, daemon=True).start()
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
        """模式切换：增加对眼睛颜色的即时控制"""
        if self.mode == "STUDY":
            self.mode = "GAME"
            accent_color = "#ef4444" # 警告红
            # ... (你原有的 UI configure 代码)
            self.lbl_mode_txt.configure(text="Game", font=("Impact", 20), text_color=accent_color)
            self.lbl_time.configure(text_color=accent_color)
            # ...
        else:
            self.mode = "STUDY"
            accent_color = "#00f2ff" # 赛博蓝
            # ... (你原有的 UI configure 代码)
            self.lbl_mode_txt.configure(text="Study", font=("Impact", 20), text_color=accent_color)
            self.lbl_time.configure(text_color=accent_color)
            # ...

        # 【核心增加】：如果已经最小化，瞬间改变眼睛颜色
        if self.is_collapsed and hasattr(self, 'eye_l') and self.eye_l.winfo_exists():
            self.eye_l.configure(fg_color=accent_color)
            self.eye_r.configure(fg_color=accent_color)
            self.current_eye_color = accent_color # 记录当前颜色供睁眼函数使用
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
        """核心监测引擎：修复语法错误，支持后台工具计时"""
        user32 = ctypes.windll.user32
        loop_counter = 0
        
        while self.running:
            try:
                time.sleep(1) 
                loop_counter += 1
                self.db["last_heartbeat"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # 获取当前所有进程
                active_procs = []
                for p in psutil.process_iter(['name']):
                    try:
                        if p.info['name']: active_procs.append(p.info['name'].lower())
                    except: continue

                # 1. 听歌统计
                if MUSIC_PROCESS_NAME in active_procs:
                    self.db[self.today]["music_total"] += 1

                # 2. 学习/架构模式统计
                if self.mode == "STUDY":
                    is_study = False
                    # 判定 A: 生产力名单在后台运行 (Cherry Studio, Chatbox etc.)
                    if any(tool in active_procs for tool in STUDIO_TOOLS):
                        is_study = True
                    
                    # 判定 B: 名单工具没开，则检查前台活动窗口
                    if not is_study:
                        hwnd = user32.GetForegroundWindow()
                        length = user32.GetWindowTextLengthW(hwnd)
                        if length > 0:
                            buff = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(hwnd, buff, length + 1)
                            title = buff.value.lower()
                            if "visual studio code" in title or "vscode" in title:
                                self.db[self.today]["study_apps"]["vscode"] += 1
                                is_study = True
                            elif "chrome" in title or "bilibili" in title or "哔哩哔哩" in title:
                                is_study = True
                    
                    if is_study:
                        self.db[self.today]["study_total"] += 1
                        if self.db[self.today]["study_total"] % 7200 == 0:
                            self.after(0, self.trigger_study_break)

                # 3. 游戏模式统计
                elif self.mode == "GAME":
                    game_active = False
                    for game in GAME_NAMES:
                        if game in active_procs:
                            game_active = True
                            if game not in self.db[self.today]["game_apps"]: 
                                self.db[self.today]["game_apps"][game] = 0
                            self.db[self.today]["game_apps"][game] += 1
                            break
                    
                    if game_active:
                        self.db[self.today]["game_total"] += 1
                        if self.db[self.today]["game_total"] >= 9000: # 2.5小时
                            if not self.warning_active and (time.time() - self.last_warning_time > 60):
                                self.after(0, self.trigger_game_warning)

                # 4. 自动存盘
                if loop_counter % 10 == 0:
                    save_data(self.db)

            except Exception as e:
                print(f"监测异常: {e}")
                continue
    def update_ui(self):
        if not self.is_collapsed:
            sec = self.db[self.today]["study_total"] if self.mode == "STUDY" else self.db[self.today]["game_total"]
            self.lbl_time.configure(text=f"{sec//3600:02d}:{(sec%3600)//60:02d}:{sec%60:02d}")
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
        
        # -- 右侧：选中日期的详情面板 --
        lbl_sel_date = ctk.CTkLabel(cal_right, text="SELECT DATE", font=("Impact", 20), text_color="#ffffff")
        lbl_sel_date.pack(pady=(20, 10))
        lbl_sel_s = ctk.CTkLabel(cal_right, text="STUDIO: --", font=("Consolas", 14), text_color="#00f2ff")
        lbl_sel_s.pack(pady=5)
        lbl_sel_g = ctk.CTkLabel(cal_right, text="GAMING: --", font=("Consolas", 14), text_color="#ef4444")
        lbl_sel_g.pack(pady=5)
        
        lbl_sel_apps = ctk.CTkLabel(cal_right, text="", font=("Consolas", 11), text_color="#a1a1aa", justify="left")
        lbl_sel_apps.pack(pady=15, padx=10, anchor="w")

        def on_day_click(date_str):
            """点击日历更新右侧数据"""
            d_data = self.db.get(date_str, {})
            s_sec, g_sec = d_data.get("study_total", 0), d_data.get("game_total", 0)
            lbl_sel_date.configure(text=date_str)
            lbl_sel_s.configure(text=f"STUDIO: {s_sec//3600}H {(s_sec%3600)//60}M")
            lbl_sel_g.configure(text=f"GAMING: {g_sec//3600}H {(g_sec%3600)//60}M")
            
            app_text = "APPS RECORD:\n"
            for app, sec in d_data.get("study_apps", {}).items():
                if sec > 0: app_text += f"+ {app[:12]}: {sec//60}m\n"
            for app, sec in d_data.get("game_apps", {}).items():
                if sec > 0: app_text += f"- {app[:12]}: {sec//60}m\n"
            if not d_data.get("study_apps") and not d_data.get("game_apps"):
                app_text += "No records."
            lbl_sel_apps.configure(text=app_text)

        # -- 左侧：动态日历网格 --
        year, month = today_obj.year, today_obj.month
        ctk.CTkLabel(cal_left, text=f"{year} - {month:02d} ARCHIVE", font=("Impact", 24), text_color="#71717a").pack(pady=10)
        
        grid_frame = ctk.CTkFrame(cal_left, fg_color="transparent")
        grid_frame.pack(expand=True, fill="both", padx=10, pady=10)
        
        # 表头
        for i, wd in enumerate(["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]):
            ctk.CTkLabel(grid_frame, text=wd, font=("Consolas", 12, "bold"), text_color="#52525b").grid(row=0, column=i, padx=8, pady=5)
            
        # 生成当月格子
        import calendar # 确保已导入
        cal_matrix = calendar.monthcalendar(year, month)
        for r, week in enumerate(cal_matrix):
            for c, day in enumerate(week):
                if day != 0:
                    d_str = f"{year}-{month:02d}-{day:02d}"
                    s_sec = self.db.get(d_str, {}).get("study_total", 0)
                    g_sec = self.db.get(d_str, {}).get("game_total", 0)
                    
                    # 热力图配色逻辑：没数据=暗灰，学习多=暗蓝，游戏多=暗红
                    btn_color = "#18181b" 
                    if s_sec > g_sec and s_sec > 0: btn_color = "#082f49" 
                    elif g_sec > s_sec and g_sec > 0: btn_color = "#450a0a" 
                    
                    btn = ctk.CTkButton(grid_frame, text=str(day), width=45, height=45, corner_radius=8,
                                        fg_color=btn_color, hover_color="#3f3f46", text_color="#e4e4e7",
                                        command=lambda d=d_str: on_day_click(d))
                    btn.grid(row=r+1, column=c, padx=5, pady=5)
    
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
    app = FloatingTracker()
    app.mainloop()