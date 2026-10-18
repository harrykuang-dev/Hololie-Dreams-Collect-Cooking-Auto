"""User-launched local player with continuous recording and fast frame access.

F8 starts/pauses, Escape exits. Never clicks while another window has focus.
--replay checks recorded images without creating a capture or input adapter.
"""
import os,argparse,ctypes as C,json,queue,threading,time,hashlib,shutil
from ctypes import wintypes as W
from pathlib import Path
import cv2,numpy as np
from perception import Perception
from planner import Planner
from motion import adjusted_point
from fast_followup import select_followup
from session_flow import advance_to_order
from motion_click import choose_motion_food
from guarded_local_relocation import choose_relocated_food
import collections
from supplemental_food import SelectedSupplement
from app_settings import StartHotkey, stop_hotkey_pressed
from game_window import GAME_TITLE

class BitmapHeader(C.Structure):
    _fields_=[('size',W.DWORD),('width',W.LONG),('height',W.LONG),
              ('planes',W.WORD),('bits',W.WORD),('compression',W.DWORD),
              ('image_size',W.DWORD),('xppm',W.LONG),('yppm',W.LONG),
              ('used',W.DWORD),('important',W.DWORD)]

class MouseInput(C.Structure):
    _fields_=[('dx',W.LONG),('dy',W.LONG),('data',W.DWORD),
              ('flags',W.DWORD),('time',W.DWORD),('extra',C.c_size_t)]
class KeyboardInput(C.Structure):
    _fields_=[('vk',W.WORD),('scan',W.WORD),('flags',W.DWORD),
              ('time',W.DWORD),('extra',C.c_size_t)]
class InputUnion(C.Union):
    _fields_=[('mouse',MouseInput),('keyboard',KeyboardInput)]
class Input(C.Structure):
    _fields_=[('type',W.DWORD),('value',InputUnion)]

