"""Build a timestamped review video from the bot's existing decision frames.

This is a reconstruction of captured observations, not a high-FPS source video.
It performs no screen capture/input and adds no work to the live decision loop.
"""
import argparse,json
from pathlib import Path
import cv2

def build(run,output,fps=10):
    records=[json.loads(s) for s in (run/'decisions.jsonl').read_text(encoding='utf8').splitlines()]
    if not records:raise ValueError('No recorded decisions')
    first=cv2.imread(records[0]['frame'])
    if first is None:raise ValueError('First recorded image is missing')
    h,w=first.shape[:2];size=(w//2*2,h//2*2)
    output.parent.mkdir(parents=True,exist_ok=True)
    writer=cv2.VideoWriter(str(output),cv2.VideoWriter_fourcc(*'mp4v'),fps,size)
    if not writer.isOpened():raise RuntimeError('Video encoder could not open output')
    start=records[0]['at'];written=0
    try:
        for i,r in enumerate(records):
            frame=cv2.imread(r['frame'])
            if frame is None:continue
            frame=cv2.resize(frame,size)
            status=r['status'];a=r['action'];elapsed=(r['at']-start)/1000
            text=f"t={elapsed:.1f}s  order={status.get('order')}  dishes={status.get('completed')}  {a.get('kind')} {a.get('label','')}"
            cv2.rectangle(frame,(0,size[1]-35),(size[0],size[1]),(0,0,0),-1)
            cv2.putText(frame,text,(10,size[1]-10),cv2.FONT_HERSHEY_SIMPLEX,.65,(255,255,255),1,cv2.LINE_AA)
            end=records[i+1]['at'] if i+1<len(records) else r['at']+1000
            count=max(1,round((end-r['at'])/1000*fps))
            for _ in range(count):writer.write(frame);written+=1
    finally:writer.release()
    cap=cv2.VideoCapture(str(output));actual=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));ok,frame=cap.read();cap.release()
    if not ok or actual!=written:raise RuntimeError('Encoded video verification failed')
    return {'path':str(output),'frames':actual,'seconds':round(actual/fps,1),'observations':len(records)}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('run',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();print(json.dumps(build(args.run,args.output)))
