"""Render an honest recut using captured live dashboard and saved real CLI replay."""
import csv,json,subprocess,concurrent.futures
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[2]; OUT=ROOT/'demo/recut'; SRC=ROOT/'demo/recording/page@3e850b87b3eb92ab91ce7e88c21963ae.webm'
W,H=1440,900
F='/System/Library/Fonts/Supplemental/Arial.ttf'; B='/System/Library/Fonts/Supplemental/Arial Bold.ttf'; G='/System/Library/Fonts/Supplemental/Georgia.ttf'
def font(size,bold=False,serif=False):return ImageFont.truetype(G if serif else B if bold else F,size)
def panel():
 im=Image.new('RGB',(W,H),'#10251e');d=ImageDraw.Draw(im);d.rounded_rectangle((44,44,W-44,H-44),radius=22,outline='#345548',width=2);d.text((90,72),'HYDRAWITNESS   /   EVIDENCE BEFORE CONFIDENCE',font=font(21,True),fill='#98c7ad');return im,d
def save(im,name):im.save(OUT/name)
im,d=panel();d.text((100,190),'Four reports.',font=font(90,serif=True),fill='#f3f6ee');d.text((100,310),'One origin.',font=font(90,serif=True),fill='#b9dcc3');d.text((100,435),'One skipped security scan.',font=font(62,serif=True),fill='#ecaaa0');d.text((105,620),'WHEN AGENTS AGREE, CHECK WHERE THE AGREEMENT CAME FROM.',font=font(21,True),fill='#a9bbb1');d.text((105,765),'SYNTHETIC FIXTURE  •  ADVISORY DECISIONS',font=font(20,True),fill='#c7d4cb');save(im,'hook.png')
# Actual saved graph frame, enlarged; no graph nodes are invented.
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss','27','-i',str(SRC),'-frames:v','1',str(OUT/'recorded-frame.png')],check=True)
graph=Image.open(OUT/'recorded-frame.png').convert('RGB').crop((410,450,1015,655));graph=graph.resize((1210,410),Image.Resampling.LANCZOS)
im,d=panel();d.text((92,160),'Four reports converge on one source.',font=font(52,serif=True),fill='#f3f6ee');d.text((95,235),'RECORDED DASHBOARD • SEPARATE FOUR-REPORT SCOPE',font=font(19,True),fill='#a5c6b0');im.paste(graph,(115,300));d=ImageDraw.Draw(im);d.text((120,745),'The required scan is shown in red: skipped.',font=font(29,True),fill='#eeaa9c');save(im,'graph.png')
rows=list(csv.DictReader((ROOT/'evals/results/iterations.csv').open()));vals=[round(float(r['accuracy'])*100) for r in rows];base=round(float(rows[0]['static_accuracy'])*100);assert vals==[50,70,70,80,100] and base==50
stats=json.loads((ROOT/'evals/repeated-results/results.json').read_text())['summary'];assert stats['graph']['queries']==672 and stats['metadata']['queries']==852
im,d=panel();d.text((88,135),'The learning curve',font=font(58,serif=True),fill='#f3f6ee');d.text((90,211),'SYNTHETIC HELD-OUT BENCHMARK  ·  20 CORRELATED QUESTIONS',font=font(19,True),fill='#a5c6b0')
left,right,top,bottom=170,1250,320,680
for pct in (50,70,80,100):
 y=bottom-(pct-40)/60*(bottom-top);d.line((left,y,right,y),fill='#36564a',width=2);d.text((90,y-14),str(pct)+'%',font=font(21),fill='#b5c6ba')
coords=[]
for i,v in enumerate(vals):
 x=left+i*(right-left)/4;y=bottom-(v-40)/60*(bottom-top);coords.append((x,y))
by=bottom-(base-40)/60*(bottom-top)
for x in range(left,right,25):d.line((x,by,min(x+13,right),by),fill='#d5ab70',width=4)
d.line(coords,fill='#8dd6a9',width=7)
for i,((x,y),v) in enumerate(zip(coords,vals)):
 d.ellipse((x-9,y-9,x+9,y+9),fill='#b5f0c7');d.text((x-30,y-43),f'{v}%',font=font(24,True),fill='#edfff0');d.text((x-8,bottom+25),str(i),font=font(20),fill='#a6bdad')
d.text((100,785),'GREEN: HYDRAWITNESS    ·    DASHED: STATIC GRAPH (50%)',font=font(19,True),fill='#c9d8ca');d.text((100,821),'Artifact-only also reached 100%; an edge-specific accuracy advantage is unproven.',font=font(18),fill='#a3b7a9');save(im,'accuracy.png')
im,d=panel();d.text((100,155),'A measurable reuse signal',font=font(58,serif=True),fill='#f3f6ee');d.text((105,245),'120 REPEATED SYNTHETIC ASSESSMENTS PER METHOD',font=font(19,True),fill='#a5c6b0');d.rounded_rectangle((100,320,680,560),20,fill='#1b382c');d.rounded_rectangle((760,320,1340,560),20,fill='#25392e');d.text((145,365),'672',font=font(95,True),fill='#a9e7bb');d.text((145,490),'PERSISTED GRAPH QUERIES',font=font(20,True),fill='#d3e6d6');d.text((805,365),'852',font=font(95,True),fill='#f0d0a3');d.text((805,490),'METADATA RECONSTRUCTION',font=font(20,True),fill='#d3e6d6');d.text((105,650),'21.1% fewer queries in this local workload.',font=font(38,serif=True),fill='#f5f6ed');d.text((105,715),'This is not proof of a general latency advantage.',font=font(23),fill='#a8bcaf');save(im,'queries.png')
im,d=panel();d.text((100,185),'Evidence before confidence.',font=font(70,serif=True),fill='#f3f6ee');d.text((103,330),'BUILT FOR ENGINEERING & SECURITY TEAMS',font=font(25,True),fill='#a8d5b5');d.text((103,405),'AI agents need decisions they can trace,',font=font(38),fill='#e9f1e8');d.text((103,460),'verify, and revisit.',font=font(38),fill='#e9f1e8');d.text((104,650),'SYNTHETIC DEMO  ·  ADVISORY ONLY  ·  NO PRODUCTION DEPLOYMENT',font=font(19,True),fill='#a8bbae');d.text((104,710),'Subscription or per-decision pricing is a hypothesis, not validated revenue.',font=font(19),fill='#a8bbae');save(im,'close.png')
# Each recorded clip is labeled explicitly. Generated overlay supplies context only.
def overlay(text,path):
 im=Image.new('RGBA',(W,H),(0,0,0,0));d=ImageDraw.Draw(im);d.rounded_rectangle((25,805,1415,875),12,fill=(13,35,28,238));d.text((55,822),text,font=font(20,True),fill='#d6f2dc');im.save(OUT/path)
