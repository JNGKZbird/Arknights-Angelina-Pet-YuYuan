# -*- coding: utf-8 -*-
"""验证官方 S-H 裁剪与掩码方案（even-odd / 三角化覆盖）的差异。

对 Sit/Sleep 眼睛裁剪段内的三角形做官方 Sutherland-Hodgman 裁剪，
对比三种方案下"眼睛内容可见区域"的面积与形状。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
from spine38.loader import SkeletonBinary, ClippingAttachment
from spine38.atlas import TextureAtlas, AtlasAttachmentLoaderImpl
from spine38.skeleton import Skeleton, compute_mesh_vertices
from spine38.animation import apply_animation
from spine38.renderer import _polygon_mask
from spine38.clipping import clip_attachment_polys, clip_triangle_to_polys

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "pets", "予愿安洁莉娜", "spine", "build", "build_char_1015_aglna2")


def load_model(base_path):
    with open(base_path + ".atlas", encoding="utf-8") as f:
        atlas_text = f.read()
    tex_img = np.asarray(Image.open(base_path + ".png").convert("RGBA"))
    atlas = TextureAtlas(atlas_text, lambda path: tex_img)
    with open(base_path + ".skel", "rb") as f:
        data = f.read()
    sd = SkeletonBinary(AtlasAttachmentLoaderImpl(atlas)).read_skeleton_data(data)
    return Skeleton(sd), sd


def poly_area_pts(pts):
    s = 0.0
    for i in range(0, len(pts), 2):
        x1, y1 = pts[i], pts[i + 1]
        x2, y2 = pts[(i + 2) % len(pts)], pts[(i + 3) % len(pts)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def main():
    anim_name = sys.argv[1] if len(sys.argv) > 1 else "Sit"
    frac = float(sys.argv[2]) if len(sys.argv) > 2 else 0.5
    skeleton, sd = load_model(BASE)
    anim = sd.find_animation(anim_name)
    t = anim.duration * frac
    skeleton.set_to_setup_pose()
    apply_animation(anim, skeleton, t, True, 1.0)
    skeleton.update_world_transform()

    from spine38.loader import MeshAttachment

    # 单遍遍历：段状态机（end_slot 本身也裁剪，其附件处理完才结束）
    current_key = None
    clip_end = -1
    clip_polys = None
    for slot in skeleton.draw_order:
        att = slot.attachment
        if att is None:
            if clip_end >= 0 and slot.data.index == clip_end:
                current_key = None
                clip_end = -1
                clip_polys = None
            continue
        if isinstance(att, ClippingAttachment):
            if current_key is None:
                verts = compute_mesh_vertices(slot, att, 0,
                                              att.world_vertices_length // 2)
                clip_polys = clip_attachment_polys(verts)
                current_key = slot.data.name
                clip_end = att.end_slot.index if att.end_slot is not None else len(skeleton.slots)
            continue
        if current_key is None:
            continue
        if isinstance(att, MeshAttachment) and "Eye" in current_key:
            verts = compute_mesh_vertices(slot, att, 0, att.world_vertices_length // 2)
            tri_area_total = 0.0
            sh_area_total = 0.0
            tri_visible = 0
            tri_clipped = 0
            for tr in range(0, len(att.triangles), 3):
                i0, i1, i2 = att.triangles[tr:tr + 3]
                tri = [(verts[i0 * 2], verts[i0 * 2 + 1]),
                       (verts[i1 * 2], verts[i1 * 2 + 1]),
                       (verts[i2 * 2], verts[i2 * 2 + 1])]
                uv = [(att.uvs[i0 * 2], att.uvs[i0 * 2 + 1]),
                      (att.uvs[i1 * 2], att.uvs[i1 * 2 + 1]),
                      (att.uvs[i2 * 2], att.uvs[i2 * 2 + 1])]
                ax, ay = tri[0]
                bx, by = tri[1]
                cx, cy = tri[2]
                area = abs((bx - ax) * (cy - ay) - (by - ay) * (cx - ax)) / 2.0
                tri_area_total += area
                results = clip_triangle_to_polys(tri, uv, clip_polys)
                if results:
                    tri_visible += 1
                    for pts, _ in results:
                        sh_area_total += poly_area_pts(pts)
                else:
                    tri_clipped += 1
            print(f"{anim_name} t={t:.3f} 段={current_key} 附件={att.name}")
            print(f"  三角形总数={len(att.triangles)//3} 原面积={tri_area_total:.1f} "
                  f"S-H后可见面积={sh_area_total:.1f} "
                  f"比例={sh_area_total/max(tri_area_total,1e-6)*100:.1f}% "
                  f"有交集三角形={tri_visible} 全裁掉={tri_clipped}")
        if clip_end >= 0 and slot.data.index == clip_end:
            current_key = None
            clip_end = -1
            clip_polys = None


if __name__ == "__main__":
    main()
