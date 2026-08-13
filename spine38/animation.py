"""Spine 3.8 动画状态机 — 精确移植自 spine-ts 3.8（含反向百分比/旋转环绕语义）."""
import math


# ── 曲线求值 ────────────────────────────────────────────
def _bezier(t, p0, p1, p2, p3):
    mt = 1.0 - t
    return mt * mt * mt * p0 + 3 * mt * mt * t * p1 + 3 * mt * t * t * p2 + t * t * t * p3


def _bezier_x(t, cx1, cx2):
    return _bezier(t, 0.0, cx1, cx2, 1.0)


def _bezier_y(t, cy1, cy2):
    return _bezier(t, 0.0, cy1, cy2, 1.0)


def curve_percent(curve, x):
    """曲线时间映射：x∈[0,1]，返回插值进度（JS getCurvePercent 语义）。"""
    if curve == 0 or curve is None:  # linear
        return x
    if curve == 1:  # stepped
        return 0.0
    cx1, cy1, cx2, cy2 = curve
    epsilon = 0.00001
    t = x
    for _ in range(8):
        xt = _bezier_x(t, cx1, cx2) - x
        if abs(xt) < epsilon:
            return _bezier_y(t, cy1, cy2)
        d = 3 * (1 - t) * (1 - t) * (cx1 - 0) + 6 * (1 - t) * t * (cx2 - cx1) + 3 * t * t * (1 - cx2)
        if abs(d) < 0.0001:
            break
        t -= xt / d
    lo, hi = 0.0, 1.0
    t = x
    if t < lo:
        return _bezier_y(lo, cy1, cy2)
    if t > hi:
        return _bezier_y(hi, cy1, cy2)
    while lo < hi:
        xt = _bezier_x(t, cx1, cx2)
        if abs(xt - x) < epsilon:
            return _bezier_y(t, cy1, cy2)
        if x > xt:
            lo = t
        else:
            hi = t
        t = (hi - lo) / 2 + lo
    return _bezier_y(t, cy1, cy2)


def _wrap_angle(value):
    """JS 的 16384 角度环绕技巧：包装到 [-180, 180)。"""
    value -= (16384 - math.floor(16384.499999999996 - value / 360.0)) * 360.0
    return value


def _binary_search(frames, time, entries):
    """返回时间所在帧区间的【下一帧】索引（JS Animation.binarySearch 语义）。"""
    n = len(frames) // entries
    if time <= frames[0]:
        return entries  # 指向第二帧（若存在）
    if time >= frames[(n - 1) * entries]:
        return (n - 1) * entries
    lo, hi = 1, n - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if frames[mid * entries] <= time:
            lo = mid + 1
        else:
            hi = mid
    return lo * entries


