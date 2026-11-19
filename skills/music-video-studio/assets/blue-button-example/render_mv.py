"""V4: one continuous desktop farce, composed against the unchanged song clock."""
from __future__ import annotations

import argparse
import functools
import hashlib
import json
import math
import subprocess
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import base_renderer as b

P = Path(__file__).resolve().parent
W, H, FPS = 1920, 1080, 30
INK, BLUE, PAPER = '#202337', '#315CFA', '#F6F5F0'
MUTED, LINE, ORANGE = '#7F8496', '#DDE1EB', '#DB805B'
PURPLE, LIME = '#29243F', '#D8F48A'
DURATION = 69.0  # Keep natural music decay; discard separate appended speech.
CAST = json.loads((P/'cast.json').read_text())
assert CAST['assistant']['id'] == CAST['mascot']['represents'], 'Assistant and mascot identity mismatch'
ASSISTANT_NAME = CAST['assistant']['display_name']
FONT = '/System/Library/Fonts/Hiragino Sans GB.ttc'


@functools.lru_cache(512)
def font(size, latin=False):
    return ImageFont.truetype(b.LATIN if latin else FONT, int(size), index=0 if latin else 2)


b.font = font
text, rr, line = b.text, b.rr, b.line
ease, smooth, clamp, pet = b.ease, b.smooth, b.clamp, b.pet


def bg(dark=False):
    return Image.new('RGB', (W, H), PURPLE if dark else '#EBEEF4')


def pane(im, box, title, subtitle='', dark=False):
    x, y, xx, yy = box
    rr(im, (x+7, y+12, xx+7, yy+12), '#171526' if dark else '#D4D9E4', 25)
    rr(im, box, '#FFFFFF', 25)
    rr(im, (x, y, xx, y+68), '#F5F6FA', 25)
    ImageDraw.Draw(im).rectangle((x, y+40, xx, y+68), fill='#F5F6FA')
    for i, col in enumerate(('#EE8B86', '#EBC67D', '#86BCA6')):
        ImageDraw.Draw(im).ellipse((x+23+i*26, y+25, x+36+i*26, y+38), fill=col)
    text(im, title, (x+125, y+19), 25, INK)
    if subtitle:
        text(im, subtitle, (xx-200, y+22), 20, MUTED)


def ui_button(im, x, y, title='开始', w=250, h=80, color=BLUE, size=37):
    rr(im, (x-w/2, y-h/2, x+w/2, y+h/2), color, 18)
    text(im, title, (x, y), size, 'white', True)


def cursor(im, x, y, color=INK, tag=None, click=False):
    d = ImageDraw.Draw(im)
    pts = [(x,y),(x,y+49),(x+14,y+36),(x+26,y+60),(x+38,y+53),(x+24,y+30),(x+45,y+30)]
    d.polygon(pts, fill=color, outline='white', width=3)
    if click:
        d.ellipse((x-20,y-20,x+20,y+20), outline=color, width=3)
    if tag:
        width = b.label(tag, 23, 'white').width+24
        rr(im,(x+35,y+53,x+35+width,y+91),color,10)
        text(im,tag,(x+47,y+59),23,'white')


def subtitle(im, words, dark=False):
    fg = 'white' if dark else INK
    width = b.label(words, 62, fg).width+76
    rr(im,(960-width/2,928,960+width/2,1028), '#211C35' if dark else 'white',20)
    text(im,words,(960,976),62,fg,True)


def header(im, words, dark=False, size=79):
    text(im,words,(960,124),size,'white' if dark else INK,True)


def note(im, words, x, y, color=INK, size=32):
    width=b.label(words,size,'white').width+40
    rr(im,(x-width/2,y-30,x+width/2,y+30),color,13)
    text(im,words,(x,y),size,'white',True)


@functools.lru_cache(32)
def component(kind):
    if kind=='nav':
        im=Image.new('RGBA',(245,420))
        rr(im,(0,0,244,419),'#F0F2F7',18)
        text(im,'工作台',(25,32),35,INK)
        for i,s in enumerate(['我的项目','素材管理','最近打开']):
            text(im,s,(26,126+i*80),27,MUTED)
        return im
    if kind=='login':
        im=Image.new('RGBA',(176,70))
        rr(im,(0,0,175,69),'#EDF0FF',15)
        text(im,'登录',(88,35),32,BLUE,True)
        return im
    k=int(kind)
    im=Image.new('RGBA',(310,235))
    rr(im,(0,0,309,234),['#E8EDFF','#EDE7F4','#E8F0E6'][k],22)
    text(im,['项目','文档','任务'][k],(30,30),38,INK)
    for j in range(3):
        rr(im,(30,118+j*25,260-j*45,128+j*25),'#C8CDDD',5)
    return im


