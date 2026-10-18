"""Cheap screenshot-only state gate; excludes dish overlays and end animations."""
from pathlib import Path
import cv2,numpy as np
from counters import Counters
from session_flow import has_next_button
class ScreenState:
    def __init__(self):
        root=Path(__file__).resolve().parent
        self.order_mask=cv2.imread(str(root/'ui-order-mask.png'),0)>0
        self.complete_rois=[(70,250,50,200),(1280,1470,675,815)]
        self.complete_masks=[cv2.imread(str(root/f'ui-complete-ornament-{i}.png'),0)>0 for i in range(2)]
        self.burst_mask=cv2.imread(str(root/'ui-burst-mask.png'),0)>0
        self.results_mask=cv2.imread(str(root/'ui-results-mask.png'),0)>0
        self.counters=Counters()
    def classify(self,im):
        hsv=cv2.cvtColor(im,cv2.COLOR_BGR2HSV)
        gold=(hsv[:,:,0]>12)&(hsv[:,:,0]<40)&(hsv[:,:,1]>140)&(hsv[:,:,2]>160)
        order=gold[105:195,565:975]
        def overlap(a,b):return float((a&b).sum()/max(1,(a|b).sum()))
        order_score=overlap(order,self.order_mask)
        # Fixed corner artwork is independent of translated dish text.
        complete_score=min(overlap(cv2.cvtColor(im[y1:y2,x1:x2],cv2.COLOR_BGR2GRAY)>110,ref)
                           for (x1,x2,y1,y2),ref in zip(self.complete_rois,self.complete_masks))
        results_white=cv2.cvtColor(im[245:280,920:1190],cv2.COLOR_BGR2GRAY)>220
        results_score=overlap(results_white,self.results_mask)
        region=hsv[315:475,500:1035]
        blue=(region[:,:,0]>95)&(region[:,:,0]<130)&(region[:,:,1]>45)&(region[:,:,2]>130)
        burst_score=overlap(blue,self.burst_mask)
        cards=self.counters.cards(im);number=self.counters.order(im)
        reliable=sum(v['remaining'] in range(7) and v['score']>.80 for v in cards)
        # Check dominant modal text before trusting still-visible gameplay UI.
        if results_score>.60 and has_next_button(im):phase='results'
        elif burst_score>.50:phase='burst'
        elif complete_score>.30:phase='dish_complete'
        elif order_score>.32:phase='order'
        elif number is not None:
            # The recipe cards can briefly be hidden by their own animation.
            # Closing curtains are terminal even while the old order is visible.
            red=(hsv[:,:,1]>120)&(hsv[:,:,2]>80)&((hsv[:,:,0]<12)|(hsv[:,:,0]>170))
            curtains=red[:,0:80].mean()>.55 and red[:,-80:].mean()>.55
            phase='ending' if curtains else 'playing'
        else:phase='unknown'
        return {'phase':phase,'order_score':round(order_score,3),'complete_score':round(complete_score,3),'burst_score':round(burst_score,3),'results_score':round(results_score,3),'order':number,'counters':cards}
