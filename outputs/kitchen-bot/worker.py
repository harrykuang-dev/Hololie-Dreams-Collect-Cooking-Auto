"""JSON-line image analysis and decision worker. Desktop input belongs to sky."""
import sys,json,cv2
from perception import Perception
from planner import Planner

p=Perception();planner=Planner()
print(json.dumps({'ready':True,'validation':p.validation}),flush=True)
for line in sys.stdin:
    try:
        req=json.loads(line)
        if req.get('reset'):planner=Planner();print(json.dumps({'reset':True}),flush=True);continue
        if req.get('commit'):planner.commit();print(json.dumps({'committed':True}),flush=True);continue
        result=p.analyze(cv2.imread(req['path']),req.get('debug'),fast=req.get('fast',True))
        action=planner.propose(result)
        print(json.dumps({'action':action,'status':planner.status(),'perception':result}),flush=True)
    except Exception as e:print(json.dumps({'error':str(e)}),flush=True)
