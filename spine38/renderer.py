"""Spine 3.8 渲染器 — numpy 纹理三角光栅化 + 裁剪 + 混合模式."""
import numpy as np
from .loader import (RegionAttachment, MeshAttachment, ClippingAttachment)
from .skeleton import (compute_region_vertices, compute_mesh_vertices)
from .clipping import clip_attachment_polys, clip_triangle_to_polys


def _rasterize_triangles(out_rgba, texture_rgba, tri_xy, tri_uv, color, blend):
    """把一组三角形光栅化到 out_rgba（numpy 向量化）。

    tri_xy: (N,3,2) 屏幕坐标；tri_uv: (N,3,2) 纹理 UV（0~1）。
    color: (r,g,b,a) 乘色。
    """
    h, w = out_rgba.shape[:2]
    for i in range(len(tri_xy)):
        p = tri_xy[i]
        uv = tri_uv[i]
        x0 = int(max(0, np.floor(np.min(p[:, 0]))))
        x1 = int(min(w, np.ceil(np.max(p[:, 0]))))
        y0 = int(max(0, np.floor(np.min(p[:, 1]))))
        y1 = int(min(h, np.ceil(np.max(p[:, 1]))))
        if x1 <= x0 or y1 <= y0:
            continue
        xs = np.arange(x0, x1, dtype=np.float64)
        ys = np.arange(y0, y1, dtype=np.float64)
        px, py = np.meshgrid(xs + 0.5, ys + 0.5)
        # 重心坐标
        x1v, y1v = p[0]
        x2v, y2v = p[1]
        x3v, y3v = p[2]
        denom = (y2v - y3v) * (x1v - x3v) + (x3v - x2v) * (y1v - y3v)
        if abs(denom) < 1e-8:
            continue
        l1 = ((y2v - y3v) * (px - x3v) + (x3v - x2v) * (py - y3v)) / denom
        l2 = ((y3v - y1v) * (px - x3v) + (x1v - x3v) * (py - y3v)) / denom
        l3 = 1.0 - l1 - l2
        inside = (l1 >= 0) & (l2 >= 0) & (l3 >= 0)
        if not inside.any():
            continue
        # 纹理坐标插值
        u = uv[0][0] * l1 + uv[1][0] * l2 + uv[2][0] * l3
        v = uv[0][1] * l1 + uv[1][1] * l2 + uv[2][1] * l3
        th, tw = texture_rgba.shape[:2]
        u = np.clip(u, 0.0, 1.0)
        v = np.clip(v, 0.0, 1.0)
        ti = np.clip((v * th).astype(np.int32), 0, th - 1)
        tj = np.clip((u * tw).astype(np.int32), 0, tw - 1)
        tex = texture_rgba[ti, tj, :4].astype(np.float32)
        # bbox 内非三角形像素清零（避免边缘伪影）
        tex[~inside] = 0
        # 乘色
        tex[:, :, 0] *= color[0]
        tex[:, :, 1] *= color[1]
        tex[:, :, 2] *= color[2]
        tex[:, :, 3] *= color[3]
        # 混合
        dst = out_rgba[y0:y1, x0:x1]
        sa = tex[:, :, 3:4] / 255.0
        da = dst[:, :, 3:4] / 255.0
        if blend == "normal":
            out_a = sa + da * (1 - sa)
            out_rgb = (tex[:, :, :3] * sa + dst[:, :, :3] * da * (1 - sa)) / np.maximum(out_a, 1e-6)
            out_rgb = np.where(out_a > 0, out_rgb, 0)
            dst[:, :, :3] = out_rgb
            dst[:, :, 3:4] = out_a * 255.0
        elif blend == "additive":
            # 预乘语义叠加：alpha 也相加，透明背景上特效可见
            new_a = np.minimum(1.0, sa + da)
            out_rgb = np.minimum(255, tex[:, :, :3] * sa + dst[:, :, :3] * da)
            dst[:, :, :3] = np.where(new_a > 0, out_rgb / np.maximum(new_a, 1e-6), 0)
            dst[:, :, 3:4] = new_a * 255.0
        elif blend == "multiply":
            dst[:, :, :3] = dst[:, :, :3] * (1 - sa + sa * tex[:, :, :3] / 255.0)
        elif blend == "screen":
            dst[:, :, :3] = 255 - (255 - dst[:, :, :3]) * (1 - sa + sa * (1 - tex[:, :, :3] / 255.0))



