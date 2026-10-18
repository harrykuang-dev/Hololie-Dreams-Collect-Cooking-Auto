"""Exposed-radius experiment; all distances use the 1536px canonical view."""
import math

PROFILE = 'required_65'
PROFILES = ('baseline', 'required_80', 'required_65', 'crowded_last')


def exposed_radius(candidate, minimum, *, human, active, counters, recipe, inventory):
    if PROFILE not in PROFILES:
        raise ValueError('Unknown radius profile: '+PROFILE)
    original = minimum
    label = candidate['label']
    local = candidate.get('local_classifier', {})
    if (not human or label == 'moyashi' or label not in active
            or local.get('label') != label or local.get('score', 0) < .995):
        return minimum, None
    if PROFILE in ('required_80', 'required_65'):
        factor = .80 if PROFILE == 'required_80' else .65
        minimum = min(minimum, max(10, math.ceil(minimum*factor)))
    elif (PROFILE == 'crowded_last' and all(n is not None for n in counters)
          and sum(counters) == 1 and counters[recipe.index(label)] == 1
          and inventory[label] == 2 and 5 <= sum(inventory.values()) <= 6
          and candidate.get('surface_label') == label
          and candidate.get('surface_confidence', 0) >= .90):
        minimum = min(minimum, 12)
    # Only candidates actually using the new smaller radius need this guard.
    if minimum < original and minimum <= candidate['radius'] < original:
        return minimum, {'profile': PROFILE, 'original_minimum': original,
                         'minimum': minimum, 'canonical_width': 1536,
                         'minimum_point_score': .995}
    return minimum, None
