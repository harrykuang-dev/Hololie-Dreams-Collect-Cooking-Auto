"""Render isolated local cooking models into labeled RGBA training views."""
from pathlib import Path
import json, re, argparse
import numpy as np
import moderngl
from PIL import Image, ImageDraw
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'kitchen-assets'
LABELS = {
 '00-ham0':'ham','00-milk0':'milk','00-noodles0':'pot','00-potato0':'potato','00-source0':'sauce',
 '01-cucumber0':'cucumber','01-meat0':'meat','01-noodles0':'udon','01-noodles1':'noodles','01-plum0':'plum',
 '02-egg0':'egg','02-egg1':'brownegg','02-fishpaste0':'kamaboko','02-granola0':'cereal','02-onion0':'onion',
 '03-breadcrumbs0':'panko','03-capsicum0':'pepper','03-tarantula0':'spider','03-wheat0':'flour','03-wiener0':'sausage',
 '04-rice0':'ricebowl','04-rice1':'plate','04-rice2':'ricepack','04-shallot0':'scallion','04-shrimp0':'shrimp',
 '05-curry0':'curry','05-other0':'seaweed','05-plate0':'glove','05-sprouts0':'moyashi','05-tuna0':'tuna'}

def read_obj(path):
    v, uv, n, faces = [], [], [], []
    for line in path.read_text().splitlines():
        p=line.split()
        if not p: continue
        if p[0]=='v': v.append(list(map(float,p[1:4])))
        elif p[0]=='vt': uv.append(list(map(float,p[1:3])))
        elif p[0]=='vn': n.append(list(map(float,p[1:4])))
        elif p[0]=='f': faces.extend([[int(t.split('/')[0])-1 for t in p[1:]]])
    v=np.array(v,np.float32);uv=np.array(uv,np.float32);n=np.array(n,np.float32)
    ix=np.array(faces,np.int32).flatten()
    return v, np.concatenate([v[ix],uv[ix],n[ix]],axis=1).astype('f4')

class Renderer:
    def __init__(self,size=192):
        self.size=size
        self.ctx=ctx=moderngl.create_standalone_context()
        self.fbo=ctx.simple_framebuffer((size,size),components=4)
        self.program=p=ctx.program(vertex_shader='''#version 330
          uniform mat4 rotation;
          in vec3 in_pos; in vec2 in_uv; in vec3 in_normal;
          out vec2 uv; out vec3 normal;
          void main() {vec4 pos=rotation*vec4(in_pos,1.0); gl_Position=vec4(pos.xy,-pos.z*.4,1.0); uv=in_uv; normal=mat3(rotation)*in_normal;}
        ''',fragment_shader='''#version 330
          uniform sampler2D tex; uniform float light;
          in vec2 uv; in vec3 normal; out vec4 color;
          void main() {vec4 c=texture(tex,uv); if(c.a<0.15)discard;
          float lambert=max(dot(normalize(normal),normalize(vec3(-.3,.8,1.))),0.);
          color=vec4(c.rgb*(1.0-light+light*lambert),c.a);}
        ''')
        ctx.enable(moderngl.DEPTH_TEST)
        self.models={}
        seen=set()
        for m in json.loads((ASSETS/'model-map.json').read_text()):
            if m['mesh'] in seen:continue
            seen.add(m['mesh'])
            group=re.search(r'ingredient-(\d\d)',m['materials'][0]['textures']['_BaseMap']['file']).group(1)
            name=m['object'].replace('Geo_','')
            if name.startswith('ham'): name='ham0'
            if name=='vinyl':name='meat0'
            if name.startswith('wheat'):name='wheat0'
            if name.startswith('sprouts'):name='sprouts0'
            label=LABELS[group+'-'+name]
            vertices,buf=read_obj(ASSETS/m['mesh'])
            im=Image.open(ASSETS/m['materials'][0]['textures']['_BaseMap']['file']).convert('RGBA')
            tex=ctx.texture(im.size,4,np.flipud(np.array(im)).tobytes());tex.build_mipmaps()
            self.models.setdefault(label,[]).append({'v':vertices,'buf':buf,'tex':tex})
        for parts in self.models.values():
            verts=np.concatenate([part['v'] for part in parts]);center=(verts.max(0)+verts.min(0))/2
            radius=np.linalg.norm(verts-center,axis=1).max()
            for part in parts:
                part['buf'][:,:3]=(part['buf'][:,:3]-center)/radius*.92
                vbo=ctx.buffer(part['buf'].tobytes())
                part['vao']=ctx.vertex_array(p,[(vbo,'3f 2f 3f','in_pos','in_uv','in_normal')])

    def render(self,label,angles,light=.3):
        self.fbo.use();self.fbo.clear(0,0,0,0,depth=1.0)
        mat=np.eye(4,dtype=np.float32);mat[:3,:3]=Rotation.from_euler('xyz',angles,degrees=True).as_matrix()
        self.program['rotation'].write(mat.T.tobytes());self.program['light'].value=light
        for part in self.models[label]:
            part['tex'].use(0);part['vao'].render()
        return Image.fromarray(np.flipud(np.frombuffer(self.fbo.read(components=4),np.uint8).reshape(self.size,self.size,4)))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--views',type=int,default=1);parser.add_argument('--out',type=Path,default=ROOT/'kitchen-bot/model-views');args=parser.parse_args()
    args.out.mkdir(exist_ok=True,parents=True)
    r=Renderer();rng=np.random.default_rng(42)
    preview=Image.new('RGB',(960,800),(245,241,230));draw=ImageDraw.Draw(preview)
    for i,label in enumerate(LABELS.values()):
        for j in range(args.views):
            angles=[-20,25,0] if j==0 else rng.uniform(-180,180,3)
            im=r.render(label,angles,light=float(rng.uniform(.12,.38)))
            im.save(args.out/f'{label}-{j:03}.png')
            if j==0:
                im.thumbnail((144,144));x=i%6*160;y=i//6*160
                preview.paste(im,(x,y),im);draw.text((x+8,y+144),label,fill='black')
        print(label,args.views,flush=True)
    preview.save(args.out.parent/'rendered-models.jpg')
