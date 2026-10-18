"""Local image-to-decision perception worker; no desktop capture or input."""
from pathlib import Path
import sys,json,time
import cv2,numpy as np,torch
from segmenter import Segmenter,LABELS
from icons import Icons
from counters import Counters
from shuffle_state import shuffle_state

RECIPES=[['ham','cucumber','potato'],['cereal','milk','glove'],['pot','moyashi','seaweed'],['meat','onion','panko'],['egg','flour','tuna'],['udon','brownegg','scallion'],['spider','kamaboko','noodles'],['sausage','plum','ricepack'],['plate','curry','pepper'],['shrimp','ricebowl','sauce']]
def constrain_recipe(cards):
    observed=[card['label'] for card in cards]
    options=[recipe for recipe in RECIPES if len(set(observed)&set(recipe))>=2]
    if len(options)!=1:return cards
    recipe=options[0];missing=[label for label in recipe if label not in observed]
    out=[];used=set()
    for card in cards:
        if card['label'] in recipe and card['label'] not in used:label=card['label']
        else:label=next((label for label in missing if label not in used),None)
        if label is None:return cards
        used.add(label);out.append(dict(card,label=label,raw_label=card['label'],recipe_constrained=label!=card['label']))
    return out

class Perception:
    def __init__(self,point_model='point-classifier.pt'):
        torch.set_num_threads(2)
        cv2.setNumThreads(2)
        self.device='cuda' if torch.cuda.is_available() else 'cpu'
        self.model=Segmenter().to(self.device).eval()
        path=Path(__file__).parent/'segmenter-adapted.pt'
        if not path.exists():path=Path(__file__).parent/'segmenter.pt'
        checkpoint=torch.load(path,map_location=self.device,weights_only=True)
        self.model.load_state_dict(checkpoint['model']);self.validation=checkpoint['validation']
        self.icons=Icons();self.counters=Counters()
        from screen_state import ScreenState
        self.screen_state=ScreenState();self.point_model=point_model
        self.recipe_cache=None
        self.order_mask=cv2.imread(str(Path(__file__).parent/'ui-order-mask.png'),0)>0
        self.complete_mask=cv2.imread(str(Path(__file__).parent/'ui-complete-mask.png'),0)>0
        self.classifier=None
        self.point_classifier=None
        if (Path(__file__).parent/'icon-classifier.pt').exists():
            from icon_classifier import IconClassifier
            self.classifier=IconClassifier(self.device)
            if (Path(__file__).parent/point_model).exists():
                self.point_classifier=IconClassifier(self.device,point_model)
        self.human_point_model=bool(self.point_classifier and self.point_classifier.is_human_point_model)
    def normalize(self,im):
        h,w=im.shape[:2];top=max(0,h-round(w*9/16))
        return cv2.resize(im[top:,:],(1536,864)),top,w/1536
    def predict(self,im):
        tensor=torch.from_numpy(im.transpose(2,0,1).copy()).unsqueeze(0).float().to(self.device)/255
        with torch.inference_mode():
            p=self.model(tensor).softmax(1)[0].cpu().numpy()
        return p
    def detect(self,canonical,top,scale):
        # Include the lower rim where large food can protrude above the tray.
        board=canonical[175:735,318:1215]
        resized=cv2.resize(board,(448,280));p=self.predict(resized)
        labels=p.argmax(0);confidence=p.max(0)
        candidates=[]
        for cls in range(1,len(LABELS)):
            mask=((labels==cls)&(confidence>.65)).astype(np.uint8)
            n,cc,stats,centroids=cv2.connectedComponentsWithStats(mask,8)
            for i in range(1,n):
                area=stats[i,cv2.CC_STAT_AREA]
                if area<120:continue
                interior=(cc==i).astype(np.uint8)
                d=cv2.distanceTransform(interior,cv2.DIST_L2,5)
                safe=d*(confidence**2);_,radius,_,loc=cv2.minMaxLoc(safe)
                if radius<4:continue
                x,y=loc
                if LABELS[cls]=='moyashi':
                    hsv=cv2.cvtColor(resized,cv2.COLOR_BGR2HSV)
                    lid=((hsv[:,:,0]>=16)&(hsv[:,:,0]<=38)&(hsv[:,:,1]>100)&(hsv[:,:,2]>80)&(interior>0)).astype(np.uint8)
                    safe_lid=cv2.distanceTransform(lid,cv2.DIST_L2,5)*(confidence**2)
                    _,lid_radius,_,lid_loc=cv2.minMaxLoc(safe_lid)
                    if lid_radius>=2.5:
                        x,y=lid_loc;radius=max(radius,10)
                    else:
                        continue
                cx=x*board.shape[1]/448+318;cy=y*board.shape[0]/280+175
                bx,by,bw,bh,_=stats[i]
                box=[round(bx*board.shape[1]/448+318),round(by*2+175),round((bx+bw)*board.shape[1]/448+318),round((by+bh)*2+175)]
                candidates.append({'label':LABELS[cls],'x':round(cx*scale),'y':round(cy*scale+top),'cx':round(cx),'cy':round(cy),'confidence':round(float(confidence[y,x]),3),'radius':round(radius*2,1),'area':int(area),'box':box,'method':'segmenter'})
        return candidates,labels,confidence
    def analyze(self,im,debug=None,fast=False):
        t0=time.perf_counter();canonical,top,scale=self.normalize(im)
        state=self.screen_state.classify(canonical)
        shuffle=shuffle_state(canonical,state['phase'])
        overlay=state['phase']=='order'
        complete_overlay=state['phase']=='dish_complete'
        recipe_surface=canonical
        if overlay:
            layouts=[]
            for layout in ['large','bottom']:
                surface=np.zeros_like(canonical)
                for i in range(3):
                    crop=canonical[365:502,464+212*i:657+212*i] if layout=='large' else canonical[573:663,560+141*i:695+141*i]
                    surface[60:150,560+141*i:695+141*i]=cv2.resize(crop,(135,90))
                cards=self.counters.cards(surface)
                quality=sum(v['score'] if v['remaining'] in [1,2,3,4,5,6] and v['score']>.78 else 0 for v in cards)
                layouts.append((quality,surface))
            recipe_surface=max(layouts,key=lambda item:item[0])[1]
        cached=state['phase']=='playing' and self.recipe_cache is not None and self.recipe_cache[0]==state['order']
        recipe=[dict(v) for v in self.recipe_cache[1]] if cached else self.classifier.recipe(recipe_surface) if self.classifier else self.icons.recipe(recipe_surface)
        if self.classifier and not cached:
            for i,r in enumerate(recipe):
                if r['score']<.88:
                    x=560+141*i
                    template=self.icons.classify(recipe_surface[60:150,x:x+135],center=(64,47))
                    if template['score']>.70:recipe[i]=template
        counters=state['counters']
        if state['phase']=='playing':recipe=constrain_recipe(recipe)
        if state['phase'] in ['order','dish_complete']:self.recipe_cache=None
        if state['phase']=='playing' and len({v['label'] for v in recipe})==3 and any(set(v['label'] for v in recipe)==set(group) for group in RECIPES):
            self.recipe_cache=(state['order'],[dict(v) for v in recipe])
        if state['phase']!='playing':
            candidates=[];labels=np.zeros((280,448),np.uint8);confidence=np.zeros((280,448));tray=[]
        else:
            candidates,labels,confidence=self.detect(canonical,top,scale)
            tray=self.classifier.tray(canonical) if self.classifier else self.icons.tray(canonical) if not fast else []
            if self.classifier and candidates:
                crops=[]
                for c in candidates:
                    x1,y1,x2,y2=c['box'];crops.append(canonical[max(0,y1-4):min(864,y2+4),max(0,x1-4):min(1536,x2+4)])
                local_crops=[canonical[max(0,c['cy']-32):min(864,c['cy']+32),max(0,c['cx']-32):min(1536,c['cx']+32)] for c in candidates]
                local_checks=(self.point_classifier or self.classifier).classify(local_crops)
                if self.human_point_model:
                    # Ordinary human-point decisions do not use box predictions.
                    # Compute boxes only when a same-food followup may need the
                    # second agreement in place of strong surface segmentation.
                    strong_counts={}
                    for local in local_checks:
                        if local['score']>=.99:
                            strong_counts[local['label']]=strong_counts.get(local['label'],0)+1
                    needed={card['label'] for card,count in zip(recipe,counters) if count['remaining'] is not None and count['remaining']>=2}
                    indices=[i for i,(c,local) in enumerate(zip(candidates,local_checks))
                             if local['score']>=.99 and strong_counts.get(local['label'],0)>=2
                             and local['label'] in needed
                             and not (c['label']==local['label'] and c['confidence']>=.97)]
                    # Small onion regions need a box check even for the last piece.
                    onion_active=any(card['label']=='onion' and (count['remaining'] is None or count['remaining']>0) for card,count in zip(recipe,counters))
                    if onion_active:
                        indices=sorted(set(indices)|{i for i,(c,local) in enumerate(zip(candidates,local_checks)) if local['label']=='onion' and local['score']>=.995 and 10<=c['radius']<20})
                    shrimp_active=any(card['label']=='shrimp' and (count['remaining'] is None or count['remaining']>0) for card,count in zip(recipe,counters))
                    if shrimp_active:
                        indices=sorted(set(indices)|{i for i,(c,local) in enumerate(zip(candidates,local_checks)) if local['label']=='shrimp' and local['score']>=.995 and 10<=c['radius']<20})
                    checks=[{'label':c['label'],'score':0.0,'alternatives':[],'skipped':True} for c in candidates]
                    if indices:
                        box_checks=self.classifier.classify([crops[i] for i in indices])
                        for i,check in zip(indices,box_checks):checks[i]=check
                else:
                    checks=self.classifier.classify(crops)
                for c,check,local in zip(candidates,checks,local_checks):
                    c['surface_label']=c['label'];c['classifier']=check
                    c['local_classifier']=local
                    # A bounding box may include another overlapping food. Keep
                    # the pixel classification at the actual click point.
        for i,r in enumerate(recipe if debug and not fast else []):
            x=560+141*i
            crop=canonical[70:136,x+23:x+92]
            probs=self.predict(cv2.resize(crop,(112,112)))
            good=probs.max(0)>.7;pred=probs.argmax(0)
            counts=np.bincount(pred[good].flatten(),minlength=len(LABELS));counts[0]=0
            best=int(counts.argmax())
            r['neural_label']=LABELS[best];r['neural_fraction']=round(float(counts[best]/max(1,good.sum())),3)
        if debug:
            palette=np.random.default_rng(122).integers(30,245,(31,3),dtype=np.uint8);palette[0]=[0,0,0]
            vis=palette[labels];vis[confidence<.65]=0
            mask=cv2.resize(vis,(897,560),interpolation=cv2.INTER_NEAREST)
            canonical[175:735,318:1215]=cv2.addWeighted(canonical[175:735,318:1215],.6,mask,.4,0)
            for c in candidates:
                cv2.circle(canonical,(c['cx'],c['cy']),5,(0,0,255),2)
                cv2.putText(canonical,c['label'],(c['cx'],c['cy']),cv2.FONT_HERSHEY_SIMPLEX,.45,(0,0,0),2)
            cv2.imwrite(str(debug),canonical)
        return {'candidates':candidates,'recipe':recipe,'counters':counters,'tray':tray,'overlay':overlay,'complete_overlay':complete_overlay,'phase':state['phase'],'screen_scores':state,'shuffle':shuffle,'human_point_model':self.human_point_model,'order':state['order'],'scale':scale,'top':top,'seconds':round(time.perf_counter()-t0,3),'model_validation':self.validation}

if __name__=='__main__':
    perception=Perception()
    if len(sys.argv)>1:
        im=cv2.imread(sys.argv[1]);print(json.dumps(perception.analyze(im,sys.argv[2] if len(sys.argv)>2 else None)))
    else:
        print(json.dumps({'ready':True,'validation':perception.validation}),flush=True)
        for line in sys.stdin:
            try:
                req=json.loads(line);im=cv2.imread(req['path']);result=perception.analyze(im,req.get('debug'))
                print(json.dumps(result),flush=True)
            except Exception as e:print(json.dumps({'error':str(e)}),flush=True)
