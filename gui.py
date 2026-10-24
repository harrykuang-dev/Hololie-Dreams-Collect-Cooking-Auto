"""Portable Windows launcher. Heavy model imports happen only in the worker."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
from fluent_theme import FluentTheme, BG, SURFACE, TEXT as UI_TEXT, MUTED
import time
import queue
import tempfile
import shutil
import webbrowser

VERSION = '1.1.0'
ROOT = Path(__file__).resolve().parent
BOT = ROOT / 'outputs' / 'kitchen-bot'
sys.path.insert(0,str(BOT))
from app_settings import parse_stop_hotkey, captured_hotkey, hotkeys_conflict
from global_hotkey import GlobalHotkey
from game_window import request_game_foreground
from model_selection import DEFAULT_MODEL, MODEL_FILES, point_model
from ui_text import UI
DATA = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'CollectCookingAuto'

TEXT = UI
PROJECT_URL = "https://github.com/harrykuang-dev/Hololive-Dreams-Collect-Cooking-Auto"


def parse_games(value):
    if not value.isascii() or not value.isdecimal() or len(value) > 9 or int(value) < 1:
        raise ValueError('Enter a positive whole number (up to 9 digits).')
    return int(value)


def window_scale(root):
    try:
        import ctypes
        return (ctypes.windll.user32.GetDpiForWindow(root.winfo_id()) or 96)/96
    except (AttributeError,OSError):
        return root.winfo_fpixels('1i')/96


class CookingApp:
    def __init__(self, root):
        self.root, self.child, self.stream = root, None, None
        self.closing = False
        self.run_state = 'idle'
        self.state_revision = None
        self.help_dialog = None
        self.completed = 0
        self.log_position = 0
        self.messages = queue.Queue()
        self.capturing = None
        self.capture_entry = None
        self.session = None
        DATA.mkdir(parents=True, exist_ok=True)
        settings = {}
        try:
            settings = json.loads((DATA/'settings.json').read_text(encoding='utf8'))
        except (OSError, ValueError):
            pass
        self.language = tk.StringVar(value=settings.get('language', '繁體中文'))
        if self.language.get() not in TEXT: self.language.set('繁體中文')
        self.model = tk.StringVar(value=settings.get('model', DEFAULT_MODEL))
        if self.model.get() not in MODEL_FILES:self.model.set(DEFAULT_MODEL)
        self.games = tk.StringVar(value=str(settings.get('games', 5)))
        self.developer_mode = tk.BooleanVar(value=bool(settings.get('developer_mode', False)))
        self.start_key = tk.StringVar(value=settings.get('start_key', 'F8'))
        self.stop_key = tk.StringVar(value=settings.get('stop_key', 'Esc'))
        try:
            parse_stop_hotkey(self.start_key.get()); parse_stop_hotkey(self.stop_key.get())
            if hotkeys_conflict(self.start_key.get(),self.stop_key.get()): raise ValueError('Conflicting shortcuts')
        except ValueError: self.start_key.set('F8'); self.stop_key.set('Esc')
        self.start_display = tk.StringVar(value=self.start_key.get())
        self.stop_display = tk.StringVar(value=self.stop_key.get())
        root.title('Hololive Dreams — '+UI[self.language.get()]['title'])
        self.scale = window_scale(root)
        self.px = lambda n: max(1, round(n*self.scale))
        root.tk.call('tk', 'scaling', self.scale*96/72)
        root.configure(bg=BG)
        height=min(self.px(800), root.winfo_screenheight()-80)
        root.geometry(f'{self.px(450)}x{height}')
        root.minsize(self.px(360), min(self.px(640), height))
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.theme=FluentTheme(root,self.scale)
        self._app_icons=[]
        icon=ROOT/'assets/cooking-icon.png'
        if icon.exists():
            with Image.open(icon) as image:
                self._app_icons=[ImageTk.PhotoImage(image.resize((size,size),Image.Resampling.LANCZOS),master=root)
                                 for size in (256,48,32,16)]
            root.iconphoto(True,*self._app_icons)
        shell=ttk.Frame(root);shell.pack(fill='both',expand=True)
        self.viewport=tk.Canvas(shell,bg=BG,highlightthickness=0,borderwidth=0)
        self.page_scrollbar=ttk.Scrollbar(shell,orient='vertical',command=self.viewport.yview)
        self.viewport.configure(yscrollcommand=self.page_scrollbar.set)
        self.viewport.pack(side='left',fill='both',expand=True)
        main=ttk.Frame(self.viewport,padding=self.px(24));self.main=main
        self.page_window=self.viewport.create_window((0,0),window=main,anchor='nw')
        main.columnconfigure(0,weight=1);main.rowconfigure(8,weight=1)
        heading=ttk.Frame(main);heading.grid(row=0,column=0,sticky='ew');heading.columnconfigure(1,weight=1)
        with Image.open(ROOT/'assets/cooking-title.png') as image:
            logo=image.convert('RGBA');logo.thumbnail((self.px(84),self.px(50)),Image.Resampling.LANCZOS)
            self._game_logo=ImageTk.PhotoImage(logo,master=root)
        ttk.Label(heading,image=self._game_logo,style='Intro.TLabel').grid(row=0,column=0,padx=(0,self.px(12)))
        self.title=ttk.Label(heading,style='Title.TLabel',wraplength=self.px(280));self.title.grid(row=0,column=1,sticky='ew')
        self.instructions=ttk.Label(main,style='Intro.TLabel',wraplength=self.px(402))
        self.instructions.grid(row=1,column=0,sticky='ew',pady=(self.px(8),self.px(12)))
        self.instructions.bind('<Configure>',lambda e:self.instructions.configure(wraplength=max(self.px(180),e.width)))
        self.status=ttk.Label(main,style='Intro.TLabel',foreground='#F15B60');self.status.grid(row=2,column=0,sticky='w',pady=(0,self.px(12)))
        summary=ttk.Frame(main,style='Card.TFrame',padding=self.px(16));summary.grid(row=3,column=0,sticky='ew',pady=(0,self.px(12)))
        self.count=ttk.Label(summary,style='Count.TLabel');self.count.pack(anchor='w')
        self.count.bind('<Configure>',lambda e:self.count.configure(wraplength=max(self.px(180),summary.winfo_width()-self.px(32))))
        form=ttk.Frame(main,style='Card.TFrame',padding=self.px(16));form.grid(row=4,column=0,sticky='ew',pady=(0,self.px(12)))
        form.columnconfigure(1,weight=1)
        self.language_label=ttk.Label(form);self.language_label.grid(row=0,column=0,sticky='w',padx=(0,self.px(12)),pady=self.px(6))
        self.language_choice=ttk.Combobox(form,textvariable=self.language,values=tuple(TEXT),state='readonly',width=12,font=('Segoe UI',10))
        self.language_choice.grid(row=0,column=1,sticky='ew',pady=self.px(6))
        self.language_choice.bind('<<ComboboxSelected>>',lambda e:self.translate())
        self.games_label=ttk.Label(form);self.games_label.grid(row=1,column=0,sticky='w',pady=self.px(6))
        self.games_entry=ttk.Entry(form,textvariable=self.games,width=12,font=('Segoe UI',10));self.games_entry.grid(row=1,column=1,sticky='ew',pady=self.px(6))
        self.hint=ttk.Label(form,style='Muted.TLabel',wraplength=self.px(230))
        self.hotkey_label=ttk.Label(form);self.hotkeys=ttk.Label(form)
        self.start_key_label=ttk.Label(form);self.start_key_label.grid(row=3,column=0,sticky='w',pady=self.px(6))
        self.stop_key_label=ttk.Label(form);self.stop_key_label.grid(row=4,column=0,sticky='w',pady=self.px(6))
        self.shortcut_entries=[]
        for row,variable,display in ((3,self.start_key,self.start_display),(4,self.stop_key,self.stop_display)):
            entry=ttk.Entry(form,textvariable=display,state='readonly',width=12,font=('Segoe UI',10))
            entry.grid(row=row,column=1,sticky='ew',pady=self.px(6))
            entry.bind('<Button-1>',lambda event,v=variable:self.begin_capture(event,v))
            entry.bind('<KeyPress>',self.capture_key)
            entry.bind('<FocusOut>',self.end_capture)
            self.shortcut_entries.append(entry)
        root.bind('<Button-1>',self.cancel_capture,add='+')
        model_heading=ttk.Frame(form,style='Surface.TFrame')
        model_heading.grid(row=5,column=0,sticky='w',padx=(0,self.px(12)),pady=self.px(6))
        self.model_label=ttk.Label(model_heading,style='Card.TLabel');self.model_label.pack(side='left')
        self.model_help=ttk.Button(model_heading,image=self.theme.help_icon,style='Info.TButton',
                                   command=self.show_model_help,takefocus=True)
        self.model_help.pack(side='left',padx=(self.px(4),0))
        model_row=ttk.Frame(form,style='Surface.TFrame')
        model_row.grid(row=5,column=1,sticky='ew',pady=self.px(6))
        self.model_choices=[]
        for key in MODEL_FILES:
            choice=ttk.Radiobutton(model_row,text=key.replace('resnet','ResNet'),variable=self.model,value=key,command=self.save_settings)
            choice.grid(row=0,column=len(self.model_choices),sticky='w',padx=(0,self.px(10)));self.model_choices.append(choice)
        def fit_models(event):
            second=self.model_choices[1]
            stacked=event.width < sum(c.winfo_reqwidth() for c in self.model_choices)+self.px(20)
            second.grid_configure(row=1 if stacked else 0,column=0 if stacked else 1)
        model_row.bind('<Configure>',fit_models)
        self.hint.bind('<Configure>',lambda e:self.hint.configure(wraplength=max(self.px(130),e.width)))
        self.load_button=ttk.Button(main,command=self.load_models,style='Primary.TButton')
        self.load_button.grid(row=5,column=0,sticky='ew',pady=(0,self.px(8)))
        controls=ttk.Frame(main);controls.grid(row=6,column=0,sticky='ew',pady=(0,self.px(12)));controls.columnconfigure((0,1),weight=1,uniform='buttons')
        self.start_button=ttk.Button(controls,command=self.start,style='Primary.TButton',image=(self.theme.operation_icons['play'],'disabled',self.theme.disabled_play_icon),compound='left')
        self.start_button.grid(row=0,column=0,sticky='ew',padx=(0,self.px(6)))
        self.stop_button=ttk.Button(controls,command=self.stop,style='Secondary.TButton',state='disabled',image=(self.theme.stop_icon,'disabled',self.theme.disabled_stop_icon),compound='left')
        self.stop_button.grid(row=0,column=1,sticky='ew',padx=(self.px(6),0))
        options=ttk.Frame(main);options.grid(row=7,column=0,sticky='ew',pady=(0,self.px(12)));options.columnconfigure(0,weight=1)
        developer_row=ttk.Frame(options);developer_row.grid(row=0,column=0,sticky='w')
        self.record=ttk.Checkbutton(developer_row,variable=self.developer_mode,style='Page.TCheckbutton',command=self.save_settings)
        self.record.pack(side='left')
        self.developer_help=ttk.Button(developer_row,image=self.theme.help_icon,style='PageInfo.TButton',
                                       command=self.show_developer_help,takefocus=True)
        self.developer_help.pack(side='left',padx=(self.px(6),0))
        log_card=ttk.Frame(main,style='Card.TFrame',padding=self.px(12));log_card.grid(row=8,column=0,sticky='nsew')
        self.log_title=ttk.Label(log_card)
        self.log=tk.Text(log_card,height=1,width=1,wrap='word',bg=SURFACE,fg=UI_TEXT,font=('Segoe UI',10),relief='flat',borderwidth=0,
                         highlightthickness=0,state='disabled',padx=self.px(4),pady=self.px(4),spacing3=self.px(4))
        scrollbar=ttk.Scrollbar(log_card,command=self.log.yview);self.log.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right',fill='y',padx=(self.px(8),0));self.log.pack(fill='both',expand=True)
        footer=ttk.Frame(main);footer.grid(row=9,column=0,sticky='ew',pady=(self.px(8),0));footer.columnconfigure(0,weight=1)
        ttk.Label(footer,text='v'+VERSION.split('-')[0],style='Intro.TLabel').grid(row=0,column=0,sticky='w')
        def fit_page(event=None):
            width=self.viewport.winfo_width();height=self.viewport.winfo_height()
            requested=main.winfo_reqheight()
            self.viewport.itemconfigure(self.page_window,width=width,height=max(height,requested))
            self.viewport.configure(scrollregion=(0,0,width,max(height,requested)))
            if requested>height+2 and not self.page_scrollbar.winfo_manager():self.page_scrollbar.pack(side='right',fill='y')
            elif requested<=height+2 and self.page_scrollbar.winfo_manager():self.page_scrollbar.pack_forget();self.viewport.yview_moveto(0)
        self.viewport.bind('<Configure>',fit_page)
        main.bind('<Configure>',fit_page)
        root.after(150,fit_page)
        def page_wheel(event):
            if event.widget is not self.log and main.winfo_reqheight()>self.viewport.winfo_height():
                self.viewport.yview_scroll(-int(event.delta/120),'units');return 'break'
        root.bind('<MouseWheel>',page_wheel,add='+')
        self.start_listener=GlobalHotkey(lambda:self.messages.put(('start',None)), self.report_hotkey)
        self.stop_listener=GlobalHotkey(lambda:self.messages.put(('stop',None)), self.report_hotkey)
        self.start_listener.configure(value=self.start_key.get(),enabled=False)
        self.stop_listener.configure(value=self.stop_key.get(),enabled=False)
        self.translate(); self.set_controls(); self.start_listener.start(); self.stop_listener.start(); root.after(100,self.poll)

    def report_hotkey(self,key,registered,error):
        if not registered: self.messages.put(('hotkey_error', (key,error)))

    def configure_hotkeys(self):
        available=not self.capturing and not self.closing and self.help_dialog is None
        self.start_listener.configure(value=self.start_key.get(),enabled=available and bool(self.child)
                                      and self.run_state in ('ready','running','paused'))
        self.stop_listener.configure(value=self.stop_key.get(),enabled=available and bool(self.child))

    def begin_capture(self,event,variable):
        if self.child or self.closing or self.help_dialog is not None:return 'break'
        self.start_display.set(self.start_key.get());self.stop_display.set(self.stop_key.get())
        self.capturing=variable;self.capture_entry=event.widget
        self.configure_hotkeys();event.widget.focus_set()
        display=self.start_display if variable is self.start_key else self.stop_display
        display.set(self.tr('capture'))
        return 'break'

    def end_capture(self,event=None):
        if event is not None and event.widget is not self.capture_entry:return
        self.capturing=None;self.capture_entry=None
        self.start_display.set(self.start_key.get());self.stop_display.set(self.stop_key.get())
        self.configure_hotkeys()

    def cancel_capture(self,event):
        if self.capturing is not None and event.widget is not self.capture_entry:self.end_capture()

    def capture_key(self,event):
        if self.capturing is None: return 'break'
        value=captured_hotkey(event.keysym,event.state,event.keycode)
        if value:
            other=self.stop_key if self.capturing is self.start_key else self.start_key
            if hotkeys_conflict(value,other.get()):
                messagebox.showerror(self.tr('title'),self.tr('conflict'),parent=self.root)
            else:
                self.capturing.set(value); self.save_settings(); self.translate()
            self.end_capture()
        return 'break'

    def save_settings(self):
        (DATA/'settings.json').write_text(json.dumps({'language':self.language.get(),'games':self.games.get().strip(),'developer_mode':self.developer_mode.get(),'start_key':self.start_key.get(),'stop_key':self.stop_key.get(),'model':self.model.get()},ensure_ascii=False),encoding='utf8')

    def with_keys(self,text):
        return (text.replace('F8','{start-key}').replace('Esc','{stop-key}')
                .replace('{start-key}',self.start_key.get()).replace('{stop-key}',self.stop_key.get()))

    def translate(self):
        self.end_capture()
        self.root.title('Hololive Dreams — '+self.tr('title'))
        for widget,key in ((self.title,'title'),(self.instructions,'instructions'),(self.language_label,'language'),
                           (self.games_label,'games'),(self.record,'developer'),(self.start_button,'start'),
                           (self.stop_button,'stop'),(self.model_label,'model'),(self.load_button,'load'),
                           (self.start_key_label,'start_key'),(self.stop_key_label,'stop_key')):
            widget.configure(text=self.tr(key))
        for key,choice in zip(MODEL_FILES,self.model_choices):choice.configure(text=self.tr(key))
        self.hotkeys.configure(text=self.tr('shortcut'))
        self.render_status()
        self.count.configure(text=self.completion_text(self.completed))
        self.close_model_help()
        self.save_settings()

    def tr(self,key):
        return self.with_keys(UI[self.language.get()][key])

    def render_status(self):
        color='#B42318' if self.run_state=='error' else '#F15B60'
        self.status.configure(text=self.tr(self.run_state),foreground=color,wraplength=self.px(402))

    def set_controls(self):
        available=not self.closing and self.help_dialog is None
        unlocked=not self.child and available
        self.load_button.configure(state='normal' if unlocked else 'disabled')
        self.start_button.configure(state='normal' if available and self.child and self.run_state=='ready' else 'disabled')
        self.stop_button.configure(state='normal' if available and self.child and self.run_state!='stopping' else 'disabled')
        for widget in (self.games_entry,self.record,*self.model_choices):
            widget.configure(state='normal' if unlocked else 'disabled')
        self.model_help.configure(state='normal' if not self.closing and self.run_state not in ('running','starting','waiting_focus') else 'disabled')
        self.developer_help.configure(state='normal' if not self.closing else 'disabled')
        self.configure_hotkeys()

    def set_state(self,state):
        if state not in UI[self.language.get()]:return
        self.run_state=state
        self.render_status()
        self.set_controls()

    def show_model_help(self):
        if self.closing:return
        if self.help_dialog is not None and self.help_dialog.winfo_exists():
            self.help_dialog.lift();return
        self.end_capture()
        dialog=tk.Toplevel(self.root);dialog.withdraw();self.help_dialog=dialog
        dialog.title(self.tr('help'));dialog.transient(self.root);dialog.resizable(False,False);dialog.configure(bg=BG)
        panel=ttk.Frame(dialog,padding=self.px(20));panel.pack(fill='both',expand=True)
        wrap=min(self.px(420),self.root.winfo_screenwidth()-self.px(100))
        for name in ('resnet18','resnet101'):
            card=ttk.Frame(panel,style='Card.TFrame',padding=self.px(16));card.pack(fill='x',pady=(0,self.px(12)))
            ttk.Label(card,text=self.tr(name),style='Card.TLabel',font=('Segoe UI',11,'bold')).pack(anchor='w')
            ttk.Label(card,text=self.tr('help18' if name=='resnet18' else 'help101'),style='CardMuted.TLabel',
                      wraplength=wrap,justify='left').pack(anchor='w',pady=(self.px(8),0))
        ttk.Button(panel,text=self.tr('close'),style='Primary.TButton',command=self.close_model_help).pack(anchor='e')
        dialog.protocol('WM_DELETE_WINDOW',self.close_model_help)
        dialog.bind('<Escape>',lambda _:self.close_model_help())
        dialog.update_idletasks()
        width,height=dialog.winfo_reqwidth(),dialog.winfo_reqheight()
        x=max(0,min(self.root.winfo_rootx()+(self.root.winfo_width()-width)//2,self.root.winfo_screenwidth()-width))
        y=max(0,min(self.root.winfo_rooty()+(self.root.winfo_height()-height)//2,self.root.winfo_screenheight()-height))
        dialog.geometry(f'{width}x{height}+{x}+{y}');dialog.deiconify()
        self.set_controls()

    def close_model_help(self):
        if self.help_dialog is not None:
            self.help_dialog.destroy();self.help_dialog=None
        self.set_controls()

    def diagnostic_base(self):
        folder=DATA/'sessions';folder.mkdir(parents=True,exist_ok=True)
        return folder

    def show_developer_help(self):
        if self.closing:return
        if self.help_dialog is not None and self.help_dialog.winfo_exists():
            self.help_dialog.lift();return
        self.end_capture()
        dialog=tk.Toplevel(self.root);dialog.withdraw();self.help_dialog=dialog
        dialog.title(self.tr('developer_help'));dialog.transient(self.root)
        dialog.resizable(False,False);dialog.configure(bg=BG)
        panel=ttk.Frame(dialog,padding=self.px(20));panel.pack(fill='both',expand=True)
        wrap=min(self.px(480),self.root.winfo_screenwidth()-self.px(100))
        card=ttk.Frame(panel,style='Card.TFrame',padding=self.px(16));card.pack(fill='x',pady=(0,self.px(12)))
        ttk.Label(card,text=self.tr('developer'),font=('Segoe UI',11,'bold')).pack(anchor='w')
        for key in ('diagnostic_body','diagnostic_folder'):
            ttk.Label(card,text=self.tr(key),style='CardMuted.TLabel',wraplength=wrap,justify='left').pack(anchor='w',pady=(self.px(12),0))
        folder=self.diagnostic_base()
        link=ttk.Label(card,text=str(folder),foreground='#0067C0',font=('Segoe UI',10,'underline'),
                       cursor='hand2',wraplength=wrap,takefocus=True)
        link.pack(anchor='w',pady=(self.px(6),0))
        link.bind('<Button-1>',lambda _:os.startfile(str(folder)))
        link.bind('<Return>',lambda _:os.startfile(str(folder)))
        ttk.Label(card,text=self.tr('diagnostic_detail'),style='CardMuted.TLabel',wraplength=wrap,justify='left').pack(anchor='w',pady=(self.px(12),0))
        project=ttk.Frame(panel,style='Card.TFrame',padding=self.px(16));project.pack(fill='x',pady=(0,self.px(12)))
        ttk.Label(project,text=self.tr('project'),font=('Segoe UI',11,'bold')).pack(anchor='w')
        link=ttk.Label(project,text=PROJECT_URL,foreground='#0067C0',font=('Segoe UI',10,'underline'),
                       cursor='hand2',wraplength=wrap,takefocus=True)
        link.pack(anchor='w',pady=(self.px(12),0))
        link.bind('<Button-1>',lambda _:webbrowser.open(PROJECT_URL))
        link.bind('<Return>',lambda _:webbrowser.open(PROJECT_URL))
        ttk.Button(panel,text=self.tr('close'),style='Primary.TButton',command=self.close_model_help).pack(anchor='e')
        dialog.protocol('WM_DELETE_WINDOW',self.close_model_help)
        dialog.bind('<Escape>',lambda _:self.close_model_help())
        dialog.update_idletasks()
        width,height=dialog.winfo_reqwidth(),dialog.winfo_reqheight()
        x=max(0,min(self.root.winfo_rootx()+(self.root.winfo_width()-width)//2,self.root.winfo_screenwidth()-width))
        y=max(0,min(self.root.winfo_rooty()+(self.root.winfo_height()-height)//2,self.root.winfo_screenheight()-height))
        dialog.geometry(f'{width}x{height}+{x}+{y}');dialog.deiconify()
        self.set_controls()

    def completion_text(self, completed, target=None):
        target=self.games.get() if target is None else target
        return self.tr('completed').format(completed=completed,target=target)

    def load_models(self):
        if self.child or self.closing or self.help_dialog is not None:return
        try: games = parse_games(self.games.get().strip())
        except ValueError:
            messagebox.showerror(self.tr('title'), self.tr('invalid_games'), parent=self.root); return
        self.save_settings()
        self.session_developer=self.developer_mode.get()
        if self.session_developer:
            self.session = self.diagnostic_base() / (time.strftime('%Y%m%d-%H%M%S')+'-'+str(time.time_ns())[-6:])
            self.session.mkdir(parents=True)
        else:self.session = Path(tempfile.mkdtemp(prefix='cooking-run-'))
        self.log_path = self.session / 'launcher.log'; self.stop_path = self.session / 'stop'
        self.start_path=self.session/'start.json';self.state_path=self.session/'state.json'
        self.state_revision=None;self.completed=0
        self.toggle_path=self.session/'toggle'; self.toggle_count=0
        self.toggle_path.write_text('0',encoding='ascii')
        self.stream = self.log_path.open('w', encoding='utf8'); self.log_position = 0
        args = ['--worker', '--games', str(games), '--output', str(self.session/'runs'), '--control-file', str(self.stop_path)]
        args += ['--start-key',self.start_key.get(),'--stop-key',self.stop_key.get(),'--model',self.model.get()]
        args += ['--wait-for-start','--state-file',str(self.state_path)]
        if self.session_developer: args.append('--developer-mode')
        command = [sys.executable] + args if getattr(sys, 'frozen', False) else [sys.executable, str(ROOT/'gui.py')] + args
        try:
            self.child = subprocess.Popen(command, cwd=ROOT, stdout=self.stream, stderr=subprocess.STDOUT,
                                          env={**os.environ,'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'},
                                          creationflags=subprocess.CREATE_NO_WINDOW)
        except OSError as e:
            self.stream.close(); self.stream=None; self.append(str(e)); self.set_state('error'); return
        self.set_state('loading')
        self.count.configure(text=self.completion_text(0,games))
        self.configure_hotkeys()

    def start(self):
        if not self.child or self.run_state!='ready' or self.help_dialog is not None or self.closing:return
        request_game_foreground()
        pending=self.start_path.with_suffix('.pending')
        pending.write_text(json.dumps({'start':True}),encoding='utf8')
        pending.replace(self.start_path)
        self.set_state('starting')

    def append(self, text):
        self.log.configure(state='normal'); self.log.insert('end', text+'\n')
        if int(self.log.index('end-1c').split('.')[0])>500:self.log.delete('1.0','100.0')
        self.log.see('end'); self.log.configure(state='disabled')

    def stop(self):
        if self.child:
            self.stop_path.touch(); self.set_state('stopping')

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
            if event=='start' and not self.closing and self.capturing is None and self.help_dialog is None:
                if self.run_state=='ready':self.start()
                elif self.child and self.run_state in ('running','paused'):self.toggle()
            elif event=='stop': self.stop()
            elif event=='error': self.append(value)
            elif event=='hotkey_error':self.append(self.tr('hotkey_error').format(key=value[0],error=value[1]))
        if self.child:
            try:
                with self.log_path.open(encoding='utf8', errors='replace') as f:
                    f.seek(self.log_position); text=f.read(); self.log_position=f.tell()
                if text:
                    self.append(text.rstrip())
                if self.state_path.exists() and not self.stop_path.exists():
                    state=json.loads(self.state_path.read_text(encoding='utf8'))
                    if state.get('revision')!=self.state_revision:
                        self.state_revision=state.get('revision')
                        self.set_state(state['state'])
                summaries = list((self.session/'runs').glob('session-*/summary.json'))
                if summaries:
                    data=json.loads(summaries[-1].read_text(encoding='utf8'))
                    self.completed=len(data['games']);self.count.configure(text=self.completion_text(self.completed))
            except (OSError, ValueError, KeyError): pass
            code = self.child.poll()
            if code is not None:
                self.stream.close(); self.stream=None; self.child=None
                if self.session_developer:
                    archives=list(self.session.glob('*.zip'))
                    if archives:self.append(self.tr('diagnostic_saved').format(path=archives[-1]))
                else:
                    # Only this launch's unique temporary directory is disposable.
                    if self.session.parent==Path(tempfile.gettempdir()) and self.session.name.startswith('cooking-run-'):
                        shutil.rmtree(self.session,ignore_errors=True)
                self.set_state('finished' if code==0 else 'error')
                self.configure_hotkeys()
                if self.closing: self.destroy(); return
        self.root.after(100, self.poll)

    def destroy(self):
        if self.help_dialog is not None:self.help_dialog.destroy();self.help_dialog=None
        for job in self.root.tk.call('after','info'):
            self.root.after_cancel(job)
        self.start_listener.close(); self.stop_listener.close(); self.root.destroy()

    def close(self):
        if self.child:
            self.closing=True; self.stop()
        else: self.destroy()


def publish_state(path,state,**details):
    if path is None:return
    pending=path.with_suffix('.pending')
    pending.write_text(json.dumps({'state':state,'revision':time.time_ns(),**details},ensure_ascii=False),encoding='utf8')
    for attempt in range(20):
        try:pending.replace(path);return
        except PermissionError:
            if attempt==19:raise
            time.sleep(.01)


def wait_for_start(start_file,stop_file):
    """No capture, native hotkey polling or game adapter before explicit start."""
    while not stop_file.exists():
        try:
            if json.loads(start_file.read_text(encoding='utf8')).get('start') is True:
                return not stop_file.exists()
        except (OSError,ValueError,AttributeError):pass
        time.sleep(.05)
    return False


def worker():
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker', action='store_true'); parser.add_argument('--games', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True); parser.add_argument('--control-file', type=Path, required=True)
    parser.add_argument('--developer-mode', action='store_true')
    parser.add_argument('--start-key',default='F8'); parser.add_argument('--stop-key',default='Esc'); parser.add_argument('--autostart',action='store_true')
    parser.add_argument('--model', choices=tuple(MODEL_FILES), default=DEFAULT_MODEL)
    parser.add_argument('--wait-for-start',action='store_true')
    parser.add_argument('--state-file',type=Path)
    parser.add_argument('--check-model-only',action='store_true',help='Load and verify the chosen model, then exit without game capture or input.')
    parser.add_argument('--check-result-screen',type=Path,help='Read and archive a saved result image without loading models or sending input.')
    args=parser.parse_args()
    import diagnostic_store as diagnostics
    previous=os.environ.get('COOKING_DIAGNOSTICS')
    store=diagnostics.configure(args.output.parent,args.developer_mode,version=VERSION,model=args.model,requested_games=args.games)
    error=None
    try:
        if args.check_result_screen:return check_result_screen(args)
        return run_worker(args,store)
    except BaseException:
        import traceback
        error=traceback.format_exc();raise
    finally:
        if store is not None:
            try:store.finish(error)
            except Exception as packing_error:
                print('Diagnostic archive failed: '+str(packing_error),flush=True)
        diagnostics._active=None
        if previous is None:os.environ.pop('COOKING_DIAGNOSTICS',None)
        else:os.environ['COOKING_DIAGNOSTICS']=previous


def check_result_screen(args):
    import cv2
    import diagnostic_store as diagnostics
    from result_reader import ResultReader
    from screen_state import ScreenState
    args.output.parent.mkdir(parents=True,exist_ok=True)
    frame=cv2.imread(str(args.check_result_screen))
    if frame is None:raise ValueError('Result image could not be read')
    h,w=frame.shape[:2];canonical=cv2.resize(frame[max(0,h-round(w*9/16)):],(1536,864))
    result=ResultReader().read(canonical,ScreenState().classify(canonical))
    result.update(source='offline_result_check',game_inputs_sent=0,confirmation='offline_still_image')
    directory=args.output/'standalone-offline-result-check'
    diagnostics.save_frame(directory/'final.jpg',frame)
    diagnostics.save_round(directory,result)
    (args.output.parent/'result-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')


def run_worker(args,store=None):
    selected_point_model=point_model(ROOT,args.model)
    # Windowed executables may have no Python standard streams, even when
    # their native handles were redirected by the launcher.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if sys.stdout is None:
        sys.stdout=(args.output.parent/'launcher.log').open('a', encoding='utf8', buffering=1)
    if sys.stderr is None: sys.stderr=sys.stdout
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf8',errors='backslashreplace',line_buffering=True)
    os.environ['COOKING_STOP_FILE']=str(args.control_file)
    os.environ['COOKING_TOGGLE_FILE']=str(args.control_file.with_name('toggle'))
    os.environ['COOKING_RECORD_VIDEO']='0'
    os.environ['COOKING_START_KEY']=args.start_key; os.environ['COOKING_STOP_KEY']=args.stop_key
    sys.path.insert(0, str(BOT))
    print('Loading Collect Cooking models… '+args.model, flush=True)
    publish_state(args.state_file,'loading',model=args.model)
    import standalone
    if args.control_file.exists():print('Canceled before loading.',flush=True);return
    try:checked=standalone.load_models(str(selected_point_model))
    except InterruptedError:
        if args.control_file.exists():print('Canceled during model loading.',flush=True);return
        raise
    # Exercise the real CUDA/CPU kernels before reporting readiness. Synthetic
    # arrays never read the desktop, advance a game or issue native input.
    import numpy as np
    checked.point_classifier.classify([np.zeros((64,64,3),dtype=np.uint8)])
    checked.classifier.classify([np.zeros((64,64,3),dtype=np.uint8)])
    checked.surface(np.zeros((280,448,3),dtype=np.uint8))
    checked.supplement.model.surface(np.zeros((280,448,3),dtype=np.uint8))
    if checked.device=='directml':
        for size in (112,160):
            checked.surface(np.zeros((size,size,3),dtype=np.uint8))
            checked.supplement.model.surface(np.zeros((size,size,3),dtype=np.uint8))
    if store is not None:
        store.details.update(device=checked.device,inference=checked.runtime.info)
    if args.control_file.exists():print('Canceled after loading.',flush=True);return
    if args.check_model_only:
        import hashlib
        from radius_policy import PROFILE
        classifier=checked.point_classifier
        if classifier is None or classifier.architecture!=args.model or not checked.human_point_model:
            raise RuntimeError('Selected point classifier did not load correctly')
        report={'passed':True,'model':args.model,'loaded_architecture':classifier.architecture,
                'parameters':classifier.parameters,'labels':classifier.labels,
                'point_model':str(selected_point_model),'sha256':hashlib.sha256(selected_point_model.read_bytes()).hexdigest(),
                'capture_implementation':standalone.Recording.__module__,'human_point_model':checked.human_point_model,'icon_template_count':len(checked.icons.bank),
                'supplement_mode':'selected_fallback','supplement_shares_classifier':checked.supplement.model.point_classifier is classifier,
                'radius_profile':PROFILE,'warmup_completed':True,'game_inputs_sent':0,
                'inference':checked.runtime.info,'torch_imported':any(name=='torch' or name.startswith('torch.') for name in sys.modules)}
        (args.output.parent/'model-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps(report,ensure_ascii=False),flush=True)
        return
    if args.control_file.exists(): print('Canceled before starting.', flush=True); return
    if args.wait_for_start:
        publish_state(args.state_file,'ready',model=args.model)
        print('Model ready. Waiting for an explicit start request.',flush=True)
        if not wait_for_start(args.control_file.with_name('start.json'),args.control_file):
            print('Canceled without starting the game.',flush=True);return
    sys.argv=['standalone.py','--games',str(args.games),'--output',str(args.output),'--point-model',str(selected_point_model)]
    if args.autostart: sys.argv.append('--autostart')
    if args.wait_for_start:sys.argv.append('--wait-for-focus')
    standalone.main(model=checked,status_callback=lambda state:publish_state(args.state_file,state,model=args.model))


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
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('HololiveDreams.CollectCookingAuto')
        except (AttributeError, OSError): pass
        CookingApp(tk.Tk()).root.mainloop()
