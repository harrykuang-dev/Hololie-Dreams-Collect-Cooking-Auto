from pathlib import Path
import cv2,numpy as np
from inference_backend import InferenceRuntime, ModelSession

class IconClassifier:
    def __init__(self,device=None,filename='icon-classifier.onnx'):
        runtime=device if isinstance(device,InferenceRuntime) else InferenceRuntime('cpu' if device=='cpu' else None)
        self.session=ModelSession(filename,runtime)
        checkpoint=self.session.metadata
        self.labels=checkpoint['labels']
        self.input_spec=checkpoint.get('input',{})
        self.dataset_sha256=checkpoint.get('dataset_sha256')
        # Model role comes from training metadata, never from a filename.
        self.is_human_point_model=bool(self.dataset_sha256 and self.input_spec.get('crop_size')==[64,64])
        architecture=checkpoint.get('architecture','resnet18')
        if architecture not in ('resnet18','resnet34','resnet50','resnet101','resnet152'):raise ValueError('Unsupported classifier architecture: '+architecture)
        self.architecture=architecture
        self.parameters=checkpoint['parameters']
    @property
    def device(self):return self.session.device
    def classify(self,crops):
        if not crops:return []
        array=np.stack([cv2.resize(im,(96,96)).transpose(2,0,1) for im in crops])
        probs=self.session.infer(array.astype(np.float32)/255)
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
