"""Render recorded results without running the database."""
import json
from pathlib import Path
P=Path(__file__).resolve().parent

def chart(path,title,values):
    width,height=760,390; left,right,top,bottom=80,720,70,310
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">','<rect width="100%" height="100%" fill="white"/>','<g font-family="Arial,sans-serif" fill="#172534">',f'<text x="40" y="30" font-size="19" font-weight="bold">{title}</text>']
    for n in range(0,101,20):
        y=bottom-(bottom-top)*n/100;out.extend([f'<line x1="{left}" x2="{right}" y1="{y}" y2="{y}" stroke="#e4eaf0"/>',f'<text x="37" y="{y+4}" font-size="12">{n}%</text>'])
    for i,(label,metric) in enumerate(values):
        x=left+40+i*(right-left-80)/len(values); bar=(right-left-80)/len(values)-35; rate=metric['rate'];y=bottom-(bottom-top)*rate
        out.extend([f'<rect x="{x}" y="{y}" width="{bar}" height="{bottom-y}" fill="#166b82"/>',f'<text x="{x+5}" y="{y-9}" font-size="14">{metric["numerator"]}/{metric["denominator"]}</text>',f'<text x="{x}" y="{bottom+22}" font-size="13">{label}</text>'])
    out.append('</g></svg>');path.write_text('\n'.join(out))

a=json.loads((P/'ablation-results/results.json').read_text()); c=json.loads((P/'challenge-results/results.json').read_text())
chart(P/'ablation-results/accuracy.svg','Synthetic held-out: artifact-only ablation',[(name,a[key]['accuracy']) for name,key in [('Static graph','static'),('Artifact only','artifact_only'),('Full graph','full')]])
chart(P/'challenge-results/accuracy.svg','Manual topology challenge: before and after',[(name,c[key]['accuracy']) for name,key in [('Before repair','initial'),('After repair','final')]])
