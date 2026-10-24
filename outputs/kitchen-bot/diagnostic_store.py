"""Complete on-disk event logs with bounded, opt-in game screenshots."""
from collections import Counter, OrderedDict
import io
import hashlib
import json
import os
from pathlib import Path
import platform
import queue
import re
import threading
import time
import zipfile
import zlib

MAX_ARCHIVE_BYTES = 20_000_000
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


def save_round(directory,report):
    if _active is not None:return _active.save_round(directory,report)
    if mode()=='legacy':
        path=Path(directory)/'result.json'
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')


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
        self.root.mkdir(parents=True,exist_ok=True)
        # Append every record to disk immediately, including across game boundaries.
        # Keep these files after packaging so an interrupted run is recoverable.
        self.trace_file=(self.root/'trace.jsonl').open('ab')
        self.event_file=(self.root/'inputs.jsonl').open('ab')
        self.round_file=(self.root/'round-results.jsonl').open('ab')
        self.trace_size = self.event_size = 0
        self.images = OrderedDict();self.image_size = 0
        self.final_images={};self.media_order=OrderedDict();self.game_stats={};self.round_count=0
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
            if not line:continue
            try:row=json.loads(line)
            except ValueError:row={'message':line}
            stream=self.relative(path)
            data=json.dumps(self.scrub({'stream':stream,'data':row}),ensure_ascii=False,separators=(',',':')).encode('utf8')+b'\n'
            critical=Path(path).name=='inputs.jsonl' or 'transitions' in stream
            with self.lock:
                if self.closed:raise ValueError('Diagnostic store is closed')
                target=self.event_file if critical else self.trace_file
                target.write(data);target.flush()
                attr='event_size' if critical else 'trace_size'
                setattr(self,attr,getattr(self,attr)+len(data))
                action=row.get('action') or {}
                if action:
                    kind=action.get('kind','unknown');self.counts[kind]+=1
                    if kind=='wait':self.waits[action.get('reason','unknown')]+=1
                    label=action.get('label')
                    if label:
                        metric=self.labels.setdefault(label,{'decisions':0,'analysis_ms':0})
                        metric['decisions']+=1;metric['analysis_ms']+=row.get('analysis_ms',0)
                game=next((part for part in Path(stream).parts if part.startswith('standalone-')),None)
                if game:
                    stats=self.game_stats.setdefault(game,{'actions':Counter(),'wait_reasons':Counter(),'inputs':Counter(),'timings':{}})
                    if action:
                        stats['actions'][action.get('kind','unknown')]+=1
                        if action.get('kind')=='wait':stats['wait_reasons'][action.get('reason','unknown')]+=1
                        timing={'analysis_ms':row.get('analysis_ms'),**row.get('timing_diagnostics',{})}
                        for key,value in timing.items():
                            if key.endswith('_ms') and isinstance(value,(int,float)):
                                stats['timings'].setdefault(key,[]).append(value)
                    elif row.get('kind') and ('input_started' in row or row.get('followup')):
                        stats['inputs'][row['kind']]+=1

    def offer_frame(self, path, frame):
        if self.closed:return
        name=Path(path).name
        priority=2 if name.startswith('final') else 1 if ('diagnostic-' in name or 'transition-' in name) else 0
        if priority==2:
            self.save_final(path,frame)
            return
        # Keep occasional regular frames and failed-motion evidence, not every inference.
        now=time.monotonic()
        if not priority and now-self.last_regular<2:
            self.dropped['sampled_frames']+=1;return
        if not priority:self.last_regular=now
        try:self.jobs.put_nowait((self.relative(path),frame.copy(),priority,now))
        except queue.Full:
            self.dropped['image_queue_full']+=1
            if priority:
                try:self.jobs.get_nowait();self.jobs.task_done()
                except queue.Empty:pass
                try:self.jobs.put_nowait((self.relative(path),frame.copy(),priority,now))
                except queue.Full:pass

    def encode(self):
        import cv2
        while True:
            item=self.jobs.get()
            try:
                if item is None:return
                name,frame,priority,captured_at=item
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
                    self.media_order.pop(name,None);self.media_order[name]=captured_at
                    self.trim_images()
            except Exception as error:
                self.details['image_error']=self.scrub(str(error));self.dropped['image_errors']+=1
            finally:self.jobs.task_done()

    def save_final(self,path,frame):
        """Save result evidence, subject to the same oldest-first media budget."""
        import cv2
        original=[frame.shape[1],frame.shape[0]]
        ratio=min(1,1536/max(original))
        if ratio<1:frame=cv2.resize(frame,None,fx=ratio,fy=ratio,interpolation=cv2.INTER_AREA)
        ok,data=cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,92])
        if not ok:raise RuntimeError('Final result screenshot encoding failed')
        name=self.relative(path);saved='round-screenshots/'+name+'.jpg'
        file=self.root/saved;file.parent.mkdir(parents=True,exist_ok=True)
        temporary=file.with_suffix('.pending');temporary.write_bytes(data.tobytes());temporary.replace(file)
        with self.lock:
            old=self.final_images.get(name)
            if old:self.image_size-=old['bytes']
            self.final_images[name]={'file':saved,'original_size':original,
                'stored_size':[frame.shape[1],frame.shape[0]],'priority':2,
                'retention':'capacity-limited','bytes':len(data),
                'sha256':hashlib.sha256(data).hexdigest()}
            self.image_size+=len(data)
            self.media_order.pop(name,None);self.media_order[name]=time.monotonic()
            self.trim_images()

    def remove_image(self,name):
        self.media_order.pop(name,None)
        if name in self.final_images:
            info=self.final_images.pop(name)
            self.image_size-=info['bytes']
            (self.root/info['file']).unlink(missing_ok=True)
            self.dropped['old_final_images']+=1
        elif name in self.images:
            self.image_size-=len(self.images.pop(name)[0])
        self.dropped['old_images']+=1

    def trim_images(self):
        while self.image_size>IMAGE_BYTES or len(self.media_order)>100:
            self.remove_image(min(self.media_order,key=self.media_order.get))

    def save_round(self,directory,report):
        import statistics
        game=Path(directory).name
        with self.lock:
            stats=self.game_stats.pop(game,{'actions':{},'wait_reasons':{},'inputs':{},'timings':{}})
            if report.get('inference'):
                self.details.update(device=report['inference']['backend'],inference=report['inference'])
            timings={key:{'count':len(values),'median_ms':statistics.median(values),
                          'mean_ms':statistics.mean(values),'total_ms':sum(values),'max_ms':max(values)}
                     for key,values in stats['timings'].items() if values}
            final=self.final_images.get(self.relative(Path(directory)/'final.jpg'))
            row=self.scrub({'schema_version':1,'round':self.round_count+1,'game_id':game,
                           'model':self.details.get('model'),'recorded_at':time.time(),**report,
                           'actions':dict(stats['actions']),'wait_reasons':dict(stats['wait_reasons']),
                           'actual_inputs':dict(stats['inputs']),'timings':timings,
                           'final_screenshot':final})
            self.round_file.write(json.dumps(row,ensure_ascii=False,separators=(',',':')).encode('utf8')+b'\n')
            self.round_file.flush()
            self.round_count+=1
            if report.get('inference'):
                self.details.update(device=report['inference']['backend'],inference=report['inference'])
        return row

    def finish(self, error=None):
        if self.closed:return
        with self.lock:
            self.closed=True
            self.trace_file.close();self.event_file.close();self.round_file.close()
        self.jobs.put(None);self.jobs.join();self.thread.join()
        self.root.mkdir(parents=True,exist_ok=True)
        if error:self.details['exception']=error
        self.details.update(ended_at=time.time(),mode='compact',archive_target_bytes=MAX_ARCHIVE_BYTES,
                            log_retention='complete; persistent on-disk; never size-trimmed',
                            round_retention='all result text; screenshots rotate oldest first',
                            final_screenshot_retention='capacity-limited; oldest first',
                            archive_hard_limit_bytes=MAX_ARCHIVE_BYTES,
                            overflow_policy='complete text split across bounded ZIP files',
                            final_screenshots=len(self.final_images),
                            rounds_recorded=self.round_count,
                            screenshots='sampled game frames; no full video',
                            dropped=dict(self.dropped),actions=dict(self.counts),wait_reasons=dict(self.waits),
                            per_food=self.labels)
        entries={}
        # Whitelist only runtime metadata; source, weights, settings and old media are excluded.
        metadata_budget=1_000_000
        for path in sorted(self.root.rglob('*.json')):
            if path.name not in ('summary.json','version.json','capture-profile.json','model-check.json','result-check.json'):continue
            if path.stat().st_size>min(metadata_budget,128_000):continue
            try:data=json.dumps(self.scrub(json.loads(path.read_text(encoding='utf8'))),ensure_ascii=False,indent=2).encode('utf8')
            except (ValueError,OSError):continue
            entries['metadata/'+self.relative(path)]=data;metadata_budget-=len(data)
        log=self.root/'launcher.log'
        if log.exists():
            with log.open('rb') as stream:
                stream.seek(max(0,log.stat().st_size-128_000))
                entries['launcher-tail.txt']=self.scrub(stream.read().decode('utf8','replace')).encode('utf8')
        # A final screenshot is evidence only; round-results remains complete
        # even when its referenced image has been evicted. The index lists only
        # retained files and is authoritative for screenshot availability.
        for name in (*self.images,*self.final_images):
            self.media_order.setdefault(name,0)
        pending=self.root/'diagnostic.pending'
        output=self.root/('CollectCooking-'+self.root.name+'.zip')
        while True:
            index=dict(self.final_images)
            for name,(data,info) in self.images.items():
                index[name]={'file':'screenshots/'+name+'.jpg',**info}
            self.details['dropped']=dict(self.dropped)
            self.details['final_screenshots']=len(self.final_images)
            entries['image-index.json']=json.dumps(index,ensure_ascii=False,indent=2).encode('utf8')
            entries['diagnostic.json']=json.dumps(self.scrub(self.details),ensure_ascii=False,indent=2).encode('utf8')
            with zipfile.ZipFile(pending,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
                for name in ('trace.jsonl','inputs.jsonl','round-results.jsonl'):
                    archive.write(self.root/name,name)
                for info in self.final_images.values():
                    archive.write(self.root/info['file'],info['file'])
                for name,(data,info) in self.images.items():
                    archive.writestr(index[name]['file'],data)
                for name,data in entries.items():archive.writestr(name,data)
            # Check the CLOSED ZIP, including central directory and metadata.
            if pending.stat().st_size<=MAX_ARCHIVE_BYTES:
                pending.replace(output)
                self.archives=[output]
                return output
            if self.media_order:
                excess=pending.stat().st_size-MAX_ARCHIVE_BYTES+4096
                removed=0
                while self.media_order and removed<excess:
                    name=min(self.media_order,key=self.media_order.get)
                    removed+=self.final_images[name]['bytes'] if name in self.final_images else len(self.images[name][0])
                    self.remove_image(name)
                continue
            # Text can exceed the limit too. Preserve all bytes on disk and in
            # independent, valid ZIP volumes rather than truncate any records.
            return self.split_text_archives(output,pending,entries)

    def split_text_archives(self,output,pending,entries):
        limit=MAX_ARCHIVE_BYTES
        chunk_bytes=max(1,(limit-2048)//2)
        explanation=("Each ZIP is at most %d bytes. Extract all ZIPs into one folder. "
                     "For NAME.parts/000001 etc., concatenate the numbered files "
                     "in ascending order as raw bytes to reconstruct NAME exactly. "
                     "Chunks may split a UTF-8 character or JSON line. Original "
                     "complete JSONL files also remain in the session folder.\n" % limit).encode('utf8')
        def pieces():
            for name in ('trace.jsonl','inputs.jsonl','round-results.jsonl'):
                path=self.root/name
                size=path.stat().st_size
                with path.open('rb') as stream:
                    if size<=chunk_bytes:
                        yield name,stream.read()
                    else:
                        number=0
                        while data:=stream.read(chunk_bytes):
                            number+=1;yield f'{name}.parts/{number:06d}',data
            for name,data in {'ARCHIVES.txt':explanation,**entries}.items():
                if len(data)<=chunk_bytes:yield name,data
                else:
                    for number,start in enumerate(range(0,len(data),chunk_bytes),1):
                        yield f'{name}.parts/{number:06d}',data[start:start+chunk_bytes]
        staged=[];archive=None;estimate=22
        try:
            for name,data in pieces():
                # zlib includes six more bytes than ZIP's raw DEFLATE; include
                # both ZIP headers, UTF-8 names and generous per-entry reserve.
                cost=len(zlib.compress(data,6))+256+2*len(name.encode('utf8'))
                if cost+22>limit:raise ValueError('Diagnostic ZIP limit too small')
                if archive is None or estimate+cost>limit:
                    if archive is not None:archive.close()
                    path=self.root/f'diagnostic-part-{len(staged)+1:03d}.pending'
                    staged.append(path)
                    archive=zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=6)
                    estimate=22
                archive.writestr(name,data);estimate+=cost
            if archive is not None:archive.close();archive=None
            if any(path.stat().st_size>limit for path in staged):
                raise RuntimeError('Diagnostic ZIP exceeded hard limit')
            self.archives=[]
            for number,path in enumerate(staged,1):
                target=output if number==1 else output.with_name(output.stem+f'-part{number:03d}.zip')
                path.replace(target);self.archives.append(target)
            pending.unlink(missing_ok=True)
            return output
        finally:
            if archive is not None:archive.close()
            for path in staged:path.unlink(missing_ok=True)
