"""Original overlapping-card fixtures with gold side totals and EN/IT controls."""
from PIL import Image,ImageDraw
from bjlab.datasets import card_font
from bjlab.engine import hand_value


def side_table(player=('A','5'),dealer=('2',),*,locale='it',settled=False,scale=1,total=None,hidden=True,disabled=('double','split'),blank=False,player_suits=None,dealer_suits=None):
    image=Image.new('RGB',(1000,900),(8,15,28));draw=ImageDraw.Draw(image)
    draw.rounded_rectangle((20,70,980,850),24,fill=(15,126,71),outline=(207,172,91),width=4)
    gold=(240,206,123)
    if not blank:
        for zone,ranks,top in (('dealer',dealer,175),('player',player,505)):
            displayed=[*ranks,None] if zone=='dealer' and hidden else ranks
            left=500-(len(displayed)*60+80)/2
            for i,rank in enumerate(displayed):
                x=int(left+i*62)
                draw.rounded_rectangle((x,top,x+114,top+160),8,fill='white')
                if rank is None:
                    draw.rectangle((x+4,top+4,x+110,top+156),fill=(195,15,20))
                    for yy in range(top+4,top+157,6):draw.line((x+4,yy,x+110,yy),fill=(255,210,210))
                else:
                    suits=dealer_suits if zone=='dealer' else player_suits
                    suit=suits[i] if suits is not None else ('D' if i%2 else 'S')
                    color=(210,0,0) if suit in ('H','D') else (8,8,8)
                    draw.text((x+9,top+9),rank,font=card_font(30),fill=color,anchor='lt')
                    draw.text((x+14,top+48),{'S':'♠','H':'♥','D':'♦','C':'♣'}[suit],font=card_font(20),fill=color,anchor='lt')
            text=('BANCO' if zone=='dealer' else 'GIOCATORE') if locale=='it' else ('DEALER' if zone=='dealer' else 'PLAYER')
            draw.text((835,top+45),text,font=card_font(16),fill=gold,anchor='mm')
            value=hand_value(ranks)[0] if zone=='dealer' or total is None else total
            draw.text((835,top+80),str(value),font=card_font(31),fill=gold,anchor='mm')
        captions={'it':['CARTA','STAI','RADDOPPIA','DIVIDI'],'en':['HIT','STAND','DOUBLE','SPLIT']}[locale]
        if settled:captions=['NUOVA MANO' if locale=='it' else 'NEW HAND'];keys=['next']
        else:keys=['hit','stand','double','split']
        for i,(text,key) in enumerate(zip(captions,keys)):
            x=125+i*195
            draw.rounded_rectangle((x,752,x+180,806),13,fill=(12,76,53),outline=gold,width=1)
            draw.text((x+90,780),text,font=card_font(19),fill=(125,107,62) if key in disabled else gold,anchor='mm')
    if scale!=1:image=image.resize((round(1000*scale),round(900*scale)),Image.Resampling.LANCZOS)
    return image