def paste(im, tile, x, y, angle=0, scale=1, opacity=1):
    if scale!=1:
        tile=tile.resize((max(1,round(tile.width*scale)),max(1,round(tile.height*scale))),Image.Resampling.LANCZOS)
    if angle:
        tile=tile.rotate(angle,Image.Resampling.BICUBIC,expand=True)
    if opacity<1:
        tile=tile.copy();tile.putalpha(tile.getchannel('A').point(lambda v:round(v*opacity)))
    im.paste(tile,(round(x),round(y)),tile)


def site(im, t, mode='normal', box=(150,215,1770,870), p=0, mascot=False):
    """The same recognizable site; parts move for concrete plot reasons."""
    x,y,xx,yy=box
    pane(im,box,'我的网站  /  localhost')
    sx=(xx-x)/1620; sy=(yy-y)/655
    def pos(a,c):return x+a*sx,y+c*sy
    navx,navy=pos(35,105)
    loginx,loginy=pos(1390,98)
    bx,by=pos(900,560)
    if mode in ('empty','button'):
        if mode=='button':ui_button(im,bx,by-170*sy,'开始',260*sx,90*sy,size=40*sx)
        return
    title_x,title_y=pos(325,112)
    if mode=='fall':
        title_y+=950*ease(clamp((p-.22)/.6))
    text(im,'我的首页',(title_x,title_y),57*sx,INK)
    nav_angle=0
    if mode=='escape':
        navx-=ease(p)*650
        loginx+=ease(clamp((p-.29)/.71))*800
        loginy-=abs(math.sin(clamp((p-.29)/.71)*math.pi*3))*30
    if mode=='fall':
        navy+=ease(clamp(p/.8))*1000;nav_angle=-30*p
        loginy+=ease(clamp((p-.15)/.85))*1000
    paste(im,component('nav'),navx,navy,nav_angle,sx)
    paste(im,component('login'),loginx,loginy,0,sx)
    if mode=='escape':
        # The mascot is pulling the menu; its position is tied to the same transform.
        px,py=navx+90,navy+470*sx
        line(im,[(px+38,py-25),(navx+130,navy+410*sx)],ORANGE,5)
        pet(im,px,py,130,t=t)
        if p>.29 and p<.9:
            for k in range(3):
                line(im,[(loginx-18-k*22,loginy+20+k*10),(loginx-65-k*22,loginy+20+k*10)],BLUE,4)
    for i in range(3):
        cx,cy=pos(325+i*365,250)
        angle=0;sc=sx
        if mode=='rebuild':
            q=smooth(clamp((p-i*.13)/.55))
            cx+=(-90,105,-45)[i]*q;cy+=(-48,100,-20)[i]*q;angle=(-9,11,-8)[i]*q
        if mode=='undo':
            cx+=(i-1)*110*p;cy+=(55,-45,40)[i]*p;angle=(8,-12,15)[i]*p
        if mode=='war':
            cx+=(1 if i%2==0 else -1)*240*p;cy+=(80,-30,80)[i]*p;angle=(20,-25,20)[i]*p
        if mode=='fall':
            q=ease(clamp((p-i*.13)/.58));cy+=q*950;angle=(25,-35,40)[i]*q
        if mode=='weird':
            cx,cy=pos((650,380,1050)[i],(185,375,280)[i]);angle=(0,13,-12)[i];sc*= (1.4,.75,.9)[i]
        paste(im,component(str(i)),cx,cy,angle,sc)
        if mode=='rebuild' and i==1:
            pet(im,cx+285*sx,cy+245*sx,140,t=t)
    ui_button(im,bx,by,'开始',270*sx,80*sy,size=39*sx)
    if mascot:
        pet(im,x+1480*sx,y+565*sy,150,t=t)


