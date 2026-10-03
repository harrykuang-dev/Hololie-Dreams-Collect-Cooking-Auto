"""Offline prototype: rerun the original segmenter on a same-scale local ROI."""
import cv2,numpy as np
from segmenter import LABELS

def detect_local(model,canonical,top,scale,native_point,expected_label):
    board=canonical[175:735,318:1215];small=cv2.resize(board,(448,280))
    cx=native_point[0]/scale;cy=(native_point[1]-top)/scale
    px=(cx-318)*448/897;py=(cy-175)/2
    if not(0<=px<448 and 0<=py<280):return []
    # Align pooling boundaries; retain exactly the full-board input scale.
    x0=int(max(0,min(288,8*round((px-80)/8))));y0=int(max(0,min(120,8*round((py-80)/8))))
    patch=small[y0:y0+160,x0:x0+160];probs=model.predict(patch)
    cls=LABELS.index(expected_label);labels=probs.argmax(0);confidence=probs.max(0)
    mask=((labels==cls)&(confidence>.65)).astype(np.uint8)
    n,components,stats,_=cv2.connectedComponentsWithStats(mask,8);out=[]
    for i in range(1,n):
        if stats[i,cv2.CC_STAT_AREA]<120:continue
        interior=(components==i).astype(np.uint8)
        # A cropped-off component has unknown clearance. Do not manufacture a
        # safe center at a crop edge, or use padding as evidence of food texture.
        if interior[0].any() or interior[-1].any() or interior[:,0].any() or interior[:,-1].any():continue
        distance=cv2.distanceTransform(interior,cv2.DIST_L2,5);safe=distance*confidence**2
        _,radius,_,loc=cv2.minMaxLoc(safe);x,y=loc
        if radius*2<20 or confidence[y,x]<.97:continue
        if min(x,y,159-x,159-y)<32:continue
        # Existing moyashi logic uses its colored lid to avoid transparent body.
        if expected_label=='moyashi':continue
        canx=(x+x0)*897/448+318;cany=(y+y0)*2+175
        if not(350<=canx<=1190 and 185<=cany<=720):continue
        bx,by,bw,bh,_=stats[i]
        c={'label':expected_label,'surface_label':expected_label,'confidence':float(confidence[y,x]),'surface_confidence':float(confidence[y,x]),'radius':float(radius*2),'area':int(stats[i,cv2.CC_STAT_AREA]),'cx':round(canx),'cy':round(cany),'x':round(canx*scale),'y':round(cany*scale+top),'box':[round((bx+x0)*897/448+318),round((by+y0)*2+175),round((bx+bw+x0)*897/448+318),round((by+bh+y0)*2+175)],'classifier':{'label':expected_label,'score':0.0,'alternatives':[],'skipped':True},'method':'local-redetection'}
        if np.linalg.norm(np.array([c['x'],c['y']])-native_point)>100:continue
        out.append(c)
    if out:
        predictions=model.point_classifier.classify([canonical[c['cy']-32:c['cy']+32,c['cx']-32:c['cx']+32] for c in out])
        out=[dict(c,local_classifier=v) for c,v in zip(out,predictions) if v['label']==expected_label and v['score']>=.995]
    return out
