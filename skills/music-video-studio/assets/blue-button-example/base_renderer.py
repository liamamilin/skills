from __future__ import annotations
import argparse, functools, json, math, subprocess, time, os, shutil
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import soundfile as sf

P=Path(__file__).resolve().parent
FF=Path(os.environ.get('FFMPEG_BIN') or shutil.which('ffmpeg') or 'ffmpeg')
W,H,FPS=1920,1080,30
WHITE='#F4F2EC'; INK='#171827'; BLUE='#275BFF'; PURPLE='#211039'; LIME='#D5FF6B'; ORANGE='#D9805D'
FONT='/System/Library/Fonts/STHeiti Medium.ttc'
LATIN='/System/Library/Fonts/Supplemental/Arial Bold.ttf'
DURATION=len(sf.read(P/'alignment.wav')[0])/16000
CUES=json.loads((P/'cues.json').read_text())

@functools.lru_cache(512)
def font(size,latin=False):return ImageFont.truetype(LATIN if latin else FONT,int(size))
@functools.lru_cache(1500)
def label(s,size,color,latin=False):
 f=font(size,latin); b=f.getbbox(s); pad=8
 im=Image.new('RGBA',(b[2]-b[0]+pad*2,b[3]-b[1]+pad*2))
 ImageDraw.Draw(im).text((pad-b[0],pad-b[1]),s,font=f,fill=color)
 return im

def text(im,s,xy,size=60,color=INK,center=False,scale=1,alpha=1,rotate=0,latin=False):
 tile=label(s,int(size),color,latin)
 if scale!=1:tile=tile.resize((max(1,round(tile.width*scale)),max(1,round(tile.height*scale))),Image.Resampling.LANCZOS)
 if rotate:tile=tile.rotate(rotate,resample=Image.Resampling.BICUBIC,expand=True)
 if alpha<1:
  tile=tile.copy();tile.putalpha(tile.getchannel('A').point(lambda v:round(v*max(0,alpha))))
 x,y=xy
 if center:x-=tile.width/2;y-=tile.height/2
 im.paste(tile,(round(x),round(y)),tile)
 return (x,y,x+tile.width,y+tile.height)

def clamp(x):return max(0,min(1,x))
def ease(x):return 1-(1-clamp(x))**3
def smooth(x):x=clamp(x);return x*x*(3-2*x)
def pop(dt):return 1+0.12*math.exp(-max(0,dt)*9)*math.sin(max(0,dt)*17)
def rr(im,box,fill,r=24,outline=None,width=2):ImageDraw.Draw(im).rounded_rectangle(tuple(map(round,box)),r,fill=fill,outline=outline,width=width)
def line(im,xy,color,width=4):ImageDraw.Draw(im).line(xy,fill=color,width=width)

# Audio-reactive accents use the actual soundtrack envelope, never an invented BPM clock.
audio,sr=sf.read(P/'alignment.wav',dtype='float32')
win=320; env=np.sqrt(np.mean(np.pad(audio,(0,(-len(audio))%win)).reshape(-1,win)**2,axis=1))
env=(env/max(float(np.percentile(env,95)),1e-6)).clip(0,1)
def pulse(t):return float(env[min(len(env)-1,max(0,int(t*50)))])

@functools.lru_cache(4)
def background(mode):
 if mode=='purple':
  yy,xx=np.mgrid[0:H,0:W];glow=np.maximum(0,1-np.sqrt(((xx-W*.55)/1300)**2+((yy-H*.45)/850)**2))
  a=np.empty((H,W,3),np.uint8)
  for i,(base,add) in enumerate([(24,20),(12,12),(46,32)]):a[:,:,i]=base+glow*add
  im=Image.fromarray(a)
  d=ImageDraw.Draw(im)
  for y in range(55,H,95):
   for x in range(55,W,95):d.ellipse((x-3,y-3,x+3,y+3),fill='#39264F')
  return im
 im=Image.new('RGB',(W,H),WHITE)
 d=ImageDraw.Draw(im)
 for y in range(0,H,72):d.line((0,y,W,y),fill='#E9E6DF',width=1)
 for x in range(0,W,72):d.line((x,0,x,H),fill='#E9E6DF',width=1)
 return im

PET=None
if (P/'pet.png').exists():
 PET=Image.open(P/'pet.png').convert('RGBA')
 bbox=PET.getchannel('A').getbbox()
 if bbox:PET=PET.crop(bbox)

