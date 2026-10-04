"""Portable Windows launcher. Heavy model imports happen only in the worker."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox
import time
import queue

VERSION = '0.2.0'
ROOT = Path(__file__).resolve().parent
BOT = ROOT / 'outputs' / 'kitchen-bot'
sys.path.insert(0,str(BOT))
from app_settings import parse_stop_hotkey, captured_hotkey, hotkeys_conflict
from global_hotkey import GlobalHotkey
DATA = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'CollectCookingAuto'

TEXT = {
    '繁體中文': ('食材妙厨房 自動料理', '開啟料理遊戲，按開始載入模型。切回遊戲後按 F8 開始／暫停，Esc 停止。', '介面語言', '遊戲局數', '填寫正整數；完成指定局數後停止。', '寫入遊戲錄影（預設關閉）', '開始', '停止', '開啟紀錄資料夾', '執行紀錄', '待命', '正在載入模型…', '正在停止…', '局數必須是正整數。', '已結束', '啟動失敗；請查看紀錄。', '熱鍵', 'F8 開始／暫停　Esc 停止', '已完成局數'),
    '简体中文': ('拼配厨房 自动料理', '打开料理游戏，按开始加载模型。切回游戏后按 F8 开始／暂停，Esc 停止。', '界面语言', '游戏局数', '填写正整数；完成指定局数后停止。', '写入游戏录像（默认关闭）', '开始', '停止', '打开记录文件夹', '运行记录', '就绪', '正在加载模型…', '正在停止…', '局数必须是正整数。', '已结束', '启动失败；请查看记录。', '快捷键', 'F8 开始／暂停　Esc 停止', '已完成局数'),
    'English': ('Collect Cooking Auto', 'Open the cooking game, then Start to load models. Return to the game and press F8 to start/pause; Esc stops.', 'Interface language', 'Number of games', 'Enter a positive whole number. Stops after that many games.', 'Save gameplay video (off by default)', 'Start', 'Stop', 'Open logs folder', 'Activity log', 'Ready', 'Loading models…', 'Stopping…', 'Enter a positive whole number of games.', 'Finished', 'Launch failed; see the log.', 'Hotkeys', 'F8 start / pause    Esc stop', 'Games completed'),
}


def parse_games(value):
    if not value.isascii() or not value.isdecimal() or len(value) > 9 or int(value) < 1:
        raise ValueError('Enter a positive whole number (up to 9 digits).')
    return int(value)


class CookingApp:
    def __init__(self, root):
        self.root, self.child, self.stream = root, None, None
        self.closing = False
        self.log_position = 0
        self.messages = queue.Queue()
        self.capturing = None
        self.session = None
        DATA.mkdir(parents=True, exist_ok=True)
        settings = {}
        try:
            settings = json.loads((DATA/'settings.json').read_text(encoding='utf8'))
        except (OSError, ValueError):
            pass
        self.language = tk.StringVar(value=settings.get('language', '繁體中文'))
        if self.language.get() not in TEXT: self.language.set('繁體中文')
        self.games = tk.StringVar(value=str(settings.get('games', 5)))
        self.video = tk.BooleanVar(value=bool(settings.get('video', False)))
        self.start_key = tk.StringVar(value=settings.get('start_key', 'F8'))
        self.stop_key = tk.StringVar(value=settings.get('stop_key', 'Esc'))
        try:
            parse_stop_hotkey(self.start_key.get()); parse_stop_hotkey(self.stop_key.get())
            if hotkeys_conflict(self.start_key.get(),self.stop_key.get()): raise ValueError('Conflicting shortcuts')
        except ValueError: self.start_key.set('F8'); self.stop_key.set('Esc')
        root.title('Collect Cooking Auto — v'+VERSION)
        root.configure(bg='#f3f3f3')
        root.geometry('660x740'); root.minsize(580, 680)
        root.protocol('WM_DELETE_WINDOW', self.close)
        style = ttk.Style(root)
        if 'vista' in style.theme_names(): style.theme_use('vista')
        style.configure('TFrame', background='#f3f3f3')
        style.configure('TLabel', background='#f3f3f3', foreground='#202020', font=('Segoe UI', 11))
        style.configure('Muted.TLabel', foreground='#666666')
        style.configure('Title.TLabel', font=('Segoe UI', 19, 'bold'))
        style.configure('Count.TLabel', font=('Segoe UI', 15, 'bold'))
        style.configure('TCheckbutton', background='#f3f3f3', font=('Segoe UI', 11))
        style.configure('Action.TButton', padding=(12, 10), font=('Segoe UI', 11))
        main = ttk.Frame(root, padding=24); main.pack(fill='both', expand=True)
        main.columnconfigure(0, weight=1); main.rowconfigure(9, weight=1)
        self.title = ttk.Label(main, style='Title.TLabel'); self.title.grid(row=0, column=0, sticky='w')
        self.instructions = ttk.Label(main, style='Muted.TLabel', wraplength=600)
        self.instructions.grid(row=1, column=0, sticky='ew', pady=(8, 16))
        self.instructions.bind('<Configure>', lambda event:self.instructions.configure(wraplength=max(200,event.width)))
        self.status = ttk.Label(main, foreground='#0067c0'); self.status.grid(row=2, column=0, sticky='w')
        self.count = ttk.Label(main, style='Count.TLabel'); self.count.grid(row=3, column=0, sticky='w', pady=(12, 14))
        form = ttk.Frame(main); form.grid(row=4, column=0, sticky='ew'); form.columnconfigure(1, weight=1)
        self.language_label = ttk.Label(form); self.language_label.grid(row=0, column=0, sticky='w', padx=(0, 18), pady=6)
        self.language_choice = ttk.Combobox(form, textvariable=self.language, values=tuple(TEXT), state='readonly')
        self.language_choice.grid(row=0, column=1, sticky='ew', pady=6)
        self.language_choice.bind('<<ComboboxSelected>>', lambda e:self.translate())
        self.games_label = ttk.Label(form); self.games_label.grid(row=1, column=0, sticky='w', pady=6)
        self.games_entry = ttk.Entry(form, textvariable=self.games); self.games_entry.grid(row=1, column=1, sticky='ew', pady=6)
        self.hint = ttk.Label(form, style='Muted.TLabel', wraplength=420); self.hint.grid(row=2, column=1, sticky='w')
        self.hotkey_label = ttk.Label(form); self.hotkey_label.grid(row=3, column=0, sticky='w', pady=10)
        self.hotkeys = ttk.Label(form); self.hotkeys.grid(row=3, column=1, sticky='w')
        self.start_key_label=ttk.Label(form); self.start_key_label.grid(row=4,column=0,sticky='w',pady=6)
        self.stop_key_label=ttk.Label(form); self.stop_key_label.grid(row=5,column=0,sticky='w',pady=6)
        self.shortcut_entries=[]
        for row,variable in ((4,self.start_key),(5,self.stop_key)):
            entry=ttk.Entry(form,textvariable=variable,state='readonly')
            entry.grid(row=row,column=1,sticky='ew',pady=6)
            entry.bind('<Button-1>',lambda event,v=variable:self.begin_capture(event,v))
            entry.bind('<KeyPress>',self.capture_key)
            entry.bind('<FocusOut>',lambda event:self.end_capture())
            self.shortcut_entries.append(entry)
        self.record = ttk.Checkbutton(main, variable=self.video); self.record.grid(row=5, column=0, sticky='w', pady=10)
        controls = ttk.Frame(main); controls.grid(row=6, column=0, sticky='ew', pady=(4, 16)); controls.columnconfigure((0, 1), weight=1, uniform='buttons')
        self.start_button = ttk.Button(controls, command=self.start, style='Action.TButton'); self.start_button.grid(row=0, column=0, sticky='ew', padx=(0, 6))
        self.stop_button = ttk.Button(controls, command=self.stop, style='Action.TButton', state='disabled'); self.stop_button.grid(row=0, column=1, sticky='ew', padx=(6, 0))
        ttk.Separator(main).grid(row=7, column=0, sticky='ew')
        header = ttk.Frame(main); header.grid(row=8, column=0, sticky='ew', pady=(12, 8))
        self.log_title = ttk.Label(header); self.log_title.pack(side='left')
        self.folder_button = ttk.Button(header, command=lambda:os.startfile(str(DATA))); self.folder_button.pack(side='right')
        log_frame = ttk.Frame(main); log_frame.grid(row=9, column=0, sticky='nsew')
        self.log = tk.Text(log_frame, height=8, wrap='word', bg='white', fg='#202020', font=('Consolas', 10), relief='solid', borderwidth=1, state='disabled')
        scrollbar = ttk.Scrollbar(log_frame, command=self.log.yview); self.log.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y'); self.log.pack(fill='both', expand=True)
        self.start_listener=GlobalHotkey(lambda:self.messages.put(('start',None)), self.report_hotkey)
        self.stop_listener=GlobalHotkey(lambda:self.messages.put(('stop',None)), self.report_hotkey)
        self.start_listener.configure(value=self.start_key.get())
        self.stop_listener.configure(value=self.stop_key.get(),enabled=False)
        self.translate(); self.start_listener.start(); self.stop_listener.start(); root.after(100,self.poll)

    def report_hotkey(self,key,registered,error):
        if not registered: self.messages.put(('error', f'Hotkey unavailable: {key} (Windows error {error}). Choose another key.'))

    def configure_hotkeys(self):
        self.start_listener.configure(value=self.start_key.get(),enabled=not self.capturing and not self.closing)
        self.stop_listener.configure(value=self.stop_key.get(),enabled=bool(self.child) and not self.capturing)

    def begin_capture(self,event,variable):
        if self.child: return 'break'
        self.capturing=variable; self.configure_hotkeys(); event.widget.focus_set()
        return 'break'

    def end_capture(self):
        self.capturing=None; self.configure_hotkeys()

    def capture_key(self,event):
        if self.capturing is None: return 'break'
        value=captured_hotkey(event.keysym,event.state,event.keycode)
        if value:
            other=self.stop_key if self.capturing is self.start_key else self.start_key
            if hotkeys_conflict(value,other.get()):
                messagebox.showerror('Collect Cooking Auto', {'繁體中文':'開始與停止熱鍵不能重疊。','简体中文':'开始与停止快捷键不能重叠。','English':'Start and stop shortcuts must not overlap.'}[self.language.get()])
            else:
                self.capturing.set(value); self.save_settings(); self.translate()
            self.end_capture()
        return 'break'

    def save_settings(self):
        (DATA/'settings.json').write_text(json.dumps({'language':self.language.get(),'games':self.games.get().strip(),'video':self.video.get(),'start_key':self.start_key.get(),'stop_key':self.stop_key.get()},ensure_ascii=False),encoding='utf8')

    def with_keys(self,text):
        return (text.replace('F8','{start-key}').replace('Esc','{stop-key}')
                .replace('{start-key}',self.start_key.get()).replace('{stop-key}',self.stop_key.get()))

    def translate(self):
        self.t = TEXT[self.language.get()]
        for widget, index in ((self.title,0),(self.instructions,1),(self.language_label,2),(self.games_label,3),(self.hint,4),(self.record,5),(self.start_button,6),(self.stop_button,7),(self.folder_button,8),(self.log_title,9),(self.hotkey_label,16),(self.hotkeys,17)):
            widget.configure(text=self.with_keys(self.t[index]))
        self.start_key_label.configure(text={'繁體中文':'開始／暫停鍵','简体中文':'开始／暂停键','English':'Start / pause key'}[self.language.get()])
        self.stop_key_label.configure(text={'繁體中文':'停止鍵','简体中文':'停止键','English':'Stop key'}[self.language.get()])
        if not self.child: self.status.configure(text=self.t[10])
        self.count.configure(text=f'{self.t[18]}: 0 / {self.games.get()}')

    def start(self,autostart=False):
        if self.child: return
        try: games = parse_games(self.games.get().strip())
        except ValueError:
            messagebox.showerror('Collect Cooking Auto', self.t[13]); return
        self.save_settings()
        self.session = DATA / ('launch-'+str(time.time_ns())); self.session.mkdir()
        self.log_path = self.session / 'launcher.log'; self.stop_path = self.session / 'stop'
        self.toggle_path=self.session/'toggle'; self.toggle_count=0
        self.toggle_path.write_text('0',encoding='ascii')
        self.stream = self.log_path.open('w', encoding='utf8'); self.log_position = 0
        args = ['--worker', '--games', str(games), '--output', str(self.session/'runs'), '--control-file', str(self.stop_path)]
        args += ['--start-key',self.start_key.get(),'--stop-key',self.stop_key.get()]
        if autostart: args.append('--autostart')
        if self.video.get(): args.append('--record-video')
        command = [sys.executable] + args if getattr(sys, 'frozen', False) else [sys.executable, str(ROOT/'gui.py')] + args
        try:
            self.child = subprocess.Popen(command, cwd=ROOT, stdout=self.stream, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        except OSError as e:
            self.stream.close(); self.stream=None; self.append(str(e)); self.status.configure(text=self.t[15]); return
        for widget in (self.start_button, self.games_entry, self.record): widget.configure(state='disabled')
        self.stop_button.configure(state='normal'); self.status.configure(text=self.t[11])
        self.count.configure(text=f'{self.t[18]}: 0 / {games}')
        self.configure_hotkeys()

    def append(self, text):
        self.log.configure(state='normal'); self.log.insert('end', text+'\n'); self.log.see('end'); self.log.configure(state='disabled')

    def stop(self):
        if self.child:
            self.stop_path.touch(); self.status.configure(text=self.t[12]); self.stop_button.configure(state='disabled')

    def toggle(self):
        if self.child and not self.stop_path.exists():
            self.toggle_count+=1
            pending=self.toggle_path.with_suffix('.pending')
            pending.write_text(str(self.toggle_count),encoding='ascii')
            self.publish_toggle()

    def publish_toggle(self):
        if not self.child or self.stop_path.exists():return
        try:
            self.toggle_path.with_suffix('.pending').replace(self.toggle_path)
        except PermissionError:
            # A Windows reader can briefly hold the destination without
            # delete sharing. Keep the newest event pending and retry.
            self.root.after(10,self.publish_toggle)
        except FileNotFoundError:
            pass  # A previously scheduled retry already published it.

    def poll(self):
        while not self.messages.empty():
            event,value=self.messages.get_nowait()
            if event=='start' and not self.closing and self.capturing is None:
                if self.child:self.toggle()
                else:self.start(autostart=True)
            elif event=='stop': self.stop()
            elif event=='error': self.append(value)
        if self.child:
            try:
                with self.log_path.open(encoding='utf8', errors='replace') as f:
                    f.seek(self.log_position); text=f.read(); self.log_position=f.tell()
                if text:
                    self.append(text.rstrip())
                    if not self.stop_path.exists():
                        line=text.strip().splitlines()[-1]
                        if line.startswith('Ready.'):
                            line=self.t[10]+' — '+self.with_keys(self.t[17])
                        elif line=='Running':
                            line={'繁體中文':'執行中','简体中文':'运行中','English':'Running'}[self.language.get()]
                        elif line=='Paused' or line.startswith('Focus changed; paused'):
                            line={'繁體中文':'已暫停；回到遊戲按 F8 繼續','简体中文':'已暂停；返回游戏按 F8 继续','English':'Paused; return to the game and press F8'}[self.language.get()]
                        self.status.configure(text=self.with_keys(line[:90]))
                summaries = list((self.session/'runs').glob('session-*/summary.json'))
                if summaries:
                    data=json.loads(summaries[-1].read_text(encoding='utf8'))
                    self.count.configure(text=f"{self.t[18]}: {len(data['games'])} / {self.games.get()}")
            except (OSError, ValueError, KeyError): pass
            code = self.child.poll()
            if code is not None:
                self.stream.close(); self.stream=None; self.child=None
                self.status.configure(text=self.t[14] if code==0 else self.t[15], foreground='#187b38' if code==0 else '#b42318')
                for widget in (self.start_button, self.games_entry, self.record): widget.configure(state='normal')
                self.stop_button.configure(state='disabled')
                self.configure_hotkeys()
                if self.closing: self.destroy(); return
        self.root.after(100, self.poll)

    def destroy(self):
        self.start_listener.close(); self.stop_listener.close(); self.root.destroy()

    def close(self):
        if self.child:
            self.closing=True; self.stop()
        else: self.destroy()


def worker():
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker', action='store_true'); parser.add_argument('--games', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True); parser.add_argument('--control-file', type=Path, required=True)
    parser.add_argument('--record-video', action='store_true'); parser.add_argument('--smoke-frame', type=Path)
    parser.add_argument('--start-key',default='F8'); parser.add_argument('--stop-key',default='Esc'); parser.add_argument('--autostart',action='store_true')
    args=parser.parse_args()
    # Windowed executables may have no Python standard streams, even when
    # their native handles were redirected by the launcher.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if sys.stdout is None:
        sys.stdout=(args.output.parent/'launcher.log').open('a', encoding='utf8', buffering=1)
    if sys.stderr is None: sys.stderr=sys.stdout
    os.environ['COOKING_STOP_FILE']=str(args.control_file)
    os.environ['COOKING_TOGGLE_FILE']=str(args.control_file.with_name('toggle'))
    os.environ['COOKING_RECORD_VIDEO']='1' if args.record_video else '0'
    os.environ['COOKING_START_KEY']=args.start_key; os.environ['COOKING_STOP_KEY']=args.stop_key
    sys.path.insert(0, str(BOT))
    print('Loading Collect Cooking models…', flush=True)
    import standalone
    if args.smoke_frame:
        import cv2
        from perception import Perception
        from supplemental_food import SupplementalFood
        model=Perception('../kitchen-labeler/point-classifier-human.pt')
        model.supplement=SupplementalFood(model,BOT/'segmenter-positive-surfaces.pt',BOT/'point-classifier-human-paired.pt')
        frame=cv2.imread(str(args.smoke_frame))
        if frame is None: raise ValueError('Smoke-test image not found')
        result=model.analyze(frame,fast=True)
        print(json.dumps({'smoke_test':'PASS','device':model.device,'phase':result.get('phase'),'order':result.get('order')}), flush=True)
        return
    if args.control_file.exists(): print('Canceled before starting.', flush=True); return
    sys.argv=['standalone.py','--games',str(args.games),'--output',str(args.output),'--point-model','../kitchen-labeler/point-classifier-human.pt']
    if args.autostart: sys.argv.append('--autostart')
    standalone.main()


if __name__ == '__main__':
    if '--worker' in sys.argv:
        try:
            worker()
        except Exception:
            import traceback
            traceback.print_exc()
            raise SystemExit(1)
    else:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except (AttributeError, OSError): pass
        CookingApp(tk.Tk()).root.mainloop()
