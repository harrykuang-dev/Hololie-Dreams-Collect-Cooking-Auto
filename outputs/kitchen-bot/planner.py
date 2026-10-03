"""Persistent conservative three-match planner driven by fresh screenshots."""
from collections import Counter
import time,math

class Planner:
    def __init__(self):
        self.recipe=None;self.order=None;self.inventory=Counter();self.pending=None;self.planned=None;self.staged=False
        self.shuffle_at=0;self.bad=[];self.completed=0;self.sequence=0
        self.unknown_since=None
    def point(self,result,x,y):
        return {'x':round(x*result['scale']),'y':round(y*result['scale']+result['top'])}
    def propose(self,r):
        self.food_options=[]
        self.sequence+=1;now=time.monotonic()
        phase=r.get('phase')
        if phase in ['burst','ending','results']:
            return {'kind':'stop','reason':'tray burst or closing game animation'}
        if phase=='unknown':
            if self.unknown_since is None:self.unknown_since=now
            settling = 10 if self.order is None and self.recipe is None else 2
            if now-self.unknown_since<settling:return {'kind':'wait','reason':'screen transition settling'}
            return {'kind':'stop','reason':'gameplay UI absent after settling'}
        self.unknown_since=None
        if r.get('complete_overlay'):
            if self.order:self.completed=max(self.completed,self.order)
            return {'kind':'continue','reason':'dismiss completed dish',**self.point(r,760,700)}
        if r['overlay']:
            # Overlay dismissals do not click ingredients. Accept a new recipe
            # only when the displayed ingredient cards classify clearly.
            # Read the fixed gameplay cards after dismissal; animated overlay
            # layouts should never replace a confirmed recipe.
            self.staged=False;self.pending=None
            return {'kind':'continue','reason':'order/transition overlay',**self.point(r,760,760)}
        counters=[v['remaining'] for v in r['counters']]
        if all(n is None for n in counters):return {'kind':'wait','reason':'ingredient cards are animating'}
        order=r.get('order')
        if order is None and sum(n is not None for n in counters)<2:
            return {'kind':'stop','reason':'gameplay UI is absent; inspect the window'}
        if order is not None and 1<=order<=99 and (self.order is None or order>self.order):
            self.completed=max(self.completed,order-1)
            self.order=order;self.inventory.clear();self.pending=None
            if self.recipe is None or not self.staged:self.recipe=[v['label'] for v in r['recipe']]
            self.staged=False
            initial=3 if max([n for n in counters if n is not None]+[3])<=3 else 6
            for label,n in zip(self.recipe,counters):
                if n is not None:self.inventory[label]=(initial-n)%3
        if self.recipe is None:self.recipe=[v['label'] for v in r['recipe']]
        # The settled gameplay cards are more reliable than a zooming overlay.
        if order is not None and all(n is not None for n in counters) and all(v['score']>.90 for v in r['recipe']):
            labels=[v['label'] for v in r['recipe']]
            if len(set(labels))==3:self.recipe=labels
        if order is None:
            return {'kind':'wait','reason':'waiting for the next order animation'}
        if self.pending:
            p=self.pending;before=p['counters']
            changed=[i for i in range(3) if counters[i] is not None and before[i] is not None and counters[i]<before[i]]
            if (p.get('needed') and not changed and p.get('occupied_at_click',0)>=4
                and now-p.get('committed_at',0)<.65):
                return {'kind':'wait','reason':'waiting for crowded-tray pick confirmation'}
            actual=self.recipe[changed[0]] if changed else p['label']
            # Same point remaining visible with unchanged counts suggests a miss.
            near=[c for c in r['candidates'] if c['label']==p['label'] and math.hypot(c['cx']-p['cx'],c['cy']-p['cy'])<18]
            if p.get('needed') and not changed:
                # A visible fragment may be covered by another collider. Do not
                # count a required ingredient until its order counter confirms it.
                self.bad.append((p['cx'],p['cy'],now))
                if not near:self.inventory['unknown']+=1
            elif changed or not near:
                self.inventory[actual]+=1
                if self.inventory[actual]>=3:self.inventory[actual]-=3
            else:self.bad.append((p['cx'],p['cy'],now))
            self.pending=None
        if 'tray' in r:
            # A settled tray observation is the authoritative inventory. This
            # corrects wrong picks and missed clicks without trusting intent.
            self.inventory=Counter(item['label'] if item['score']>.55 else 'unknown' for item in r['tray'])
            slots=max((item['index'] for item in r['tray']),default=-1)+1
            self.inventory['unknown']+=slots-len(r['tray'])
            # Required-food counts are confirmed by the order, even when a
            # shiny tray icon has a low classifier score.
            for label,n in zip(self.recipe,counters):
                if n is not None:self.inventory[label]=(-n)%3
            known=sum(n for label,n in self.inventory.items() if label!='unknown')
            self.inventory['unknown']=max(0,slots-known)
        if all(n==0 for n in counters):
            # A digit can be misread for one frame. Completion is confirmed by
            # its overlay or a subsequent order, and never locks gameplay.
            return {'kind':'wait','reason':'dish completion animation'}
        self.bad=[b for b in self.bad if now-b[2]<3]
        active={label for label,n in zip(self.recipe,counters) if n is None or n>0}
        available=[]
        for c in r['candidates']:
            check=c.get('classifier',{})
            local=c.get('local_classifier',{})
            if r.get('human_point_model'):
                # Human labels describe this exact click point, whereas a box
                # often includes an overlapping ingredient of another kind.
                if local.get('label')=='background' or local.get('score',0)<.94:continue
                c={**c,'label':local['label'],'surface_confidence':c['confidence'],'confidence':local['score']}
                check=local
            ranked=check.get('alternatives',[])
            margin=ranked[0][1]-ranked[1][1] if len(ranked)>1 else 0
            if check.get('label')=='moyashi' and c['label']!='moyashi':
                continue
            correction=(check.get('label') in ['egg','glove','ricebowl','moyashi','pot','curry','tuna','potato'] and check.get('score',0)>.90 and margin>.6) or (check.get('label')!='plate' and check.get('score',0)>.97 and margin>.9)
            if c['label']!=check.get('label') and correction:
                c={**c,'label':check['label'],'confidence':max(c['confidence'],check['score'])}
            elif c['label'] in active and check.get('label') not in active and check.get('score',0)>.90 and margin>.6:
                # A transparent jar fragment can actually be the spider box
                # behind it; avoid filling the tray with a conflicting object.
                continue
            local=c.get('local_classifier',{})
            if local.get('score',0)>.80 and local.get('label')!=c['label']:
                continue
            if check.get('label')!=c['label'] and check.get('score',0)>.40:
                continue
            if sum(self.inventory.values())>=6 and (check.get('label')!=c['label'] or check.get('score',0)<.995 or local.get('label')!=c['label'] or local.get('score',0)<.995):
                continue
            minimum=10 if c['label'] in ['scallion','cucumber','pepper','sausage'] else 12 if c['label']=='potato' else 14 if c['label'] in ['udon','plum','egg','tuna','glove'] else 20
            if c['label']=='moyashi' and check.get('label')=='moyashi' and check.get('score',0)>.5 and c['confidence']>.96:minimum=10
            box_check=c.get('classifier',{})
            if (r.get('human_point_model') and c['label']=='onion'
                and local.get('score',0)>=.995
                and box_check.get('label')=='onion' and box_check.get('score',0)>=.98
                and (sum(self.inventory.values())<=4 or self.inventory['onion']==2)):
                # Onion texture is often split into egg/shrimp regions. Two
                # independent crop views agree, and latest-frame verification
                # applies a stricter threshold before an actual click.
                minimum=10
            if (r.get('human_point_model') and c['label']=='shrimp'
                and c['label'] in active and sum(self.inventory.values())<=4
                and local.get('score',0)>=.995
                and box_check.get('label')=='shrimp' and box_check.get('score',0)>=.98):
                minimum=10
            # A strong, visible last piece can finish its triple even when
            # only a narrow surface remains. Keep the ordinary thresholds for
            # all other picks and for the transparent moyashi container.
            remaining=counters[self.recipe.index(c['label'])] if c['label'] in self.recipe else None
            if (r.get('human_point_model') and c['label']!='moyashi'
                and remaining==1 and self.inventory[c['label']]==2
                and sum(self.inventory.values())<=4
                and local.get('score',0)>=.99
                and c.get('surface_label')==c['label']
                and c.get('surface_confidence',c['confidence'])>=.95):
                minimum=min(minimum,10)
            if c['confidence']<.94 or c['radius']<minimum:continue
            if c['cx']<350 or c['cx']>1190 or c['cy']<185 or c['cy']>720:continue
            if any(math.hypot(c['cx']-x,c['cy']-y)<25 for x,y,t in self.bad):continue
            available.append(c)
        targets=[c for c in available if c['label'] in active]
        occupied=sum(self.inventory.values())
        if occupied>=4:targets=[c for c in targets if self.inventory[c['label']]>=1]
        if occupied>=6:targets=[c for c in targets if self.inventory[c['label']]==2]
        finishing=[c for c in available if self.inventory[c['label']]==2]
        if occupied>=4 and finishing:
            targets=finishing
        if targets:
            def score(c):return c['radius']+45*self.inventory[c['label']]+c['confidence']*10
            targets=sorted(targets,key=score,reverse=True)
            for option in targets[:3]:
                option_needed=option['label'] in active
                planned={**option,'counters':counters,'needed':option_needed}
                proposal={'kind':'food','reason':'needed ingredient' if option_needed else 'finish tray triple','label':option['label'],'confidence':option['confidence'],'radius':option['radius'],'x':option['x'],'y':option['y']}
                self.food_options.append({'action':proposal,'planned':planned})
            c=targets[0]
            needed=c['label'] in active
            self.planned={**c,'counters':counters,'needed':needed}
            return {'kind':'food','reason':'needed ingredient' if needed else 'finish tray triple','label':c['label'],'confidence':c['confidence'],'radius':c['radius'],'x':c['x'],'y':c['y']}
        # The interval only debounces a missed input; the rendered button,
        # rather than an assumed cooldown duration, determines availability.
        if r.get('shuffle',{}).get('ready',False) and now-self.shuffle_at>1.5:
            self.shuffle_at=now
            return {'kind':'shuffle','reason':'needed ingredients hidden',**self.point(r,235,750)}
        # Non-target triples can free space. Start only with enough visibly
        # distinct pieces and room for the entire triple.
        grouped={}
        for c in sorted(available,key=lambda c:-c['radius']):
            if c['confidence']<.99:continue
            same=grouped.setdefault(c['label'],[])
            if all(math.hypot(c['cx']-q['cx'],c['cy']-q['cy'])>80 for q in same):same.append(c)
        choices=[]
        for label,cs in grouped.items():
            need=3-self.inventory[label]
            # The seventh slot may be the piece that completes a triple:
            # the game removes that triple before checking for a full tray.
            # Keep a spare slot while collecting a clearing group. A
            # matching seventh piece can still finish a confirmed pair above,
            # but a newly collected triple must tolerate one wrong pick.
            if need>0 and len(cs)>=need and occupied+need<=6:
                choices.extend(cs)
        if choices:
            c=max(choices,key=lambda c:c['radius']+60*self.inventory[c['label']])
            # Keep a clearing triple together; alternatives may change its
            # position but must not start a different non-target food.
            for option in sorted([q for q in choices if q['label']==c['label']],key=lambda q:-q['radius'])[:3]:
                self.food_options.append({'action':{'kind':'food','reason':'clear non-target triple','label':option['label'],'confidence':option['confidence'],'radius':option['radius'],'x':option['x'],'y':option['y']},'planned':{**option,'counters':counters,'needed':False}})
            self.planned={**c,'counters':counters,'needed':False}
            return {'kind':'food','reason':'clear non-target triple','label':c['label'],'confidence':c['confidence'],'radius':c['radius'],'x':c['x'],'y':c['y']}
        return {'kind':'wait','reason':'waiting for a safe target or shuffle cooldown'}

    def status(self):
        return {'order':self.order,'completed':self.completed,'recipe':self.recipe,'inventory':dict(self.inventory),'steps':self.sequence}

    def commit(self):
        if self.planned:
            self.planned={**self.planned,'committed_at':time.monotonic(),
                          'occupied_at_click':sum(self.inventory.values())}
        self.pending=self.planned;self.planned=None
