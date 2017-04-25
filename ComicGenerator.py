import os
import os.path
import random
import re
import unicodedata

from PIL import Image, ImageFont, ImageDraw

panel_height = 300
panel_width = 450

class ComicGenerator:
    def __init__(self):
        self.char_paths = list(map(lambda p: os.path.join("chars", p), os.listdir("chars/")))
        self.bg_paths = list(map(lambda p: os.path.join("backgrounds", p), os.listdir("backgrounds/")))
        # TODO: put these in config file
        self.font_file = "fonts/Comic.ttf"
        self.font_size = 16

    def _gen_panel_text(self, msgs):
        panels = []
        panel = []
        for msg in msgs:
            # if we already have a full panel (two speakers, or consecutive msg speaker), create a new panel
            if len(panel) >= 2 or (len(panel) == 1 and panel[0][0] == msg.author.id):
                panels.append(panel)
                panel = []
            panel.append((msg.author.id,
                # tidy up custom emotes and replace unicode emotes with names
                # todo: skintone stuff
                #([/U0001F3FB-/U0001F3FF][\u261D\u2639\u263A\u26F9\u270A-\u270D\U0001F385\U0001F3C2-\U0001FC4\U0001FC7\U0001F3CA-\U0001F3CC\U0001F442\U0001F443\U0001F446-\U0001F450\U0001F466-\U0001F478\U0001F47C\U0001F481-\U0001F483\U0001F486\U0001F487\U0001F48F\U0001F491\U0001F4AA\U0001F590-\U0001F596\U0001F600-\U0001F637\U0001F641-\U0001F647\U0001F64B-\U0001F64F\U0001F6A3\U0001F6B4-\U0001F6B6\U0001F6C0\U0001F910-\U0001F915\U0001F917\U0001F918])|
                re.sub(r'([\U0001F1E6-\U0001F1FF\U0001F1E6-\U0001F1FF])|([\U0001F000-\U0001F991])|([\u26BD\uFE0F\uE57A\u231A-\u231B\u2600-\u2747\u2764\u2690\u200D])',
                       lambda y: ":" + unicodedata.name(y.group(0)).replace(" ","").lower() + ":",
                re.sub(r'<:([a-zA-Z_0-9]*):([0-9]*)>', r":\1:", msg.clean_content))))
        panels.append(panel)
        return panels

    def _wrap(self, st, font, draw, width):
        st = st.split()
        mw = 0
        mh = 0
        ret = []

        while len(st) > 0:
            s = 1
            while True and s < len(st):
                w, h = draw.textsize(" ".join(st[:s]), font=font)
                if w > width:
                    s -= 1
                    break
                else:
                    s += 1

            if s == 0 and len(st) > 0:  # we've hit a case where the current line is wider than the screen
                s = 1

            w, h = draw.textsize(" ".join(st[:s]), font=font)
            mw = max(mw, w)
            mh += h
            ret.append(" ".join(st[:s]))
            st = st[s:]

        return ret, (mw, mh)

    def _render_text(self, st, font, draw, pos):
        ch = pos[1]
        for s in st:
            w, h = draw.textsize(s, font=font)
            draw.text((pos[0], ch), s, font=font, fill=(0xff, 0xff, 0xff, 0xff))
            ch += h

    def _fit_img(self, img, width, height):
        scale1 = float(width) / img.size[0]
        scale2 = float(height) / img.size[1]

        l1 = (img.size[0] * scale1, img.size[1] * scale1)
        l2 = (img.size[0] * scale2, img.size[1] * scale2)

        if l1[0] > width or l1[1] > height:
            l = l2
        else:
            l = l1

        return img.resize((int(l[0]), int(l[1])), Image.ANTIALIAS)

    def make_comic(self, msgs):
        # takes a list of rows from db

        random.shuffle(self.char_paths)
        random.shuffle(self.bg_paths)

        trimmed = []
        characters = set()
        for msg in msgs:
            trimmed.append(msg)
            characters.add(msg.author.id)
           # if msgs[i]["time"] - msgs[i-1]["time"] > 120:
           #     break
           # if len(characters) > 3:
           #     break
           # if len(trimmed) > 10:
           #     break
        trimmed.reverse()

        # panels is now a list of nick, msg
        panels = self._gen_panel_text(trimmed)

        char_map = {ch: path for (ch, path) in zip(characters, self.char_paths)}

        img_width = panel_width
        img_height = panel_height * len(panels)
        img = Image.new("RGBA", (img_width, img_height), (0xff, 0xff, 0xff, 0xff))
        font = ImageFont.truetype(self.font_file, self.font_size)

        bg = Image.open(self.bg_paths[0])

        for (i, panel) in enumerate(panels):
            panel_img = Image.new("RGBA", (panel_width, panel_height), (0xff, 0xff, 0xff, 0xff))
            panel_img.paste(bg, (0, 0))
            drawn = ImageDraw.Draw(panel_img)

            st1w = 0; st1h = 0; st2w = 0; st2h = 0
            (st1, (st1w, st1h)) = self._wrap(panel[0][1], font, drawn, 2*panel_width/3.0)
            self._render_text(st1, font, drawn, (10, 10))
            if len(panel) == 2:
                (st2, (st2w, st2h)) = self._wrap(panels[i][1][1], font, drawn, 2*panel_width/3.0)
                self._render_text(st2, font, drawn, (panel_width-10-st2w, st1h + 10))

            text_height = st1h + 10
            if st2h > 0:
                text_height += st2h + 10 + 5

            max_ch_height = panel_height - text_height
            im1 = self._fit_img(Image.open(char_map[panel[0][0]]), 2*panel_width/5.0-10, max_ch_height)

            panel_img.paste(im1, (10, panel_height-im1.size[1]), im1)

            if len(panel) == 2:
                im2 = self._fit_img(Image.open(char_map[panel[1][0]]), 2*panel_width/5.0-10, max_ch_height)
                im2 = im2.transpose(Image.FLIP_LEFT_RIGHT)
                panel_img.paste(im2, (panel_width-im2.size[0]-10, panel_height-im2.size[1]), im2)

            drawn.line([(0, 0), (0, panel_height-1), (panel_width-1, panel_height-1), (panel_width-1, 0), (0, 0)], (0, 0, 0, 0xff))
            del drawn
            img.paste(panel_img, (0, panel_height * i))

        return img