class Desktop:
    def __init__(self,title):
        self.u=C.WinDLL('user32',use_last_error=True)
        self.start_hotkey=StartHotkey()
        self.toggle_seen=self.toggle_sequence()
        self.g=C.WinDLL('gdi32',use_last_error=True)
        def bind(lib,name,args,result):
            f=getattr(lib,name);f.argtypes=args;f.restype=result;return f
        bind(self.u,'FindWindowW',[W.LPCWSTR,W.LPCWSTR],W.HWND)
        bind(self.u,'GetForegroundWindow',[],W.HWND)
        bind(self.u,'GetClientRect',[W.HWND,C.POINTER(W.RECT)],W.BOOL)
        bind(self.u,'ClientToScreen',[W.HWND,C.POINTER(W.POINT)],W.BOOL)
        bind(self.u,'GetDC',[W.HWND],W.HDC)
        bind(self.u,'ReleaseDC',[W.HWND,W.HDC],C.c_int)
        bind(self.u,'GetAsyncKeyState',[C.c_int],C.c_short)
        bind(self.u,'SetCursorPos',[C.c_int,C.c_int],W.BOOL)
        bind(self.u,'SendInput',[W.UINT,C.POINTER(Input),C.c_int],W.UINT)
        bind(self.u,'IsWindow',[W.HWND],W.BOOL)
        bind(self.u,'IsIconic',[W.HWND],W.BOOL)
        bind(self.g,'CreateCompatibleDC',[W.HDC],W.HDC)
        bind(self.g,'CreateDIBSection',[W.HDC,C.POINTER(BitmapHeader),W.UINT,C.POINTER(C.c_void_p),W.HANDLE,W.DWORD],W.HBITMAP)
        bind(self.g,'SelectObject',[W.HDC,W.HANDLE],W.HANDLE)
        bind(self.g,'BitBlt',[W.HDC,C.c_int,C.c_int,C.c_int,C.c_int,W.HDC,C.c_int,C.c_int,W.DWORD],W.BOOL)
        bind(self.g,'DeleteObject',[W.HANDLE],W.BOOL)
        bind(self.g,'DeleteDC',[W.HDC],W.BOOL)
        try:self.u.SetProcessDpiAwarenessContext(C.c_void_p(-4))
        except AttributeError:self.u.SetProcessDPIAware()
        self.hwnd=self.u.FindWindowW(None,title)
        if not self.hwnd:raise RuntimeError('Game window not found: '+title)
        if self.u.IsIconic(self.hwnd):raise RuntimeError('Game window minimized: '+title)
        rect=W.RECT()
        if not self.u.GetClientRect(self.hwnd,C.byref(rect)):raise C.WinError(C.get_last_error())
        self.w,self.h=rect.right,rect.bottom
        if self.w<640 or self.h<360 or not 1.65<self.w/self.h<1.90:raise RuntimeError('Use a normal 16:9 game window')
        self.screen=self.u.GetDC(None);self.memory=self.g.CreateCompatibleDC(self.screen)
        header=BitmapHeader(C.sizeof(BitmapHeader),self.w,-self.h,1,32,0,self.w*self.h*4,0,0,0,0)
        self.bits=C.c_void_p()
        self.bitmap=self.g.CreateDIBSection(self.screen,C.byref(header),0,C.byref(self.bits),None,0)
        if not self.bitmap or not self.bits.value:raise RuntimeError('Could not create screenshot buffer')
        self.old=self.g.SelectObject(self.memory,self.bitmap)
        self.buffer=(C.c_ubyte*(self.w*self.h*4)).from_address(self.bits.value)
    def should_stop(self):
        stop_file=os.environ.get('COOKING_STOP_FILE')
        return bool(stop_file and Path(stop_file).exists()) or stop_hotkey_pressed(os.environ.get('COOKING_STOP_KEY','Esc'),self.u.GetAsyncKeyState)
    def toggle_sequence(self):
        path=os.environ.get('COOKING_TOGGLE_FILE')
        if not path:return 0
        try:return int(Path(path).read_text(encoding='ascii'))
        except (OSError,ValueError):return getattr(self,'toggle_seen',0)
    def should_toggle(self):
        if os.environ.get('COOKING_TOGGLE_FILE'):
            count=self.toggle_sequence();changed=(count-self.toggle_seen)%2!=0
            self.toggle_seen=count
            return changed
        return self.start_hotkey.poll(os.environ.get('COOKING_START_KEY','F8'),self.u.GetAsyncKeyState)
    def focused(self):
        return self.u.IsWindow(self.hwnd) and not self.u.IsIconic(self.hwnd) and self.u.GetForegroundWindow()==self.hwnd
    def origin(self):
        rect=W.RECT();point=W.POINT(0,0)
        if not self.u.GetClientRect(self.hwnd,C.byref(rect)) or (rect.right,rect.bottom)!=(self.w,self.h):raise RuntimeError('Game window resized or closed; restart the program')
        if not self.u.ClientToScreen(self.hwnd,C.byref(point)):raise C.WinError(C.get_last_error())
        return point.x,point.y
    def capture(self):
        if not self.focused():return None
        x,y=self.origin()
        if not self.g.BitBlt(self.memory,0,0,self.w,self.h,self.screen,x,y,0x00CC0020|0x40000000):raise C.WinError(C.get_last_error())
        return np.frombuffer(self.buffer,dtype=np.uint8).reshape(self.h,self.w,4)[:,:,:3].copy()
    def click(self,x,y):
        if self.should_stop() or not self.focused():return False
        if not 0<=x<self.w or not 0<=y<self.h:raise RuntimeError('Click is outside the game')
        ox,oy=self.origin()
        cursor_started=time.monotonic()
        if not self.u.SetCursorPos(ox+x,oy+y):raise C.WinError(C.get_last_error())
        # Unity samples its pointer during the game loop. Give it a render
        # frame to see the move before the button-down arrives.
        time.sleep(.025)
        if self.should_stop() or not self.focused():return False
        down=Input(0,InputUnion(mouse=MouseInput(0,0,0,2,0,0)))
        up=Input(0,InputUnion(mouse=MouseInput(0,0,0,4,0,0)))
        mouse_down_started=time.monotonic()
        if self.u.SendInput(1,C.byref(down),C.sizeof(Input))!=1:raise C.WinError(C.get_last_error())
        try:time.sleep(.025)
        finally:
            if self.u.SendInput(1,C.byref(up),C.sizeof(Input))!=1:raise C.WinError(C.get_last_error())
        self.last_click_profile={'cursor_move_started':cursor_started,'mouse_down_dispatch_started':mouse_down_started,'mouse_up_completed':time.monotonic()}
        return True
    def close(self):
        self.g.SelectObject(self.memory,self.old);self.g.DeleteObject(self.bitmap)
        self.g.DeleteDC(self.memory);self.u.ReleaseDC(None,self.screen)

