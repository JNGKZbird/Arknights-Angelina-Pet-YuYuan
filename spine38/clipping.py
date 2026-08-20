"""官方 spine-ts 3.8 SkeletonClipping 逐行移植。

官方裁剪语义：裁剪附件世界顶点 → makeClockwise → triangulate（ear-clipping）
→ decompose（合并为凸多边形）→ 对每个被裁剪三角形 × 每个凸多边形做
Sutherland-Hodgman 半平面序列裁剪。对自交多边形，S-H 结果 = 所有边半平面交
（凸区域），与"多边形内部覆盖"（even-odd / 三角化覆盖）完全不同。
"""
import numba
import numpy as np


def _make_clockwise(verts):
    """spine-ts 3.8 SkeletonClipping.makeClockwise 移植（原地修改，y 向上坐标）。"""
    n = len(verts)
    area = verts[n - 2] * verts[1] - verts[0] * verts[n - 1]
    for i in range(0, n - 3, 2):
        area += verts[i] * verts[i + 3] - verts[i + 2] * verts[i + 1]
    if area < 0:
        return
    last = n - 2
    for i in range(0, n // 2, 2):
        x, y = verts[i], verts[i + 1]
        o = last - i
        verts[i] = verts[o]
        verts[i + 1] = verts[o + 1]
        verts[o] = x
        verts[o + 1] = y


def _positive_area(p1x, p1y, p2x, p2y, p3x, p3y):
    return p1x * (p3y - p2y) + p2x * (p1y - p3y) + p3x * (p2y - p1y) >= 0


def _is_concave(index, vertex_count, verts, indices):
    prev = indices[(vertex_count + index - 1) % vertex_count]
    cur = indices[index]
    nxt = indices[(index + 1) % vertex_count]
    return not _positive_area(verts[prev * 2], verts[prev * 2 + 1],
                              verts[cur * 2], verts[cur * 2 + 1],
                              verts[nxt * 2], verts[nxt * 2 + 1])


def _triangulate_polygon(verts):
    """spine-ts 3.8 Triangulator.triangulate 移植。返回三角形顶点索引列表。"""
    vertex_count = len(verts) // 2
    indices = list(range(vertex_count))
    concave = [_is_concave(i, vertex_count, verts, indices)
               for i in range(vertex_count)]
    triangles = []
    while vertex_count > 3:
        previous = vertex_count - 1
        i = 0
        nxt = 1
        while True:
            ear_ok = False
            if not concave[i]:
                p1 = indices[previous]
                p2 = indices[i]
                p3 = indices[nxt]
                p1x, p1y = verts[p1 * 2], verts[p1 * 2 + 1]
                p2x, p2y = verts[p2 * 2], verts[p2 * 2 + 1]
                p3x, p3y = verts[p3 * 2], verts[p3 * 2 + 1]
                # JS: break outer 表示"耳内有凹点，此耳不能剪"→ 推进 i
                blocked = False
                ii = (nxt + 1) % vertex_count
                while ii != previous:
                    if concave[ii]:
                        v = indices[ii]
                        vx, vy = verts[v * 2], verts[v * 2 + 1]
                        if _positive_area(p3x, p3y, p1x, p1y, vx, vy):
                            if _positive_area(p1x, p1y, p2x, p2y, vx, vy):
                                if _positive_area(p2x, p2y, p3x, p3y, vx, vy):
                                    blocked = True
                                    break
                    ii = (ii + 1) % vertex_count
                if not blocked:
                    ear_ok = True
            if ear_ok:
                break
            if nxt == 0:
                while True:
                    if not concave[i]:
                        break
                    i -= 1
                    if i <= 0:
                        break
                break
            previous = i
            i = nxt
            nxt = (nxt + 1) % vertex_count
        triangles.append(indices[(vertex_count + i - 1) % vertex_count])
        triangles.append(indices[i])
        triangles.append(indices[(i + 1) % vertex_count])
        del indices[i]
        del concave[i]
        vertex_count -= 1
        prev_index = (vertex_count + i - 1) % vertex_count
        next_index = i if i != vertex_count else 0
        concave[prev_index] = _is_concave(prev_index, vertex_count, verts, indices)
        concave[next_index] = _is_concave(next_index, vertex_count, verts, indices)
    if vertex_count == 3:
        triangles += [indices[2], indices[0], indices[1]]
    return triangles


def _winding(p1x, p1y, p2x, p2y, p3x, p3y):
    px = p2x - p1x
    py = p2y - p1y
    return 1 if p3x * py - p3y * px + px * p1y - p1x * py >= 0 else -1


def _decompose(verts, triangles):
    """spine-ts 3.8 Triangulator.decompose 移植：合并三角形为凸多边形。

    verts: 平铺顶点；triangles: 三角形顶点索引（每 3 个一组）。
    返回凸多边形列表（平铺顶点，未闭合）。覆盖区域与三角形并集相同，
    但边序列不同——S-H 对自交多边形的输出依赖边序列，必须忠实移植。
    """
    convex_polys = []
    convex_indices = []
    poly_indices = []
    polygon = []
    fan_base_index = -1
    last_winding = 0
    for i in range(0, len(triangles), 3):
        t1 = triangles[i] * 2
        t2 = triangles[i + 1] * 2
        t3 = triangles[i + 2] * 2
        x1, y1 = verts[t1], verts[t1 + 1]
        x2, y2 = verts[t2], verts[t2 + 1]
        x3, y3 = verts[t3], verts[t3 + 1]
        merged = False
        if fan_base_index == t1:
            o = len(polygon) - 4
            winding1 = _winding(polygon[o], polygon[o + 1],
                                polygon[o + 2], polygon[o + 3], x3, y3)
            winding2 = _winding(x3, y3, polygon[0], polygon[1],
                                polygon[2], polygon[3])
            if winding1 == last_winding and winding2 == last_winding:
                polygon.append(x3)
                polygon.append(y3)
                poly_indices.append(t3)
                merged = True
        if not merged:
            if len(polygon) > 0:
                convex_polys.append(polygon)
                convex_indices.append(poly_indices)
            polygon = [x1, y1, x2, y2, x3, y3]
            poly_indices = [t1, t2, t3]
            last_winding = _winding(x1, y1, x2, y2, x3, y3)
            fan_base_index = t1
    if len(polygon) > 0:
        convex_polys.append(polygon)
        convex_indices.append(poly_indices)

    # 第二循环：把共享 (firstIndex, lastIndex) 边的三角形合并进多边形
    for i in range(len(convex_polys)):
        poly_indices = convex_indices[i]
        if len(poly_indices) == 0:
            continue
        first_index = poly_indices[0]
        last_index = poly_indices[-1]
        polygon = convex_polys[i]
        o = len(polygon) - 4
        prev_prev_x, prev_prev_y = polygon[o], polygon[o + 1]
        prev_x, prev_y = polygon[o + 2], polygon[o + 3]
        first_x, first_y = polygon[0], polygon[1]
        second_x, second_y = polygon[2], polygon[3]
        winding = _winding(prev_prev_x, prev_prev_y, prev_x, prev_y,
                           first_x, first_y)
        ii = 0
        while ii < len(convex_polys):
            if ii == i:
                ii += 1
                continue
            other_indices = convex_indices[ii]
            if len(other_indices) != 3:
                ii += 1
                continue
            if other_indices[0] != first_index or other_indices[1] != last_index:
                ii += 1
                continue
            other_poly = convex_polys[ii]
            x3 = other_poly[-2]
            y3 = other_poly[-1]
            winding1 = _winding(prev_prev_x, prev_prev_y, prev_x, prev_y, x3, y3)
            winding2 = _winding(x3, y3, first_x, first_y, second_x, second_y)
            if winding1 == winding and winding2 == winding:
                convex_polys[ii] = []
                convex_indices[ii] = []
                polygon.append(x3)
                polygon.append(y3)
                poly_indices.append(other_indices[2])
                prev_prev_x, prev_prev_y = prev_x, prev_y
                prev_x, prev_y = x3, y3
                ii = 0
            else:
                ii += 1

    return [p for p in convex_polys if len(p) > 0]


def clip_attachment_polys(verts):
    """裁剪附件世界顶点 → 官方语义的裁剪多边形列表（闭合，CW，骨架坐标）。

    返回 np.float64 数组列表（供 S-H numba 内核直接使用）。
    """
    v = list(verts)
    _make_clockwise(v)
    tris = _triangulate_polygon(v)
    polys = _decompose(v, tris)
    out = []
    for p in polys:
        _make_clockwise(p)
        p.append(p[0])
        p.append(p[1])
        out.append(np.asarray(p, dtype=np.float64))
    return out


def sh_clip(x1, y1, x2, y2, x3, y3, clipping_area):
    """spine-ts 3.8 SkeletonClipping.clip 移植（Sutherland-Hodgman）。

    三角形 (x1,y1)(x2,y2)(x3,y3) 与裁剪多边形 clipping_area（平铺、闭合）
    求交。返回交集多边形平铺顶点（未闭合）；空交集返回 []。
    """
    n = _sh_clip_numba(x1, y1, x2, y2, x3, y3, clipping_area, _sh_out_buf)
    if n == 0:
        return []
    return _sh_out_buf[:n].tolist()


_sh_out_buf = np.empty(64, dtype=np.float64)


@numba.njit(cache=True)
def _sh_clip_numba(x1, y1, x2, y2, x3, y3, clip_area, out_arr):
    """S-H 裁剪内核。clip_area: float64 平铺闭合多边形。返回交集顶点元素数。"""
    inp = np.empty(32, dtype=np.float64)
    out = np.empty(32, dtype=np.float64)
    inp[0] = x1
    inp[1] = y1
    inp[2] = x2
    inp[3] = y2
    inp[4] = x3
    inp[5] = y3
    inp[6] = x1
    inp[7] = y1
    inp_len = 8
    last = clip_area.shape[0] - 4
    i = 0
    out_len = 0
    while True:
        edge_x = clip_area[i]
        edge_y = clip_area[i + 1]
        edge_x2 = clip_area[i + 2]
        edge_y2 = clip_area[i + 3]
        delta_x = edge_x - edge_x2
        delta_y = edge_y - edge_y2
        out_len = 0
        input_len = inp_len - 2
        for ii in range(0, input_len, 2):
            in_x = inp[ii]
            in_y = inp[ii + 1]
            in_x2 = inp[ii + 2]
            in_y2 = inp[ii + 3]
            side2 = delta_x * (in_y2 - edge_y2) - delta_y * (in_x2 - edge_x2) > 0.0
            if delta_x * (in_y - edge_y2) - delta_y * (in_x - edge_x2) > 0.0:
                if side2:
                    out[out_len] = in_x2
                    out[out_len + 1] = in_y2
                    out_len += 2
                    continue
                c0 = in_y2 - in_y
                c2 = in_x2 - in_x
                s = c0 * (edge_x2 - edge_x) - c2 * (edge_y2 - edge_y)
                if abs(s) > 0.000001:
                    ua = (c2 * (edge_y - in_y) - c0 * (edge_x - in_x)) / s
                    out[out_len] = edge_x + (edge_x2 - edge_x) * ua
                    out[out_len + 1] = edge_y + (edge_y2 - edge_y) * ua
                else:
                    out[out_len] = edge_x
                    out[out_len + 1] = edge_y
                out_len += 2
            elif side2:
                c0 = in_y2 - in_y
                c2 = in_x2 - in_x
                s = c0 * (edge_x2 - edge_x) - c2 * (edge_y2 - edge_y)
                if abs(s) > 0.000001:
                    ua = (c2 * (edge_y - in_y) - c0 * (edge_x - in_x)) / s
                    out[out_len] = edge_x + (edge_x2 - edge_x) * ua
                    out[out_len + 1] = edge_y + (edge_y2 - edge_y) * ua
                else:
                    out[out_len] = edge_x
                    out[out_len + 1] = edge_y
                out_len += 2
                out[out_len] = in_x2
                out[out_len + 1] = in_y2
                out_len += 2
        if out_len == 0:
            return 0
        out[out_len] = out[0]
        out[out_len + 1] = out[1]
        out_len += 2
        if i == last:
            break
        for k in range(out_len):
            inp[k] = out[k]
        inp_len = out_len
        i += 2
    n = out_len - 2
    for k in range(n):
        out_arr[k] = out[k]
    return n


def clip_triangle_to_polys(tri, uv, clip_polys):
    """三角形（骨架坐标 (x,y) 三元组 + uv 三元组）经官方 S-H 裁剪。

    官方 clipTriangles 语义：对每个裁剪多边形求交并**全部输出**——
    裁剪路径没有 continue outer，重叠多边形会产生重叠输出（官方如此，
    重叠区域重复 alpha 混合）。返回 [(pts, uvs), ...]（0 或 N 个交集），
    pts 为骨架坐标平铺列表，uvs 为对应插值 UV 平铺列表（重心插值）。
    """
    x1, y1 = tri[0]
    x2, y2 = tri[1]
    x3, y3 = tri[2]
    u1, v1 = uv[0]
    u2, v2 = uv[1]
    u3, v3 = uv[2]
    # 重心坐标反解系数（spine-ts clipTriangles 同款）
    d0 = y2 - y3
    d1 = x3 - x2
    d2 = x1 - x3
    d4 = y3 - y1
    denom = d0 * d2 + d1 * (y1 - y3)
    if abs(denom) < 1e-12:
        return []
    inv = 1.0 / denom
    results = []
    for poly in clip_polys:
        pts = sh_clip(x1, y1, x2, y2, x3, y3, poly)
        if len(pts) < 6:
            continue
        uvs = []
        for k in range(0, len(pts), 2):
            px, py = pts[k], pts[k + 1]
            c0 = px - x3
            c1 = py - y3
            a = (d0 * c0 + d1 * c1) * inv
            b = (d4 * c0 + d2 * c1) * inv
            c = 1.0 - a - b
            uvs.append(u1 * a + u2 * b + u3 * c)
            uvs.append(v1 * a + v2 * b + v3 * c)
        results.append((pts, uvs))
    return results


def fan_triangulate(pts):
    """凸多边形平铺顶点 → 扇形三角形索引列表（顶点索引，每 3 个一组）。"""
    n = len(pts) // 2
    tris = []
    for i in range(1, n - 1):
        tris += [0, i, i + 1]
    return tris
