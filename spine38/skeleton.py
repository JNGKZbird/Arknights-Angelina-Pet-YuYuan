"""Spine 3.8 姿态计算 — ported from spine-ts 3.8 Bone/Skeleton."""
import math
import numpy as np
import numba
from .loader import (TRANSFORM_NORMAL, TRANSFORM_ONLY_TRANSLATION,
                    TRANSFORM_NO_ROTATION_OR_REFLECTION, TRANSFORM_NO_SCALE,
                    TRANSFORM_NO_SCALE_OR_REFLECTION)

RAD_DEG = 180.0 / math.pi
DEG_RAD = math.pi / 180.0


def cos_deg(d):
    return math.cos(d * DEG_RAD)


def sin_deg(d):
    return math.sin(d * DEG_RAD)


class Bone:
    def __init__(self, data, skeleton, parent):
        self.data = data
        self.skeleton = skeleton
        self.parent = parent
        self.x = data.x
        self.y = data.y
        self.rotation = data.rotation
        self.scale_x = data.scale_x
        self.scale_y = data.scale_y
        self.shear_x = data.shear_x
        self.shear_y = data.shear_y
        # 已应用变换（约束系统使用）
        self.ax = self.x
        self.ay = self.y
        self.arotation = self.rotation
        self.ascale_x = self.scale_x
        self.ascale_y = self.scale_y
        self.ashear_x = self.shear_x
        self.ashear_y = self.shear_y
        self.a = self.b = self.c = self.d = 0.0
        self.world_x = self.world_y = 0.0
        self.active = True
        self.applied_valid = False
        self.children = []
        self.sorted = False

    def update_world_transform(self):
        self._update_with(self.x, self.y, self.rotation, self.scale_x,
                          self.scale_y, self.shear_x, self.shear_y)

    def update(self):
        self.update_world_transform()

    def update_applied_transform(self):
        """从世界矩阵反推局部已应用变换（约束修改世界坐标后调用）。"""
        self.applied_valid = True
        parent = self.parent
        if parent is None:
            self.ax = self.world_x
            self.ay = self.world_y
            self.arotation = math.atan2(self.c, self.a) * RAD_DEG
            self.ascale_x = math.sqrt(self.a * self.a + self.c * self.c)
            self.ascale_y = math.sqrt(self.b * self.b + self.d * self.d)
            self.ashear_x = 0.0
            self.ashear_y = math.atan2(self.a * self.b + self.c * self.d,
                                       self.a * self.d - self.b * self.c) * RAD_DEG
            return
        pa, pb, pc, pd = parent.a, parent.b, parent.c, parent.d
        det = pa * pd - pb * pc
        if abs(det) < 0.0001:
            return
        pid = 1.0 / det
        dx = self.world_x - parent.world_x
        dy = self.world_y - parent.world_y
        self.ax = dx * pd * pid - dy * pb * pid
        self.ay = dy * pa * pid - dx * pc * pid
        ia = pid * pd
        id_ = pid * pa
        ib = pid * pb
        ic = pid * pc
        ra = ia * self.a - ib * self.c
        rb = ia * self.b - ib * self.d
        rc = id_ * self.c - ic * self.a
        rd = id_ * self.d - ic * self.b
        self.ashear_x = 0.0
        self.ascale_x = math.sqrt(ra * ra + rc * rc)
        if self.ascale_x > 0.0001:
            det2 = ra * rd - rb * rc
            self.ascale_y = det2 / self.ascale_x
            self.ashear_y = math.atan2(ra * rb + rc * rd, det2) * RAD_DEG
            self.arotation = math.atan2(rc, ra) * RAD_DEG
        else:
            self.ascale_x = 0.0
            self.ascale_y = math.sqrt(rb * rb + rd * rd)
            self.ashear_y = 0.0
            self.arotation = 90 - math.atan2(rd, rb) * RAD_DEG

    def _update_with(self, x, y, rotation, scale_x, scale_y, shear_x, shear_y):
        self.ax = x
        self.ay = y
        self.arotation = rotation
        self.ascale_x = scale_x
        self.ascale_y = scale_y
        self.ashear_x = shear_x
        self.ashear_y = shear_y
        self.applied_valid = True
        parent = self.parent
        if parent is None:
            skeleton = self.skeleton
            rotation_y = rotation + 90 + shear_y
            sx = skeleton.scale_x
            sy = skeleton.scale_y
            self.a = cos_deg(rotation + shear_x) * scale_x * sx
            self.b = cos_deg(rotation_y) * scale_y * sx
            self.c = sin_deg(rotation + shear_x) * scale_x * sy
            self.d = sin_deg(rotation_y) * scale_y * sy
            self.world_x = x * sx + skeleton.x
            self.world_y = y * sy + skeleton.y
            return
        pa, pb, pc, pd = parent.a, parent.b, parent.c, parent.d
        self.world_x = pa * x + pb * y + parent.world_x
        self.world_y = pc * x + pd * y + parent.world_y
        mode = self.data.transform_mode
        if mode == TRANSFORM_NORMAL:
            rotation_y = rotation + 90 + shear_y
            la = cos_deg(rotation + shear_x) * scale_x
            lb = cos_deg(rotation_y) * scale_y
            lc = sin_deg(rotation + shear_x) * scale_x
            ld = sin_deg(rotation_y) * scale_y
            self.a = pa * la + pb * lc
            self.b = pa * lb + pb * ld
            self.c = pc * la + pd * lc
            self.d = pc * lb + pd * ld
            return
        if mode == TRANSFORM_ONLY_TRANSLATION:
            rotation_y = rotation + 90 + shear_y
            self.a = cos_deg(rotation + shear_x) * scale_x
            self.b = cos_deg(rotation_y) * scale_y
            self.c = sin_deg(rotation + shear_x) * scale_x
            self.d = sin_deg(rotation_y) * scale_y
        elif mode == TRANSFORM_NO_ROTATION_OR_REFLECTION:
            s = pa * pa + pc * pc
            prx = 0.0
            if s > 0.0001:
                s = abs(pa * pd - pb * pc) / s
                pa /= self.skeleton.scale_x
                pc /= self.skeleton.scale_y
                pb = pc * s
                pd = pa * s
                prx = math.atan2(pc, pa) * RAD_DEG
            else:
                pa = 0.0
                pc = 0.0
                prx = 90 - math.atan2(pd, pb) * RAD_DEG
            rx = rotation + shear_x - prx
            ry = rotation + shear_y - prx + 90
            la = cos_deg(rx) * scale_x
            lb = cos_deg(ry) * scale_y
            lc = sin_deg(rx) * scale_x
            ld = sin_deg(ry) * scale_y
            self.a = pa * la - pb * lc
            self.b = pa * lb - pb * ld
            self.c = pc * la + pd * lc
            self.d = pc * lb + pd * ld
        else:  # NO_SCALE / NO_SCALE_OR_REFLECTION
            cos = cos_deg(rotation)
            sin = sin_deg(rotation)
            za = (pa * cos + pb * sin) / self.skeleton.scale_x
            zc = (pc * cos + pd * sin) / self.skeleton.scale_y
            s = math.sqrt(za * za + zc * zc)
            if s > 0.00001:
                s = 1.0 / s
            za *= s
            zc *= s
            s = math.sqrt(za * za + zc * zc)
            if mode == TRANSFORM_NO_SCALE and ((pa * pd - pb * pc < 0) !=
                                               ((self.skeleton.scale_x < 0) != (self.skeleton.scale_y < 0))):
                s = -s
            r = math.pi / 2 + math.atan2(zc, za)
            zb = math.cos(r) * s
            zd = math.sin(r) * s
            la = cos_deg(shear_x) * scale_x
            lb = cos_deg(90 + shear_y) * scale_y
            lc = sin_deg(shear_x) * scale_x
            ld = sin_deg(90 + shear_y) * scale_y
            self.a = za * la + zb * lc
            self.b = za * lb + zb * ld
            self.c = zc * la + zd * lc
            self.d = zc * lb + zd * ld
        self.a *= self.skeleton.scale_x
        self.b *= self.skeleton.scale_x
        self.c *= self.skeleton.scale_y
        self.d *= self.skeleton.scale_y