from async_recording import Recording
import diagnostic_store as diagnostics

class FrameWriter:
    def __init__(self):
        self.thread=None;self.error=None
        if diagnostics.mode()!='legacy':return
        self.jobs=queue.Queue();self.error=None
        self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
    def run(self):
        while True:
            job=self.jobs.get()
            try:
                if job is None:return
                file,frame=job
                if not cv2.imwrite(str(file),frame,[cv2.IMWRITE_JPEG_QUALITY,92] if file.suffix.lower()=='.jpg' else [cv2.IMWRITE_PNG_COMPRESSION,1]):raise RuntimeError('Could not save '+str(file))
            except Exception as e:self.error=e
            finally:self.jobs.task_done()
    def save(self,file,frame):
        if diagnostics.save_frame(file,frame):return
        if self.error:raise self.error
        self.jobs.put((file,frame.copy()))
    def close(self):
        if self.thread is not None:self.jobs.put(None);self.jobs.join();self.thread.join()

def replay(file,model):
    frame=cv2.imread(str(file))
    if frame is None:raise ValueError('Image cannot be read')
    result=model.analyze(frame,fast=True);planner=Planner()
    return {'action':planner.propose(result),'status':planner.status(),'perception':result}

def play(args,model,autostart=False,status_callback=None):
    directory=args.output/('standalone-'+str(int(time.time()*1000)))
    directory.mkdir(parents=True,exist_ok=True)
    desktop=Desktop(args.title);recording=Recording(desktop,directory,args.fps);writer=FrameWriter();planner=Planner()
    print('Ready. Focus the game at its Order screen, then press F8. F8 pauses; Escape exits.',flush=True)
    print('Recording/log directory: '+str(directory.resolve()),flush=True)
    paused=not autostart;fresh_after=time.monotonic();number=0;last_report=0;last_frame=None;started=time.monotonic() if autostart else None;natural_end=False;last_lossless=0
    if autostart:print('Continuing the next game automatically.',flush=True)
    if status_callback:status_callback('running' if autostart else 'paused')
    try:
        with diagnostics.open_log(directory/'decisions.jsonl') as log, diagnostics.open_log(directory/'inputs.jsonl') as inputs:
            while True:
                if desktop.should_stop():break
                if desktop.should_toggle():
                    paused=not paused;fresh_after=time.monotonic();print('Paused' if paused else 'Running',flush=True)
                    if status_callback:status_callback('paused' if paused else 'running')
                    if not paused and started is None:started=time.monotonic()
                if started is not None and time.monotonic()-started>args.seconds:print('Run time limit reached');break
                if not desktop.focused():
                    if not paused:
                        paused=True;print('Focus changed; paused. Return to game and press F8.',flush=True)
                        if status_callback:status_callback('paused')
                if paused:time.sleep(.05);continue
                packet=recording.frame_after(fresh_after)
                if packet is None:continue
                stamp,frame=packet;last_frame=frame
                begin=time.monotonic()
                perception=model.analyze(frame,fast=True);perception_completed=time.monotonic()
                action=model.supplement.propose(planner,perception,frame);planning_completed=time.monotonic();number+=1
                followup_base=None
                click_point=(action.get('x'),action.get('y'))
                decision_profile={'capture':recording.packet_profile(stamp),'frame_age_after_analysis_ms':(time.monotonic()-stamp)*1000,'perception_ms':(perception_completed-begin)*1000,'planner_and_supplement_ms':(planning_completed-perception_completed)*1000}
                if action['kind']=='food':
                    latest_wait_started=time.perf_counter()
                    latest=recording.frame_after(stamp+.05,timeout=.06) or recording.latest_packet()
                    decision_profile['latest_packet_wait_ms']=(time.perf_counter()-latest_wait_started)*1000
                    if latest:
                        decision_profile['latest_capture']=recording.packet_profile(latest[0])
                        choose_started=time.perf_counter()
                        chosen=choose_motion_food(planner.food_options,model,frame,stamp,latest,planner.inventory,planner.order,supplement=model.supplement)
                        decision_profile['motion_and_validation_ms']=(time.perf_counter()-choose_started)*1000
                        original_choice=chosen
                        relocation_started=time.perf_counter()
                        chosen=choose_relocated_food(chosen,planner.food_options,model,planner,perception,latest,recording.frame_after)
                        if chosen is not original_choice:
                            decision_profile['local_relocation_ms']=(time.perf_counter()-relocation_started)*1000
                        if chosen.get('execution_packet'):
                            latest=chosen['execution_packet']
                            planner.inventory=collections.Counter(chosen['refreshed_inventory'])
                            decision_profile['latest_capture']=recording.packet_profile(latest[0])
                        action=chosen['action'];click_point=chosen['point'];planner.planned=chosen['planned']
                        validation_file=str((directory/f'frame-{number:05}-validated.jpg').resolve())
                        writer.save(Path(validation_file),latest[1])
                        if action['kind']=='wait' and action.get('motion_attempts') and time.monotonic()-last_lossless>=args.diagnostic_lossless_interval:
                            last_lossless=time.monotonic()
                            old_lossless=directory/f'frame-{number:05}-diagnostic-old.png'
                            new_lossless=directory/f'frame-{number:05}-diagnostic-latest.png'
                            writer.save(old_lossless,frame);writer.save(new_lossless,latest[1])
                            decision_profile['lossless_frames']={'old':str(old_lossless.resolve()),'latest':str(new_lossless.resolve())}
                        for attempt in action.get('motion_attempts',[]):
                            if attempt.get('validation'):attempt['validation']['frame']=validation_file
                        if action['kind']=='food':
                            followup=None if action.get('source') in ['supplement','local_relocation'] else select_followup(action,perception,planner.inventory)
                            if followup:
                                tracked_followup=adjusted_point(frame,stamp,latest[1],latest[0],(followup['x'],followup['y']),lead=0)
                                inputs.write(json.dumps({'decision':number,'kind':'followup_check','stage':'baseline_tracking','accepted':tracked_followup is not None,'label':followup['label'],'point':[followup['x'],followup['y']],'frame_age_ms':round((latest[0]-stamp)*1000),'at':round(time.time()*1000)})+'\n');inputs.flush()
                                if tracked_followup is not None:followup_base=(latest[0],latest[1],tracked_followup)
                    else:
                        action={'kind':'wait','reason':'latest frame unavailable'};planner.planned=None
                if action['kind']=='shuffle':
                    shuffle_packet=recording.latest_packet()
                    shuffle_guard={'minimum_interval_s':5.0,'elapsed_s':time.monotonic()-planner.shuffle_at}
                    if shuffle_packet:
                        shuffle_view,_,_=model.normalize(shuffle_packet[1])
                        shuffle_phase=model.screen_state.classify(shuffle_view)['phase']
                        from shuffle_state import shuffle_state
                        shuffle_guard.update(shuffle_state(shuffle_view,shuffle_phase),capture_age_ms=(time.monotonic()-shuffle_packet[0])*1000)
                    allowed=(shuffle_packet is not None and shuffle_guard.get('ready',False)
                             and shuffle_guard['elapsed_s']>=5.0 and shuffle_guard.get('capture_age_ms',999)<250)
                    action['shuffle_guard']=shuffle_guard
                    if not allowed:action={'kind':'wait','reason':'minimum shuffle interval or button not ready','shuffle_guard':shuffle_guard}
                file=directory/f'frame-{number:05}.jpg';writer.save(file,frame)
                log.write(json.dumps({'frame':str(file.resolve()),'at':round(time.time()*1000),'action':action,'status':planner.status(),'perception':perception,'analysis_ms':round((time.monotonic()-begin)*1000),'timing_diagnostics':decision_profile})+'\n');log.flush()
                if time.monotonic()-last_report>5:print(json.dumps(planner.status()),flush=True);last_report=time.monotonic()
                if action['kind']=='stop':
                    natural_end=perception.get('phase') in ['burst','ending','results']
                    print('Gameplay ended or unrecognized screen; stopped.',flush=True)
                    time.sleep(2)
                    final=recording.frame_after(time.monotonic()-.2)
                    if final:
                        last_frame=final[1]
                        final_canonical,_,_=model.normalize(last_frame)
                        final_phase=model.screen_state.classify(final_canonical)['phase']
                        natural_end=natural_end or final_phase in ['burst','ending','results']
                    break
                if not desktop.focused():paused=True;continue
                if action['kind']=='wait':fresh_after=time.monotonic()+.10;continue
                if action.get('source')=='local_relocation' and time.monotonic()-latest[0]>.15:
                    inputs.write(json.dumps({'decision':number,'kind':'relocation_dispatch_rejected','reason':'capture age exceeded 150ms','at':round(time.time()*1000)})+'\n');inputs.flush()
                    planner.planned=None;fresh_after=time.monotonic();continue
                input_started=time.monotonic()
                if not desktop.click(*click_point):paused=True;continue
                input_completed=time.monotonic()
                if action['kind']=='shuffle':planner.shuffle_at=desktop.last_click_profile['mouse_down_dispatch_started']
                inputs.write(json.dumps({'decision':number,'kind':action['kind'],'label':action.get('label'),'point':list(click_point),'at':round(time.time()*1000),'native_input_diagnostics':desktop.last_click_profile,'latest_frame_age_at_mouse_down_ms':(desktop.last_click_profile['mouse_down_dispatch_started']-latest[0])*1000 if action['kind']=='food' and latest else None,'input_started':input_started,'input_completed':input_completed,'input_ms':(input_completed-input_started)*1000,'frame_age_at_input_start_ms':(input_started-stamp)*1000,'latest_frame_age_at_input_start_ms':(input_started-latest[0])*1000 if action['kind']=='food' and latest else None})+'\n');inputs.flush()
                if action['kind']=='food':
                    planner.commit()
                    if followup_base and desktop.focused():
                        packet2=recording.frame_after(time.monotonic()+.07,timeout=.15)
                        if packet2:
                            point2=adjusted_point(followup_base[1],followup_base[0],packet2[1],packet2[0],followup_base[2],lead=time.monotonic()-packet2[0]+.06,max_extrapolation=8)
                            inputs.write(json.dumps({'decision':number,'kind':'followup_check','stage':'tracking','accepted':point2 is not None,'frame_age_ms':round((packet2[0]-followup_base[0])*1000)})+'\n');inputs.flush()
                            if point2 is not None:
                                canonical2,top2,scale2=model.normalize(packet2[1]);cx2=round(point2[0]/scale2);cy2=round((point2[1]-top2)/scale2)
                                state2=model.screen_state.classify(canonical2)
                                crop2=canonical2[max(0,cy2-32):min(864,cy2+32),max(0,cx2-32):min(1536,cx2+32)]
                                check2=model.point_classifier.classify([crop2])[0] if model.point_classifier and crop2.size else {}
                                inputs.write(json.dumps({'decision':number,'kind':'followup_check','stage':'classification','phase':state2['phase'],'order':state2['order'],'expected':action['label'],'prediction':check2})+'\n');inputs.flush()
                                if state2['phase']=='playing' and state2['order']==planner.order and check2.get('label')==action['label'] and check2.get('score',0)>=.995:
                                    file2=directory/f'frame-{number:05}-followup.jpg';writer.save(file2,packet2[1])
                                    if desktop.click(*point2):
                                        inputs.write(json.dumps({'decision':number,'kind':'food','label':action['label'],'point':list(point2),'followup':True,'frame':str(file2.resolve()),'at':round(time.time()*1000)})+'\n');inputs.flush()
                fresh_after=time.monotonic()+(.20 if action['kind']=='food' else .80)
    finally:
        if last_frame is not None:writer.save(directory/'final.jpg',last_frame)
        recording.close();writer.close();desktop.close()
        (directory/'summary.json').write_text(json.dumps({'status':planner.status(),'frames':number,'video':'game.mp4' if recording.video is not None else None,'goal_verified':False},indent=2),encoding='utf8')
        print('Finished. Review final.jpg and game.mp4. Ten dishes are not assumed from the internal counter.',flush=True)
    return {'directory':str(directory.resolve()),'status':planner.status(),'natural_end':natural_end}

