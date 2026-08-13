# -*- coding: utf-8 -*-
"""spine38 渲染验证：渲染 Relax 到 PNG"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
from spine38.loader import SkeletonBinary
from spine38.atlas import TextureAtlas, AtlasAttachmentLoaderImpl
from spine38.skeleton import Skeleton
from spine38.animation import apply_animation
from spine38.renderer import render_skeleton


def load_model(base_path, png_path):
    with open(base_path + ".atlas", encoding="utf-8") as f:
        atlas_text = f.read()
    tex_img = np.asarray(Image.open(png_path).convert("RGBA"))
    # 纹理以页面名注册
    def loader(path):
        return tex_img
    atlas = TextureAtlas(atlas_text, loader)
    with open(base_path + ".skel", "rb") as f:
        data = f.read()
    sd = SkeletonBinary(AtlasAttachmentLoaderImpl(atlas)).read_skeleton_data(data)
    return Skeleton(sd), sd, atlas


BASE = r"D:\模型\spine\char_1015_aglna2\original_build\build_char_1015_aglna2"
skeleton, sd, atlas = load_model(BASE, BASE + ".png")
a = sd.find_animation("Relax")

OUT = 600
out = np.zeros((OUT, OUT, 4), dtype=np.uint8)
for t in [0.0, 1.0, 2.0]:
    skeleton.set_to_setup_pose()
    apply_animation(a, skeleton, t, True, 1.0)
    skeleton.update_world_transform()
    off_x, off_y, w, h = skeleton.get_bounds()
    scale = (OUT - 20) / max(w, h)
    tx = OUT / 2 - (off_x + w / 2) * scale
    ty = OUT / 2 - (off_y + h / 2) * scale
    img = np.zeros((OUT, OUT, 4), dtype=np.uint8)
    render_skeleton(skeleton, atlas, img, (scale, tx, ty))
    Image.fromarray(img, "RGBA").save(f"C:/Users/pc/AppData/Local/Temp/relax_{t:.1f}.png")
    print(f"t={t:.1f} 已渲染")
print("完成，检查临时目录的 PNG")
