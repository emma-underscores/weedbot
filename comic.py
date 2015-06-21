import pillow
import io
import os
import os.path

def make_comic(msgs):
    panels = []
    panel = []
    characters = set()
    for msg in msgs:
        # if we already have a full panel (two speakers, or consecutive msg speaker), create a new panel
        if len(panel) >= 2 or (len(panel) == 1 and panel[0][5] == msg[5]):
            panels.append(panel)
            panel = []
        panel.append(msg)
    panels.append(panel)

    comic_img = io.BytesIO()

    # generate image

    # save image to jpg in memory

    # upload to imgur

def gen_img(panels, n_characters):
    panelheight = 300
    panelwidth = 450

    filenames = os.listdir('chars/')
    filepaths = map(lambda x: os.path.join("chars", x), filenames[:len(n_characters)])