class Slot:
    def __init__(self, data, bone):
        self.data = data
        self.bone = bone
        self.color = None  # Color 副本，初始化时设置
        self.dark_color = None
        self.attachment = None
        self.deform = []  # 变形缓冲区（DeformTimeline 写入，顶点计算消费）
        from .utils import Color as _C
        self.color = _C(data.color.r, data.color.g, data.color.b, data.color.a)
        if data.dark_color is not None:
            self.dark_color = _C(data.dark_color.r, data.dark_color.g, data.dark_color.b, 1.0)

    def set_attachment(self, attachment):
        self.attachment = attachment
        self.deform.clear()


class Skeleton:
    def __init__(self, data):
        self.data = data
        self.bones = []
        self.slots = []
        self.draw_order = []
        self.x = data.x
        self.y = data.y
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.color = None
        from .utils import Color
        self.color = Color(1, 1, 1, 1)
        for bone_data in data.bones:
            parent = self.bones[bone_data.parent.index] if bone_data.parent else None
            self.bones.append(Bone(bone_data, self, parent))
        for bone in self.bones:
            if bone.parent is not None:
                bone.parent.children.append(bone)
        for slot_data in data.slots:
            bone = self.bones[slot_data.bone_data.index]
            self.slots.append(Slot(slot_data, bone))
        self.draw_order = list(self.slots)
        # 持久约束实例（动画层会写入 mix/position 等属性）
        from .constraints import IkConstraint, TransformConstraint, PathConstraint
        self.ik_constraints = [IkConstraint(d, self) for d in data.ik_constraints]
        self.transform_constraints = [TransformConstraint(d, self) for d in data.transform_constraints]
        self.path_constraints = [PathConstraint(d, self) for d in data.path_constraints]
        self._build_update_cache()

    # ── 更新缓存（照 spine-ts 3.8 Skeleton.updateCache 移植） ──
    def _sort_bone(self, bone):
        if bone.sorted:
            return
        if bone.parent is not None:
            self._sort_bone(bone.parent)
        bone.sorted = True
        self.update_cache.append(bone)

    def _sort_reset(self, bones):
        for bone in bones:
            if not bone.active:
                continue
            if bone.sorted:
                self._sort_reset(bone.children)
            bone.sorted = False

    def _sort_ik_constraint(self, constraint):
        constraint.active = constraint.target.active
        if not constraint.active:
            return
        self._sort_bone(constraint.target)
        constrained = constraint.bones
        parent = constrained[0]
        self._sort_bone(parent)
        if len(constrained) > 1:
            child = constrained[-1]
            if child not in self.update_cache:
                self.update_cache_reset.append(child)
        self.update_cache.append(constraint)
        self._sort_reset(parent.children)
        constrained[-1].sorted = True

    def _sort_transform_constraint(self, constraint):
        constraint.active = constraint.target.active
        if not constraint.active:
            return
        self._sort_bone(constraint.target)
        constrained = constraint.bones
        if constraint.data.local:
            for child in constrained:
                self._sort_bone(child.parent)
                if child not in self.update_cache:
                    self.update_cache_reset.append(child)
        else:
            for bone in constrained:
                self._sort_bone(bone)
        self.update_cache.append(constraint)
        for bone in constrained:
            self._sort_reset(bone.children)
        for bone in constrained:
            bone.sorted = True

    def _sort_path_constraint(self, constraint):
        constraint.active = constraint.target.bone.active
        if not constraint.active:
            return
        constrained = constraint.bones
        for bone in constrained:
            self._sort_bone(bone)
        self.update_cache.append(constraint)
        for bone in constrained:
            self._sort_reset(bone.children)
        for bone in constrained:
            bone.sorted = True

    def _build_update_cache(self):
        """骨骼与约束按依赖顺序交错排入缓存（约束修改父骨骼后子骨骼才更新）。"""
        self.update_cache = []
        self.update_cache_reset = []
        for bone in self.bones:
            bone.sorted = bone.data.skin_required
            bone.active = not bone.sorted
        ik = self.ik_constraints
        tx = self.transform_constraints
        path = self.path_constraints
        constraint_count = len(ik) + len(tx) + len(path)
        for i in range(constraint_count):
            found = False
            for c in ik:
                if c.data.order == i:
                    self._sort_ik_constraint(c)
                    found = True
                    break
            if found:
                continue
            for c in tx:
                if c.data.order == i:
                    self._sort_transform_constraint(c)
                    found = True
                    break
            if found:
                continue
            for c in path:
                if c.data.order == i:
                    self._sort_path_constraint(c)
                    break
        for bone in self.bones:
            self._sort_bone(bone)

    def update_world_transform(self):
        for bone in self.update_cache_reset:
            bone.ax = bone.x
            bone.ay = bone.y
            bone.arotation = bone.rotation
            bone.ascale_x = bone.scale_x
            bone.ascale_y = bone.scale_y
            bone.ashear_x = bone.shear_x
            bone.ashear_y = bone.shear_y
            bone.applied_valid = True
        for entry in self.update_cache:
            entry.update()

    def set_to_setup_pose(self):
        for bone in self.bones:
            bone.x = bone.data.x
            bone.y = bone.data.y
            bone.rotation = bone.data.rotation
            bone.scale_x = bone.data.scale_x
            bone.scale_y = bone.data.scale_y
            bone.shear_x = bone.data.shear_x
            bone.shear_y = bone.data.shear_y
        for c in self.ik_constraints:
            c.mix = c.data.mix
            c.softness = c.data.softness
            c.bend_direction = c.data.bend_direction
            c.compress = c.data.compress
            c.stretch = c.data.stretch
            c.uniform = c.data.uniform
        for c in self.transform_constraints:
            c.rotate_mix = c.data.rotate_mix
            c.translate_mix = c.data.translate_mix
            c.scale_mix = c.data.scale_mix
            c.shear_mix = c.data.shear_mix
        for c in self.path_constraints:
            c.position = c.data.position
            c.spacing = c.data.spacing
            c.rotate_mix = c.data.rotate_mix
            c.translate_mix = c.data.translate_mix
        for slot in self.slots:
            from .utils import Color
            slot.color.set(slot.data.color.r, slot.data.color.g, slot.data.color.b, slot.data.color.a)
            name = slot.data.attachment_name
            slot.attachment = self.get_attachment(slot.data.index, name) if name else None
        for slot in self.slots:
            slot.deform.clear()
        self.draw_order = list(self.slots)

    def get_attachment(self, slot_index, name):
        return self.data.default_skin.get_attachment(slot_index, name) if self.data.default_skin else None

    def find_bone(self, name):
        return self.data.find_bone(name)

    def get_bounds(self):
        """计算包围盒（不含约束），返回 (offset_x, offset_y, w, h)"""
        import numpy as np
        xs = []
        ys = []
        for slot in self.draw_order:
            att = slot.attachment
            if att is None:
                continue
            verts = compute_attachment_vertices(slot, att, 0, att.world_vertices_length or 8)
            for i in range(0, len(verts), 2):
                xs.append(verts[i])
                ys.append(verts[i + 1])
        if not xs:
            return (0.0, 0.0, 0.0, 0.0)
        return (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))