def _frame_percent(frames, curves, time, entries):
    """按 JS 语义计算插值百分比（反向输入 + 曲线）。返回 (percent, next_frame_index)。"""
    n = len(frames) // entries
    if n == 1 or time >= frames[(n - 1) * entries]:
        return 1.0, (n - 1) * entries
    if time < frames[0]:
        return 0.0, 0
    frame = _binary_search(frames, time, entries)  # 下一帧索引
    frame_time = frames[frame - entries]
    next_time = frames[frame]
    percent = (time - frame_time) / (next_time - frame_time) if next_time > frame_time else 0.0
    curve = curves[(frame // entries) - 1] if (frame // entries) - 1 < len(curves) else 0
    return curve_percent(curve, percent), frame


def _lerp(a, b, p):
    return a + (b - a) * p


# ── 时间线应用（JS blend=first + alpha 语义） ─────────────
def apply_rotate(tl, skeleton, time, alpha=1.0):
    frames = tl["frames"]
    curves = tl.get("curves", [])
    bone = skeleton.bones[tl["bone"]]
    n = len(frames)
    if time < frames[0][0]:
        # blend=first: 向 setup 值靠拢
        r = bone.data.rotation - bone.rotation
        r = _wrap_angle(r)
        bone.rotation += r * alpha
        return
    if time >= frames[-1][0]:
        # PREV_ROTATION = 最后一帧自身的旋转值
        prev_rot = frames[-1][1]
        r = frames[-1][1] - prev_rot
        r = _wrap_angle(r)
        r = prev_rot + r
        r += bone.data.rotation - bone.rotation
        bone.rotation += _wrap_angle(r) * alpha
        return
    # 二分定位下一帧
    ts = [f[0] for f in frames]
    frame = _binary_search(ts, time, 1)
    fi = frame - 1  # 当前帧索引
    # PREV_ROTATION = 当前帧自身的旋转值
    prev_rot = frames[fi][1]
    frame_time = frames[fi][0]
    next_time = frames[fi + 1][0]
    percent = (time - frame_time) / (next_time - frame_time) if next_time > frame_time else 0.0
    curve = curves[fi] if fi < len(curves) else 0
    percent = curve_percent(curve, percent)
    r = frames[fi + 1][1] - prev_rot
    r = _wrap_angle(r)
    r = prev_rot + r * percent
    r += bone.data.rotation - bone.rotation
    bone.rotation += _wrap_angle(r) * alpha


def apply_translate(tl, skeleton, time, alpha=1.0):
    """平移时间线：帧值是对 data 的偏移（blend=first 语义）。"""
    frames = tl["frames"]
    curves = tl.get("curves", [])
    bone = skeleton.bones[tl["bone"]]
    if time < frames[0][0]:
        bone.x += (bone.data.x - bone.x) * alpha
        bone.y += (bone.data.y - bone.y) * alpha
        return
    if time >= frames[-1][0]:
        x, y = frames[-1][1], frames[-1][2]
    else:
        ts = [f[0] for f in frames]
        frame = _binary_search(ts, time, 1)
        fi = frame - 1
        x0, y0 = frames[fi][1], frames[fi][2]
        x1, y1 = frames[fi + 1][1], frames[fi + 1][2]
        frame_time = frames[fi][0]
        next_time = frames[fi + 1][0]
        percent = (time - frame_time) / (next_time - frame_time) if next_time > frame_time else 0.0
        curve = curves[fi] if fi < len(curves) else 0
        percent = curve_percent(curve, percent)
        x = _lerp(x0, x1, percent)
        y = _lerp(y0, y1, percent)
    bone.x += (bone.data.x + x - bone.x) * alpha
    bone.y += (bone.data.y + y - bone.y) * alpha


def apply_scale_shear(tl, skeleton, time, alpha, is_scale):
    """缩放时间线：帧值是对 data 的倍率；剪切：帧值是对 data 的偏移。"""
    frames = tl["frames"]
    curves = tl.get("curves", [])
    bone = skeleton.bones[tl["bone"]]
    if time < frames[0][0]:
        if is_scale:
            bone.scale_x += (bone.data.scale_x - bone.scale_x) * alpha
            bone.scale_y += (bone.data.scale_y - bone.scale_y) * alpha
        else:
            bone.shear_x += (bone.data.shear_x - bone.shear_x) * alpha
            bone.shear_y += (bone.data.shear_y - bone.shear_y) * alpha
        return
    if time >= frames[-1][0]:
        x, y = frames[-1][1], frames[-1][2]
    else:
        ts = [f[0] for f in frames]
        frame = _binary_search(ts, time, 1)
        fi = frame - 1
        x0, y0 = frames[fi][1], frames[fi][2]
        x1, y1 = frames[fi + 1][1], frames[fi + 1][2]
        frame_time = frames[fi][0]
        next_time = frames[fi + 1][0]
        percent = (time - frame_time) / (next_time - frame_time) if next_time > frame_time else 0.0
        curve = curves[fi] if fi < len(curves) else 0
        percent = curve_percent(curve, percent)
        x = _lerp(x0, x1, percent)
        y = _lerp(y0, y1, percent)
    if is_scale:
        # 倍率语义：raw × data
        vx = x * bone.data.scale_x
        vy = y * bone.data.scale_y
        bone.scale_x += (vx - bone.scale_x) * alpha
        bone.scale_y += (vy - bone.scale_y) * alpha
    else:
        # 偏移语义：data + raw
        vx = bone.data.shear_x + x
        vy = bone.data.shear_y + y
        bone.shear_x += (vx - bone.shear_x) * alpha
        bone.shear_y += (vy - bone.shear_y) * alpha


def apply_color(tl, skeleton, time, alpha=1.0):
    frames = tl["frames"]
    curves = tl.get("curves", [])
    slot = skeleton.slots[tl["slot"]]
    if time < frames[0][0]:
        f = frames[0]
    elif time >= frames[-1][0]:
        f = frames[-1]
    else:
        ts = [f[0] for f in frames]
        frame = _binary_search(ts, time, 1)
        fi = frame - 1
        c0, c1 = frames[fi][1], frames[fi + 1][1]
        frame_time = frames[fi][0]
        next_time = frames[fi + 1][0]
        percent = (time - frame_time) / (next_time - frame_time) if next_time > frame_time else 0.0
        curve = curves[fi] if fi < len(curves) else 0
        percent = curve_percent(curve, percent)
        from .utils import Color
        f = (frames[fi][0], Color(_lerp(c0.r, c1.r, percent), _lerp(c0.g, c1.g, percent),
                                  _lerp(c0.b, c1.b, percent), _lerp(c0.a, c1.a, percent)), None)
    c = f[1]
    slot.color.r += (c.r - slot.color.r) * alpha
    slot.color.g += (c.g - slot.color.g) * alpha
    slot.color.b += (c.b - slot.color.b) * alpha
    slot.color.a += (c.a - slot.color.a) * alpha


def apply_attachment(tl, skeleton, time, alpha):
    frames = tl["frames"]
    slot_index = tl["slot"]
    name = frames[0][1]
    for t, n in frames:
        if time >= t:
            name = n
        else:
            break
    slot = skeleton.slots[slot_index]
    if alpha < 0.5:
        return
    slot.attachment = skeleton.get_attachment(slot_index, name) if name else None


def apply_deform(tl, skeleton, time, alpha=1.0):
    """变形写入 slot.deform 缓冲区（JS 语义）：非加权=绝对坐标，加权=增量。"""
    frames = tl["frames"]
    curves = tl.get("curves", [])
    attachment = tl["attachment"]
    slot_index = tl["slot"]
    if attachment is None:
        return
    slot = skeleton.slots[slot_index]
    cur_att = slot.attachment
    if cur_att is None:
        return
    # JS 守卫：当前附件的变形目标必须匹配
    target = getattr(cur_att, "deform_attachment", None) or cur_att
    if target is not attachment:
        return
    if time < frames[0][0]:
        # blend=first alpha=1：清空变形（回到基础顶点）
        slot.deform.clear()
        return
    deform = None
    if time >= frames[-1][0]:
        deform = frames[-1][1]
    else:
        ts = [f[0] for f in frames]
        frame = _binary_search(ts, time, 1)
        fi = frame - 1
        d0 = frames[fi][1]
        d1 = frames[fi + 1][1]
        frame_time = frames[fi][0]
        next_time = frames[fi + 1][0]
        percent = (time - frame_time) / (next_time - frame_time) if next_time > frame_time else 0.0
        curve = curves[fi] if fi < len(curves) else 0
        percent = curve_percent(curve, percent)
        deform = [_lerp(d0[i], d1[i], percent) for i in range(len(d0))]
    if alpha >= 1:
        slot.deform = list(deform)
    else:
        if len(slot.deform) < len(deform):
            slot.deform = [0.0] * len(deform)
        for i in range(len(deform)):
            slot.deform[i] += (deform[i] - slot.deform[i]) * alpha


def apply_draw_order(tl, skeleton, time):
    frames = tl["frames"]
    slot_count = len(skeleton.slots)
    if time < frames[0][0]:
        offsets = frames[0][1]
    elif time >= frames[-1][0]:
        offsets = frames[-1][1]
    else:
        offsets = frames[0][1]
        for t, o in frames:
            if time >= t:
                offsets = o
            else:
                break
    draw_order = [-1] * slot_count
    unchanged = []
    original_index = 0
    for slot_i, off in offsets:
        while original_index != slot_i:
            unchanged.append(original_index)
            original_index += 1
        draw_order[original_index + off] = original_index
        original_index += 1
    while original_index < slot_count:
        unchanged.append(original_index)
        original_index += 1
    ui = len(unchanged) - 1
    for i in range(slot_count - 1, -1, -1):
        if draw_order[i] == -1:
            draw_order[i] = unchanged[ui]
            ui -= 1
    skeleton.draw_order = [skeleton.slots[i] for i in draw_order]


# ── 约束时间线 ──────────────────────────────────────────
def apply_ik_timelines(animation, skeleton, time, alpha=1.0):
    for tl in animation.ik_timelines:
        c = skeleton.ik_constraints[tl["index"]]
        frames = tl["frames"]
        curves = tl.get("curves", [])
        if time < frames[0][0]:
            f = frames[0]
        elif time >= frames[-1][0]:
            f = frames[-1]
        else:
            ts = [x[0] for x in frames]
            frame = _binary_search(ts, time, 1)
            fi = frame - 1
            f0 = frames[fi]
            f1 = frames[fi + 1]
            frame_time = f0[0]
            next_time = f1[0]
            percent = (time - frame_time) / (next_time - frame_time) if next_time > frame_time else 0.0
            curve = curves[fi] if fi < len(curves) else 0
            percent = curve_percent(curve, percent)
            f = tuple(_lerp(a, b, percent) for a, b in zip(f0, f1))
        t, mix, softness, bend, compress, stretch = f
        c.mix += (mix - c.mix) * alpha
        c.softness += (softness - c.softness) * alpha
        if alpha >= 1:
            c.bend_direction = int(bend)
            c.compress = bool(compress)
            c.stretch = bool(stretch)


def apply_transform_timelines(animation, skeleton, time, alpha=1.0):
    for tl in animation.transform_timelines:
        c = skeleton.transform_constraints[tl["index"]]
        frames = tl["frames"]
        curves = tl.get("curves", [])
        if time < frames[0][0]:
            f = frames[0]
        elif time >= frames[-1][0]:
            f = frames[-1]
        else:
            ts = [x[0] for x in frames]
            frame = _binary_search(ts, time, 1)
            fi = frame - 1
            f0 = frames[fi]
            f1 = frames[fi + 1]
            frame_time = f0[0]
            next_time = f1[0]
            percent = (time - frame_time) / (next_time - frame_time) if next_time > frame_time else 0.0
            curve = curves[fi] if fi < len(curves) else 0
            percent = curve_percent(curve, percent)
            f = tuple(_lerp(a, b, percent) for a, b in zip(f0, f1))
        t, rm, tm, sm, hm = f
        c.rotate_mix += (rm - c.rotate_mix) * alpha
        c.translate_mix += (tm - c.translate_mix) * alpha
        c.scale_mix += (sm - c.scale_mix) * alpha
        c.shear_mix += (hm - c.shear_mix) * alpha


def apply_path_timelines(animation, skeleton, time, alpha=1.0):
    for tl in animation.path_timelines:
        c = skeleton.path_constraints[tl["index"]]
        frames = tl["frames"]
        if time < frames[0][0]:
            f = frames[0]
        elif time >= frames[-1][0]:
            f = frames[-1]
        else:
            ts = [x[0] for x in frames]
            frame = _binary_search(ts, time, 1)
            fi = frame - 1
            f0 = frames[fi]
            f1 = frames[fi + 1]
            frame_time = f0[0]
            next_time = f1[0]
            percent = (time - frame_time) / (next_time - frame_time) if next_time > frame_time else 0.0
            f = tuple(_lerp(a, b, percent) for a, b in zip(f0, f1))
        if tl["type"] == "position":
            c.position += (f[1] - c.position) * alpha
        elif tl["type"] == "spacing":
            c.spacing += (f[1] - c.spacing) * alpha
        else:  # mix
            c.rotate_mix += (f[1] - c.rotate_mix) * alpha
            c.translate_mix += (f[2] - c.translate_mix) * alpha


def reset_constraints(skeleton):
    for c in skeleton.ik_constraints:
        c.mix = c.data.mix
        c.softness = c.data.softness
        c.bend_direction = c.data.bend_direction
        c.compress = c.data.compress
        c.stretch = c.data.stretch
        c.uniform = c.data.uniform
    for c in skeleton.transform_constraints:
        c.rotate_mix = c.data.rotate_mix
        c.translate_mix = c.data.translate_mix
        c.scale_mix = c.data.scale_mix
        c.shear_mix = c.data.shear_mix
    for c in skeleton.path_constraints:
        c.position = c.data.position
        c.spacing = c.data.spacing
        c.rotate_mix = c.data.rotate_mix
        c.translate_mix = c.data.translate_mix


def apply_animation(animation, skeleton, time, loop, alpha=1.0):
    """应用动画全部时间线（JS blend=first + direction=mixIn 语义，alpha=1 时等价）。"""
    if animation is None:
        return
    duration = animation.duration
    if loop and duration > 0:
        time = time % duration
    reset_constraints(skeleton)
    for tl in animation.bone_timelines:
        if tl["type"] == "rotate":
            apply_rotate(tl, skeleton, time, alpha)
        elif tl["type"] == "translate":
            apply_translate(tl, skeleton, time, alpha)
        else:
            apply_scale_shear(tl, skeleton, time, alpha, tl["type"] == "scale")
    for tl in animation.slot_timelines:
        if tl["type"] == "attachment":
            apply_attachment(tl, skeleton, time, alpha)
        else:
            apply_color(tl, skeleton, time, alpha)
    for tl in animation.deform_timelines:
        apply_deform(tl, skeleton, time, alpha)
    for tl in animation.draw_order_timelines:
        apply_draw_order(tl, skeleton, time)
    apply_ik_timelines(animation, skeleton, time, alpha)
    apply_transform_timelines(animation, skeleton, time, alpha)
    apply_path_timelines(animation, skeleton, time, alpha)


# ── 动画状态机（单轨） ───────────────────────────────────
class TrackEntry:
    def __init__(self, animation, loop, mix_duration=0.0):
        self.animation = animation
        self.loop = loop
        self.mix_duration = mix_duration
        self.time = 0.0
        self.last_time = -1.0
        self.alpha = 1.0
        self.hold = False


class AnimationStateImpl:
    """单轨状态机：setAnimation/update/apply。"""

    def __init__(self, skeleton_data):
        self.skeleton_data = skeleton_data
        self.track = None

    def set_animation(self, track_index, name, loop, mix_duration=0.0):
        anim = self.skeleton_data.find_animation(name)
        if anim is None:
            return None
        self.track = TrackEntry(anim, loop, mix_duration)
        return self.track

    def get_current(self, track_index=0):
        return self.track

    def update(self, delta):
        if self.track is None:
            return
        self.track.time += delta
        if not self.track.loop and self.track.animation.duration > 0:
            if self.track.time >= self.track.animation.duration:
                self.track.time = self.track.animation.duration
                self.track.hold = True

    def apply(self, skeleton):
        if self.track is None:
            return
        skeleton.set_to_setup_pose()
        apply_animation(self.track.animation, skeleton, self.track.time,
                        self.track.loop, self.track.alpha)
        skeleton.update_world_transform()

    def is_finished(self, track_index=0):
        return self.track is not None and self.track.hold
