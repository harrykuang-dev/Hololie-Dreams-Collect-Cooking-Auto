"""Small local semantic model; predicts visible ingredient pixels, not hidden items."""
import torch
from torch import nn
import torch.nn.functional as F

LABELS=['background','ham','milk','pot','potato','sauce','cucumber','meat','udon','noodles','plum','egg','brownegg','kamaboko','cereal','onion','panko','pepper','spider','flour','sausage','ricebowl','plate','ricepack','scallion','shrimp','curry','seaweed','glove','moyashi','tuna']

def block(a,b):
    return nn.Sequential(nn.Conv2d(a,b,3,padding=1),nn.BatchNorm2d(b),nn.SiLU(),
                         nn.Conv2d(b,b,3,padding=1),nn.BatchNorm2d(b),nn.SiLU())

class Segmenter(nn.Module):
    def __init__(self):
        super().__init__()
        self.a=block(3,24);self.b=block(24,48);self.c=block(48,96);self.d=block(96,160)
        self.u=block(256,96);self.v=block(144,48);self.w=block(72,24)
        self.out=nn.Conv2d(24,len(LABELS),1)
    def forward(self,x):
        a=self.a(x);b=self.b(F.max_pool2d(a,2));c=self.c(F.max_pool2d(b,2));d=self.d(F.max_pool2d(c,2))
        c=self.u(torch.cat([c,F.interpolate(d,size=c.shape[-2:],mode='bilinear',align_corners=False)],1))
        b=self.v(torch.cat([b,F.interpolate(c,size=b.shape[-2:],mode='bilinear',align_corners=False)],1))
        a=self.w(torch.cat([a,F.interpolate(b,size=a.shape[-2:],mode='bilinear',align_corners=False)],1))
        return self.out(a)
