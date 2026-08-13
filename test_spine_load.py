# -*- coding: utf-8 -*-
"""spine38 加载器验证：对照 Node 版已知数据"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spine38.loader import (SkeletonBinary, AttachmentLoader, RegionAttachment,
                            MeshAttachment, BoundingBoxAttachment, PathAttachment,
                            PointAttachment, ClippingAttachment)


class StubLoader(AttachmentLoader):
    def new_region_attachment(self, skin, name, path):
        return RegionAttachment(name)
    def new_mesh_attachment(self, skin, name, path):
        return MeshAttachment(name)
    def new_bounding_box_attachment(self, skin, name):
        return BoundingBoxAttachment(name)
    def new_path_attachment(self, skin, name):
        return PathAttachment(name)
    def new_point_attachment(self, skin, name):
        return PointAttachment(name)
    def new_clipping_attachment(self, skin, name):
        return ClippingAttachment(name)


BASE = r"D:\模型\spine\char_1015_aglna2"
MODELS = [
    ("build", os.path.join(BASE, "original_build", "build_char_1015_aglna2.skel")),
    ("back", os.path.join(BASE, "defaultskin", "back", "char_1015_aglna2.skel")),
    ("front", os.path.join(BASE, "defaultskin", "front", "char_1015_aglna2.skel")),
]

for name, path in MODELS:
    with open(path, "rb") as f:
        data = f.read()
    sd = SkeletonBinary(StubLoader()).read_skeleton_data(data)
    print(f"{name}: 版本={sd.version} 骨骼={len(sd.bones)} 插槽={len(sd.slots)} "
          f"动画={len(sd.animations)} 皮肤={len(sd.skins)}")
    print(f"  动画列表: {[a.name for a in sd.animations]}")
    print(f"  时长: {[f'{a.name}={a.duration:.2f}s' for a in sd.animations[:6]]}")
    # 裁剪附件统计
    clips = 0
    for skin in sd.skins:
        for (si, n), att in skin.attachments.items():
            if isinstance(att, ClippingAttachment):
                clips += 1
    print(f"  裁剪附件: {clips}")
    print()