def load_models(point_model):
    model=Perception(point_model)
    model.supplement=SelectedSupplement(model,Path(__file__).parent/'segmenter-positive-surfaces.pt')
    return model


def main(model=None,status_callback=None):
    parser=argparse.ArgumentParser();parser.add_argument('--replay',type=Path);parser.add_argument('--title',default=GAME_TITLE)
    parser.add_argument('--seconds',type=int,default=300);parser.add_argument('--fps',type=int,default=20)
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parent/'runs')
    parser.add_argument('--diagnostic-lossless-interval',type=float,default=2.0,help='Minimum seconds between failed tracking PNG pairs.')
    parser.add_argument('--point-model',default='../kitchen-labeler/point-classifier-resnet18.pt')
    parser.add_argument('--autostart',action='store_true',help='Start after model loading only if the game is foreground.')
    parser.add_argument('--wait-for-focus',action='store_true',help='After an explicit start request, wait for the game foreground.')
    parser.add_argument('--games',type=int,default=5,help='Positive number of games; defaults to five.')
    args=parser.parse_args()
    if args.games<1:parser.error('--games must be positive')
    if model is None:model=load_models(args.point_model)
    if args.replay:print(json.dumps(replay(args.replay,model)))
    else:
        session=args.output/('session-'+str(int(time.time()*1000)));session.mkdir(parents=True,exist_ok=True);results=[]
        source=Path(__file__).resolve().parent;fingerprints={}
        # UI templates affect decisions just as source code and weights do.
        for file in sorted(list(source.glob('*.py'))+list(source.rglob('*.png'))):
            relative=file.relative_to(source).as_posix()
            if diagnostics.mode()=='legacy':
                saved=session/'source'/relative;saved.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(file,saved)
            fingerprints[relative]=hashlib.sha256(file.read_bytes()).hexdigest()
        for file in sorted((source.parent/'kitchen-assets/textures').glob('*.png')):
            relative='../kitchen-assets/textures/'+file.name
            if diagnostics.mode()=='legacy':
                saved=session/'source/shared-textures'/file.name;saved.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(file,saved)
            fingerprints[relative]=hashlib.sha256(file.read_bytes()).hexdigest()
        for filename in [args.point_model,'segmenter-adapted.pt','icon-classifier.pt','segmenter-positive-surfaces.pt']:
            file=source/filename
            if file.exists():
                digest=hashlib.sha256()
                with file.open('rb') as stream:
                    for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
                fingerprints[filename]=digest.hexdigest()
        version=hashlib.sha256(json.dumps(fingerprints,sort_keys=True).encode()).hexdigest()[:16]
        (session/'version.json').write_text(json.dumps({'version':version,'files':fingerprints,'requested_games':args.games,'capture_fps':args.fps},indent=2),encoding='utf8')
        print(f'Fixed-version batch {version}: {args.games} games. Session: {session.resolve()}',flush=True)
        print('Ready. Focus the game at its results, kitchen menu, or Order screen, then press F8. Escape exits.',flush=True)
        if args.wait_for_focus:
            if status_callback:status_callback('waiting_focus')
            # Model loading needs no game window. Only an explicit start request
            # enters this loop or creates the native game adapter.
            while True:
                stop_file=os.environ.get('COOKING_STOP_FILE')
                if stop_file and Path(stop_file).exists():return
                try:
                    desktop=Desktop(args.title)
                    break
                except RuntimeError as error:
                    if not str(error).startswith(('Game window not found:','Game window minimized:')):raise
                    time.sleep(.1)
        else:
            desktop=Desktop(args.title)
        ready=False
        try:
            if args.wait_for_focus:
                while not desktop.should_stop():
                    if desktop.focused():
                        if status_callback:status_callback('running')
                        ready=advance_to_order(desktop,model,session/'before-game-1')
                        break
                    time.sleep(.05)
            elif args.autostart and not desktop.should_stop() and desktop.focused():
                ready=advance_to_order(desktop,model,session/'before-game-1')
            while not ready and not args.wait_for_focus:
                if args.autostart and desktop.focused():break
                args.autostart=False
                if desktop.should_stop():break
                if desktop.should_toggle():
                    if desktop.focused():ready=advance_to_order(desktop,model,session/'before-game-1')
                    break
                time.sleep(.05)
        finally:desktop.close()
        if not ready:print('Session start canceled or game was not ready.',flush=True);raise SystemExit(0)
        for game in range(args.games):
            model.recipe_cache=None
            result=play(args,model,autostart=True,status_callback=status_callback);results.append(result)
            (session/'summary.json').write_text(json.dumps({'games':results,'goal_verified':False},indent=2),encoding='utf8')
            if not result['natural_end'] or game+1>=args.games:break
            desktop=Desktop(args.title)
            try:ready=advance_to_order(desktop,model,session/f'to-game-{game+2}')
            finally:desktop.close()
            if not ready:print('Automatic next-game transition stopped; inspect the game or focus.',flush=True);break

if __name__=='__main__':
    main()
