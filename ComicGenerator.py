import os
import os.path
import random

from PIL import Image, ImageFont, ImageDraw

panel_height = 300
panel_width = 450

class ComicGenerator:
    def __init__(self):
        self.char_paths = list(map(lambda p: os.path.join("chars", p), os.listdir("chars/")))
        self.bg_paths = list(map(lambda p: os.path.join("backgrounds", p), os.listdir("backgrounds/")))
        # TODO: put these in config file
        self.font_file = "fonts/ComicBD.ttf"
        self.font_size = 16

    def _gen_panel_text(self, msgs):
        panels = []
        panel = []
        for msg in msgs:
            # if we already have a full panel (two speakers, or consecutive msg speaker), create a new panel
            if len(panel) >= 2 or (len(panel) == 1 and panel[0][0] == msg["sender"]):
                panels.append(panel)
                panel = []
            panel.append((msg["sender"], msg["content"]))
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
        for i in range(len(msgs)-1, -1, -1):
            trimmed.append(msgs[i])
            characters.add(msgs[i]["sender"])
            if msgs[i]["time"] - msgs[i-1]["time"] > 120:
                print("time triggered")
                break
            if len(characters) > 3:
                print("characters triggered")
                break
            if len(trimmed) > 10:
                print("trimmed triggered")
                break
        trimmed.reverse()
        print(msgs)
        print(trimmed)
        # panels is now a list of nick, msg
        panels = self._gen_panel_text(trimmed)

        # characters = set(msg[4] for msg in msgs)
        char_map = {ch: path for (ch, path) in zip(characters, self.char_paths)}

        # DEBUG
        print(char_map)

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

            # DEBUG
            print(char_map[panel[0][0]])
            panel_img.paste(im1, (10, panel_height-im1.size[1]), im1)

            if len(panel) == 2:
                im2 = self._fit_img(Image.open(char_map[panel[1][0]]), 2*panel_width/5.0-10, max_ch_height)
                im2 = im2.transpose(Image.FLIP_LEFT_RIGHT)
                panel_img.paste(im2, (panel_width-im2.size[0]-10, panel_height-im2.size[1]), im2)

            drawn.line([(0, 0), (0, panel_height-1), (panel_width-1, panel_height-1), (panel_width-1, 0), (0, 0)], (0, 0, 0, 0xff))
            del drawn
            img.paste(panel_img, (0, panel_height * i))

        return img