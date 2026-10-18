"""Exercise bounded issue bundles, error recovery and disabled collection."""
import json
import os
from pathlib import Path
import sys
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
            # More text and image bytes than either ring can retain.
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
            self.assertLessEqual(store.trace_size,diagnostics.TRACE_BYTES)
            with zipfile.ZipFile(output) as archive:
                names=archive.namelist()
                self.assertNotIn('secret.pt',names);self.assertNotIn('settings.json',names)
                meta=json.loads(archive.read('diagnostic.json'))
                self.assertEqual(meta['actions']['food'],1600)
                self.assertTrue(meta['dropped']['old_trace_lines'])
                self.assertTrue(meta['dropped']['old_images'])
                self.assertIn('runs/final.jpg',json.loads(archive.read('image-index.json')))
                text=archive.read('trace.jsonl').decode()
                self.assertNotIn(str(root),text);self.assertNotIn('ExampleName',text)
                self.assertNotIn('ExampleName',archive.read('diagnostic.json').decode())
                self.assertTrue(archive.testzip() is None)

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
