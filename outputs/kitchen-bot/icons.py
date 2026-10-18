"""Official icon matching with alpha masks, for order cards and tray slots."""
from pathlib import Path
import re,cv2,numpy as np
from render_samples import LABELS

class Icons:
    def __init__(self):
        self.bank=[]
        assets=Path(__file__).resolve().parents[1]/'kitchen-assets/textures'
        for p in assets.glob('img_mg_cooking_foodstuff_ingredient*.png'):
            key=re.search(r'ingredient-(\d\d-[a-z]+\d)',p.stem).group(1);label=LABELS[key]
            im=cv2.imread(str(p),cv2.IMREAD_UNCHANGED)
            ys,xs=np.where(im[:,:,3]>120);im=im[ys.min():ys.max()+1,xs.min():xs.max()+1]
            # Height of actual visible object, not the transparent canvas.
            for height in [44,50,56,62,68,74,80,86,90]:
                width=round(im.shape[1]*height/im.shape[0])
                ref=cv2.resize(im,(width,height),interpolation=cv2.INTER_AREA)
                mask=(ref[:,:,3]>180).astype(np.uint8)*255
                self.bank.append((label,ref[:,:,:3],mask))
        missing=set(LABELS.values())-{label for label,ref,mask in self.bank}
        if missing:
            raise FileNotFoundError('Missing ingredient icon templates in '+str(assets)+': '+', '.join(sorted(missing)))

    def classify(self,crop,center=None):
        ranked={}; locations={}
        region=crop
        if center is not None:
            cx,cy=map(int,center);region=crop[max(0,cy-36):cy+18,max(0,cx-30):cx+25]
        hsv=cv2.cvtColor(region,cv2.COLOR_BGR2HSV)
        foreground=((hsv[:,:,1]>65)&(hsv[:,:,2]>60)).astype(np.uint8)*255
        target_hist=cv2.calcHist([hsv],[0],foreground,[18],[0,180]);cv2.normalize(target_hist,target_hist,alpha=1,norm_type=cv2.NORM_L1)
        for label,ref,mask in self.bank:
            if ref.shape[0]>crop.shape[0] or ref.shape[1]>crop.shape[1]:continue
            scores=cv2.matchTemplate(crop,ref,cv2.TM_SQDIFF,mask=mask)
            if center is not None:
                yy,xx=np.indices(scores.shape)
                valid=(abs(xx+ref.shape[1]/2-center[0])<10)&(abs(yy+ref.shape[0]/2-center[1])<12)
                scores[~valid]=1e12
            _,_,loc,_=cv2.minMaxLoc(scores)
            # Color error on foreground pixels distinguishes similar shapes.
            mse=float(scores[loc[1],loc[0]])/max(1,np.count_nonzero(mask)*3)
            score=1-np.sqrt(max(0,mse))/255
            rhsv=cv2.cvtColor(ref,cv2.COLOR_BGR2HSV)
            rmask=((rhsv[:,:,1]>65)&(rhsv[:,:,2]>60)&(mask>0)).astype(np.uint8)*255
            hist=cv2.calcHist([rhsv],[0],rmask,[18],[0,180]);cv2.normalize(hist,hist,alpha=1,norm_type=cv2.NORM_L1)
            similarity=1-cv2.compareHist(target_hist,hist,cv2.HISTCMP_BHATTACHARYYA)
            if np.count_nonzero(foreground)>600 and score<.96:score=.6*score+.4*similarity
            if score>ranked.get(label,-1):ranked[label]=score;locations[label]=(loc,ref.shape[:2])
        order=sorted(ranked.items(),key=lambda x:-x[1])
        if not order:
            return {'label':'background','score':0.0,'margin':0.0,'alternatives':[],'location':None}
        label,score=order[0]
        return {'label':label,'score':round(score,3),'margin':round(score-(order[1][1] if len(order)>1 else 0),3),'alternatives':order[:3],'location':locations[label]}

    def recipe(self,canonical):
        return [self.classify(canonical[60:150,560+141*i:695+141*i],center=(64,47)) for i in range(3)]

    def tray(self,canonical):
        slots=[]
        for i in range(7):
            x=385+i*128;crop=canonical[750:842,x-50:x+50]
            # Uniform cream slots have almost no edges in their central region.
            center=crop[15:80,12:86]
            gray=cv2.cvtColor(center,cv2.COLOR_BGR2GRAY)
            edges=cv2.Canny(gray,60,120)
            if (edges>0).mean()<.018 and center.std(axis=(0,1)).mean()<13:continue
            result=self.classify(crop,center=(50,48));result['index']=i;slots.append(result)
        return slots
