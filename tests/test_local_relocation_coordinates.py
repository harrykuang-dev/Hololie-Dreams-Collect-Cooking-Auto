"""Coordinate and crop-boundary tests, independent of human food labels."""
import sys,cv2,numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'outputs/kitchen-bot'))
from local_relocation import detect_local
from model_labels import LABELS
class Classifier:
    def classify(self,crops):return [{'label':'egg','score':.999,'alternatives':[]} for _ in crops]
class Model:
    point_classifier=Classifier()
    mode='center'
    def predict(self,patch):
        assert patch.shape==(160,160,3)
        p=np.zeros((len(LABELS),160,160),np.float32);p[0]=1
        mask=np.zeros((160,160),np.uint8)
        cv2.circle(mask,(80,80) if self.mode=='center' else (1,80),18,1,-1)
        p[0][mask>0]=.001;p[LABELS.index('egg')][mask>0]=.999
        return p
model=Model();image=np.zeros((864,1536,3),np.uint8);point=np.array([768,432])
out=detect_local(model,image,0,1,point,'egg');assert len(out)==1
c=out[0];assert abs(c['cx']-768)<9 and abs(c['cy']-432)<9,c
scaled=detect_local(model,image,13,1.25,point*1.25+np.array([0,13]),'egg')
assert len(scaled)==1
assert scaled[0]['cx']==c['cx'] and scaled[0]['cy']==c['cy']
assert abs(scaled[0]['x']-c['x']*1.25)<=1 and abs(scaled[0]['y']-(c['y']*1.25+13))<=1
model.mode='edge';assert not detect_local(model,image,0,1,point,'egg')
assert not detect_local(model,image,0,1,np.array([0,0]),'egg')
model.mode='center';assert not detect_local(model,image,0,1,point,'moyashi')
print('PASS: full-board scale, DPI/top offset mapping, crop-edge rejection, outside-board and transparent-container rejection.')
