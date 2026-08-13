"""Spine 3.8 约束求解 — IK / 变换 / 路径约束，精确移植自 spine-ts 3.8."""
import math
from .loader import (TRANSFORM_ONLY_TRANSLATION,
                    TRANSFORM_NO_ROTATION_OR_REFLECTION, TRANSFORM_NO_SCALE,
                    TRANSFORM_NO_SCALE_OR_REFLECTION,
                    POSITION_FIXED, SPACING_LENGTH, SPACING_FIXED,
                    ROTATE_TANGENT, ROTATE_CHAIN, ROTATE_CHAIN_SCALE)

DEG_RAD = math.pi / 180.0
RAD_DEG = 180.0 / math.pi
PI = math.pi
PI2 = math.pi * 2


def _atan2(y, x):
    return math.atan2(y, x)


# ── IK 约束 ─────────────────────────────────────────────
class IkConstraint:
    def __init__(self, data, skeleton):
        self.data = data
        self.bones = [skeleton.bones[b.index] for b in data.bones]
        self.target = skeleton.bones[data.target.index]
        self.mix = data.mix
        self.softness = data.softness
        self.bend_direction = data.bend_direction
        self.compress = data.compress
        self.stretch = data.stretch
        self.uniform = data.uniform
        self.active = False

    def apply(self):
        target = self.target
        bones = self.bones
        if len(bones) == 1:
            self._apply1(bones[0], target.world_x, target.world_y,
                         self.compress, self.stretch, self.uniform)
        elif len(bones) == 2:
            self._apply2(bones[0], bones[1], target.world_x, target.world_y)

    def update(self):
        self.apply()

    def _apply1(self, bone, target_x, target_y, compress, stretch, uniform):
        p = bone.parent
        pa, pb, pc, pd = p.a, p.b, p.c, p.d
        if not bone.applied_valid:
            bone.update_applied_transform()
        p = bone.parent
        pa0, pb0, pc0, pd0 = p.a, p.b, p.c, p.d
        rotation_ik = -bone.ashear_x - bone.arotation
        tx = ty = 0.0
        mode = bone.data.transform_mode
        if mode == TRANSFORM_ONLY_TRANSLATION:
            tx = target_x - bone.world_x
            ty = target_y - bone.world_y
        elif mode == TRANSFORM_NO_ROTATION_OR_REFLECTION:
            s = abs(pa0 * pd0 - pb0 * pc0) / (pa0 * pa0 + pc0 * pc0)
            sa = pa0 / bone.skeleton.scale_x
            sc = pc0 / bone.skeleton.scale_y
            pb0 = -sc * s * bone.skeleton.scale_x
            pd0 = sa * s * bone.skeleton.scale_y
            rotation_ik += _atan2(sc, sa) * RAD_DEG
        else:
            x = target_x - p.world_x
            y = target_y - p.world_y
            d = pa0 * pd0 - pb0 * pc0
            if abs(d) < 0.0001:
                return
            tx = (x * pd0 - y * pb0) / d - bone.ax
            ty = (y * pa0 - x * pc0) / d - bone.ay
        rotation_ik += _atan2(ty, tx) * RAD_DEG
        if bone.ascale_x < 0:
            rotation_ik += 180
        if rotation_ik > 180:
            rotation_ik -= 360
        elif rotation_ik < -180:
            rotation_ik += 360
        sx, sy = bone.ascale_x, bone.ascale_y
        if compress or stretch:
            if mode in (TRANSFORM_NO_SCALE, TRANSFORM_NO_SCALE_OR_REFLECTION):
                tx = target_x - bone.world_x
                ty = target_y - bone.world_y
            b = bone.data.length * sx
            dd = math.sqrt(tx * tx + ty * ty)
            if ((compress and dd < b) or (stretch and dd > b)) and b > 0.0001:
                s = (dd / b - 1) * self.mix + 1
                sx *= s
                if uniform:
                    sy *= s
        bone._update_with(bone.ax, bone.ay, bone.arotation + rotation_ik * self.mix,
                          sx, sy, bone.ashear_x, bone.ashear_y)

    def _apply2(self, parent, child, target_x, target_y):
        if self.mix == 0:
            child.update_world_transform()
            return
        if not parent.applied_valid:
            parent.update_applied_transform()
        if not child.applied_valid:
            child.update_applied_transform()
        px, py = parent.ax, parent.ay
        psx, sx = parent.ascale_x, parent.ascale_x
        psy = parent.ascale_y
        csx = child.ascale_x
        os1, os2, s2 = 0, 0, 0
        if psx < 0:
            psx = -psx
            os1 = 180
            s2 = -1
        else:
            os1 = 0
            s2 = 1
        if psy < 0:
            psy = -psy
            s2 = -s2
        if csx < 0:
            csx = -csx
            os2 = 180
        else:
            os2 = 0
        cx = child.ax
        cy = 0.0
        cwx = cwy = 0.0
        a, b, c, d = parent.a, parent.b, parent.c, parent.d
        u = abs(psx - psy) <= 0.0001
        if not u:
            cy = 0.0
            cwx = a * cx + parent.world_x
            cwy = c * cx + parent.world_y
        else:
            cy = child.ay
            cwx = a * cx + b * cy + parent.world_x
            cwy = c * cx + d * cy + parent.world_y
        pp = parent.parent
        a, b, c, d = pp.a, pp.b, pp.c, pp.d
        det = a * d - b * c
        if abs(det) < 0.0001:
            return
        id = 1.0 / det
        x = cwx - pp.world_x
        y = cwy - pp.world_y
        dx = (x * d - y * b) * id - px
        dy = (y * a - x * c) * id - py
        l1 = math.sqrt(dx * dx + dy * dy)
        l2 = child.data.length * csx
        a1 = a2 = 0.0
        if l1 < 0.0001:
            # JS: apply1(parent, targetX, targetY, false, stretch, false, alpha)
            self._apply1(parent, target_x, target_y, False, self.stretch, False)
            child._update_with(cx, cy, 0.0, child.ascale_x, child.ascale_y, child.ashear_x, child.ashear_y)
            return
        x = target_x - pp.world_x
        y = target_y - pp.world_y
        tx = (x * d - y * b) * id - px
        ty = (y * a - x * c) * id - py
        dd = tx * tx + ty * ty
        softness = self.softness
        if softness != 0:
            softness *= psx * (csx + 1) / 2
            td = math.sqrt(dd)
            sd = td - l1 - l2 * psx + softness
            if sd > 0:
                p = min(1.0, sd / (softness * 2)) - 1
                p = (sd - softness * (1 - p * p)) / td
                tx -= p * tx
                ty -= p * ty
                dd = tx * tx + ty * ty
        if u:
            l2 *= psx
            cos = (dd - l1 * l1 - l2 * l2) / (2 * l1 * l2)
            if cos < -1:
                cos = -1
            elif cos > 1:
                cos = 1
                if self.stretch:
                    sx *= (math.sqrt(dd) / (l1 + l2) - 1) * self.mix + 1
            a2 = math.acos(cos) * self.bend_direction
            a = l1 + l2 * cos
            b = l2 * math.sin(a2)
            a1 = _atan2(ty * a - tx * b, tx * a + ty * b)
        else:
            a = psx * l2
            b = psy * l2
            aa = a * a
            bb = b * b
            ta = _atan2(ty, tx)
            c = bb * l1 * l1 + aa * dd - aa * bb
            c1 = -2 * bb * l1
            c2 = bb - aa
            d = c1 * c1 - 4 * c2 * c
            if d >= 0:
                q = math.sqrt(d)
                if c1 < 0:
                    q = -q
                q = -(c1 + q) / 2
                r0 = q / c2
                r1 = c / q
                r = r0 if abs(r0) < abs(r1) else r1
                if r * r <= dd:
                    y = math.sqrt(dd - r * r) * self.bend_direction
                    a1 = ta - _atan2(y, r)
                    a2 = _atan2(y / psy, (r - l1) / psx)
                    break_outer = True
                else:
                    break_outer = False
            else:
                break_outer = False
            if not break_outer:
                min_angle = PI
                min_x = l1 - a
                min_dist = min_x * min_x
                min_y = 0.0
                max_angle = 0.0
                max_x = l1 + a
                max_dist = max_x * max_x
                max_y = 0.0
                c = -a * l1 / (aa - bb) if abs(aa - bb) > 0.0001 else 0.0
                if -1 <= c <= 1:
                    c = math.acos(c)
                    x = a * math.cos(c) + l1
                    y = b * math.sin(c)
                    d = x * x + y * y
                    if d < min_dist:
                        min_angle = c
                        min_dist = d
                        min_x = x
                        min_y = y
                    if d > max_dist:
                        max_angle = c
                        max_dist = d
                        max_x = x
                        max_y = y
                if dd <= (min_dist + max_dist) / 2:
                    a1 = ta - _atan2(min_y * self.bend_direction, min_x)
                    a2 = min_angle * self.bend_direction
                else:
                    a1 = ta - _atan2(max_y * self.bend_direction, max_x)
                    a2 = max_angle * self.bend_direction
        os = _atan2(cy, cx) * s2
        rotation = parent.arotation
        a1 = (a1 - os) * RAD_DEG + os1 - rotation
        if a1 > 180:
            a1 -= 360
        elif a1 < -180:
            a1 += 360
        parent._update_with(px, py, rotation + a1 * self.mix, sx, parent.ascale_y, 0.0, 0.0)
        rotation = child.arotation
        a2 = ((a2 + os) * RAD_DEG - child.ashear_x) * s2 + os2 - rotation
        if a2 > 180:
            a2 -= 360
        elif a2 < -180:
            a2 += 360
        child._update_with(cx, cy, rotation + a2 * self.mix, child.ascale_x, child.ascale_y,
                           child.ashear_x, child.ashear_y)


