# -*- coding: utf-8 -*-
"""spine38 姿态计算验证：对照 JS 运行时"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spine38.loader import SkeletonBinary
from spine38.atlas import TextureAtlas, AtlasAttachmentLoaderImpl
from spine38.skeleton import Skeleton


def load_model(base_path):
    with open(base_path + ".atlas", encoding="utf-8") as f:
        atlas_text = f.read()
    atlas = TextureAtlas(atlas_text, None)
    loader = AtlasAttachmentLoaderImpl(atlas)
    with open(base_path + ".skel", "rb") as f:
        data = f.read()
    sd = SkeletonBinary(loader).read_skeleton_data(data)
    return Skeleton(sd), atlas


BASE = r"D:\模型\spine\char_1015_aglna2"
for name, path in [
    ("build", os.path.join(BASE, "original_build", "build_char_1015_aglna2")),
    ("back", os.path.join(BASE, "defaultskin", "back", "char_1015_aglna2")),
    ("front", os.path.join(BASE, "defaultskin", "front", "char_1015_aglna2")),
]:
    skeleton, atlas = load_model(path)
    skeleton.set_to_setup_pose()
    skeleton.update_world_transform()
    off_x, off_y, w, h = skeleton.get_bounds()
    print(f"{name}: 包围盒 offset=({off_x:.1f},{off_y:.1f}) size=({w:.1f}x{h:.1f}) "
          f"图集页={[(p.width, p.height) for p in atlas.pages]} 区域数={len(atlas.regions)}")
