"""Track an ingredient patch between already-recorded frames before clicking."""
import cv2,numpy as np,time
def adjusted_point(old,old_stamp,current,current_stamp,point,lead=.10,max_extrapolation=None,details=False,diagnostics=None):
    started=time.perf_counter()
    def note(reason,**values):
        if diagnostics is not None:diagnostics.update(reason=reason,elapsed_ms=(time.perf_counter()-started)*1000,frame_delta_seconds=current_stamp-old_stamp,lead_seconds=lead,max_extrapolation=max_extrapolation,**values)
    def reject(reason,**values):
        note(reason,**values);return None
    def result(observed,predicted):
        note('accepted',observed_point=list(observed),predicted_point=list(predicted))
        return {'point':predicted,'observed_point':observed,'delta_seconds':current_stamp-old_stamp} if details else predicted
    if current_stamp<old_stamp or current_stamp-old_stamp>.45:return reject('frame_gap')
    if current_stamp-old_stamp<.015:return result(point,point)
    x,y=point;h,w=old.shape[:2]
    radius=12;grid=np.array([[[x+dx,y+dy]] for dx in [-6,0,6] for dy in [-6,0,6]],np.float32)
    a=cv2.cvtColor(old,cv2.COLOR_BGR2GRAY);b=cv2.cvtColor(current,cv2.COLOR_BGR2GRAY)
    moved,status,error=cv2.calcOpticalFlowPyrLK(a,b,grid,None,winSize=(25,25),maxLevel=3,criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,20,.01))
    if moved is None:return reject('no_forward_flow')
    backward,back_status,_=cv2.calcOpticalFlowPyrLK(b,a,moved,None,winSize=(25,25),maxLevel=3)
    good=(status.ravel()>0)&(back_status.ravel()>0)&(error.ravel()<18)&(np.linalg.norm(backward-grid,axis=2).ravel()<1.5)
    if diagnostics is not None:diagnostics.update(valid_points=int(good.sum()),status_points=int(((status.ravel()>0)&(back_status.ravel()>0)).sum()),error_points=int((error.ravel()<18).sum()),roundtrip_points=int((np.linalg.norm(backward-grid,axis=2).ravel()<1.5).sum()))
    if good.sum()<3:
        # A flat, unchanged patch has no trackable texture but is stationary.
        aa=old[max(0,y-radius):min(h,y+radius),max(0,x-radius):min(w,x+radius)]
        bb=current[max(0,y-radius):min(h,y+radius),max(0,x-radius):min(w,x+radius)]
        return result(point,point) if aa.size and np.mean(np.abs(aa.astype(float)-bb.astype(float)))<3 else reject('insufficient_tracks')
    flows=(moved-grid).reshape(-1,2)[good];flow=np.median(flows,axis=0)
    if diagnostics is not None:diagnostics.update(flow=flow.tolist(),dispersion=float(np.median(np.linalg.norm(flows-flow,axis=1))))
    if np.median(np.linalg.norm(flows-flow,axis=1))>2.5 or np.linalg.norm(flow)>70:return reject('inconsistent_or_large_flow')
    # Include current capture age, cursor settling, and one Unity render frame.
    extrapolation=flow*min(.18,max(0,lead))/(current_stamp-old_stamp)
    if diagnostics is not None:diagnostics['extrapolation_pixels']=float(np.linalg.norm(extrapolation))
    if max_extrapolation is not None and np.linalg.norm(extrapolation)>max_extrapolation:return reject('extrapolation_limit')
    delta=flow+extrapolation
    if np.linalg.norm(delta)>90:return reject('total_displacement_limit')
    observed=(int(round(x+flow[0])),int(round(y+flow[1])))
    q=(int(round(x+delta[0])),int(round(y+delta[1])))
    return result(observed,q) if 0<=q[0]<w and 0<=q[1]<h else reject('outside_frame')