# ── 变换约束 ────────────────────────────────────────────
class TransformConstraint:
    def __init__(self, data, skeleton):
        self.data = data
        self.bones = [skeleton.bones[b.index] for b in data.bones]
        self.target = skeleton.bones[data.target.index]
        self.rotate_mix = data.rotate_mix
        self.translate_mix = data.translate_mix
        self.scale_mix = data.scale_mix
        self.shear_mix = data.shear_mix
        self.active = False

    def apply(self):
        # 本模型数据均为 local=false, relative=false → applyAbsoluteWorld
        self._apply_absolute_world()

    def update(self):
        self.apply()

    def _apply_absolute_world(self):
        rotate_mix = self.rotate_mix
        translate_mix = self.translate_mix
        scale_mix = self.scale_mix
        shear_mix = self.shear_mix
        target = self.target
        ta, tb, tc, td = target.a, target.b, target.c, target.d
        deg_rad_reflect = DEG_RAD if ta * td - tb * tc > 0 else -DEG_RAD
        offset_rotation = self.data.offset_rotation * deg_rad_reflect
        offset_shear_y = self.data.offset_shear_y * deg_rad_reflect
        for bone in self.bones:
            if rotate_mix != 0:
                a, b, c, d = bone.a, bone.b, bone.c, bone.d
                r = _atan2(tc, ta) - _atan2(c, a) + offset_rotation
                if r > PI:
                    r -= PI2
                elif r < -PI:
                    r += PI2
                r *= rotate_mix
                cos = math.cos(r)
                sin = math.sin(r)
                bone.a = cos * a - sin * c
                bone.b = cos * b - sin * d
                bone.c = sin * a + cos * c
                bone.d = sin * b + cos * d
                bone.applied_valid = False
            if translate_mix != 0:
                # target.localToWorld(offsetX, offsetY)
                ox = self.data.offset_x
                oy = self.data.offset_y
                tx = target.a * ox + target.b * oy + target.world_x
                ty = target.c * ox + target.d * oy + target.world_y
                bone.world_x += (tx - bone.world_x) * translate_mix
                bone.world_y += (ty - bone.world_y) * translate_mix
                bone.applied_valid = False
            if scale_mix > 0:
                s = math.sqrt(bone.a * bone.a + bone.c * bone.c)
                ts = math.sqrt(ta * ta + tc * tc)
                if s > 0.00001:
                    s = (s + (ts - s + self.data.offset_scale_x) * scale_mix) / s
                bone.a *= s
                bone.c *= s
                s = math.sqrt(bone.b * bone.b + bone.d * bone.d)
                ts = math.sqrt(tb * tb + td * td)
                if s > 0.00001:
                    s = (s + (ts - s + self.data.offset_scale_y) * scale_mix) / s
                bone.b *= s
                bone.d *= s
                bone.applied_valid = False
            if shear_mix > 0:
                b, d = bone.b, bone.d
                by = _atan2(d, b)
                r = _atan2(td, tb) - _atan2(tc, ta) - (by - _atan2(bone.c, bone.a))
                if r > PI:
                    r -= PI2
                elif r < -PI:
                    r += PI2
                r = by + (r + offset_shear_y) * shear_mix
                s = math.sqrt(b * b + d * d)
                bone.b = math.cos(r) * s
                bone.d = math.sin(r) * s
                bone.applied_valid = False


