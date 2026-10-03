"""Texas Hold'em showdown analysis. Hidden opponent cards are marginalized."""
from collections import Counter
import math
import random
import re

RANKS='23456789TJQKA'
DECK=tuple(r+s for r in RANKS for s in 'SHDC')
NAMES=('High card','Pair','Two pair','Three of a kind','Straight','Flush','Full house','Four of a kind','Straight flush')


def card(value):
    text=str(value).strip().upper().replace('10','T')
    for symbol,suit in zip('♠♥♦♣','SHDC'):
        text=text.replace(symbol,suit)
    if not re.fullmatch('[2-9TJQKA][SHDC]',text):
        raise ValueError('Poker cards need rank and suit, for example AS, 10H or K♦.')
    return text


def straight(values):
    ranks=set(values)
    if 14 in ranks:ranks.add(1)
    for high in range(14,4,-1):
        if all(value in ranks for value in range(high-4,high+1)):
            return high
    return 0


def rank_hand(cards):
    cards=tuple(card(c) for c in cards)
    if not 5<=len(cards)<=7 or len(set(cards))!=len(cards):
        raise ValueError('A ranked poker hand requires five to seven distinct cards.')
    values=[RANKS.index(c[0])+2 for c in cards]
    counts=Counter(values)
    flushes=[[RANKS.index(c[0])+2 for c in cards if c[1]==suit] for suit in 'SHDC']
    flushes=[v for v in flushes if len(v)>=5]
    for suited in flushes:
        high=straight(suited)
        if high:return (8,high)
    quads=sorted((v for v,n in counts.items() if n==4),reverse=True)
    if quads:return (7,quads[0],max(v for v in values if v!=quads[0]))
    triples=sorted((v for v,n in counts.items() if n>=3),reverse=True)
    pairs=sorted((v for v,n in counts.items() if n>=2),reverse=True)
    if triples:
        other=[v for v in pairs if v!=triples[0]]
        if other:return (6,triples[0],other[0])
    if flushes:return (5,*max(tuple(sorted(v,reverse=True)[:5]) for v in flushes))
    high=straight(values)
    if high:return (4,high)
    if triples:return (3,triples[0],*sorted((v for v in values if v!=triples[0]),reverse=True)[:2])
    if len(pairs)>=2:return (2,pairs[0],pairs[1],max(v for v in values if v not in pairs[:2]))
    if pairs:return (1,pairs[0],*sorted((v for v in values if v!=pairs[0]),reverse=True)[:3])
    return (0,*sorted(values,reverse=True)[:5])


def equity(hole,board=(),*,opponents=1,samples=2000,seed=42,dead=(),opponent_ranges=None,pot=0.,call_cost=0.):
    hole,board,dead=tuple(map(card,hole)),tuple(map(card,board)),tuple(map(card,dead))
    if len(hole)!=2 or len(board) not in (0,3,4,5):
        raise ValueError('Texas Hold’em needs two hole cards and a board of zero, three, four or five cards.')
    known=hole+board+dead
    if len(set(known))!=len(known):raise ValueError('The same physical card appears more than once.')
    if type(opponents) is not int or not 1<=opponents<=8 or type(samples) is not int or not 100<=samples<=20000:
        raise ValueError('Use one to eight opponents and 100 to 20,000 samples.')
    if any(not math.isfinite(v) or v<0 for v in (pot,call_cost)):
        raise ValueError('Pot and call cost must be finite, non-negative values.')
    remaining=tuple(c for c in DECK if c not in known)
    if len(remaining)<opponents*2+5-len(board):raise ValueError('Too few unknown cards remain for this deal.')
    configured=opponent_ranges or [None]*opponents
    if len(configured)!=opponents:raise ValueError('Provide exactly one range per opponent.')
    ranges=[]
    for configured_range in configured:
        if configured_range is None:
            ranges.append(None);continue
        if len(configured_range)>1326:raise ValueError('A range may contain at most 1,326 combinations.')
        valid=set()
        for combo in configured_range:
            combo=tuple(sorted(map(card,combo)))
            if len(combo)!=2 or combo[0]==combo[1]:raise ValueError('Each range combination needs two distinct cards.')
            if not set(combo).intersection(known):valid.add(combo)
        if not valid:raise ValueError('An opponent range has no combinations after known-card blockers.')
        ranges.append(tuple(sorted(valid)))
    rng=random.Random(seed);wins=ties=losses=0;shares=[];attempts=0
    while len(shares)<samples:
        attempts+=1
        if attempts>max(10000,samples*100):raise ValueError('Opponent ranges do not provide enough compatible joint deals.')
        # Independent proposals + global rejection avoid sequential range bias.
        hands=[rng.choice(r) if r else tuple(rng.sample(remaining,2)) for r in ranges]
        exposed=tuple(c for hand in hands for c in hand)
        if len(set(exposed))!=len(exposed):continue
        runout=board+tuple(rng.sample([c for c in remaining if c not in exposed],5-len(board)))
        hero=rank_hand(hole+runout)
        villains=[rank_hand(hand+runout) for hand in hands]
        best=max([hero,*villains])
        if hero<best:losses+=1;shares.append(0.)
        elif any(v==hero for v in villains):ties+=1;shares.append(1/(1+sum(v==hero for v in villains)))
        else:wins+=1;shares.append(1.)
    mean=sum(shares)/samples
    variance=sum((v-mean)**2 for v in shares)/(samples-1)
    margin=1.96*math.sqrt(variance/samples)
    made=rank_hand(hole+board) if len(board)>=3 else None
    return {'game':'texas-holdem','hole':list(hole),'board':list(board),'opponents':opponents,
            'equity':mean,'win':wins/samples,'tie':ties/samples,'loss':losses/samples,
            'equity_ci95':[max(0.,mean-margin),min(1.,mean+margin)],'samples':samples,'seed':seed,
            'made_hand':NAMES[made[0]] if made else 'Preflop',
            'pot_odds':call_cost/(pot+call_cost) if pot+call_cost else None,
            'showdown_call_ev':mean*(pot+call_cost)-call_cost if call_cost else None,
            'range_assumption':'Explicit equally weighted combinations where supplied; otherwise uniformly random unknown hands.',
            'scope':'Showdown equity with split-pot shares. Future betting, rake, side pots and opponent strategy are excluded. Equity alone is not an optimal betting policy.',
            'method':'Monte Carlo without replacement; interval measures sampling, not recognition error.'}