def pet(im,x,y,size=145,tilt=0,t=0,react=False):
 if PET is None:return
 h=round(size*PET.height/PET.width)
 pic=PET.resize((size,h),Image.Resampling.NEAREST)
 if tilt:pic=pic.rotate(tilt,expand=True,resample=Image.Resampling.NEAREST)
 if react:y-=max(0,math.sin(t*5))*20
 im.paste(pic,(int(x-pic.width/2),int(y-pic.height/2)),pic)

def chip(im,s,x,y,fill=INK,fg='#FFFFFF',width=None):
 width=width or label(s,28,fg).width+44
 rr(im,(x,y,x+width,y+52),fill,26)
 text(im,s,(x+width/2,y+26),28,fg,True,latin=s.isascii())

def cursor(im,x,y,scale=1,click=False):
 pts=[(0,0),(0,55),(15,41),(29,68),(42,61),(27,35),(48,34)]
 pts=[(x+a*scale,y+b*scale) for a,b in pts]
 ImageDraw.Draw(im).polygon(pts,fill='white',outline=INK,width=4)
 if click:ImageDraw.Draw(im).ellipse((x-25,y-25,x+25,y+25),outline=BLUE,width=5)

def button(im,x,y,w=440,h=135,color=BLUE,title='确认修改',scale=1):
 w*=scale;h*=scale
 rr(im,(x-w/2+9,y-h/2+12,x+w/2+9,y+h/2+12),'#BFC9E6',30)
 rr(im,(x-w/2,y-h/2,x+w/2,y+h/2),color,30)
 text(im,title,(x,y),50*scale,'#FFFFFF',True)

def browser(im,x=225,y=190,w=1470,h=660,mode='normal',progress=0):
 rr(im,(x+14,y+18,x+w+14,y+h+18),'#DAD7D3',30)
 rr(im,(x,y,x+w,y+h),'#FFFFFF',30,outline='#CECBD4',width=3)
 rr(im,(x+3,y+3,x+w-3,y+72),'#E8E6EE',27)
 ImageDraw.Draw(im).rectangle((x+3,y+45,x+w-3,y+74),fill='#E8E6EE')
 for k,c in enumerate(['#FF7979','#F8CA6C','#74C995']):ImageDraw.Draw(im).ellipse((x+27+k*30,y+27,x+41+k*30,y+41),fill=c)
 text(im,'localhost / my-website',(x+170,y+32),25,'#777285',latin=True)
 if mode=='blank':return
 shift=progress*150 if mode=='wreck' else 0
 navx=x+50-(ease(progress)*1900 if mode=='vanish' else 0)
 rr(im,(navx,y+110,navx+270,y+h-40),'#F1EFF5',18)
 for k,tx in enumerate(['工作台','我的项目','素材管理']):text(im,tx,(navx+33,y+155+k*83),34,INK if k==0 else '#9993A3')
 lx=x+w-180+(ease(max(0,progress-.3)/.7)*1900 if mode=='vanish' else shift*1.5)
 rr(im,(lx,y+100,lx+130,y+160),BLUE,16)
 text(im,'登录',(lx+65,y+130),30,'#FFFFFF',True)
 text(im,'我的首页',(x+370,y+130),66,INK)
 # Layout cards are UI components, and their motion illustrates the requested redesign.
 for k in range(3):
  cx=x+365+k*310;cy=y+260
  if mode=='wreck':cx+=math.sin(k*2+1)*shift;cy+=math.cos(k*3+1)*shift
  rr(im,(cx,cy,cx+270,cy+210),['#E7EDFF','#EFE7FA','#E9F2E5'][k],22)
  text(im,['项目','文档','任务'][k],(cx+30,cy+35),37,INK)
  for j in range(3):rr(im,(cx+30,cy+105+j*25,cx+210-j*25,cy+116+j*25),'#CACBD8',5)
 button(im,x+w*.61,y+h-85,300,78,title='开始',scale=1)

def caption(im,s,t,cue,dark=False):
 size=68
 color='#FFFFFF' if dark else INK
 width=label(s,size,color).width+80
 rr(im,(W/2-width/2,910,W/2+width/2,1020),'#151021' if dark else '#FFFFFF',22)
 text(im,s,(W/2,965),size,color,True,scale=pop(t-cue))

def arrow(im,cx,cy,size=150,color=LIME):
 d=ImageDraw.Draw(im)
 d.arc((cx-size/2,cy-size/2,cx+size/2,cy+size/2),35,300,fill=color,width=13)
 d.polygon([(cx-size*.46,cy-size*.22),(cx-size*.65,cy-size*.48),(cx-size*.24,cy-size*.48)],fill=color)
