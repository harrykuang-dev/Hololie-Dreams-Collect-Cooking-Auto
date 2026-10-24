"""Retrain a ResNet using the published human labels and original BGR inputs."""
import argparse
import json
import math
import random
from collections import Counter
from pathlib import Path
from dataset import read_rows, load_bgr
from training_policy import policy_state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--architecture', choices=['resnet18','resnet34','resnet50','resnet101','resnet152'], default='resnet18')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-epochs', type=int, default=200)
    parser.add_argument('--initialization', choices=['imagenet','random'], default='imagenet')
    args = parser.parse_args()
    if args.max_epochs < 1:parser.error('--max-epochs must be positive')
    import cv2
    import numpy as np
    import torch
    from torchvision import models
    config = json.loads((args.data/'training-config.json').read_text(encoding='utf8'))
    labels = [r['id'] for r in json.loads((args.data/'labels.json').read_text(encoding='utf8'))['labels']]
    index = {label:i for i,label in enumerate(labels)}
    sets = {split:list(read_rows(args.data,split)) for split in ('train','validation','development_test')}
    random.seed(config['seed']);np.random.seed(config['seed']);torch.manual_seed(config['seed'])
    cv2.setNumThreads(2);torch.set_num_threads(2);torch.use_deterministic_algorithms(True)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    if device == 'cuda':torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
    weights_enum = getattr(models, 'ResNet'+args.architecture.removeprefix('resnet')+'_Weights')
    net = getattr(models,args.architecture)(weights=weights_enum.IMAGENET1K_V1 if args.initialization=='imagenet' else None)
    net.fc = torch.nn.Linear(net.fc.in_features,len(labels));net.to(device)
    optimizer = torch.optim.AdamW(net.parameters(),lr=config['learning_rate'],weight_decay=config['weight_decay'])
    counts = Counter(r['label'] for r in sets['train'])
    weights = torch.tensor([1/math.sqrt(counts[k]) for k in labels],device=device);weights/=weights.mean()
    args.output.mkdir(parents=True,exist_ok=True)
    def batch(rows,epoch=None,step=None):
        images=[load_bgr(args.data,r,random.Random(f'{config["seed"]}|{epoch}|{step}|{r["id"]}') if epoch is not None else None) for r in rows]
        return torch.from_numpy(np.stack(images)).to(device),torch.tensor([index[r['label']] for r in rows],device=device)
    def evaluate(rows):
        net.eval();confusion=np.zeros((len(labels),len(labels)),dtype='int64');high=0
        with torch.inference_mode():
            for start in range(0,len(rows),config['batch_size']):
                x,y=batch(rows[start:start+config['batch_size']]);p=net(x).softmax(1);confidence,pred=p.max(1)
                high+=int(((confidence>=.995)&(pred!=y)).sum())
                for truth,guess in zip(y.cpu().tolist(),pred.cpu().tolist()):confusion[truth,guess]+=1
        return {'samples':len(rows),'accuracy':float(confusion.trace()/len(rows)),
                'macro_recall':float((confusion.diagonal()/np.maximum(1,confusion.sum(1))).mean()),
                'high_confidence_errors':high,'confusion':confusion.tolist()}
    def checkpoint(path,value):
        temporary=path.with_suffix('.pending');torch.save(value,temporary);temporary.replace(path)
    history=[];best=(-1,-10**9)
    try:
        for epoch in range(args.max_epochs):
            net.train();order=list(sets['train']);random.Random(config['seed']+epoch).shuffle(order)
            lr=config['learning_rate']*(.05+.95*(1+math.cos(math.pi*min(epoch,30)/30))/2)
            for group in optimizer.param_groups:group['lr']=lr
            for step,start in enumerate(range(0,len(order),config['batch_size'])):
                x,y=batch(order[start:start+config['batch_size']],epoch,step)
                optimizer.zero_grad(set_to_none=True);loss=torch.nn.functional.cross_entropy(net(x),y,weight=weights)
                loss.backward();optimizer.step()
            metrics=evaluate(sets['validation']);history.append({'epoch':epoch+1,'validation':metrics})
            value={'architecture':args.architecture,'labels':labels,'input':config['input'],
                   'dataset_sha256':config['original_frozen_dataset_sha256'],'model':net.state_dict(),
                   'epoch':epoch+1,'initialization':args.initialization,'validation':metrics}
            key=(metrics['macro_recall'],-metrics['high_confidence_errors'])
            if key>best:checkpoint(args.output/'best.pt',value);best=key
            checkpoint(args.output/'last.pt',{**value,'optimizer':optimizer.state_dict(),'history':history})
            (args.output/'history.json').write_text(json.dumps(history,indent=2)+'\n',encoding='utf8')
            policy=policy_state(history,epoch+1);print(json.dumps({'epoch':epoch+1,'validation':metrics,'continuation':policy}),flush=True)
            if not policy['continue_training']:break
    except KeyboardInterrupt:
        print('Stopped. Checkpoints from the last completed epoch are preserved.',flush=True)
        return
    best_checkpoint=torch.load(args.output/'best.pt',map_location=device,weights_only=True)
    net.load_state_dict(best_checkpoint['model'])
    result={'architecture':args.architecture,'best_epoch':best_checkpoint['epoch'],'validation':best_checkpoint['validation'],
            'development_test':evaluate(sets['development_test']),'initialization':args.initialization,
            'dataset_sha256':config['original_frozen_dataset_sha256'],'device':device}
    (args.output/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')


if __name__ == '__main__':main()
