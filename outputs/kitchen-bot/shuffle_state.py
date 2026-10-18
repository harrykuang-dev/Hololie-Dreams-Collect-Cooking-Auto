"""Read the shuffle button's rendered cooldown state from a canonical frame."""
import cv2


def shuffle_state(canonical, phase):
    if phase != 'playing':
        return {'ready': False, 'reason': 'not_playing'}
    # During cooldown the button is translucent and its hat turns gray as
    # the blue fill rises. A ready button has a gold hat outline AND blue
    # behind it. Requiring both rejects gold flashes crossing a cooling hat.
    hsv = cv2.cvtColor(canonical[710:780, 205:265], cv2.COLOR_BGR2HSV)
    gold = (hsv[:, :, 0] > 12) & (hsv[:, :, 0] < 40) & (hsv[:, :, 1] > 100) & (hsv[:, :, 2] > 100)
    blue = (hsv[:, :, 0] > 95) & (hsv[:, :, 0] < 125) & (hsv[:, :, 1] > 80) & (hsv[:, :, 2] > 100)
    gold_fraction = float(gold.mean())
    blue_fraction = float(blue.mean())
    cap=canonical[731:748,224:247].astype('float32')
    b,g,r=cv2.split(cap)
    cream_fraction=float(((r>205)&(g>200)&(r>=g-8)&(g>b+6)).mean())
    ready = gold_fraction >= .025 and blue_fraction >= .145 and cream_fraction >= .65
    return {'ready': ready, 'gold_fraction': round(gold_fraction, 4),
            'blue_fraction': round(blue_fraction, 4),
            'reason': 'ready_button' if ready else 'cooldown_or_obscured'}