def render_skeleton(skeleton, atlas, out_rgba, transform=None):
    """渲染骨架到 out_rgba（RGBA uint8，H×W×4）。

    transform: (scale, tx, ty) — 骨架坐标 → 像素坐标。
    裁剪语义：官方 spine-ts 3.8 SkeletonClipping 逐三角形 S-H 裁剪（见 clipping.py）。
    """
    if transform is None:
        scale, tx, ty = 1.0, 0.0, 0.0
    else:
        scale, tx, ty = transform
    h, w = out_rgba.shape[:2]
    out_rgba.fill(0)
    clip_polys = None
    clip_end_index = -1
    for slot in skeleton.draw_order:
        attachment = slot.attachment
        if attachment is None:
            # JS 渲染器语义：空附件也检查裁剪结束
            if clip_polys is not None and slot.data.index == clip_end_index:
                clip_polys = None
                clip_end_index = -1
            continue
        if isinstance(attachment, ClippingAttachment):
            # JS：已在裁剪中则忽略新裁剪；结束条件为遇到 end_slot（按 data.index）
            if clip_polys is None:
                verts = compute_mesh_vertices(slot, attachment, 0,
                                              attachment.world_vertices_length // 2)
                clip_polys = clip_attachment_polys(verts)
                clip_end_index = (attachment.end_slot.index
                                  if attachment.end_slot is not None
                                  else len(skeleton.slots))
            continue
        if isinstance(attachment, RegionAttachment):
            verts = compute_region_vertices(slot, attachment)
            r = attachment.region
            # 角点顺序：BL, TL, TR, BR（照 spine-ts setRegion 的 uvs 赋值）
            if r.degrees == 90:
                corners = [(r.u2, r.v2), (r.u, r.v2), (r.u, r.v), (r.u2, r.v)]
            else:
                corners = [(r.u, r.v2), (r.u, r.v), (r.u2, r.v), (r.u2, r.v2)]
            uvs = [c for corner in corners for c in corner]
            tris_world = [[(verts[0], verts[1]), (verts[2], verts[3]), (verts[4], verts[5])],
                          [(verts[4], verts[5]), (verts[6], verts[7]), (verts[2], verts[3])]]
            tri_uv = [[(uvs[0], uvs[1]), (uvs[2], uvs[3]), (uvs[4], uvs[5])],
                      [(uvs[4], uvs[5]), (uvs[6], uvs[7]), (uvs[2], uvs[3])]]
        elif isinstance(attachment, MeshAttachment):
            verts = compute_mesh_vertices(slot, attachment, 0,
                                          attachment.world_vertices_length // 2)
            tris_world = []
            tri_uv = []
            for t in range(0, len(attachment.triangles), 3):
                i0, i1, i2 = attachment.triangles[t:t + 3]
                tris_world.append([(verts[i0 * 2], verts[i0 * 2 + 1]),
                                   (verts[i1 * 2], verts[i1 * 2 + 1]),
                                   (verts[i2 * 2], verts[i2 * 2 + 1])])
                tri_uv.append([(attachment.uvs[i0 * 2], attachment.uvs[i0 * 2 + 1]),
                               (attachment.uvs[i1 * 2], attachment.uvs[i1 * 2 + 1]),
                               (attachment.uvs[i2 * 2], attachment.uvs[i2 * 2 + 1])])
        else:
            continue
        # 纹理
        region = attachment.region
        if region is None or region.page is None or region.page.texture is None:
            continue
        tex = region.page.texture  # RGBA uint8
        c = slot.color
        color = (c.r, c.g, c.b, c.a)
        blend = "normal"
        if slot.data.blend_mode == 1:
            blend = "additive"
        elif slot.data.blend_mode == 2:
            blend = "multiply"
        elif slot.data.blend_mode == 3:
            blend = "screen"
        # 裁剪段：官方 S-H 逐三角形裁剪（end_slot 本身也裁剪，渲染后结束裁剪）
        if clip_polys is not None:
            for k in range(len(tris_world)):
                results = clip_triangle_to_polys(tris_world[k], tri_uv[k], clip_polys)
                for pts, uvs in results:
                    screen = [(pts[i] * scale + tx, h - (pts[i + 1] * scale + ty))
                              for i in range(0, len(pts), 2)]
                    tris_out = []
                    tri_uv_out = []
                    for i in range(1, len(screen) - 1):
                        tris_out.append([screen[0], screen[i], screen[i + 1]])
                        tri_uv_out.append([(uvs[0], uvs[1]),
                                           (uvs[i * 2], uvs[i * 2 + 1]),
                                           (uvs[(i + 1) * 2], uvs[(i + 1) * 2 + 1])])
                    if tris_out:
                        _rasterize_triangles(out_rgba, tex,
                                             np.array(tris_out), np.array(tri_uv_out),
                                             color, blend)
            if slot.data.index == clip_end_index:
                clip_polys = None
                clip_end_index = -1
        else:
            tris = [[(t[0][0] * scale + tx, h - (t[0][1] * scale + ty)),
                     (t[1][0] * scale + tx, h - (t[1][1] * scale + ty)),
                     (t[2][0] * scale + tx, h - (t[2][1] * scale + ty))]
                    for t in tris_world]
            _rasterize_triangles(out_rgba, tex,
                                 np.array(tris), np.array(tri_uv), color, blend)
    return out_rgba


def _polygon_mask(pts, h, w):
    """多边形填充掩码（偶数奇数规则）——仅供测试对比，渲染路径已改用官方三角化语义。"""
    mask = np.zeros((h, w), dtype=np.uint8)
    if len(pts) < 3:
        return mask
    xs = np.array([p[0] for p in pts])
    ys = np.array([p[1] for p in pts])
    x0 = int(max(0, np.floor(np.min(xs))))
    x1 = int(min(w, np.ceil(np.max(xs))))
    y0 = int(max(0, np.floor(np.min(ys))))
    y1 = int(min(h, np.ceil(np.max(ys))))
    if x1 <= x0 or y1 <= y0:
        return mask
    px, py = np.meshgrid(np.arange(x0, x1, dtype=np.float64) + 0.5,
                         np.arange(y0, y1, dtype=np.float64) + 0.5)
    inside = np.zeros_like(px, dtype=bool)
    n = len(pts)
    for i in range(n):
        x1v, y1v = pts[i]
        x2v, y2v = pts[(i + 1) % n]
        cond = ((y1v > py) != (y2v > py))
        xint = (x2v - x1v) * (py - y1v) / ((y2v - y1v) if y2v != y1v else 1e-9) + x1v
        inside ^= cond & (px < xint)
    mask[y0:y1, x0:x1] = inside.astype(np.uint8) * 255
    return mask




def _composite(dst, src):
    """src 叠加到 dst（src 已含 alpha）。"""
    sa = src[:, :, 3:4].astype(np.float32) / 255.0
    da = dst[:, :, 3:4].astype(np.float32) / 255.0
    out_a = sa + da * (1 - sa)
    out_rgb = np.where(out_a > 0,
                       (src[:, :, :3] * sa + dst[:, :, :3] * da * (1 - sa)) / np.maximum(out_a, 1e-6),
                       0)
    dst[:, :, :3] = out_rgb
    dst[:, :, 3:4] = out_a * 255.0
