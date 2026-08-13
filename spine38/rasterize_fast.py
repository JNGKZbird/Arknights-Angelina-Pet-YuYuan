"""numba 加速光栅化 — 桌宠实时渲染路径.

renderer.py 是纯 numpy 参考实现（测试/离线烘焙用）；
本模块的 numba 内核语义与其一致，速度约 30 倍。
"""
import math
import numpy as np
import numba
from .renderer import _polygon_mask
from .skeleton import compute_region_vertices, compute_mesh_vertices
from .loader import RegionAttachment, MeshAttachment, ClippingAttachment


@numba.njit(cache=True)
def rasterize_batch(out, texture, tris, tri_uvs, colors, blend_ids, bilinear):
    """批量光栅化三角形到 out（RGBA uint8，H×W×4）。

    tris: float64 (N,3,2) 屏幕坐标（y 向下）
    tri_uvs: float64 (N,3,2) 纹理 UV（0~1）
    colors: float64 (N,4) 乘色
    blend_ids: int32 (N,) 0=normal 1=additive 2=multiply 3=screen
    bilinear: 双线性过滤（quality 模式，预乘修正避免边缘黑边）
    """
    h, w = out.shape[:2]
    th, tw = texture.shape[:2]
    for i in range(tris.shape[0]):
        t0x = tris[i, 0, 0]
        t0y = tris[i, 0, 1]
        t1x = tris[i, 1, 0]
        t1y = tris[i, 1, 1]
        t2x = tris[i, 2, 0]
        t2y = tris[i, 2, 1]
        x0 = int(np.floor(min(t0x, min(t1x, t2x))))
        x1 = int(np.ceil(max(t0x, max(t1x, t2x))))
        y0 = int(np.floor(min(t0y, min(t1y, t2y))))
        y1 = int(np.ceil(max(t0y, max(t1y, t2y))))
        if x0 < 0:
            x0 = 0
        if y0 < 0:
            y0 = 0
        if x1 > w:
            x1 = w
        if y1 > h:
            y1 = h
        if x1 <= x0 or y1 <= y0:
            continue
        denom = (t1y - t2y) * (t0x - t2x) + (t2x - t1x) * (t0y - t2y)
        if abs(denom) < 1e-8:
            continue
        inv = 1.0 / denom
        cr = colors[i, 0]
        cg = colors[i, 1]
        cb = colors[i, 2]
        ca = colors[i, 3]
        blend = blend_ids[i]
        for y in range(y0, y1):
            py = y + 0.5
            row_out = out[y]
            for x in range(x0, x1):
                px = x + 0.5
                l1 = ((t1y - t2y) * (px - t2x) + (t2x - t1x) * (py - t2y)) * inv
                l2 = ((t2y - t0y) * (px - t2x) + (t0x - t2x) * (py - t2y)) * inv
                l3 = 1.0 - l1 - l2
                if l1 < 0.0 or l2 < 0.0 or l3 < 0.0:
                    continue
                u = tri_uvs[i, 0, 0] * l1 + tri_uvs[i, 1, 0] * l2 + tri_uvs[i, 2, 0] * l3
                v = tri_uvs[i, 0, 1] * l1 + tri_uvs[i, 1, 1] * l2 + tri_uvs[i, 2, 1] * l3
                if bilinear:
                    uf = u * tw - 0.5
                    vf = v * th - 0.5
                    ui = int(np.floor(uf))
                    vi = int(np.floor(vf))
                    fu = uf - ui
                    fv = vf - vi
                    ui1 = ui + 1
                    vi1 = vi + 1
                    if ui < 0:
                        ui = 0
                    if vi < 0:
                        vi = 0
                    if ui1 >= tw:
                        ui1 = tw - 1
                    if vi1 >= th:
                        vi1 = th - 1
                    if ui >= tw:
                        ui = tw - 1
                    if vi >= th:
                        vi = th - 1
                    t00 = texture[vi, ui]
                    t10 = texture[vi, ui1]
                    t01 = texture[vi1, ui]
                    t11 = texture[vi1, ui1]
                    w00 = (1.0 - fu) * (1.0 - fv)
                    w10 = fu * (1.0 - fv)
                    w01 = (1.0 - fu) * fv
                    w11 = fu * fv
                    # 预乘修正插值，避免透明边缘黑边
                    pr = t00[0] * t00[3] * w00 + t10[0] * t10[3] * w10 + t01[0] * t01[3] * w01 + t11[0] * t11[3] * w11
                    pg = t00[1] * t00[3] * w00 + t10[1] * t10[3] * w10 + t01[1] * t01[3] * w01 + t11[1] * t11[3] * w11
                    pb = t00[2] * t00[3] * w00 + t10[2] * t10[3] * w10 + t01[2] * t01[3] * w01 + t11[2] * t11[3] * w11
                    ta = t00[3] * w00 + t10[3] * w10 + t01[3] * w01 + t11[3] * w11
                    if ta > 0.0:
                        tr = pr / ta
                        tg = pg / ta
                        tb = pb / ta
                    else:
                        tr = 0.0
                        tg = 0.0
                        tb = 0.0
                    sr = tr * cr
                    sg = tg * cg
                    sb = tb * cb
                    sa = ta * ca / 255.0
                else:
                    ti = int(v * th)
                    tj = int(u * tw)
                    if ti < 0:
                        ti = 0
                    if tj < 0:
                        tj = 0
                    if ti >= th:
                        ti = th - 1
                    if tj >= tw:
                        tj = tw - 1
                    texel = texture[ti, tj]
                    sr = texel[0] * cr
                    sg = texel[1] * cg
                    sb = texel[2] * cb
                    sa = texel[3] * ca / 255.0
                if blend == 0:
                    da = row_out[x, 3] / 255.0
                    oa = sa + da * (1.0 - sa)
                    if oa > 0.0:
                        row_out[x, 0] = (sr * sa + row_out[x, 0] * da * (1.0 - sa)) / oa
                        row_out[x, 1] = (sg * sa + row_out[x, 1] * da * (1.0 - sa)) / oa
                        row_out[x, 2] = (sb * sa + row_out[x, 2] * da * (1.0 - sa)) / oa
                        row_out[x, 3] = oa * 255.0
                elif blend == 1:
                    # additive：预乘语义叠加（alpha 也相加，透明背景上特效可见）
                    da = row_out[x, 3] / 255.0
                    na = sa + da
                    if na > 1.0:
                        na = 1.0
                    if na > 0.0:
                        v0 = sr * sa + row_out[x, 0] * da
                        v1 = sg * sa + row_out[x, 1] * da
                        v2 = sb * sa + row_out[x, 2] * da
                        if v0 > 255.0:
                            v0 = 255.0
                        if v1 > 255.0:
                            v1 = 255.0
                        if v2 > 255.0:
                            v2 = 255.0
                        row_out[x, 0] = v0 / na
                        row_out[x, 1] = v1 / na
                        row_out[x, 2] = v2 / na
                        row_out[x, 3] = na * 255.0
                elif blend == 2:
                    f = 1.0 - sa + sa * sr / 255.0
                    row_out[x, 0] = row_out[x, 0] * f
                    f = 1.0 - sa + sa * sg / 255.0
                    row_out[x, 1] = row_out[x, 1] * f
                    f = 1.0 - sa + sa * sb / 255.0
                    row_out[x, 2] = row_out[x, 2] * f
                else:
                    f = 1.0 - sa + sa * (1.0 - sr / 255.0)
                    row_out[x, 0] = 255.0 - (255.0 - row_out[x, 0]) * f
                    f = 1.0 - sa + sa * (1.0 - sg / 255.0)
                    row_out[x, 1] = 255.0 - (255.0 - row_out[x, 1]) * f
                    f = 1.0 - sa + sa * (1.0 - sb / 255.0)
                    row_out[x, 2] = 255.0 - (255.0 - row_out[x, 2]) * f


