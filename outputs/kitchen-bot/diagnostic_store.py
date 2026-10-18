"""Bounded, opt-in issue diagnostics. Never captures outside the game adapter."""
from collections import Counter, OrderedDict, deque
import io
import json
import os
from pathlib import Path
import platform
import queue
import re
import threading
import time
import zipfile

MAX_ARCHIVE_BYTES = 20_000_000
TRACE_BYTES = 4_000_000
EVENT_BYTES = 1_000_000
IMAGE_BYTES = 10_000_000
MAX_IMAGE_BYTES = 220_000
_active = None


def mode():
    return os.environ.get('COOKING_DIAGNOSTICS', 'legacy')


class Log(io.TextIOBase):
    def __init__(self, path):
        self.path = path

    def writable(self):return True

    def write(self, text):
        if _active is not None:_active.log(self.path, text)
        return len(text)

    def flush(self):pass


def open_log(path):
    if mode() == 'legacy':return Path(path).open('w', encoding='utf8')
    return Log(path)


def save_frame(path, frame):
    """Return True if handled, including disabled mode; legacy uses its writer."""
    if mode() == 'legacy':return False
    if _active is not None:_active.offer_frame(path, frame)
    return True


def configure(root, enabled, **details):
    global _active
    os.environ['COOKING_DIAGNOSTICS'] = 'compact' if enabled else 'off'
    _active = Store(root, details) if enabled else None
    return _active