# ── 路径约束 ────────────────────────────────────────────
class PathConstraint:
    NONE = -1
    BEFORE = -2
    AFTER = -3
    epsilon = 0.00001

    def __init__(self, data, skeleton):
        self.data = data
        self.bones = [skeleton.bones[b.index] for b in data.bones]
        self.target = skeleton.slots[data.target.index]
        self.position = data.position
        self.spacing = data.spacing
        self.rotate_mix = data.rotate_mix
        self.translate_mix = data.translate_mix
        self.active = False
        self.spaces = [0.0] * 8
        self.positions = [0.0] * 8
        self.world = [0.0] * 8
        self.lengths = [0.0] * 8

    def apply(self):
        self.update()

    def update(self):
        from .loader import PathAttachment
        attachment = self.target.attachment
        if not isinstance(attachment, PathAttachment):
            return
        rotate_mix = self.rotate_mix
        translate_mix = self.translate_mix
        translate = translate_mix > 0
        rotate = rotate_mix > 0
        if not translate and not rotate:
            return
        data = self.data
        percent_spacing = data.spacing_mode == 2  # Percent
        rotate_mode = data.rotate_mode
        tangents = rotate_mode == ROTATE_TANGENT
        scale = rotate_mode == ROTATE_CHAIN_SCALE
        bone_count = len(self.bones)
        spaces_count = bone_count if tangents else bone_count + 1
        bones = self.bones
        if len(self.spaces) < spaces_count:
            self.spaces.extend([0.0] * (spaces_count - len(self.spaces)))
        spaces = self.spaces
        lengths = None
        spacing = self.spacing
        if scale or not percent_spacing:
            if scale:
                if len(self.lengths) < bone_count:
                    self.lengths.extend([0.0] * (bone_count - len(self.lengths)))
                lengths = self.lengths
            length_spacing = data.spacing_mode == SPACING_LENGTH
            for i in range(spaces_count - 1):
                bone = bones[i]
                setup_length = bone.data.length
                if setup_length < PathConstraint.epsilon:
                    if scale:
                        lengths[i] = 0.0
                    spaces[i + 1] = 0.0
                elif percent_spacing:
                    if scale:
                        x = setup_length * bone.a
                        y = setup_length * bone.c
                        lengths[i] = math.sqrt(x * x + y * y)
                    spaces[i + 1] = spacing
                else:
                    x = setup_length * bone.a
                    y = setup_length * bone.c
                    length = math.sqrt(x * x + y * y)
                    if scale:
                        lengths[i] = length
                    spaces[i + 1] = ((setup_length + spacing) if length_spacing else spacing) * length / setup_length
        else:
            for i in range(1, spaces_count):
                spaces[i] = spacing
        positions = self._compute_world_positions(attachment, spaces_count, tangents,
                                                  data.position_mode == 1, percent_spacing)
        bone_x = positions[0]
        bone_y = positions[1]
        offset_rotation = data.offset_rotation
        tip = False
        if offset_rotation == 0:
            tip = rotate_mode == ROTATE_CHAIN
        else:
            tip = False
            p = self.target.bone
            offset_rotation *= DEG_RAD if p.a * p.d - p.b * p.c > 0 else -DEG_RAD
        for i in range(bone_count):
            bone = bones[i]
            bone.world_x += (bone_x - bone.world_x) * translate_mix
            bone.world_y += (bone_y - bone.world_y) * translate_mix
            x = positions[(i + 1) * 3]
            y = positions[(i + 1) * 3 + 1]
            dx = x - bone_x
            dy = y - bone_y
            if scale:
                length = lengths[i]
                if length != 0:
                    s = (math.sqrt(dx * dx + dy * dy) / length - 1) * rotate_mix + 1
                    bone.a *= s
                    bone.c *= s
            bone_x = x
            bone_y = y
            if rotate:
                a, b, c, d = bone.a, bone.b, bone.c, bone.d
                if tangents:
                    r = positions[(i + 1) * 3 - 1]
                elif spaces[i + 1] == 0:
                    r = positions[(i + 1) * 3 + 2]
                else:
                    r = _atan2(dy, dx)
                r -= _atan2(c, a)
                if tip:
                    cos = math.cos(r)
                    sin = math.sin(r)
                    length = bone.data.length
                    bone_x += (length * (cos * a - sin * c) - dx) * rotate_mix
                    bone_y += (length * (sin * a + cos * c) - dy) * rotate_mix
                else:
                    r += offset_rotation
                if r > PI:
                    r -= PI2
                elif r < -PI:
                    r += PI2
                r *= rotate_mix
                cos = math.cos(r)
                sin = math.sin(r)
                bone.a = cos * a - sin * c
                bone.b = cos * b - sin * d
                bone.c = sin * a + cos * c
                bone.d = sin * b + cos * d
            bone.applied_valid = False

    def _compute_world_positions(self, path, spaces_count, tangents, percent_position, percent_spacing):
        target = self.target
        position = self.position
        spaces = self.spaces
        if len(self.positions) < spaces_count * 3 + 2:
            self.positions.extend([0.0] * (spaces_count * 3 + 2 - len(self.positions)))
        out = self.positions
        closed = path.closed
        vertices_length = path.world_vertices_length
        curve_count = vertices_length // 6
        prev_curve = PathConstraint.NONE
        from .skeleton import compute_mesh_vertices

        def compute_verts(start, count):
            return compute_mesh_vertices(target, path, start // 2, count // 2)

        if not path.constant_speed:
            lengths = path.lengths
            curve_count -= 1 if closed else 2
            path_length = lengths[curve_count]
            if percent_position:
                position *= path_length
            if percent_spacing:
                for i in range(1, spaces_count):
                    spaces[i] *= path_length
            if len(self.world) < 8:
                self.world = [0.0] * 8
            world = self.world
            o = 0
            curve = 0
            for i in range(spaces_count):
                space = spaces[i]
                position += space
                p = position
                if closed:
                    p %= path_length
                    if p < 0:
                        p += path_length
                    curve = 0
                elif p < 0:
                    if prev_curve != PathConstraint.BEFORE:
                        prev_curve = PathConstraint.BEFORE
                        w = compute_verts(2, 4)
                        world[0:4] = w[0:4]
                    self._add_before_position(p, world, 0, out, o)
                    o += 3
                    continue
                elif p > path_length:
                    if prev_curve != PathConstraint.AFTER:
                        prev_curve = PathConstraint.AFTER
                        w = compute_verts(vertices_length - 6, 4)
                        world[0:4] = w[0:4]
                    self._add_after_position(p - path_length, world, 0, out, o)
                    o += 3
                    continue
                while True:
                    length = lengths[curve]
                    if p > length:
                        curve += 1
                        continue
                    if curve == 0:
                        p /= length
                    else:
                        prev = lengths[curve - 1]
                        p = (p - prev) / (length - prev)
                    break
                if curve != prev_curve:
                    prev_curve = curve
                    if closed and curve == curve_count:
                        w1 = compute_verts(vertices_length - 4, 4)
                        w2 = compute_verts(0, 4)
                        world[0:4] = w1[0:4]
                        world[4:8] = w2[0:4]
                    else:
                        w = compute_verts(curve * 6 + 2, 8)
                        world[0:8] = w[0:8]
                self._add_curve_position(p, world[0], world[1], world[2], world[3],
                                         world[4], world[5], world[6], world[7], out, o,
                                         tangents or (i > 0 and space == 0))
                o += 3
            return out
        # constantSpeed 分支（本模型不使用，省略）
        return out

    @staticmethod
    def _add_before_position(p, temp, i, out, o):
        x1 = temp[i]
        y1 = temp[i + 1]
        dx = temp[i + 2] - x1
        dy = temp[i + 3] - y1
        r = _atan2(dy, dx)
        out[o] = x1 + p * math.cos(r)
        out[o + 1] = y1 + p * math.sin(r)
        out[o + 2] = r

    @staticmethod
    def _add_after_position(p, temp, i, out, o):
        x1 = temp[i + 2]
        y1 = temp[i + 3]
        dx = x1 - temp[i]
        dy = y1 - temp[i + 1]
        r = _atan2(dy, dx)
        out[o] = x1 + p * math.cos(r)
        out[o + 1] = y1 + p * math.sin(r)
        out[o + 2] = r

    @staticmethod
    def _add_curve_position(p, x1, y1, cx1, cy1, cx2, cy2, x2, y2, out, o, tangents):
        if p == 0 or math.isnan(p):
            out[o] = x1
            out[o + 1] = y1
            out[o + 2] = _atan2(cy1 - y1, cx1 - x1)
            return
        tt = p * p
        ttt = tt * p
        u = 1 - p
        uu = u * u
        uuu = uu * u
        ut = u * p
        ut3 = ut * 3
        uut3 = u * ut3
        utt3 = ut3 * p
        x = x1 * uuu + cx1 * uut3 + cx2 * utt3 + x2 * ttt
        y = y1 * uuu + cy1 * uut3 + cy2 * utt3 + y2 * ttt
        out[o] = x
        out[o + 1] = y
        if tangents:
            if p < 0.001:
                out[o + 2] = _atan2(cy1 - y1, cx1 - x1)
            else:
                out[o + 2] = _atan2(y - (y1 * uu + cy1 * ut * 2 + cy2 * tt),
                                    x - (x1 * uu + cx1 * ut * 2 + cx2 * tt))


def apply_constraints(skeleton):
    """兼容入口：使用骨架上的持久约束实例。"""
    for c in skeleton.ik_constraints:
        c.apply()
    for c in skeleton.transform_constraints:
        c.apply()
    for c in skeleton.path_constraints:
        c.apply()