overlay('SAVED REAL CODEX MCP EVENTS • TWO-REPORT SYNTHETIC SCOPE','codex.png')
overlay('RECORDED LIVE DASHBOARD • SEPARATE FOUR-REPORT SYNTHETIC SCOPE','dashboard.png')
overlay('SAVED REAL CODEX MCP EVENTS • SAME SCOPE AS SESSION ONE','codex2.png')
# 12+15+26+17+13+20+12+15 = 130 seconds.
segments=[('still','hook.png',12),('video',0,12,15,'codex.png'),('video',12,20,26,'dashboard.png'),('still','graph.png',17),('video',32,13,13,'codex2.png'),('still','accuracy.png',20),('still','queries.png',12),('still','close.png',15)]
lines=[
 'Four reports. One origin. One skipped security scan. When agents agree, we need to know whether their evidence is actually independent.',
 'This is a replay of a real Codex session using two synthetic reports. HydraWitness first returns review required, then discovers the missing evidence and returns block.',
 'The next sequence is a real dashboard recording in a separate, four report synthetic scope. We begin with incomplete lineage. Investigate the missing references, and HydraDB stores the discovered evidence and relationships. The recommendation changes from review required to block.',
 'Here is the recorded graph enlarged. The reports converge on a shared CI origin. Its required security scan, shown in red, was skipped. Missing evidence alone requires review. The skipped required scan is why this policy blocks.',
 'A second real Codex session asks a related question in the first session’s graph scope. It retrieves the repaired evidence and recommends block without repeating ingestion.',
 'Across twenty correlated synthetic held-out questions, accuracy rises from fifty to seventy, seventy, eighty, and one hundred percent. The static graph remains at fifty percent. An artifact-only method also reached one hundred percent, so a graph-specific accuracy advantage is unproven.',
 'In a separate local reuse experiment, persisted graph traversal used six hundred seventy-two queries versus eight hundred fifty-two for metadata reconstruction. That is twenty-one point one percent fewer requests in this workload, not proof of a general latency advantage.',
 'HydraWitness is for engineering and security teams using AI agents to validate evidence and make release recommendations. Decisions are advisory, the evidence is synthetic, and production validation and restart durability remain open.'
]
def narration(i,text):
 path=OUT/f'voice-{i}.aiff';subprocess.run(['say','-r','185','-o',str(path),text],check=True);return i
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(lambda z:narration(*z),enumerate(lines)))
for i,seg in enumerate(segments):
 typ=seg[0];dur=seg[2] if typ=='still' else seg[3];vout=OUT/f'video-{i}.mp4'
 if typ=='still':
  cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-loop','1','-i',str(OUT/seg[1]),'-t',str(dur),'-vf',"scale=1512:945,zoompan=z='min(zoom+0.00016,1.05)':d=1:s=1440x900:fps=15",'-an','-c:v','libx264','-preset','ultrafast','-crf','24','-pix_fmt','yuv420p',str(vout)]
 else:
  _,start,length,duration,label=seg;rate=duration/length
  cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(start),'-t',str(length),'-i',str(SRC),'-loop','1','-i',str(OUT/label),'-filter_complex',f'[0:v]setpts={rate}*PTS,fps=15[base];[base][1:v]overlay=0:0:shortest=1[v]','-map','[v]','-t',str(duration),'-an','-c:v','libx264','-preset','ultrafast','-crf','24','-pix_fmt','yuv420p',str(vout)]
 subprocess.run(cmd,check=True)
 audio=OUT/f'audio-{i}.m4a'; voice=OUT/f'voice-{i}.aiff'
 voice_duration=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(voice)],text=True))
 speed=max(1.0,voice_duration/(dur-0.35))
 if speed>2: raise ValueError('Narration too long for scene '+str(i))
 subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(voice),'-af',f'atempo={speed},apad,atrim=0:{dur}','-c:a','aac','-b:a','96k',str(audio)],check=True)
 final=OUT/f'part-{i}.mp4';subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(vout),'-i',str(audio),'-c','copy','-shortest',str(final)],check=True)
 print('rendered scene',i,flush=True)
(OUT/'concat.txt').write_text(''.join("file '"+str(OUT/f'part-{i}.mp4')+"'\n" for i in range(len(segments))))
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(OUT/'concat.txt'),'-c','copy','-movflags','+faststart',str(ROOT/'demo/hydrawitness-recut.mp4')],check=True)
print(ROOT/'demo/hydrawitness-recut.mp4')