def chat(im,t,compact=False):
    if compact:
        box=(1320,205,1810,875);x=1350
        pane(im,box,ASSISTANT_NAME)
        text(im,'按钮改成蓝色',(x+14,310),32,INK)
        line(im,[(1350,383),(1780,383)],LINE,2)
        pet(im,1387,443,60)
        text(im,'Agent 执行中',(1430,420),30,INK)
        steps=[('定位按钮',9.0),('修改颜色',10.5),('顺便整理页面',12.0)]
        for i,(s,at) in enumerate(steps):
            if t>=at:
                yy=515+i*86
                ImageDraw.Draw(im).ellipse((1368,yy+6,1382,yy+20),fill=BLUE if i<2 else ORANGE)
                text(im,s,(1400,yy),29,INK)
        if t>=13:
            rr(im,(1355,775,1775,835),'#FFF0E7',13)
            text(im,'修改范围：整个首页',(1565,805),27,'#A55A35',True)
        return
    pane(im,(270,125,1650,915),ASSISTANT_NAME,'新对话')
    text(im,'一个很小的需求',(330,235),32,MUTED)
    rr(im,(680,335,1555,480),'#EAF0FF',26)
    text(im,'按钮改成蓝色。',(1118,407),65,INK,True)
    if t>=6.56:
        pet(im,385,620,100)
        text(im,'好的，小改动。',(480,578),75,INK)
        text(im,'准备交给 Agent 执行',(489,700),28,MUTED)
    rr(im,(330,797,1590,869),'#F1F3F7',18)
    text(im,'继续对话…',(360,815),28,'#A3A7B4')


def undo_control(im,t,at,label='撤销上一步',color=LIME):
    x,y=960,855
    rr(im,(720,y-45,1200,y+45),color,19)
    b.arrow(im,775,y,45,INK)
    text(im,label,(990,y),34,INK,True)
    dt=t-at
    cursor(im,1120-25*ease(dt/.25),y-8,INK,click=0<dt<.25)


