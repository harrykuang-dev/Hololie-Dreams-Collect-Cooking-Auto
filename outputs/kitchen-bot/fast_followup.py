"""One same-food follow-up, verified again on a fresh recorded frame."""
import math

def select_followup(action,perception,inventory):
    if action.get('kind')!='food' or sum(inventory.values())>4:return None
    label=action['label'];recipe=[c['label'] for c in perception['recipe']]
    if label not in recipe or inventory.get(label,0)>=2:return None
    remaining=perception['counters'][recipe.index(label)]['remaining']
    if remaining is None or remaining<2:return None
    first=next((c for c in perception['candidates'] if (c['x'],c['y'])==(action['x'],action['y'])),None)
    if first is None:return None
    def strong(c):
        local=c.get('local_classifier',{});box=c.get('classifier',{})
        agreement=(box.get('label')==label and box.get('score',0)>=.80) or (c.get('surface_label',c['label'])==label and c['confidence']>=.97)
        minimum=10 if label in ['scallion','cucumber','pepper','sausage'] else 14
        return local.get('label')==label and local.get('score',0)>=.99 and agreement and c['radius']>=minimum
    if not strong(first):return None
    choices=[]
    for c in perception['candidates']:
        if not strong(c) or not 350<=c['cx']<=1190 or not 185<=c['cy']<=720:continue
        if math.hypot(c['cx']-first['cx'],c['cy']-first['cy'])<max(65,c['radius']+first['radius']):continue
        a=first['box'];b=c['box']
        overlap=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
        smaller=min((a[2]-a[0])*(a[3]-a[1]),(b[2]-b[0])*(b[3]-b[1]))
        if overlap>smaller*.25:continue
        choices.append(c)
    return max(choices,key=lambda c:c['radius']) if choices else None
