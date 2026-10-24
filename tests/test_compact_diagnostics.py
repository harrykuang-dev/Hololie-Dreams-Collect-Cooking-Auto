"""Exercise complete durable logs, bounded media and disabled collection."""
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'outputs/kitchen-bot')]
import diagnostic_store as diagnostics
import gui
import standalone


class CompactDiagnostics(unittest.TestCase):
    def tearDown(self):diagnostics._active=None

    def test_off_never_saves_frames_logs_or_starts_image_writer(self):
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'COOKING_DIAGNOSTICS':'off'}):
            path=Path(folder)/'frame.jpg';writer=standalone.FrameWriter()
            writer.save(path,np.zeros((64,64,3),np.uint8));writer.close()
            with diagnostics.open_log(Path(folder)/'decisions.jsonl') as log:log.write('{"action":{"kind":"food"}}\n')
            self.assertIsNone(writer.thread)
            self.assertEqual(list(Path(folder).iterdir()),[])

    def test_long_noisy_run_keeps_archive_under_limit_and_scrubs_paths(self):
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'COOKING_DIAGNOSTICS':'compact'}):
            root=Path(folder);store=diagnostics.Store(root,{'test':True})
            diagnostics._active=store
            # More text than the old ring retained; only images may be evicted.
            for i in range(1600):
                store.log(root/'runs/standalone-1/decisions.jsonl',json.dumps({
                    'action':{'kind':'food','label':'onion'},'analysis_ms':20,
                    'path':str(root/'runs/frame.jpg'),'debug':'x'*8192,
                    'private':r'C:\Users\ExampleName\Documents\game.pt'}))
            frame=np.random.default_rng(17).integers(0,256,(1000,1800,3),np.uint8)
            for i in range(110):
                store.offer_frame(root/f'runs/frame-{i:05}-diagnostic-old.png',frame)
                store.jobs.join()
            store.offer_frame(root/'runs/final.jpg',frame);store.jobs.join()
            (root/'secret.pt').write_bytes(b'not a model to share')
            (root/'settings.json').write_text('{"private":true}')
            (root/'summary.json').write_text(json.dumps({'directory':str(root/'runs')}))
            output=store.finish('test failure at C:\\Users\\ExampleName\\app.py')
            self.assertLessEqual(output.stat().st_size,diagnostics.MAX_ARCHIVE_BYTES)
            self.assertLessEqual(store.image_size,diagnostics.IMAGE_BYTES)
            self.assertGreater(store.trace_size,4_000_000)
            with zipfile.ZipFile(output) as archive:
                names=archive.namelist()
                self.assertNotIn('secret.pt',names);self.assertNotIn('settings.json',names)
                meta=json.loads(archive.read('diagnostic.json'))
                self.assertEqual(meta['actions']['food'],1600)
                self.assertNotIn('old_trace_lines',meta['dropped'])
                self.assertTrue(meta['dropped']['old_images'])
                self.assertIn('runs/final.jpg',json.loads(archive.read('image-index.json')))
                text=archive.read('trace.jsonl').decode()
                self.assertEqual(len(text.splitlines()),1600)
                self.assertEqual(archive.read('trace.jsonl'),(root/'trace.jsonl').read_bytes())
                self.assertNotIn(str(root),text);self.assertNotIn('ExampleName',text)
                self.assertNotIn('ExampleName',archive.read('diagnostic.json').decode())
                self.assertTrue(archive.testzip() is None)

    def test_ten_games_keep_every_event_and_large_decision_on_disk_and_in_zip(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);store=diagnostics.Store(root)
            for game in range(10):
                for click in range(120):
                    store.log(root/f'runs/game-{game}/inputs.jsonl',json.dumps({
                        'click':click,'detail':'x'*1024}))
                store.log(root/f'runs/game-{game}/decisions.jsonl',json.dumps({
                    'decision':game,'detail':'x'*110_000}))
            store.log(root/'transitions.jsonl','\n'+json.dumps({'transition':'last'}))
            store.log(root/'decisions.jsonl','unstructured detail '+'x'*12_000)
            self.assertGreater(store.event_size,1_000_000)
            # Visible to a separate reader before finish, not just an in-memory ring.
            self.assertEqual(len((root/'inputs.jsonl').read_bytes().splitlines()),1201)
            output=store.finish()
            with zipfile.ZipFile(output) as archive:
                for name,count in (('trace.jsonl',11),('inputs.jsonl',1201)):
                    self.assertEqual(archive.read(name),(root/name).read_bytes())
                    rows=[json.loads(line) for line in archive.read(name).splitlines()]
                    self.assertEqual(len(rows),count)
                self.assertEqual(rows[0]['stream'],'runs/game-0/inputs.jsonl')
                self.assertEqual(rows[-2]['stream'],'runs/game-9/inputs.jsonl')
                self.assertEqual(rows[-1]['data']['transition'],'last')

    def test_process_exit_before_packaging_keeps_all_written_records(self):
        with tempfile.TemporaryDirectory() as folder:
            script=("import os,sys;from pathlib import Path;"
                    f"sys.path.insert(0,{str(ROOT/'outputs/kitchen-bot')!r});"
                    "import diagnostic_store as d;root=Path(sys.argv[1]);s=d.Store(root);"
                    "s.log(root/'inputs.jsonl','{\"click\":1}');"
                    "s.log(root/'decisions.jsonl','{\"decision\":1}');os._exit(0)")
            subprocess.run([sys.executable,'-c',script,folder],check=True,timeout=20)
            root=Path(folder)
            self.assertEqual(json.loads((root/'inputs.jsonl').read_bytes())['data']['click'],1)
            self.assertEqual(json.loads((root/'trace.jsonl').read_bytes())['data']['decision'],1)
            self.assertFalse(list(root.glob('*.zip')))

    def test_log_only_overflow_splits_valid_archives_without_losing_records(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(diagnostics,'MAX_ARCHIVE_BYTES',4096):
            root=Path(folder);store=diagnostics.Store(root)
            store.log(root/'decisions.jsonl',json.dumps({'data':os.urandom(20_000).hex()}))
            output=store.finish()
            self.assertGreater(len(store.archives),1)
            pieces={}
            for path in store.archives:
                self.assertLessEqual(path.stat().st_size,4096)
                with zipfile.ZipFile(path) as archive:
                    self.assertIsNone(archive.testzip())
                    for name in archive.namelist():pieces[name]=archive.read(name)
            restored=b''.join(pieces[name] for name in sorted(pieces) if name.startswith('trace.jsonl.parts/'))
            self.assertEqual(restored,(root/'trace.jsonl').read_bytes())
            self.assertEqual(json.loads(pieces['diagnostic.json'])['archive_hard_limit_bytes'],4096)

    def test_archive_budget_removes_oldest_screenshots_before_any_logs(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(diagnostics,'MAX_ARCHIVE_BYTES',20_000):
            root=Path(folder);store=diagnostics.Store(root)
            store.log(root/'inputs.jsonl','{"click":1}')
            store.images['old']=(os.urandom(14_000),{'priority':2})
            store.images['new']=(os.urandom(14_000),{'priority':0})
            output=store.finish()
            self.assertLessEqual(output.stat().st_size,20_000)
            with zipfile.ZipFile(output) as archive:
                index=json.loads(archive.read('image-index.json'))
                self.assertNotIn('old',index);self.assertIn('new',index)
                self.assertNotIn('screenshots/old.jpg',archive.namelist())
                self.assertIn('screenshots/new.jpg',archive.namelist())
                self.assertEqual(archive.read('inputs.jsonl'),(root/'inputs.jsonl').read_bytes())

    def test_real_twenty_mb_limit_keeps_incompressible_text_in_bounded_volumes(self):
        import hashlib
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);store=diagnostics.Store(root)
            # One unusually large record also exercises byte splitting across a
            # JSON line. Hex-encoded random bytes compress to over 20 MB.
            store.log(root/'decisions.jsonl',json.dumps({'detail':os.urandom(19_000_000).hex()}))
            expected=hashlib.sha256((root/'trace.jsonl').read_bytes()).digest()
            store.finish()
            self.assertGreater(len(store.archives),1)
            restored=hashlib.sha256()
            for path in store.archives:
                self.assertLessEqual(path.stat().st_size,20_000_000)
                with zipfile.ZipFile(path) as archive:
                    self.assertIsNone(archive.testzip())
                    for name in archive.namelist():
                        if name.startswith('trace.jsonl.parts/'):
                            restored.update(archive.read(name))
            self.assertEqual(restored.digest(),expected)

    def test_image_memory_limit_evicts_oldest_regardless_of_priority(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(diagnostics,'IMAGE_BYTES',1000):
            root=Path(folder);store=diagnostics.Store(root)
            store.images['old']=(b'x'*1000,{'priority':2});store.image_size=1000
            store.media_order['old']=0
            store.offer_frame(root/'new-diagnostic.png',np.zeros((32,32,3),np.uint8))
            store.jobs.join();store.finish()
            self.assertNotIn('old',store.images)
            self.assertIn('new-diagnostic.png',store.images)

    def test_model_load_failure_still_produces_issue_bundle_without_game_input(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            args=['gui.py','--worker','--developer-mode','--games','1',
                  '--output',str(root/'runs'),'--control-file',str(root/'stop')]
            with patch.object(sys,'argv',args),patch.object(standalone,'load_models',side_effect=RuntimeError('test load failure')),\
                 patch.object(standalone,'Desktop',side_effect=AssertionError('Native adapter forbidden')) as desktop:
                with self.assertRaisesRegex(RuntimeError,'test load failure'):gui.worker()
                desktop.assert_not_called()
            archives=list(root.glob('*.zip'));self.assertEqual(len(archives),1)
            with zipfile.ZipFile(archives[0]) as archive:
                self.assertIn('test load failure',archive.read('diagnostic.json').decode())


if __name__=='__main__':unittest.main()