@numba.njit(cache=True)
def composite_over(dst, src, mask):
    """src 按 mask 门控叠加到 dst（直通 alpha source-over）。mask uint8：>0 生效。"""
    h, w = dst.shape[:2]
    for y in range(h):
        for x in range(w):
            if mask[y, x] > 0:
                sa = src[y, x, 3] / 255.0
                da = dst[y, x, 3] / 255.0
                oa = sa + da * (1.0 - sa)
                if oa > 0.0:
                    dst[y, x, 0] = (src[y, x, 0] * sa + dst[y, x, 0] * da * (1.0 - sa)) / oa
                    dst[y, x, 1] = (src[y, x, 1] * sa + dst[y, x, 1] * da * (1.0 - sa)) / oa
                    dst[y, x, 2] = (src[y, x, 2] * sa + dst[y, x, 2] * da * (1.0 - sa)) / oa
                    dst[y, x, 3] = oa * 255.0


def render_skeleton_fast(skeleton, atlas, out_rgba, transform=None, bilinear=False):
    """实时渲染骨架到 out_rgba（RGBA uint8，H×W×4）。语义与 renderer.render_skeleton 一致。

    transform: (scale, tx, ty) — 骨架坐标 → 像素坐标。
    性能要点：整帧三角形合并成一次内核调用（numba 调度开销约 0.5ms/次），
    仅裁剪段单独成批以保持绘制顺序。
    """
    if transform is None:
        scale, tx, ty = 1.0, 0.0, 0.0
    else:
        scale, tx, ty = transform
    h, w = out_rgba.shape[:2]
    out_rgba.fill(0)
    # 每帧复用的缓冲（避免重复分配）
    if not hasattr(render_skeleton_fast, "_bufs") or render_skeleton_fast._bufs[0].shape[0] != h:
        render_skeleton_fast._bufs = (
            np.zeros((h, w, 4), dtype=np.uint8),   # 裁剪临时缓冲
        )
    tmp_buf = render_skeleton_fast._bufs[0]

    def _emit(slot, attachment, tris, tri_uvs):
        region = attachment.region
        if region is None or region.page is None or region.page.texture is None:
            return None, 0
        n_tris = 0
        if isinstance(attachment, RegionAttachment):
            verts = compute_region_vertices(slot, attachment)
            r = region
            # 角点顺序：BL, TL, TR, BR（照 spine-ts setRegion 的 uvs 赋值）
            if r.degrees == 90:
                corners = [(r.u2, r.v2), (r.u, r.v2), (r.u, r.v), (r.u2, r.v)]
            else:
                corners = [(r.u, r.v2), (r.u, r.v), (r.u2, r.v), (r.u2, r.v2)]
            uvs = [crd for corner in corners for crd in corner]
            tris.append([(verts[0] * scale + tx, h - (verts[1] * scale + ty)),
                         (verts[2] * scale + tx, h - (verts[3] * scale + ty)),
                         (verts[4] * scale + tx, h - (verts[5] * scale + ty))])
            tris.append([(verts[4] * scale + tx, h - (verts[5] * scale + ty)),
                         (verts[6] * scale + tx, h - (verts[7] * scale + ty)),
                         (verts[2] * scale + tx, h - (verts[3] * scale + ty))])
            tri_uvs.append([(uvs[0], uvs[1]), (uvs[2], uvs[3]), (uvs[4], uvs[5])])
            tri_uvs.append([(uvs[4], uvs[5]), (uvs[6], uvs[7]), (uvs[2], uvs[3])])
            n_tris = 2
        elif isinstance(attachment, MeshAttachment):
            verts = compute_mesh_vertices(slot, attachment, 0,
                                          attachment.world_vertices_length // 2)
            tri_count = len(attachment.triangles) // 3
            for t in range(tri_count):
                i0, i1, i2 = attachment.triangles[t * 3:t * 3 + 3]
                tris.append([(verts[i0 * 2] * scale + tx, h - (verts[i0 * 2 + 1] * scale + ty)),
                             (verts[i1 * 2] * scale + tx, h - (verts[i1 * 2 + 1] * scale + ty)),
                             (verts[i2 * 2] * scale + tx, h - (verts[i2 * 2 + 1] * scale + ty))])
                tri_uvs.append([(attachment.uvs[i0 * 2], attachment.uvs[i0 * 2 + 1]),
                                (attachment.uvs[i1 * 2], attachment.uvs[i1 * 2 + 1]),
                                (attachment.uvs[i2 * 2], attachment.uvs[i2 * 2 + 1])])
            n_tris = tri_count
        else:
            return None, 0
        return region.page.texture, n_tris

    def _flush(batch, tex):
        if not batch[0]:
            return
        bt = np.asarray(batch[0], dtype=np.float64)
        bu = np.asarray(batch[1], dtype=np.float64)
        bc = np.asarray(batch[2], dtype=np.float64)
        bb = np.asarray(batch[3], dtype=np.int32)
        rasterize_batch(out_rgba, tex, bt, bu, bc, bb, bilinear)
        batch[0].clear()
        batch[1].clear()
        batch[2].clear()
        batch[3].clear()

    def _flush_clipped(batch, tex, mask):
        if not batch[0]:
            return
        bt = np.asarray(batch[0], dtype=np.float64)
        bu = np.asarray(batch[1], dtype=np.float64)
        bc = np.asarray(batch[2], dtype=np.float64)
        bb = np.asarray(batch[3], dtype=np.int32)
        tmp_buf.fill(0)
        rasterize_batch(tmp_buf, tex, bt, bu, bc, bb, bilinear)
        composite_over(out_rgba, tmp_buf, mask)
        batch[0].clear()
        batch[1].clear()
        batch[2].clear()
        batch[3].clear()

    normal = ([], [], [], [])   # tris, uvs, colors, blends（同纹理段）
    clipped = ([], [], [], [])
    normal_tex = None
    clip_tex = None
    clip_mask = None
    clip_end_index = -1

    for slot in skeleton.draw_order:
        attachment = slot.attachment
        if attachment is None:
            # JS 渲染器语义：空附件也检查裁剪结束（end slot 可能恰好无附件，
            # 否则掩码永不结束、其后所有槽位被误裁）
            if clip_mask is not None and slot.data.index == clip_end_index:
                clip_mask = None
                clip_end_index = -1
            continue
        if isinstance(attachment, ClippingAttachment):
            if clip_mask is None:
                verts = compute_mesh_vertices(slot, attachment, 0,
                                              attachment.world_vertices_length // 2)
                pts = [(verts[i] * scale + tx, h - (verts[i + 1] * scale + ty))
                       for i in range(0, len(verts), 2)]
                clip_mask = _polygon_mask(pts, h, w)
                clip_end_index = (attachment.end_slot.index
                                  if attachment.end_slot is not None
                                  else len(skeleton.slots))
            continue
        tris = []
        tri_uvs = []
        tex, n_tris = _emit(slot, attachment, tris, tri_uvs)
        if n_tris == 0:
            continue
        color = (slot.color.r, slot.color.g, slot.color.b, slot.color.a)
        if clip_mask is not None:
            # 进入裁剪段：先冲刷普通批次（保持绘制顺序），再累积裁剪批次
            if normal_tex is not None:
                _flush(normal, normal_tex)
                normal_tex = None
            if clip_tex is None:
                clip_tex = tex
            clipped[0].extend(tris)
            clipped[1].extend(tri_uvs)
            for _ in range(n_tris):
                clipped[2].append(color)
                clipped[3].append(slot.data.blend_mode)
            if slot.data.index == clip_end_index:
                _flush_clipped(clipped, clip_tex, clip_mask)
                clip_tex = None
                clip_mask = None
                clip_end_index = -1
        else:
            if normal_tex is None:
                normal_tex = tex
            normal[0].extend(tris)
            normal[1].extend(tri_uvs)
            for _ in range(n_tris):
                normal[2].append(color)
                normal[3].append(slot.data.blend_mode)
    if normal_tex is not None:
        _flush(normal, normal_tex)
    if clip_tex is not None and clip_mask is not None:
        _flush_clipped(clipped, clip_tex, clip_mask)
    return out_rgba
