"""Read the current round's blue/white result digits, never the best score."""
from pathlib import Path
import time
import cv2
import numpy as np

REGIONS={'score':(840,305,1290,435),'completed_dishes':(1110,560,1270,625)}


def glyphs(canonical,field):
    x1,y1,x2,y2=REGIONS[field]
    crop=canonical[y1:y2,x1:x2]
    hsv=cv2.cvtColor(crop,cv2.COLOR_BGR2HSV)
    white=((hsv[:,:,1]<65)&(hsv[:,:,2]>220)).astype(np.uint8)
    count,components,boxes,_=cv2.connectedComponentsWithStats(white,8)
    minimum=70 if field=='score' else 25
    valid=[i for i in range(1,count) if minimum<=boxes[i,3]<=110 and boxes[i,2]>5 and boxes[i,4]>100]
    result=[]
    for index in sorted(valid,key=lambda i:boxes[i,0]):
        x,y,w,h,_=boxes[index]
        mask=(components[y:y+h,x:x+w]==index).astype(np.uint8)*255
        result.append((cv2.resize(mask,(40,64),interpolation=cv2.INTER_NEAREST),w/h))
    return result


class ResultReader:
    def __init__(self):
        self.templates={}
        for field in REGIONS:
            root=Path(__file__).parent/'result-digits'/field
            self.templates[field]=[(int(p.stem.split('-')[0]),cv2.imread(str(p),0)>127)
                                   for p in sorted(root.glob('*.png'))]

    def read(self,canonical,state):
        result={'score':None,'completed_dishes':None,'verified':False,'reason':'not_results',
                'digit_confidence':{},'reader':'result-digits-v1'}
        if state.get('phase')!='results':return result
        for field in REGIONS:
            chars=glyphs(canonical,field)
            if not chars or len(chars)>(7 if field=='score' else 3):
                result['reason']='digit_count';return result
            digits=[];confidences=[]
            for mask,ratio in chars:
                if not self.templates[field]:result['reason']='templates_unavailable';return result
                scores={}
                for digit,reference in self.templates[field]:
                    binary=mask>127
                    overlap=float(2*np.count_nonzero(binary&reference)/max(1,np.count_nonzero(binary)+np.count_nonzero(reference)))
                    scores[digit]=max(scores.get(digit,0),overlap)
                ranked=sorted(scores,key=scores.get,reverse=True)
                best=ranked[0];score=scores[best]
                if score<.88 or len(ranked)>1 and score-scores[ranked[1]]<.035:
                    result['reason']='uncertain_digit';return result
                digits.append(str(best));confidences.append(round(score,4))
            result[field]=int(''.join(digits));result['digit_confidence'][field]=confidences
        result.update(verified=True,reason='recognized')
        return result


def collect_result(recording,model,last_frame,natural_end,timeout=3.0):
    """Observe results only; no keyboard, cursor, or transition input is issued."""
    reader=ResultReader();first=last_frame;deadline=time.monotonic()+timeout
    previous=None;since=None;last_reading=None
    while first is not None:
        canonical,_,_=model.normalize(first)
        state=model.screen_state.classify(canonical)
        reading=reader.read(canonical,state);last_reading=reading
        key=(reading['score'],reading['completed_dishes']) if reading['verified'] else None
        now=time.monotonic()
        if key is not None and key==previous:
            if now-since>=.35:return first,{**reading,'confirmation':'stable_repeated_frames'}
        else:previous=key;since=now
        if not natural_end or now>=deadline:break
        packet=None
        while packet is None and time.monotonic()<deadline:
            packet=recording.frame_after(time.monotonic()+.10,timeout=.25)
        if packet is None:break
        first=packet[1]
    # An unconfirmed animation value must not enter the verified score table.
    return first,{'score':None,'completed_dishes':None,'verified':False,
                  'reason':'results_not_confirmed','last_reading':last_reading}
