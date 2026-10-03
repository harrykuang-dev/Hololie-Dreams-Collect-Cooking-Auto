"""Try ranked planner-approved foods against the same latest captured frame."""
import time
from motion import adjusted_point
from latest_click import verify_latest_click


def choose_motion_food(options, model, old, old_stamp, latest, inventory, order, supplement=None):
    attempts = []
    latest_stamp, frame = latest
    for index, option in enumerate(options[:3]):
        action = dict(option['action'])
        limit = 8 if sum(inventory.values()) >= 5 else min(25, max(10, action.get('radius', 20) * old.shape[1] / 1536 * .35))
        small_onion = action['label']=='onion' and action.get('radius',20)<20
        small_shrimp=action['label']=='shrimp' and action.get('radius',20)<20
        if small_onion or small_shrimp:limit=min(limit,6)
        motion_diagnostics={}
        lead_seconds=time.monotonic()-latest_stamp+.06
        tracking = adjusted_point(old, old_stamp, frame, latest_stamp, (action['x'], action['y']),
                                  lead=lead_seconds, max_extrapolation=limit, details=True, diagnostics=motion_diagnostics)
        attempt = {'rank': index, 'label': action['label'], 'point': [action['x'], action['y']],
                   'frame_delta_ms': round((latest_stamp-old_stamp)*1000), 'tracked': tracking is not None, 'tracking_diagnostics': motion_diagnostics}
        attempts.append(attempt)
        if tracking is None:
            continue
        validation_started=time.perf_counter()
        strict_clear=action.get('reason')=='clear non-target triple'
        full_tray=sum(inventory.values())>=6
        if action.get('source') == 'supplement':
            if supplement is None:
                continue
            validation = supplement.verify_latest(frame, tracking['observed_point'], tracking['point'], action['label'], order)
        else:
            validation = verify_latest_click(model, frame, tracking['observed_point'], tracking['point'], action['label'], order, minimum_score=.995 if small_onion or small_shrimp or strict_clear or full_tray else .94)
        attempt['validation_ms']=(time.perf_counter()-validation_started)*1000
        validation['capture_age_ms'] = round((time.monotonic()-latest_stamp)*1000)
        attempt['validation'] = validation
        if validation['accepted']:
            action['execution_point'] = list(tracking['point'])
            action['validation'] = validation
            action['selected_rank'] = index
            action['motion_attempts'] = attempts
            return {'action': action, 'point': tracking['point'], 'planned': option['planned']}
        if validation['reason'] == 'game_phase_changed':
            break
    return {'action': {'kind': 'wait', 'reason': 'no approved food point survived latest-frame checks', 'motion_attempts': attempts},
            'point': None, 'planned': None}
