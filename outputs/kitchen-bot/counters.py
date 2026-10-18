from pathlib import Path
import cv2,numpy as np

class Counters:
    def __init__(self):
        self.digits={int(p.stem):cv2.imread(str(p),0) for p in (Path(__file__).parent/'digits').glob('*.png')}
    def cards(self,canonical):
        out=[]
        for i in range(3):
            # The cyan completion badge replaces the lower-right counter.
            crop=canonical[92:141,648+141*i:689+141*i]
            hsv=cv2.cvtColor(crop,cv2.COLOR_BGR2HSV)
            blue=(hsv[:,:,0]>85)&(hsv[:,:,0]<110)&(hsv[:,:,1]>100)&(hsv[:,:,2]>150)
            if blue.sum()>180:
                out.append({'remaining':0,'complete':True,'score':1.});continue
            mask=(cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY)<100).astype(np.uint8)*255
            n,cc,stats,centers=cv2.connectedComponentsWithStats(mask,8)
            valid=[j for j in range(1,n) if stats[j,cv2.CC_STAT_AREA]>60 and stats[j,cv2.CC_STAT_HEIGHT]>15]
            if not valid:out.append({'remaining':None,'complete':False,'score':0.});continue
            idx=max(valid,key=lambda j:stats[j,cv2.CC_STAT_AREA]);x,y,w,h,area=stats[idx]
            a=cv2.resize((cc[y:y+h,x:x+w]==idx).astype(np.uint8)*255,(28,40))
            scores={digit:float(np.mean((a>128)==(ref>128))) for digit,ref in self.digits.items()}
            best=max(scores,key=scores.get)
            # Zero is represented by a cyan checkmark, never a numeric zero.
            out.append({'remaining':best if 1<=best<=6 else None,'complete':False,'score':round(scores[best],3)})
        return out

    def order(self,canonical):
        crop=canonical[134:194,1390:1508]
        mask=(cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY)<100).astype(np.uint8)*255
        n,cc,stats,centers=cv2.connectedComponentsWithStats(mask,8)
        valid=[j for j in range(1,n) if stats[j,cv2.CC_STAT_AREA]>90 and 23<stats[j,cv2.CC_STAT_HEIGHT]<54]
        digits=[]
        for idx in sorted(valid,key=lambda j:stats[j,cv2.CC_STAT_LEFT]):
            x,y,w,h,area=stats[idx]
            a=cv2.resize((cc[y:y+h,x:x+w]==idx).astype(np.uint8)*255,(28,40))
            scores={digit:float(np.mean((a>128)==(ref>128))) for digit,ref in self.digits.items()}
            best=max(scores,key=scores.get)
            if scores[best]>.79:digits.append(str(best))
        return int(''.join(digits)) if digits else None