def compute_region_vertices(slot, region_attachment, out=None):
    """区域附件 4 角世界坐标。返回 8 元素列表。"""
    bone = slot.bone
    off = region_attachment.offset
    x, y = bone.world_x, bone.world_y
    a, b, c, d = bone.a, bone.b, bone.c, bone.d
    if out is None:
        out = [0.0] * 8
    out[0] = off[0] * a + off[1] * b + x
    out[1] = off[0] * c + off[1] * d + y
    out[2] = off[2] * a + off[3] * b + x
    out[3] = off[2] * c + off[3] * d + y
    out[4] = off[4] * a + off[5] * b + x
    out[5] = off[4] * c + off[5] * d + y
    out[6] = off[6] * a + off[7] * b + x
    out[7] = off[6] * c + off[7] * d + y
    return out


@numba.njit(cache=True)
def _mesh_verts_weighted(vertices, bones, deform, bone_mats, start, count, out):
    """加权网格顶点 numba 内核。deform 按权重条目序号索引（官方语义）。"""
    o = 0
    bi = 0
    vi = 0
    f = 0
    v = start
    if start > 0:
        for _ in range(start):
            n = bones[bi]
            bi += n + 1
            f += n
        vi = f * 3
    has_deform = deform.shape[0] > 0
    while v < start + count:
        bone_count = bones[bi]
        bi += 1
        wx = 0.0
        wy = 0.0
        for _ in range(bone_count):
            bone_index = bones[bi]
            bi += 1
            if has_deform:
                vx = vertices[vi] + deform[f * 2]
                vy = vertices[vi + 1] + deform[f * 2 + 1]
            else:
                vx = vertices[vi]
                vy = vertices[vi + 1]
            weight = vertices[vi + 2]
            vi += 3
            f += 1
            a = bone_mats[bone_index, 0]
            b = bone_mats[bone_index, 1]
            c = bone_mats[bone_index, 2]
            d = bone_mats[bone_index, 3]
            bx = bone_mats[bone_index, 4]
            by = bone_mats[bone_index, 5]
            wx += (vx * a + vy * b + bx) * weight
            wy += (vx * c + vy * d + by) * weight
        out[o] = wx
        out[o + 1] = wy
        o += 2
        v += 1
    return o


