"""Original test artwork: conventional printed corners, not lab ASCII suits.

No proprietary game image is copied. Labels live in the test, independently
of the recognizer; its only input is this rendered RGB image.
"""
from PIL import Image, ImageDraw
from bjlab.datasets import card_font
from bjlab.engine import hand_value


def classic_table(player=('7', '2'), dealer=('6',), *, message='Your turn',
                  actions=('HIT', 'STAND', 'DOUBLE'), total=None, scale=1,
                  duplicate=False, blank=False, obscure_rank=False):
    image=Image.new('RGB',(1280,1439),(4,15,62))
    draw=ImageDraw.Draw(image)
    draw.rectangle((0,376,1279,910),fill=(9,139,45))
    def panel(box,text,size=22):
        draw.rounded_rectangle(box,radius=12,fill=(10,39,65),outline=(218,190,106),width=2)
        draw.text(((box[0]+box[2])/2,(box[1]+box[3])/2),text,font=card_font(size),fill='white',anchor='mm')
    if not blank:
        panel((852,386,1160,470),message)
        for zone,ranks,top,left in (('dealer',dealer,417,527),('player',player,672,527)):
            for i,rank in enumerate(ranks):
                cx=left+113*i
                color=(180,0,0) if (i+int(zone=='dealer'))%2 else (0,0,0)
                draw.rounded_rectangle((cx,top,cx+111,top+141),radius=5,fill='white')
                if not (obscure_rank and zone=='player' and i==len(ranks)-1):
                    draw.text((cx+6,top+6),rank,font=card_font(18),fill=color,anchor='lt')
                # Actual suit-shaped pips, without an S/H/D/C label.
                draw.polygon(((cx+12,top+30),(cx+17,top+36),(cx+12,top+42),(cx+7,top+36)),fill=color)
                draw.polygon(((cx+55,top+53),(cx+65,top+67),(cx+55,top+81),(cx+45,top+67)),fill=color)
        if player:
            panel((527,640,748,667),str(hand_value(player)[0] if total is None else total),22)
        for i,action in enumerate(actions):
            cx=527+i*110
            draw.ellipse((cx,988,cx+84,1072),fill=(44,174,33),outline=(220,196,110),width=3)
            panel((cx+4,1074,cx+80,1096),action,16)
    if scale!=1:
        image=image.resize((round(image.width*scale),round(image.height*scale)),Image.Resampling.LANCZOS)
    if duplicate:
        desktop=Image.new('RGB',(image.width*2,image.height),(15,18,24))
        desktop.paste(image,(image.width,0))
        preview=image.resize((round(image.width*.36),round(image.height*.36)),Image.Resampling.LANCZOS)
        desktop.paste(preview,(20,200))
        return desktop
    return image