def draw(t):
    dark=28<=t<44
    im=bg(dark)
    d=ImageDraw.Draw(im)
    if t<4:
        pane(im,(110,170,1810,900),'我的网站  /  一个小需求')
        text(im,'我只想改个',(220,350),83,INK)
        text(im,'按钮颜色',(215,465),130,BLUE)
        ui_button(im,1410,505,'开始',355,122,color='#8790A7',size=51)
        rr(im,(1190,410,1630,600),None,27,outline=BLUE,width=4)
        text(im,'只改这里',(1410,690),40,BLUE,True)
        line(im,[(1410,650),(1410,607)],BLUE,4)
        cursor(im,1500-110*ease(t/1.2),660-80*ease(t/1.2))
        if t>1.7:
            note(im,'Agent：收到！',500,760,INK,36)
            pet(im,780,760,125)
    elif t<8.1:
        chat(im,t)
    elif t<15.2:
        header(im,'一个按钮，值得这么大阵仗？',size=62)
        site(im,t,'normal' if t<12 else 'rebuild',box=(110,205,1270,875),p=clamp((t-12)/2.6))
        chat(im,t,True)
        if t<11.7:
            cursor(im,770,680,BLUE,tag='Agent',click=10.5<t<10.8)
    elif t<18.56:
        pane(im,(225,195,1695,865),'修改按钮  /  样式')
        text(im,'修改范围',(340,335),38,MUTED)
        text(im,'就这一个。',(340,430),87,INK)
        ui_button(im,1250,500,'开始',410,145,size=62)
        rr(im,(1005,385,1495,615),None,25,outline=BLUE,width=4)
        for x,y in [(1005,385),(1495,385),(1005,615),(1495,615)]:
            rr(im,(x-7,y-7,x+7,y+7),'white',2,BLUE,3)
        text(im,'颜色',(1070,725),33,MUTED)
        for i,col in enumerate(['#9AA1B3',BLUE,'#DB805B']):
            rr(im,(1190+i*80,713,1244+i*80,767),col,11)
        cursor(im,1295,746,INK,click=t<15.5)
        subtitle(im,'我只让你改个按钮')
    elif t<22.08:
        header(im,'Agent 正在“顺手”整理页面',size=67)
        site(im,t,'rebuild',p=clamp((t-18.56)/2.7))
        cursor(im,1140,520,ORANGE,tag='Agent')
        subtitle(im,'你把整个首页翻修')
    elif t<25.44:
        header(im,'菜单失踪' if t<22.88 else '登录出走',size=89)
        # Cut closer so the cause is visible before either component leaves frame.
        pane(im,(150,215,1770,870),'我的网站 / 导航与登录')
        q=smooth((t-22.08)/1.9)
        nx,ny=345-850*q,325
        rr(im,(345,325,650,850),'#F6F7FA',18)
        paste(im,component('nav'),nx,ny,scale=1.15)
        px,py=nx-110,730
        line(im,[(px+55,py),(nx+12,ny+340)],ORANGE,5)
        pet(im,px,py,160,tilt=-7)
        lq=smooth((t-22.88)/2.1)
        lx,ly=1260+850*lq,505-abs(math.sin(lq*math.pi*3))*40
        ui_button(im,lx,ly,'登录',330,126,size=54)
        if 0<lq<1:
            for i in range(3):
                line(im,[(lx-190-i*20,ly-20+i*22),(lx-240-i*20,ly-20+i*22)],BLUE,5)
        if t>=24.2:
            text(im,'菜单与登录：未找到',(1100,752),37,MUTED,True)
        subtitle(im,'菜单失踪，登录出走')
    elif t<28:
        header(im,'这也叫“小改动”？',size=79)
        site(im,t,'weird')
        pane(im,(1110,500,1720,790),'Agent / 操作记录')
        text(im,'重排菜单',(1155,602),31,INK)
        text(im,'重新设计首页',(1155,675),34,ORANGE)
        pet(im,1600,681,115)
        subtitle(im,'你说顺便优化结构')
    elif t<30.96:
        at=28 if t<29.76 else 29.76
        header(im,'改回来',True,size=143)
        q=ease((t-at)/.65)*(1 if t<29.76 else 1.65)
        site(im,t,'undo',box=(210,285,1710,765),p=q)
        undo_control(im,t,at)
        if t>=29.76:
            note(im,'又改了一版',1470,744,ORANGE,28)
    elif t<34.88:
        header(im,'怎么越改越奇怪',True,size=105)
        site(im,t,'weird',box=(210,285,1710,835))
        # An absurdly oversized login actually replaces the homepage hero.
        q=ease((t-32.48)/.6)
        if q>0:
            ui_button(im,1050,550,'登录',420+q*170,140+q*75,color=ORANGE,size=68)
        pet(im,1540,766,155,tilt=-10)
    elif t<37.84:
        header(im,'改回来',True,size=143)
        q=clamp((t-34.88)/2.4)
        site(im,t,'war',box=(210,285,1710,765),p=q)
        # Agents genuinely act on the shared objects; names travel with their cursors.
        cursor(im,680+q*240,510+30*q,BLUE,'Agent 1',t<35.1)
        cursor(im,1250-q*260,510-35*q,ORANGE,'Agent 2',36.24<t<36.5)
        pet(im,640+q*240,670,105)
        pet(im,1360-q*240,670,105,tilt=10)
        undo_control(im,t,34.88 if t<36.24 else 36.24,'撤销，再撤销')
    elif t<44:
        header(im,'我的首页' if t<39.28 else '还在不在',True,size=133)
        site(im,t,'fall',box=(210,285,1710,835),p=clamp((t-39.28)/3.6))
        if t>=42:
            text(im,'……',(960,550),95,MUTED,True)
    elif t<46.96:
        pane(im,(325,220,1595,855),'Agent / 最后一步')
        pet(im,480,465,150)
        text(im,'正在整理修改结果',(665,405),58,INK)
        text(im,'马上就好',(675,520),35,MUTED)
        # Progress represents the fictional task completing, no factual metric.
        rr(im,(440,670,1480,690),'#EAEFF8',10)
        rr(im,(440,670,440+1040*smooth((t-44)/2.96),690),BLUE,10)
    elif t<49.4:
        pane(im,(325,220,1595,855),'Agent / 任务完成')
        d.ellipse((430,355,590,515),fill='#E2F3D5')
        line(im,[(469,433),(500,461),(551,404)],'#49793C',13)
        text(im,'已修复。',(700,355),135,INK)
        text(im,'按钮已经是蓝色了',(700,565),44,MUTED)
        pet(im,1380,735,175,tilt=-6)
    elif t<52.88:
        header(im,'回来检查一下…',size=66)
        site(im,t,'button')
        cursor(im,680+230*math.sin((t-49.4)*1.5),530+70*math.cos((t-49.4)*2))
        pet(im,1610,813,145)
    elif t<57:
        site(im,t,'button')
        text(im,'网站呢？',(960,125),148,INK,True)
        # The actor leaves the scene because the missing website has been noticed.
        q=smooth((t-54)/2.2)
        pet(im,1610+520*q,813-abs(math.sin(q*math.pi*5))*22,145,tilt=-8*q)
        cursor(im,1125,621,INK)
    elif t<61:
        pane(im,(300,175,1620,910),ASSISTANT_NAME)
        rr(im,(865,315,1515,440),'#EAF0FF',24)
        text(im,'我的首页呢？',(1190,377),61,INK,True)
        pet(im,412,594,94)
        if t<59:
            for i in range(3):
                d.ellipse((520+i*65,580,541+i*65,601),fill=BLUE if int(t*3)%3==i else LINE)
        else:
            text(im,'按钮不是已经蓝了吗',(525,555),57,INK)
        text(im,'正在输入…' if t<59 else ' ',(520,700),27,MUTED)
    elif t<65:
        pane(im,(220,165,1700,900),'修改记录')
        text(im,'你的需求',(320,300),40,MUTED)
        text(im,'按钮变蓝',(320,390),70,INK)
        line(im,[(960,300),(960,790)],LINE,3)
        text(im,'实际结果',(1060,300),40,MUTED)
        text(im,'按钮变蓝',(1060,390),70,BLUE)
        if t>62.5:
            text(im,'首页没了',(1060,545),70,ORANGE)
            pet(im,1435,740,130,tilt=10)
    elif t<67:
        site(im,t,'button',box=(220,170,1700,870))
        text(im,'按钮留下了。',(960,955),76,INK,True)
        if t>=65.2:
            rr(im,(385,640,1030,775),'#F2F4F8',20)
            text(im,'下次我自己改。',(707,706),52,INK,True)
        if t>=66.3:
            # Returning character peeks at the actual site edge; no idle sticker.
            pet(im,1650,875-40*ease((t-66.3)/.6),115)
    else:
        pane(im,(150,150,1770,930),'只想要个蓝按钮')
        text(im,'只想要个',(310,350),105,INK)
        text(im,'蓝按钮',(300,490),160,BLUE)
        ui_button(im,1430,565,'开始',330,120,size=56)
        pet(im,1420,742,170)
        text(im,'你也遇到过这种“小改动”吗？',(960,845),36,MUTED,True)
    return im


