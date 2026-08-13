# -*- coding: utf-8 -*-
"""spine38 动画应用验证：Relax 动画多时间点包围盒，与 JS 运行时对照"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spine38.loader import SkeletonBinary
from spine38.atlas import TextureAtlas, AtlasAttachmentLoaderImpl
from spine38.skeleton import Skeleton
from spine38.animation import AnimationStateImpl


def load_model(base_path):
    with open(base_path + ".atlas", encoding="utf-8") as f:
        atlas_text = f.read()
    loader = AtlasAttachmentLoaderImpl(TextureAtlas(atlas_text, None))
    with open(base_path + ".skel", "rb") as f:
        data = f.read()
    sd = SkeletonBinary(loader).read_skeleton_data(data)
    return Skeleton(sd), sd


BASE = r"D:\模型\spine\char_1015_aglna2\original_build\build_char_1015_aglna2"
skeleton, sd = load_model(BASE)
state = AnimationStateImpl(sd)
state.set_animation(0, "Relax", True)

print("Relax 时长:", state.track.animation.duration)
for t in [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 2.566, 2.7, 2.8, 3.0, 3.5, 3.9]:
    skeleton.set_to_setup_pose()
    from spine38.animation import apply_animation
    apply_animation(state.track.animation, skeleton, t, True, 1.0)
    skeleton.update_world_transform()
    off_x, off_y, w, h = skeleton.get_bounds()
    print(f"t={t:5.2f} 包围盒=({off_x:8.2f},{off_y:8.2f}) {w:7.2f}x{h:7.2f}")
