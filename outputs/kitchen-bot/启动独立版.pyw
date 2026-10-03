"""Graphical launcher; opens no terminal and keeps a local diagnostic log."""
import subprocess,sys
from pathlib import Path
import tkinter as tk

root_path=Path(__file__).resolve().parent
window=tk.Tk();window.title('Kitchen Bot Launcher');window.geometry('620x300')
status=tk.StringVar(value='Ready to launch. Start, return to the game, then press F8.')
child=None;stream=None
tk.Label(window,text='食材妙厨房独立测试',font=('Microsoft YaHei',17)).pack(pady=12)
tk.Label(window,text='F8: start / pause    Esc: stop\nKeep the game in the foreground. Video and logs are saved in runs/.',justify='left').pack(pady=8)
tk.Label(window,textvariable=status,wraplength=580,justify='left').pack(pady=8)
batch_row=tk.Frame(window);batch_row.pack(pady=3)
tk.Label(batch_row,text='本次測試局數：').pack(side='left')
games=tk.StringVar(value='5')
tk.Spinbox(batch_row,from_=1,to=5,textvariable=games,width=4,state='readonly').pack(side='left')
def start():
    global child,stream
    if child is not None and child.poll() is None:return
    stream=(root_path/'launcher.log').open('w',encoding='utf8')
    point_model='../kitchen-labeler/point-classifier-human.pt' if (root_path.parent/'kitchen-labeler/point-classifier-human.pt').exists() else 'point-classifier.pt'
    child=subprocess.Popen([sys.executable,str(root_path/'standalone.py'),'--point-model',point_model,'--games',games.get()],cwd=root_path,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    status.set('Loading models. Return to game and press F8 after Ready appears in launcher.log.')
    window.after(1000,monitor)
def monitor():
    if child is None:return
    code=child.poll()
    if code is not None:
        if stream:stream.close()
        status.set(f'Finished (exit {code}). See launcher.log and runs/.');return
    try:
        lines=(root_path/'launcher.log').read_text(encoding='utf8').splitlines()
        if lines:status.set(lines[-1][-260:])
    except OSError:pass
    window.after(1000,monitor)
def close():
    if child is not None and child.poll() is None:
        status.set('Stop with Esc in the game before closing the launcher.');return
    if stream and not stream.closed:stream.close()
    window.destroy()
tk.Button(window,text='Start',command=start,width=16).pack(pady=10)
window.protocol('WM_DELETE_WINDOW',close)
window.mainloop()
