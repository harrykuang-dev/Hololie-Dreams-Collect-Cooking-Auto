"""Native capture with independent bounded video encoding and exact frame mapping."""
import json, os, queue, statistics, threading, time
import cv2
from diagnostic_store import open_log, mode


class Recording:
    def __init__(self,desktop,directory,fps=20):
        self.desktop=desktop;self.directory=directory;self.fps=fps
        self.condition=threading.Condition();self.latest=None;self.error=None;self.stopped=False
        self.packet_profiles={};self.capture_metrics=[];self.encode_metrics=[]
        self.jobs=queue.Queue(maxsize=4);self.dropped=0;self.max_queue=0;self.video=None
        self.rows_lock=threading.Lock();self.rows=open_log(directory/'video-frames.jsonl')
        if os.environ.get('COOKING_RECORD_VIDEO','1')=='1':
            self.video=cv2.VideoWriter(str(directory/'game.mp4'),cv2.VideoWriter_fourcc(*'mp4v'),fps,(desktop.w//2*2,desktop.h//2*2))
            if not self.video.isOpened():self.rows.close();raise RuntimeError('Video encoder unavailable')
        self.encoder=threading.Thread(target=self.encode,daemon=True)
        self.thread=threading.Thread(target=self.run,daemon=True)
        self.encoder.start();self.thread.start()

    def log_frame(self,row):
        with self.rows_lock:self.rows.write(json.dumps(row)+'\n');self.rows.flush()

    def fail(self,error):
        self.error=error;self.stopped=True
        with self.condition:self.condition.notify_all()

    def run(self):
        deadline=time.monotonic();last=None;capture_id=0
        try:
            while not self.stopped:
                started=time.monotonic();frame=self.desktop.capture();captured=time.monotonic()
                if frame is not None:
                    last=(started,frame)
                    with self.condition:
                        self.latest=last
                        self.packet_profiles[started]={'capture_started':started,'capture_completed':captured,'capture_ms':(captured-started)*1000}
                        if len(self.packet_profiles)>120:del self.packet_profiles[min(self.packet_profiles)]
                        self.condition.notify_all()
                    self.capture_metrics.append((started,captured-started))
                if self.video is not None and last is not None:
                    capture_id+=1
                    row={'capture_id':capture_id,'capture_started':last[0],'scheduled_at':started,'repeated_source':frame is None}
                    if self.jobs.full():
                        try:
                            discarded=self.jobs.get_nowait();self.jobs.task_done();self.dropped+=1
                            self.log_frame(dict(discarded[1],encoded=False,reason='encoder_queue_full'))
                        except queue.Empty:pass
                    self.jobs.put_nowait((last[1],row));self.max_queue=max(self.max_queue,self.jobs.qsize())
                deadline+=1/self.fps
                time.sleep(max(0,deadline-time.monotonic()))
                if time.monotonic()-deadline>1/self.fps:deadline=time.monotonic()
        except Exception as error:self.fail(error)

    def encode(self):
        index=0
        try:
            while True:
                item=self.jobs.get()
                try:
                    if item is None:break
                    frame,row=item;started=time.monotonic()
                    self.video.write(frame[:frame.shape[0]//2*2,:frame.shape[1]//2*2])
                    encoded=time.monotonic();self.encode_metrics.append(encoded-started)
                    self.log_frame(dict(row,encoded=True,video_frame=index,video_pts_seconds=index/self.fps,
                                        encode_ms=(encoded-started)*1000,encode_started=started))
                    index+=1
                finally:self.jobs.task_done()
        except Exception as error:self.fail(error)
        finally:
            if self.video is not None:self.video.release()

    def frame_after(self,stamp,timeout=.5):
        deadline=time.monotonic()+timeout
        with self.condition:
            while not self.error and not self.stopped:
                if self.latest is not None and self.latest[0]>=stamp:return self.latest[0],self.latest[1].copy()
                remaining=deadline-time.monotonic()
                if remaining<=0:return None
                self.condition.wait(remaining)
            if self.error:raise self.error
            return None

    def packet_profile(self,stamp):
        with self.condition:return dict(self.packet_profiles.get(stamp,{}))

    def latest_packet(self):
        with self.condition:
            if self.latest is None:return None
            return self.latest[0],self.latest[1].copy()

    def close(self):
        self.stopped=True
        with self.condition:self.condition.notify_all()
        self.thread.join(timeout=3)
        if self.thread.is_alive():raise RuntimeError('Capture thread did not stop')
        if self.encoder.is_alive():
            while True:
                try:self.jobs.put(None,timeout=.1);break
                except queue.Full:
                    if not self.encoder.is_alive():break
            self.encoder.join(timeout=10)
        if self.encoder.is_alive():raise RuntimeError('Video encoder did not stop')
        self.rows.close()
        if self.capture_metrics:
            stamps=[v[0] for v in self.capture_metrics];gaps=[b-a for a,b in zip(stamps,stamps[1:])]
            profile={'requested_fps':self.fps,'captured_frames':len(stamps),
                     'actual_average_fps':(len(stamps)-1)/(stamps[-1]-stamps[0]) if len(stamps)>1 else None,
                     'median_capture_ms':statistics.median(v[1] for v in self.capture_metrics)*1000,
                     'median_encode_ms':statistics.median(self.encode_metrics)*1000 if self.encode_metrics else 0,
                     'median_interval_ms':statistics.median(gaps)*1000 if gaps else None,
                     'encoder_queue_limit':4,'max_encoder_queue':self.max_queue,'dropped_video_frames':self.dropped,
                     'diagnostics_mode':mode(),
                     'note':'Independent native capture. Video frame mapping is available only with full recording.'}
            (self.directory/'capture-profile.json').write_text(json.dumps(profile,indent=2),encoding='utf-8')
        if self.error:raise self.error
