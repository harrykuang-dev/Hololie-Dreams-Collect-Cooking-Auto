"""Staged fallback only. No native input; no deployed runtime imports this file."""
import copy
import time
from local_relocation import detect_local
from motion import adjusted_point
from latest_click import verify_latest_click


def snapshot(model, frame):
    canonical, top, scale = model.normalize(frame)
    state = model.screen_state.classify(canonical)
    tray = model.classifier.tray(canonical) if model.classifier else model.icons.tray(canonical)
    return canonical, top, scale, state, tray


def signature(state, tray):
    # Unknown slots cannot certify unchanged inventory.
    if any(item.get('score', 0) <= .55 for item in tray):
        return None
    if sorted(item['index'] for item in tray) != list(range(len(tray))):
        return None
    counters = tuple(item['remaining'] for item in state['counters'])
    if any(n is None for n in counters):
        return None
    return state['phase'], state['order'], counters, tuple((item['index'], item['label']) for item in tray)


def choose_relocated_food(previous_choice, options, model, planner, perception,
                          packet, frame_after, clock=time.monotonic):
    """Keep approved primary untouched; otherwise re-detect ONE required food.

    frame_after is the recording's capture callback. Both capture timestamps
    must be real host capture timestamps, never video-FPS approximations.
    The caller must still enforce focus and capture age at input dispatch.
    """
    if previous_choice['action']['kind'] != 'wait':
        return previous_choice
    report = {'accepted': False}
    result = {'action': dict(previous_choice['action']), 'point': None, 'planned': None}
    result['action']['relocation'] = report
    def reject(reason):
        report['reason'] = reason
        return result
    if not options or packet is None or planner.pending is not None:
        return reject('no_eligible_option')
    original = options[0]['action']
    if original.get('reason') != 'needed ingredient' or original.get('source') == 'supplement':
        return reject('required_primary_food_only')
    stamp, frame = packet
    if clock() - stamp > .15:
        return reject('redetection_frame_too_old')
    canonical, top, scale, state, tray = snapshot(model, frame)
    before = signature(state, tray)
    if before is None or state['phase'] != 'playing' or state['order'] != planner.order:
        return reject('unconfirmed_current_state')
    label = original['label']
    if label not in planner.recipe or state['counters'][planner.recipe.index(label)]['remaining'] <= 0:
        return reject('target_no_longer_required')
    candidates = detect_local(model, canonical, top, scale,
                              (original['x'], original['y']), label)
    fresh = dict(perception, candidates=candidates, counters=state['counters'],
                 order=state['order'], phase=state['phase'], tray=tray,
                 overlay=False, complete_overlay=False, top=top, scale=scale,
                 shuffle={'ready': False})
    trial = copy.deepcopy(planner)
    trial.propose(fresh)
    approved = [o for o in trial.food_options if o['action']['label'] == label
                and o['action']['reason'] == 'needed ingredient']
    report['candidate_count'] = len(approved)
    if not approved:
        return reject('no_planner_approved_local_point')
    # Capture starts after all re-detection/planning work, not just after the
    # historical frame. Never reuse a same-frame "tracking" acceptance.
    inferred_at = clock()
    next_packet = frame_after(inferred_at, timeout=.12)
    if next_packet is None:
        return reject('no_post_inference_frame')
    new_stamp, new_frame = next_packet
    if new_stamp < inferred_at or not .015 <= new_stamp - stamp <= .45:
        return reject('invalid_post_inference_interval')
    _, _, _, new_state, new_tray = snapshot(model, new_frame)
    if signature(new_state, new_tray) != before:
        return reject('order_counters_or_tray_changed')
    if clock() - new_stamp > .15:
        return reject('verification_frame_too_old')
    selected = approved[0]
    action = dict(selected['action'])
    limit = 8 if sum(trial.inventory.values()) >= 5 else min(25, max(10, action['radius'] * frame.shape[1] / 1536 * .35))
    diagnostics = {}
    tracking = adjusted_point(frame, stamp, new_frame, new_stamp,
                              (action['x'], action['y']),
                              lead=clock()-new_stamp+.06, max_extrapolation=limit,
                              details=True, diagnostics=diagnostics)
    report['tracking'] = diagnostics
    if tracking is None:
        return reject('new_point_tracking_rejected')
    validation = verify_latest_click(model, new_frame, tracking['observed_point'],
                                     tracking['point'], label, planner.order,
                                     minimum_score=.995)
    report['validation'] = validation
    if not validation['accepted']:
        return reject('new_point_classification_rejected')
    if clock()-new_stamp > .15:
        return reject('validation_finished_too_late')
    report.update(accepted=True, reason='confirmed_post_inference_point', capture_stamp=new_stamp)
    action.update(source='local_relocation', execution_point=list(tracking['point']),
                  validation=validation, relocation=report,
                  motion_attempts=previous_choice['action'].get('motion_attempts', []))
    return {'action': action, 'point': tracking['point'], 'planned': selected['planned'],
            'execution_packet': next_packet, 'refreshed_inventory': dict(trial.inventory)}
