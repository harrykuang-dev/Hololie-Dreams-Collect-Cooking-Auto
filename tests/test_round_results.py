"""Recorded score digits, stable result capture, and permanent round evidence."""
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch,Mock
import zipfile
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'outputs/kitchen-bot'))
import result_reader as reader
import diagnostic_store as diagnostics


class Results(unittest.TestCase):
    def test_held_out_result_screens_and_jpeg_variants(self):
        import cv2
        examples=np.load(ROOT/'tests/fixtures/result-screens.npz')
        engine=reader.ResultReader()
        for i,(score,dishes) in enumerate(examples['labels']):
            image=np.zeros((864,1536,3),np.uint8)
            for field in reader.REGIONS:
                x1,y1,x2,y2=reader.REGIONS[field]
                image[y1:y2,x1:x2]=examples[f'{i}-{field}']
            # Unrelated historical best score area must not be read.
            image[460:510,1090:1290]=255
            for quality in (None,70,92):
                current=image if quality is None else cv2.imdecode(cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,quality])[1],cv2.IMREAD_COLOR)
                result=engine.read(current,{'phase':'results'})
                self.assertTrue(result['verified'],result)
                self.assertEqual((result['score'],result['completed_dishes']),(score,dishes))

    def test_non_result_screen_cannot_produce_a_score(self):
        result=reader.ResultReader().read(np.zeros((864,1536,3),np.uint8),{'phase':'playing'})
        self.assertFalse(result['verified']);self.assertIsNone(result['score'])

    def test_missing_digits_are_explicitly_unverified(self):
        result=reader.ResultReader().read(np.zeros((864,1536,3),np.uint8),{'phase':'results'})
        self.assertFalse(result['verified']);self.assertIsNone(result['score'])

    def model(self):
        return SimpleNamespace(normalize=lambda image:(image,0,1),screen_state=SimpleNamespace(classify=lambda image:{'phase':'results'}))

    def test_result_requires_new_frames_not_repeated_reads_of_one_old_frame(self):
        clock=[0.]
        def tick():clock[0]+=.1;return clock[0]
        recording=Mock();recording.frame_after.return_value=None
        engine=Mock();engine.read.return_value={'score':100,'completed_dishes':1,'verified':True}
        with patch.object(reader,'ResultReader',return_value=engine),patch.object(reader.time,'monotonic',side_effect=tick):
            frame,result=reader.collect_result(recording,self.model(),np.zeros((1,1,3)),True,timeout=.8)
        self.assertFalse(result['verified']);self.assertIsNone(result['score']);self.assertEqual(engine.read.call_count,1)

    def test_stable_fresh_frames_confirm_score_without_native_input(self):
        clock=[0.]
        def tick():clock[0]+=.1;return clock[0]
        image=np.zeros((1,1,3));recording=SimpleNamespace(frame_after=lambda *args,**kwargs:(clock[0],image))
        engine=Mock();engine.read.return_value={'score':9280,'completed_dishes':11,'verified':True}
        with patch.object(reader,'ResultReader',return_value=engine),patch.object(reader.time,'monotonic',side_effect=tick):
            frame,result=reader.collect_result(recording,self.model(),image,True)
        self.assertTrue(result['verified']);self.assertEqual(result['score'],9280);self.assertGreater(engine.read.call_count,1)

    def test_round_text_survives_while_old_final_screenshots_are_evicted(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(diagnostics,'MAX_ARCHIVE_BYTES',15_000):
            root=Path(folder);store=diagnostics.Store(root)
            for i in range(20):
                game=root/'runs'/f'standalone-{i}'
                store.log(game/'decisions.jsonl',json.dumps({'action':{'kind':'wait','reason':'motion'},'analysis_ms':11,'timing_diagnostics':{'perception_ms':7}}))
                store.log(game/'inputs.jsonl','{"kind":"food","input_started":1}')
                store.offer_frame(game/'final.jpg',np.random.default_rng(i).integers(0,256,(64,64,3),np.uint8))
                store.save_round(game,{'score':i*100,'completed_dishes':i,'verified':True})
            output=store.finish()
            self.assertLessEqual(output.stat().st_size,15_000)
            with zipfile.ZipFile(output) as archive:
                rounds=[json.loads(line) for line in archive.read('round-results.jsonl').splitlines()]
                self.assertEqual(len(rounds),20)
                self.assertEqual(archive.read('round-results.jsonl'),(root/'round-results.jsonl').read_bytes())
                for i,row in enumerate(rounds):
                    self.assertEqual(row['round'],i+1)
                    self.assertEqual(row['score'],i*100)
                    self.assertEqual(row['wait_reasons'],{'motion':1})
                    self.assertEqual(row['actual_inputs'],{'food':1})
                    self.assertEqual(row['timings']['analysis_ms']['median_ms'],11)
                    final=row['final_screenshot']['file']
                    retained=final in archive.namelist()
                    self.assertEqual(retained,(root/final).is_file())
                index=json.loads(archive.read('image-index.json'))
                self.assertLess(len(index),20);self.assertGreater(len(index),0)
                self.assertNotIn('runs/standalone-0/final.jpg',index)
                self.assertIn('runs/standalone-19/final.jpg',index)
                self.assertEqual(set(info['file'] for info in index.values()),
                                 set(name for name in archive.namelist() if name.startswith('round-screenshots/')))
                self.assertIsNone(archive.testzip())


if __name__=='__main__':unittest.main()
