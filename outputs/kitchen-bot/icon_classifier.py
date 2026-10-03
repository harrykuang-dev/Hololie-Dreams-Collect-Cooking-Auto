from pathlib import Path
import cv2,numpy as np,torch
from torch import nn
from torchvision.models import resnet18

class IconClassifier:
    def __init__(self,device='cuda',filename='icon-classifier.pt'):
        checkpoint=torch.load(Path(__file__).parent/filename,map_location=device,weights_only=True)
        self.labels=checkpoint['labels'];self.device=device
        self.model=resnet18(weights=None);self.model.fc=nn.Linear(512,len(self.labels));self.model.to(device).eval()
        self.model.load_state_dict(checkpoint['model'])
    def classify(self,crops):
        array=np.stack([cv2.resize(im,(96,96)).transpose(2,0,1) for im in crops])
        tensor=torch.from_numpy(array.copy()).float().to(self.device)/255
        with torch.inference_mode():probs=self.model(tensor).softmax(1).cpu().numpy()
        out=[]
        for row in probs:
            indices=np.argsort(-row)[:3]
            out.append({'label':self.labels[indices[0]],'score':round(float(row[indices[0]]),3),'alternatives':[(self.labels[i],round(float(row[i]),3)) for i in indices]})
        return out

    def recipe(self,canonical):
        return self.classify([canonical[70:136,583+141*i:652+141*i] for i in range(3)])

    def tray(self,canonical):
        crops=[];indices=[]
        for i in range(7):
            x=385+i*128;crop=canonical[755:835,x-42:x+42]
            center=crop[7:73,7:77];gray=cv2.cvtColor(center,cv2.COLOR_BGR2GRAY)
            yy,xx=np.mgrid[-1:1:66j,-1:1:70j]
            design=np.stack([np.ones_like(xx),xx,yy,xx*xx,yy*yy,xx*yy],-1).reshape(-1,6)
            pixels=center.reshape(-1,3).astype(float)
            residual=pixels-design@np.linalg.lstsq(design,pixels,rcond=None)[0]
            # Empty slots have a smooth lighting gradient. Pale noodles still
            # have local texture after removing that gradient.
            if np.sqrt(np.mean(residual**2))<4.0:continue
            crops.append(crop);indices.append(i)
        if not crops:return []
        results=self.classify(crops)
        for result,i in zip(results,indices):result['index']=i
        return results
