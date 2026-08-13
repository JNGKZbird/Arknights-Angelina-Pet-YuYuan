# -*- coding: utf-8 -*-
"""spine38 全量动画验证：三模型 × 多动画 × 多时间点"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spine38.loader import SkeletonBinary
from spine38.atlas import TextureAtlas, AtlasAttachmentLoaderImpl
from spine38.skeleton import Skeleton
from spine38.animation import apply_animation


def load_model(base_path):
    with open(base_path + ".atlas", encoding="utf-8") as f:
        atlas_text = f.read()
    loader = AtlasAttachmentLoaderImpl(TextureAtlas(atlas_text, None))
    with open(base_path + ".skel", "rb") as f:
        data = f.read()
    sd = SkeletonBinary(loader).read_skeleton_data(data)
    return Skeleton(sd), sd


BASE = r"D:\模型\spine\char_1015_aglna2"
MODELS = [
    ("build", os.path.join(BASE, "original_build", "build_char_1015_aglna2")),
    ("back", os.path.join(BASE, "defaultskin", "back", "char_1015_aglna2")),
    ("front", os.path.join(BASE, "defaultskin", "front", "char_1015_aglna2")),
]

for name, path in MODELS:
    skeleton, sd = load_model(path)
    print(f"=== {name} ===")
    for an in sd.animations[:5]:
        times = [0.0, an.duration * 0.5]
        results = []
        for t in times:
            skeleton.set_to_setup_pose()
            apply_animation(an, skeleton, t, True, 1.0)
            skeleton.update_world_transform()
            off_x, off_y, w, h = skeleton.get_bounds()
            results.append(f"t={t:.1f}:({off_x:.0f},{off_y:.0f}){w:.0f}x{h:.0f}")
        print(f"  {an.name}: {results}")
