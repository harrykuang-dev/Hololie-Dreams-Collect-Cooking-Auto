"""Offline visual perception. Receives PNGs; never captures a screen or sends input."""
from pathlib import Path
import json, sys, cv2, numpy as np

ROOT = Path(__file__).parent
cv2.setNumThreads(2)

class Vision:
    def __init__(self):
        self.sift = cv2.SIFT_create(contrastThreshold=.015, edgeThreshold=15)
        self.matcher = cv2.BFMatcher(cv2.NORM_L2)
        self.samples, self.icons = [], []
        desc, names, colors = [], [], []
        for p in (ROOT/'templates').glob('*.png'):
            im = cv2.imread(str(p))
            if p.stem.startswith('icon-'):
                self.icons.append((p.stem.split('-')[1], im))
                continue
            label = p.stem.rsplit('-',1)[0]
            kp, ds = self.sift.detectAndCompute(cv2.cvtColor(im,cv2.COLOR_BGR2GRAY),None)
            self.samples.append((label,im))
            if ds is None: continue
            for k,d in zip(kp,ds):
                x,y=k.pt
                if min(x,y,im.shape[1]-x,im.shape[0]-y)<5: continue
                desc.append(d); names.append(label)
                colors.append(im[int(y),int(x)].astype(float))
        self.ds=np.asarray(desc,np.float32)
        self.names=np.asarray(names)
        self.colors=np.asarray(colors)

    def normalize(self, im):
        # The supported game window has a Windows title bar, then a 16:9 game surface.
        h,w=im.shape[:2]
        game_h=round(w*9/16)
        top=max(0,h-game_h)
        return cv2.resize(im[top:,:],(1536,864)),top,w/1536

    def detect(self, im):
        canonical,top,scale=self.normalize(im)
        board=canonical[180:710,318:1210]
        kp,ds=self.sift.detectAndCompute(cv2.cvtColor(board,cv2.COLOR_BGR2GRAY),None)
        groups={}
        if ds is not None:
            matches=self.matcher.knnMatch(ds,self.ds,k=min(12,len(self.ds)))
            for i,ms in enumerate(matches):
                if len(ms)<2: continue
                m=ms[0]; label=self.names[m.trainIdx]
                other=next((n for n in ms[1:] if self.names[n.trainIdx]!=label),ms[-1])
                if m.distance>260 or m.distance>.78*other.distance: continue
                x,y=kp[i].pt
                color=board[int(y),int(x)].astype(float)
                if np.linalg.norm(color-self.colors[m.trainIdx])>115:continue
                groups.setdefault(str(label),[]).append([x+318,y+180,1-m.distance/400])
        candidates=[]
        for label,points in groups.items():
            pts=np.asarray(points)
            while len(pts):
                dist=np.linalg.norm(pts[:,None,:2]-pts[None,:,:2],axis=-1)
                seed=np.argmax((dist<48).sum(axis=1))
                subset=pts[dist[seed]<48]
                if len(subset)<3: break
                center=np.median(subset[:,:2],axis=0)
                # Use a real matched visible pixel, not a centroid over a neighbour.
                best=np.argmin(np.linalg.norm(subset[:,:2]-center,axis=1))
                x,y=subset[best,:2]
                candidates.append(dict(label=label,x=round(x*scale),y=round(y*scale+top),votes=len(subset),confidence=round(float(subset[:,2].mean()),3),cx=float(x),cy=float(y)))
                pts=pts[np.linalg.norm(pts[:,:2]-center,axis=1)>85]
        candidates=[c for c in candidates if c['votes']>=6 and c['confidence']>=.48]
        hsv=cv2.cvtColor(board,cv2.COLOR_BGR2HSV)
        masks=[('green',cv2.inRange(hsv,np.array([35,120,70]),np.array([90,255,255]))),
               ('egg',cv2.inRange(hsv,np.array([0,0,165]),np.array([179,42,255])))]
        for kind,mask in masks:
            mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
            contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                area=cv2.contourArea(contour)
                if area<1800:continue
                x,y,w,h=cv2.boundingRect(contour)
                hullarea=cv2.contourArea(cv2.convexHull(contour))
                solidity=area/max(1,hullarea)
                if kind=='green':
                    if area>23000:continue
                    label='cucumber' if solidity>.86 else 'scallion'
                else:
                    if area>12500 or min(w,h)/max(w,h)<.48 or solidity<.94:continue
                    ell=cv2.fitEllipse(contour) if len(contour)>=5 else None
                    if not ell:continue
                    ellarea=np.pi*ell[1][0]*ell[1][1]/4
                    if abs(area/ellarea-1)>.12:continue
                    roi=board[y:y+h,x:x+w]
                    cmask=mask[y:y+h,x:x+w]
                    vals=cv2.cvtColor(roi,cv2.COLOR_BGR2GRAY)[cmask>0]
                    if np.std(vals)>22:continue
                    label='egg'
                interior=np.zeros(mask.shape,np.uint8);cv2.drawContours(interior,[contour],-1,255,-1)
                d=cv2.distanceTransform(interior,cv2.DIST_L2,5)
                _,_,_,loc=cv2.minMaxLoc(d);cx,cy=loc[0]+318,loc[1]+180
                if any(c['label']==label and np.hypot(c['cx']-cx,c['cy']-cy)<70 for c in candidates):continue
                candidates.append(dict(label=label,x=round(cx*scale),y=round(cy*scale+top),cx=cx,cy=cy,votes=7,confidence=.68,method='shape'))
        return canonical, candidates

    def icon_score(self, crop, template):
        a=cv2.resize(crop,(64,64));b=cv2.resize(template,(64,64))
        ah=cv2.cvtColor(a,cv2.COLOR_BGR2HSV);bh=cv2.cvtColor(b,cv2.COLOR_BGR2HSV)
        ma=((ah[:,:,1]>35)&(ah[:,:,2]>40)).astype(np.uint8)*255
        mb=((bh[:,:,1]>35)&(bh[:,:,2]>40)).astype(np.uint8)*255
        ha=cv2.calcHist([ah],[0,1],ma,[18,8],[0,180,0,256]);hb=cv2.calcHist([bh],[0,1],mb,[18,8],[0,180,0,256])
        cv2.normalize(ha,ha);cv2.normalize(hb,hb)
        hist=cv2.compareHist(ha,hb,cv2.HISTCMP_CORREL)
        gray=1-np.mean(abs(cv2.cvtColor(a,cv2.COLOR_BGR2GRAY).astype(float)-cv2.cvtColor(b,cv2.COLOR_BGR2GRAY).astype(float)))/255
        return .72*hist+.28*gray

    def read_recipe(self,canonical):
        slots=[]
        for i in range(3):
            x=560+141*i
            crop=canonical[78:138,x+23:x+86]
            scores={}
            for label,icon in self.icons:
                scores[label]=max(scores.get(label,-1),self.icon_score(crop,icon))
            ranked=sorted(scores.items(),key=lambda kv:-kv[1])
            slots.append({'label':ranked[0][0],'score':round(ranked[0][1],3),'alternatives':ranked[:3]})
        return slots

    def read_tray(self,canonical):
        slots=[]
        for i in range(7):
            x=325+i*126
            crop=canonical[756:835,x+15:x+96]
            # Empty slots have a uniform cream centre, with no saturated object.
            hsv=cv2.cvtColor(crop,cv2.COLOR_BGR2HSV)
            sat=hsv[:,:,1]; gray=cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY)
            edge=cv2.Canny(gray,60,120)
            occupied=bool((sat>130).mean()>.025 or (edge>0).mean()>.035)
            scores={}
            if occupied:
                for label,icon in self.icons:
                    scores[label]=max(scores.get(label,-1),self.icon_score(crop,icon))
                slots.append({'index':i,'label':max(scores,key=scores.get),'score':round(max(scores.values()),3)})
        return slots

    def analyze(self,im):
        canonical,candidates=self.detect(im)
        return {'candidates':sorted(candidates,key=lambda c:-c['votes']),'recipe':self.read_recipe(canonical),'tray':self.read_tray(canonical)}

if __name__=='__main__':
    vision=Vision()
    if len(sys.argv)>1:
        im=cv2.imread(sys.argv[1]); print(json.dumps(vision.analyze(im)))
    else:
        # Persistent JSON-line worker keeps templates and descriptors in memory.
        for line in sys.stdin:
            try:
                req=json.loads(line); im=cv2.imread(req['path'])
                result=vision.analyze(im)
                print(json.dumps(result),flush=True)
            except Exception as e:print(json.dumps({'error':str(e)}),flush=True)
