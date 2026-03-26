"""
Diagramme d'architecture LangGraph — version simplifiee.
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import matplotlib.patheffects as pe

fig, ax = plt.subplots(figsize=(14, 16))
ax.set_xlim(0, 14)
ax.set_ylim(0, 16)
ax.axis('off')
fig.patch.set_facecolor('#0d1117')
ax.set_facecolor('#0d1117')

BG      = '#0d1117'
C_WHITE = '#e6edf3'
C_MUTED = '#8b949e'

def box(ax, x, y, w, h, color, label, sub=None, fsz=11):
    p = FancyBboxPatch((x - w/2, y - h/2), w, h,
                       boxstyle='round,pad=0,rounding_size=0.2',
                       facecolor=color, edgecolor='#ffffff18', linewidth=1.5, zorder=4)
    ax.add_patch(p)
    if sub:
        ax.text(x, y + 0.18, label, ha='center', va='center',
                fontsize=fsz, color=C_WHITE, fontweight='bold', zorder=5)
        ax.text(x, y - 0.25, sub, ha='center', va='center',
                fontsize=fsz - 2.5, color=C_WHITE, alpha=0.7, style='italic', zorder=5)
    else:
        ax.text(x, y, label, ha='center', va='center',
                fontsize=fsz, color=C_WHITE, fontweight='bold', zorder=5)

def dot(ax, x, y, r, color, label, fsz=9):
    ax.add_patch(plt.Circle((x, y), r, color=color, zorder=4))
    ax.add_patch(plt.Circle((x, y), r, fill=False, edgecolor='#ffffff33', lw=1.5, zorder=5))
    ax.text(x, y, label, ha='center', va='center',
            fontsize=fsz, color=C_WHITE, fontweight='bold', zorder=6)

def arr(ax, x1, y1, x2, y2, color, lw=2.0, rad=0.0, lbl='', dashed=False):
    ls = (0, (5, 3)) if dashed else 'solid'
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color=color, lw=lw,
                                linestyle=ls,
                                connectionstyle=f'arc3,rad={rad}'),
                zorder=3)
    if lbl:
        mx = (x1 + x2) / 2 + rad * abs(y2 - y1) * 0.4
        my = (y1 + y2) / 2 + rad * abs(x2 - x1) * 0.3
        ax.text(mx, my, lbl, ha='center', va='center', fontsize=8, color=color,
                zorder=6, bbox=dict(facecolor=BG, edgecolor='none', alpha=0.85, pad=1.5))

def divider(ax, y, label):
    ax.axhline(y, xmin=0.04, xmax=0.96, color='#30363d', lw=1, zorder=1)
    ax.text(7, y + 0.18, label, ha='center', va='center',
            fontsize=8, color=C_MUTED, style='italic',
            bbox=dict(facecolor=BG, edgecolor='none', pad=2))


# ── Titre ─────────────────────────────────────────────────────────────────
ax.text(7, 15.6, 'LangGraph  —  E-commerce Analysis Agent',
        ha='center', va='center', fontsize=16, color=C_WHITE, fontweight='bold')
ax.text(7, 15.1, 'Pattern ReAct  ·  Gemini LLM  ·  SerpApi',
        ha='center', va='center', fontsize=9.5, color=C_MUTED, style='italic')

# ── FastAPI ────────────────────────────────────────────────────────────────
divider(ax, 14.6, 'FastAPI  (main.py)')
box(ax, 4.0, 14.0, 4.2, 0.8, '#00695c', 'POST /analyze',        fsz=10)
box(ax, 9.5, 14.0, 4.8, 0.8, '#00695c', 'POST /analyze/stream', fsz=10)

# ── LangGraph ──────────────────────────────────────────────────────────────
divider(ax, 13.3, 'LangGraph StateGraph  (agent.py + nodes.py)')

# START
dot(ax, 7, 12.7, 0.38, '#484f58', 'START', 8)

# node_orchestrator
box(ax, 7, 11.4, 5.0, 1.1, '#5e35b1',
    'node_orchestrator', sub='Gemini LLM  —  decide la prochaine action', fsz=11)

# log_reasoning
box(ax, 7, 9.9, 3.8, 0.8, '#37474f',
    'log_reasoning', sub='enregistre chaque decision', fsz=9)

# Tools
box(ax, 2.5, 8.1, 3.2, 1.0, '#1565c0', 'node_scraper',   sub='SerpApi Google Shopping',  fsz=9)
box(ax, 7.0, 8.1, 3.2, 1.0, '#1565c0', 'node_sentiment', sub='SerpApi Shopping Reviews', fsz=9)
box(ax,11.5, 8.1, 3.2, 1.0, '#1565c0', 'node_trends',    sub='SerpApi Google Trends',    fsz=9)

# node_report
box(ax, 7, 6.3, 5.0, 1.0, '#2e7d32',
    'node_report', sub='Gemini LLM  —  rapport strategique final', fsz=10)

# END
dot(ax, 7, 5.1, 0.38, '#484f58', 'END', 8)

# ── Edges ──────────────────────────────────────────────────────────────────
BLUE   = '#58a6ff'
RED    = '#ff7b72'
PURPLE = '#c084fc'
GREEN  = '#4ade80'

# FastAPI -> START
arr(ax, 4.0, 13.6, 6.5, 13.05, '#39d353', lw=1.5, dashed=True)
arr(ax, 9.5, 13.6, 7.5, 13.05, '#39d353', lw=1.5, dashed=True)

# START -> orchestrator
arr(ax, 7, 12.32, 7, 11.95, BLUE, lw=2.2)

# orchestrator -> log_reasoning
arr(ax, 7, 10.85, 7, 10.3,  BLUE, lw=2.2)

# log_reasoning -> tools (conditional)
arr(ax, 5.1,  9.51,  2.5,  8.6,  PURPLE, lw=1.8, rad=0.15, lbl='route_next()')
arr(ax, 7.0,  9.51,  7.0,  8.6,  PURPLE, lw=1.8)
arr(ax, 8.9,  9.51, 11.5,  8.6,  PURPLE, lw=1.8, rad=-0.15)

# log_reasoning -> node_report (direct)
arr(ax, 7, 9.51, 7, 6.8, PURPLE, lw=1.8, rad=0.6)

# Tools -> orchestrator (ReAct loop)
arr(ax,  2.5, 8.6,  4.5, 11.4,  RED, lw=1.8, rad=-0.3, lbl='loop')
arr(ax,  7.0, 8.6,  7.0, 10.85, RED, lw=1.8, rad=-0.4)
arr(ax, 11.5, 8.6,  9.5, 11.4,  RED, lw=1.8, rad=0.3)

# report -> END
arr(ax, 7, 5.8, 7, 5.48, BLUE, lw=2.2)

# ── AgentState ─────────────────────────────────────────────────────────────
divider(ax, 4.5, 'AgentState  —  etat partage entre tous les nodes')

rows = [
    ('prompt  ·  product  ·  market  ·  market_code',        C_WHITE),
    ('next_action  ·  turn  ·  last_reasoning',              '#c084fc'),
    ('reasoning_log  [ {turn, action, reason} ]',             C_MUTED),
    ('scraper_data  ·  sentiment_data  ·  trends_data',      '#60a5fa'),
    ('report  ·  errors  ·  exhausted_tools',                '#4ade80'),
]
for i, (txt, col) in enumerate(rows):
    ax.text(7, 4.0 - i * 0.55, f'•  {txt}',
            ha='center', va='center', fontsize=8.5, color=col)

# ── Legend ─────────────────────────────────────────────────────────────────
items = [
    (BLUE,   'Flux principal'),
    (PURPLE, 'Edges conditionnels  (route_next)'),
    (RED,    'Boucle ReAct  (retour orchestrateur)'),
]
lx, ly = 0.6, 1.2
for i, (col, lbl) in enumerate(items):
    ax.plot([lx, lx + 0.5], [ly - i*0.5, ly - i*0.5], color=col, lw=2.5)
    ax.text(lx + 0.7, ly - i*0.5, lbl, va='center', fontsize=8, color=C_WHITE)

# ── Save ───────────────────────────────────────────────────────────────────
plt.tight_layout(pad=0.3)
plt.savefig('architecture_langgraph.png', dpi=160, bbox_inches='tight',
            facecolor=BG, edgecolor='none')
print('Sauvegarde : architecture_langgraph.png')