TIMES=[1.9,6.9,10.8,13.7,16.4,20.0,22.6,23.5,26.5,28.8,30.3,33.4,35.4,37.0,40.4,42.9,45.4,47.7,51.4,53.6,55.6,59.7,63.6,65.9,68.2]


def preview():
    (P/'frames').mkdir(exist_ok=True)
    sheet=Image.new('RGB',(1440,5*184),'#202337')
    for i,t in enumerate(TIMES):
        im=draw(t)
        im.save(P/'frames'/f'{t:05.1f}.jpg',quality=93)
        x,y=(i%5)*288,(i//5)*184
        sheet.paste(im.resize((288,162),Image.Resampling.LANCZOS),(x,y))
        ImageDraw.Draw(sheet).text((x+8,y+164),f'{t:.1f}s',font=font(16,True),fill='white')
    sheet.save(P/'contact-sheet.jpg',quality=95)
    draw(68.2).save(P/'cover.jpg',quality=95)


def render(output):
    frames=math.ceil(DURATION*FPS)
    cmd=[str(b.FF),'-nostdin','-hide_banner','-loglevel','warning','-y','-f','rawvideo','-vcodec','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','pipe:0','-i',str(P/'song.mp3'),'-map','0:v','-map','1:a:0','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','256k','-t',str(DURATION),'-movflags','+faststart',str(P/output)]
    start=time.monotonic()
    with (P/'encode.log').open('w') as log:
        proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=log)
        try:
            for n in range(frames):
                proc.stdin.write(draw(n/FPS).tobytes())
                if n%300==0:
                    print(f'frame {n}/{frames}, {time.monotonic()-start:.1f}s',flush=True)
        finally:
            proc.stdin.close()
        if proc.wait():
            raise RuntimeError('FFmpeg render failed; see encode.log')
    (P/'render-info.json').write_text(json.dumps({'width':W,'height':H,'fps':FPS,'duration':DURATION,'input_frames':frames,'audio_speed':1.0,'render_seconds':time.monotonic()-start,'source_audio_sha256':hashlib.sha256((P/'song.mp3').read_bytes()).hexdigest()},indent=2))
    print('RENDER COMPLETE',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--preview',action='store_true')
    parser.add_argument('--output',default='只想要个蓝按钮-MV-v4.mp4')
    args=parser.parse_args()
    preview()
    if not args.preview:
        render(args.output)
