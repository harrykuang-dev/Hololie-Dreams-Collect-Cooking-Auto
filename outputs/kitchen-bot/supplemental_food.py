"""Work-only fallback detector. Existing food decisions retain their models."""
import copy
import time
from pathlib import Path
import numpy as np
import cv2
import torch
from segmenter import Segmenter, LABELS
from icon_classifier import IconClassifier
from latest_click import verify_latest_click

TARGETS = {'onion', 'shrimp', 'tuna'}

class SupplementalFood:
    def __init__(self, baseline, locator_path, classifier_path):
        # Share normalization, screen state and the original box classifier.
        self.model = copy.copy(baseline)
        self.model.model = Segmenter().to(baseline.device).eval()
        self.model.model.load_state_dict(torch.load(locator_path, map_location=baseline.device, weights_only=True)['model'])
        self.model.point_classifier = IconClassifier(baseline.device, str(Path(classifier_path).resolve()))

    def candidates(self, frame, perception):
        active = {card['label'] for card, count in zip(perception['recipe'], perception['counters'])
                  if count['remaining'] is None or count['remaining'] > 0} & TARGETS
        if perception['phase'] != 'playing' or not active:
            return []
        canonical, top, scale = self.model.normalize(frame)
        candidates, _, _ = self.model.detect(canonical, top, scale)
        candidates = [c for c in candidates if c['label'] in active and c['confidence'] >= .90
                      and not any(np.hypot(c['cx']-b['cx'], c['cy']-b['cy']) < 18
                                  and b.get('local_classifier', {}).get('label') == c['label']
                                  for b in perception['candidates'])]
        if not candidates:
            return []
        checks = self.model.point_classifier.classify([
            canonical[c['cy']-32:c['cy']+32, c['cx']-32:c['cx']+32] for c in candidates])
        extras = []
        for c, local in zip(candidates, checks):
            if local['label'] != c['label'] or local['score'] < .995:
                continue
            c = dict(c, surface_label=c['label'], local_classifier=local,
                     classifier={'label': c['label'], 'score': 0., 'alternatives': [], 'skipped': True},
                     source='supplement')
            if c['label'] in {'onion', 'shrimp'} and 10 <= c['radius'] < 20:
                x1,y1,x2,y2 = c['box']
                c['classifier'] = self.model.classifier.classify([
                    canonical[max(0,y1-4):min(864,y2+4),max(0,x1-4):min(1536,x2+4)]])[0]
            extras.append(c)
        return extras

    def propose(self, planner, perception, frame):
        before = copy.deepcopy(planner.__dict__)
        action = planner.propose(perception)
        if action['kind'] not in {'wait', 'shuffle'}:
            return action
        started = time.perf_counter()
        extras = self.candidates(frame, perception)
        if not extras:
            return action
        after = planner.__dict__
        planner.__dict__ = before
        augmented = dict(perception, candidates=perception['candidates'] + extras)
        augmented_action = planner.propose(augmented)
        if augmented_action['kind'] != 'food':
            planner.__dict__ = after
            return action
        perception['supplement_candidates'] = extras
        # Mark only candidates supplied by the new models, never old choices.
        for option in planner.food_options:
            if option['planned'].get('source') == 'supplement':
                option['action']['source'] = 'supplement'
        if planner.planned.get('source') == 'supplement':
            augmented_action['source'] = 'supplement'
        augmented_action['supplement_seconds'] = round(time.perf_counter()-started, 4)
        return augmented_action

    def verify_latest(self, frame, observed, predicted, label, order):
        validation = verify_latest_click(self.model, frame, observed, predicted, label, order, minimum_score=.995)
        if not validation['accepted']:
            return validation
        canonical, top, scale = self.model.normalize(frame)
        probabilities = self.model.predict(cv2.resize(canonical[175:735,318:1215], (448,280)))
        agreement = []
        for x,y in [observed, predicted]:
            cx,cy = x/scale,(y-top)/scale
            gx,gy = round((cx-318)*448/897),round((cy-175)/2)
            if not (0 <= gx < 448 and 0 <= gy < 280):
                agreement.append(False)
            else:
                p = probabilities[:,gy,gx]
                agreement.append(LABELS[int(p.argmax())] == label and float(p.max()) >= .90)
        validation['surface_agreement'] = agreement
        if not all(agreement):
            validation.update(accepted=False, reason='supplement_latest_surface_disagrees')
        return validation
