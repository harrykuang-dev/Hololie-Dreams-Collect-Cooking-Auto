"""State/timestamp/confirmation tests for staged fallback; never game input."""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'outputs/kitchen-bot'))
import guarded_local_relocation as g

class Planner:
    order=1
    recipe=['ricepack','ham','milk']
    pending=None
    inventory={}
    def propose(self, fresh):
        self.inventory={item['label']:1 for item in fresh['tray']}
        self.food_options=[{'action':dict(option['action']), 'planned':dict(label='ricepack',counters=[3,3,3])}] if fresh['candidates'] else []

option={'action':{'kind':'food','label':'ricepack','reason':'needed ingredient','x':500,'y':400,'radius':25}}
waiting={'action':{'kind':'wait','reason':'tracking failed'},'point':None,'planned':None}
food={'action':{'kind':'food'},'point':(500,400),'planned':{}}
frame=np.zeros((864,1536,3),np.uint8)
state={'phase':'playing','order':1,'counters':[{'remaining':3} for _ in range(3)]}
tray=[]
calls=[]
def snap(model, im):
    i=len(calls);calls.append(i)
    return frame,0,1,state, tray if i==0 else changed_tray
def run(new_stamp=1.05, now=1.03, changed=None, tracking=True, accepted=True):
    global changed_tray
    changed_tray=tray if changed is None else changed
    calls.clear()
    with patch.object(g,'snapshot',side_effect=snap), patch.object(g,'detect_local',return_value=[{}]), patch.object(g,'adjusted_point',return_value={'observed_point':(500,400),'point':(500,400)} if tracking else None), patch.object(g,'verify_latest_click',return_value={'accepted':accepted}) as verify:
        result=g.choose_relocated_food(waiting,[option],SimpleNamespace(),Planner(),{},(1.0,frame),lambda stamp,timeout:(new_stamp,frame),clock=lambda:now)
        if accepted and tracking and result['action']['kind']=='food':
            assert verify.call_args.kwargs['minimum_score']==.995
        return result
assert g.choose_relocated_food(food,[],None,None,None,None,None) is food
assert run()['action']['kind']=='food'
assert run(new_stamp=1.0)['action']['relocation']['reason']=='invalid_post_inference_interval'
assert run(new_stamp=1.6)['action']['relocation']['reason']=='invalid_post_inference_interval'
assert run(now=1.2)['action']['relocation']['reason']=='redetection_frame_too_old'
assert run(changed=[{'index':0,'label':'ham','score':.99}])['action']['relocation']['reason']=='order_counters_or_tray_changed'
assert run(tracking=False)['action']['relocation']['reason']=='new_point_tracking_rejected'
assert run(accepted=False)['action']['relocation']['reason']=='new_point_classification_rejected'
assert g.signature(state,[{'index':0,'label':'ham','score':.5}]) is None
assert g.signature(dict(state,counters=[{'remaining':None}]),[]) is None
assert waiting=={'action':{'kind':'wait','reason':'tracking failed'},'point':None,'planned':None}
print('PASS: approved primary identity; fresh capture interval; age; inventory change; optical-flow rejection; strict dual-point confirmation; unknown state; no mutation.')