@numba.njit(cache=True)
def _mesh_verts_unweighted(vertices, deform, a, b, c, d, wx, wy, start, count, out):
    """非加权网格顶点 numba 内核。deform 非空时 vertices 已被替换为 deform。"""
    o = 0
    for v in range(start, start + count):
        vx = vertices[v * 2]
        vy = vertices[v * 2 + 1]
        out[o] = vx * a + vy * b + wx
        out[o + 1] = vx * c + vy * d + wy
        o += 2
    return o


def collect_bone_mats(skeleton):
    """所有骨骼世界矩阵 → (n, 6) float64 数组 [a, b, c, d, world_x, world_y]。"""
    bones = skeleton.bones
    mats = np.empty((len(bones), 6), dtype=np.float64)
    for i, b in enumerate(bones):
        mats[i, 0] = b.a
        mats[i, 1] = b.b
        mats[i, 2] = b.c
        mats[i, 3] = b.d
        mats[i, 4] = b.world_x
        mats[i, 5] = b.world_y
    return mats


def compute_mesh_vertices(slot, mesh, start=0, count=None, out=None, bone_mats=None):
    """网格附件世界顶点（含变形）。变形值在 slot.deform 缓冲区。

    bone_mats: collect_bone_mats 输出（渲染路径每帧构建一次复用）。
    """
    deform = slot.deform
    bones = mesh.bones
    vertices = mesh.vertices
    if count is None:
        count = mesh.world_vertices_length // 2
    if bones is None:
        # 非加权：deform 非空时替换顶点数组（绝对坐标语义）
        if deform:
            vertices = deform
        a, b, c, d = slot.bone.a, slot.bone.b, slot.bone.c, slot.bone.d
        wx, wy = slot.bone.world_x, slot.bone.world_y
        out_arr = np.empty(count * 2, dtype=np.float64)
        n = _mesh_verts_unweighted(
            np.asarray(vertices, dtype=np.float64), np.empty(0),
            a, b, c, d, wx, wy, start, count, out_arr)
        return out_arr[:n].tolist()
    # 加权：deform 增量按权重条目序号索引（官方 f=skip<<1）
    if bone_mats is None:
        bone_mats = collect_bone_mats(slot.bone.skeleton)
    out_arr = np.empty(count * 2, dtype=np.float64)
    n = _mesh_verts_weighted(
        np.asarray(vertices, dtype=np.float64),
        np.asarray(bones, dtype=np.int64),
        np.asarray(deform, dtype=np.float64) if deform else np.empty(0),
        bone_mats, start, count, out_arr)
    return out_arr[:n].tolist()


def compute_attachment_vertices(slot, attachment, start, count):
    """统一入口：根据附件类型计算世界顶点。"""
    if attachment is None:
        return []
    from .loader import RegionAttachment, MeshAttachment, ClippingAttachment
    if isinstance(attachment, RegionAttachment):
        return compute_region_vertices(slot, attachment)
    if isinstance(attachment, MeshAttachment):
        return compute_mesh_vertices(slot, attachment, start, count // 2 if count else None)
    if isinstance(attachment, ClippingAttachment):
        return compute_mesh_vertices(slot, attachment, start, count // 2 if count else None)
    return []
