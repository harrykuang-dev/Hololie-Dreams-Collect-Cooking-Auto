"""Only recognize the kitchen's bottom-right Next/OK/Play control."""
import cv2,numpy as np

def has_next_button(canonical):
    roi=canonical[760:810,1190:1460]
    hsv=cv2.cvtColor(roi,cv2.COLOR_BGR2HSV)
    mask=(hsv[:,:,0]>=80)&(hsv[:,:,0]<=110)&(hsv[:,:,1]>100)&(hsv[:,:,2]>170)
    return int(mask.sum())>2000

def advance_to_order(desktop,model,directory,deadline_seconds=45):
    import time,json
    directory.mkdir(parents=True,exist_ok=True)
    deadline=time.monotonic()+deadline_seconds;last_click=0;number=0
    with (directory/'transitions.jsonl').open('w',encoding='utf8') as log:
        while time.monotonic()<deadline:
            if desktop.u.GetAsyncKeyState(0x1B)&0x8001 or not desktop.focused():return False
            frame=desktop.capture()
            if frame is None:return False
            canonical,top,scale=model.normalize(frame);state=model.screen_state.classify(canonical)
            if state['phase']=='order':return True
            if state['phase'] in ['unknown','playing','results'] and has_next_button(canonical) and time.monotonic()-last_click>1.2:
                number+=1;file=directory/f'transition-{number:02}.jpg';cv2.imwrite(str(file),frame)
                if not desktop.click(round(1300*scale),round(785*scale+top)):return False
                log.write(json.dumps({'image':str(file.resolve()),'state':state,'point':[1300,785],'at':round(time.time()*1000)})+'\n');log.flush();last_click=time.monotonic()
            time.sleep(.1)
    return False