class Store:
    def __init__(self, root, details=None):
        self.root = Path(root).resolve()
        self.details = dict(details or {})
        self.details.update(python=platform.python_version(), system=platform.platform(),
                            processor=platform.processor(), started_at=time.time())
        self.traces = deque();self.events = deque()
        self.trace_size = self.event_size = 0
        self.images = OrderedDict();self.image_size = 0
        self.lock = threading.Lock();self.jobs = queue.Queue(maxsize=2)
        self.dropped = Counter();self.counts = Counter();self.waits = Counter()
        self.labels = {};self.last_regular = 0;self.closed = False
        self.thread = threading.Thread(target=self.encode, daemon=True);self.thread.start()

    def relative(self, path):
        try:return Path(path).resolve().relative_to(self.root).as_posix()
        except ValueError:return Path(path).name

    def scrub(self, value):
        if isinstance(value, dict):return {str(k):self.scrub(v) for k,v in value.items()}
        if isinstance(value, (list,tuple)):return [self.scrub(v) for v in value]
        if not isinstance(value,str):return value
        for original in (str(self.root), self.root.as_posix()):value=value.replace(original,'session')
        # Tracebacks and model paths may contain the Windows account name.
        value=re.sub(r'(?i)[a-z]:[\\/]Users[\\/][^\\/\s"\']+', '<user>', value)
        return value

    def log(self, path, text):
        for line in text.splitlines():
            if not line:return
            try:row=json.loads(line)
            except ValueError:row={'message':line[:8192]}
            stream=self.relative(path)
            data=json.dumps(self.scrub({'stream':stream,'data':row}),ensure_ascii=False,separators=(',',':')).encode('utf8')+b'\n'
            if len(data)>96_000:
                self.dropped['oversized_trace']+=1;continue
            critical=Path(path).name=='inputs.jsonl' or 'transitions' in stream
            with self.lock:
                action=row.get('action') or {}
                if action:
                    kind=action.get('kind','unknown');self.counts[kind]+=1
                    if kind=='wait':self.waits[action.get('reason','unknown')]+=1
                    label=action.get('label')
                    if label:
                        metric=self.labels.setdefault(label,{'decisions':0,'analysis_ms':0})
                        metric['decisions']+=1;metric['analysis_ms']+=row.get('analysis_ms',0)
                target=self.events if critical else self.traces
                attr='event_size' if critical else 'trace_size'
                limit=EVENT_BYTES if critical else TRACE_BYTES
                target.append(data);setattr(self,attr,getattr(self,attr)+len(data))
                while getattr(self,attr)>limit:
                    setattr(self,attr,getattr(self,attr)-len(target.popleft()));self.dropped['old_trace_lines']+=1

    def offer_frame(self, path, frame):
        if self.closed:return
        name=Path(path).name
        priority=2 if name.startswith('final') else 1 if ('diagnostic-' in name or 'transition-' in name) else 0
        # Keep occasional regular frames and failed-motion evidence, not every inference.
        now=time.monotonic()
        if not priority and now-self.last_regular<2:
            self.dropped['sampled_frames']+=1;return
        if not priority:self.last_regular=now
        try:self.jobs.put_nowait((self.relative(path),frame.copy(),priority))
        except queue.Full:
            self.dropped['image_queue_full']+=1
            if priority:
                try:self.jobs.get_nowait();self.jobs.task_done()
                except queue.Empty:pass
                try:self.jobs.put_nowait((self.relative(path),frame.copy(),priority))
                except queue.Full:pass

    def encode(self):
        import cv2
        while True:
            item=self.jobs.get()
            try:
                if item is None:return
                name,frame,priority=item
                original=[frame.shape[1],frame.shape[0]]
                ratio=min(1,1536/max(original))
                if ratio<1:frame=cv2.resize(frame,None,fx=ratio,fy=ratio,interpolation=cv2.INTER_AREA)
                for quality in (82,70,55):
                    ok,data=cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,quality])
                    if not ok:raise ValueError('JPEG encoder unavailable')
                    if len(data)<=MAX_IMAGE_BYTES:break
                if len(data)>MAX_IMAGE_BYTES:
                    frame=cv2.resize(frame,None,fx=.65,fy=.65,interpolation=cv2.INTER_AREA)
                    ok,data=cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,65])
                if not ok or len(data)>MAX_IMAGE_BYTES:
                    self.dropped['oversized_images']+=1;continue
                with self.lock:
                    if name in self.images:self.image_size-=len(self.images.pop(name)[0])
                    self.images[name]=(data.tobytes(),{'original_size':original,'stored_size':[frame.shape[1],frame.shape[0]],'priority':priority})
                    self.image_size+=len(data)
                    # Long sessions must not replace every useful frame with result screens.
                    group_limit=(2_000_000,6_000_000,2_000_000)[priority]
                    count_limit=(20,60,20)[priority]
                    group=[k for k,v in self.images.items() if v[1]['priority']==priority]
                    group_size=sum(len(self.images[k][0]) for k in group)
                    while group_size>group_limit or len(group)>count_limit:
                        key=group.pop(0);size=len(self.images.pop(key)[0])
                        self.image_size-=size;group_size-=size;self.dropped['old_images']+=1
                    while self.image_size>IMAGE_BYTES or len(self.images)>100:
                        lowest=min(v[1]['priority'] for v in self.images.values())
                        key=next(k for k,v in self.images.items() if v[1]['priority']==lowest)
                        self.image_size-=len(self.images.pop(key)[0]);self.dropped['old_images']+=1
            except Exception as error:
                self.details['image_error']=self.scrub(str(error));self.dropped['image_errors']+=1
            finally:self.jobs.task_done()

    def finish(self, error=None):
        if self.closed:return
        self.closed=True
        self.jobs.put(None);self.jobs.join();self.thread.join()
        self.root.mkdir(parents=True,exist_ok=True)
        if error:self.details['exception']=error
        self.details.update(ended_at=time.time(),mode='compact',archive_limit_bytes=MAX_ARCHIVE_BYTES,
                            screenshots='sampled game frames; no full video',
                            dropped=dict(self.dropped),actions=dict(self.counts),wait_reasons=dict(self.waits),
                            per_food=self.labels)
        entries={}
        # Whitelist only runtime metadata; source, weights, settings and old media are excluded.
        metadata_budget=1_000_000
        for path in sorted(self.root.rglob('*.json')):
            if path.name not in ('summary.json','version.json','capture-profile.json','model-check.json'):continue
            if path.stat().st_size>min(metadata_budget,128_000):continue
            try:data=json.dumps(self.scrub(json.loads(path.read_text(encoding='utf8'))),ensure_ascii=False,indent=2).encode('utf8')
            except (ValueError,OSError):continue
            entries['metadata/'+self.relative(path)]=data;metadata_budget-=len(data)
        log=self.root/'launcher.log'
        if log.exists():
            with log.open('rb') as stream:
                stream.seek(max(0,log.stat().st_size-128_000))
                entries['launcher-tail.txt']=self.scrub(stream.read().decode('utf8','replace')).encode('utf8')
        entries['trace.jsonl']=b''.join(self.traces)
        entries['inputs.jsonl']=b''.join(self.events)
        index={}
        for name,(data,info) in self.images.items():
            saved='screenshots/'+name+'.jpg'
            entries[saved]=data;index[name]={'file':saved,**info}
        entries['image-index.json']=json.dumps(index,ensure_ascii=False,indent=2).encode('utf8')
        entries['diagnostic.json']=json.dumps(self.scrub(self.details),ensure_ascii=False,indent=2).encode('utf8')
        pending=self.root/'diagnostic.pending'
        with zipfile.ZipFile(pending,'w',zipfile.ZIP_DEFLATED,compresslevel=3) as archive:
            budget=MAX_ARCHIVE_BYTES-100_000
            for name,data in entries.items():
                # Reserve uncompressed bytes + header overhead: ZIP remains bounded even for noise.
                cost=len(data)+512+len(name.encode('utf8'))*2
                if cost>budget:continue
                archive.writestr(name,data);budget-=cost
        if pending.stat().st_size>MAX_ARCHIVE_BYTES:
            raise RuntimeError('Diagnostic archive exceeded its size limit')
        output=self.root/('CollectCooking-'+self.root.name+'.zip');pending.replace(output)
        return output
