"""Spine 3.8 binary skeleton loader — ported from spine-ts 3.8 SkeletonBinary."""
import struct
from .utils import Color, deg_to_rad

# ── 枚举 ──────────────────────────────────────────────
ATTACHMENT_REGION = 0
ATTACHMENT_BOUNDING_BOX = 1
ATTACHMENT_MESH = 2
ATTACHMENT_LINKED_MESH = 3
ATTACHMENT_PATH = 4
ATTACHMENT_POINT = 5
ATTACHMENT_CLIPPING = 6

BLEND_NORMAL = 0
BLEND_ADDITIVE = 1
BLEND_MULTIPLY = 2
BLEND_SCREEN = 3

TRANSFORM_NORMAL = 0
TRANSFORM_ONLY_TRANSLATION = 1
TRANSFORM_NO_ROTATION_OR_REFLECTION = 2
TRANSFORM_NO_SCALE = 3
TRANSFORM_NO_SCALE_OR_REFLECTION = 4

POSITION_FIXED = 0
POSITION_PERCENT = 1

SPACING_LENGTH = 0
SPACING_FIXED = 1
SPACING_PERCENT = 2

ROTATE_TANGENT = 0
ROTATE_CHAIN = 1
ROTATE_CHAIN_SCALE = 2

# 时间线类型
SLOT_ATTACHMENT = 0
SLOT_COLOR = 1
SLOT_TWO_COLOR = 2
BONE_ROTATE = 3
BONE_TRANSLATE = 4
BONE_SCALE = 5
BONE_SHEAR = 6
PATH_POSITION = 7
PATH_SPACING = 8
PATH_MIX = 9
DEFORM = 10
EVENT = 11
DRAW_ORDER = 12


# ── 数据类 ─────────────────────────────────────────────
class BoneData:
    def __init__(self, index, name, parent):
        self.index = index
        self.name = name
        self.parent = parent
        self.length = 0.0
        self.x = self.y = 0.0
        self.rotation = 0.0
        self.scale_x = self.scale_y = 1.0
        self.shear_x = self.shear_y = 0.0
        self.transform_mode = TRANSFORM_NORMAL
        self.skin_required = False
        self.color = Color()


class SlotData:
    def __init__(self, index, name, bone_data):
        self.index = index
        self.name = name
        self.bone_data = bone_data
        self.color = Color()
        self.dark_color = None
        self.attachment_name = None
        self.blend_mode = BLEND_NORMAL


class IkConstraintData:
    def __init__(self, name):
        self.name = name
        self.order = 0
        self.skin_required = False
        self.bones = []
        self.target = None
        self.mix = 1.0
        self.softness = 0.0
        self.bend_direction = 1
        self.compress = False
        self.stretch = False
        self.uniform = False


class TransformConstraintData:
    def __init__(self, name):
        self.name = name
        self.order = 0
        self.skin_required = False
        self.bones = []
        self.target = None
        self.local = False
        self.relative = False
        self.offset_rotation = 0.0
        self.offset_x = self.offset_y = 0.0
        self.offset_scale_x = self.offset_scale_y = 1.0
        self.offset_shear_y = 0.0
        self.rotate_mix = self.translate_mix = self.scale_mix = self.shear_mix = 1.0


class PathConstraintData:
    def __init__(self, name):
        self.name = name
        self.order = 0
        self.skin_required = False
        self.bones = []
        self.target = None
        self.position_mode = POSITION_FIXED
        self.spacing_mode = SPACING_LENGTH
        self.rotate_mode = ROTATE_TANGENT
        self.offset_rotation = 0.0
        self.position = 0.0
        self.spacing = 0.0
        self.rotate_mix = self.translate_mix = 1.0


class EventData:
    def __init__(self, name):
        self.name = name
        self.int_value = 0
        self.float_value = 0.0
        self.string_value = None
        self.audio_path = None
        self.volume = 0.0
        self.balance = 0.0


# ── 附件 ──────────────────────────────────────────────
class RegionAttachment:
    def __init__(self, name):
        self.name = name
        self.path = None
        self.x = self.y = 0.0
        self.scale_x = self.scale_y = 1.0
        self.rotation = 0.0
        self.width = self.height = 0.0
        self.color = Color()
        self.region = None
        self.offset = [0.0] * 8

    def update_offset(self):
        """照 spine-ts 3.8 RegionAttachment.updateOffset 移植。
        角点顺序：BL, TL, TR, BR（JS OX1..OX4）。"""
        import math
        r = self.region
        ow = r.original_width or r.width
        oh = r.original_height or r.height
        region_scale_x = self.width / ow * self.scale_x
        region_scale_y = self.height / oh * self.scale_y
        local_x = -self.width / 2.0 * self.scale_x + r.offset_x * region_scale_x
        local_y = -self.height / 2.0 * self.scale_y + r.offset_y * region_scale_y
        local_x2 = local_x + r.width * region_scale_x
        local_y2 = local_y + r.height * region_scale_y
        radians = deg_to_rad(self.rotation)
        cos = math.cos(radians)
        sin = math.sin(radians)
        local_x_cos = local_x * cos + self.x
        local_x_sin = local_x * sin
        local_y_cos = local_y * cos + self.y
        local_y_sin = local_y * sin
        local_x2_cos = local_x2 * cos + self.x
        local_x2_sin = local_x2 * sin
        local_y2_cos = local_y2 * cos + self.y
        local_y2_sin = local_y2 * sin
        self.offset[0] = local_x_cos - local_y_sin
        self.offset[1] = local_y_cos + local_x_sin
        self.offset[2] = local_x_cos - local_y2_sin
        self.offset[3] = local_y2_cos + local_x_sin
        self.offset[4] = local_x2_cos - local_y2_sin
        self.offset[5] = local_y2_cos + local_x2_sin
        self.offset[6] = local_x2_cos - local_y_sin
        self.offset[7] = local_y_cos + local_x2_sin


class MeshAttachment:
    def __init__(self, name):
        self.name = name
        self.path = None
        self.color = Color()
        self.bones = None
        self.vertices = None
        self.world_vertices_length = 0
        self.triangles = None
        self.region_uvs = None
        self.uvs = None
        self.hull_length = 0
        self.edges = None
        self.width = self.height = 0.0
        self.region = None
        self.parent_mesh = None
        self.deform_attachment = None
        self.base_vertices = None  # setup 恢复用

    def update_uvs(self):
        """照 spine-ts 3.8 MeshAttachment.updateUVs 移植。
        二进制里 region_uvs 是相对区域原始空间的归一化坐标（0~1）。"""
        if self.uvs is None or len(self.uvs) != len(self.region_uvs):
            self.uvs = [0.0] * len(self.region_uvs)
        region = self.region
        if region is None:
            return
        tw = region.page_width or 1.0
        th = region.page_height or 1.0
        u = region.u
        v = region.v
        ruvs = self.region_uvs
        uvs = self.uvs
        ow = region.original_width or region.width
        oh = region.original_height or region.height
        if region.degrees == 90:
            u -= (oh - region.offset_y - region.height) / tw
            v -= (ow - region.offset_x - region.width) / th
            width = oh / tw
            height = ow / th
            for i in range(0, len(ruvs), 2):
                uvs[i] = u + ruvs[i + 1] * width
                uvs[i + 1] = v + (1.0 - ruvs[i]) * height
        elif region.degrees == 180:
            u -= (ow - region.offset_x - region.width) / tw
            v -= region.offset_y / th
            width = ow / tw
            height = oh / th
            for i in range(0, len(ruvs), 2):
                uvs[i] = u + (1.0 - ruvs[i]) * width
                uvs[i + 1] = v + (1.0 - ruvs[i + 1]) * height
        elif region.degrees == 270:
            u -= region.offset_y / tw
            v -= region.offset_x / th
            width = oh / tw
            height = ow / th
            for i in range(0, len(ruvs), 2):
                uvs[i] = u + (1.0 - ruvs[i + 1]) * width
                uvs[i + 1] = v + ruvs[i] * height
        else:
            u -= region.offset_x / tw
            v -= (oh - region.offset_y - region.height) / th
            width = ow / tw
            height = oh / th
            for i in range(0, len(ruvs), 2):
                uvs[i] = u + ruvs[i] * width
                uvs[i + 1] = v + ruvs[i + 1] * height


class BoundingBoxAttachment:
    def __init__(self, name):
        self.name = name
        self.vertices = None
        self.bones = None
        self.world_vertices_length = 0
        self.color = Color()


class PathAttachment:
    def __init__(self, name):
        self.name = name
        self.closed = False
        self.constant_speed = False
        self.vertices = None
        self.bones = None
        self.lengths = None
        self.world_vertices_length = 0
        self.color = Color()


class PointAttachment:
    def __init__(self, name):
        self.name = name
        self.x = self.y = self.rotation = 0.0
        self.color = Color()


class ClippingAttachment:
    def __init__(self, name):
        self.name = name
        self.end_slot = None
        self.vertices = None
        self.bones = None
        self.world_vertices_length = 0
        self.color = Color()


# ── 图集区域（渲染时由 atlas.py 填充） ───────────────────
class AtlasRegion:
    def __init__(self):
        self.page = None
        self.name = ""
        self.u = self.v = self.u2 = self.v2 = 0.0
        self.x = self.y = 0
        self.width = self.height = 0
        self.original_width = self.original_height = 0
        self.offset_x = self.offset_y = 0
        self.page_width = 0
        self.page_height = 0
        self.degrees = 0
        self.rotate = False


class AttachmentLoader:
    def new_region_attachment(self, skin, name, path):
        raise NotImplementedError

    def new_mesh_attachment(self, skin, name, path):
        raise NotImplementedError

    def new_bounding_box_attachment(self, skin, name):
        raise NotImplementedError

    def new_path_attachment(self, skin, name):
        raise NotImplementedError

    def new_point_attachment(self, skin, name):
        raise NotImplementedError

    def new_clipping_attachment(self, skin, name):
        raise NotImplementedError


# ── 皮肤 ──────────────────────────────────────────────
class Skin:
    def __init__(self, name):
        self.name = name
        self.attachments = {}  # (slot_index, name) -> attachment

    def set_attachment(self, slot_index, name, attachment):
        self.attachments[(slot_index, name)] = attachment

    def get_attachment(self, slot_index, name):
        return self.attachments.get((slot_index, name))


# ── 骨骼数据 ──────────────────────────────────────────
class SkeletonData:
    def __init__(self):
        self.name = ""
        self.bones = []
        self.slots = []
        self.skins = []
        self.default_skin = None
        self.events = []
        self.animations = []
        self.ik_constraints = []
        self.transform_constraints = []
        self.path_constraints = []
        self.x = self.y = 0.0
        self.width = self.height = 0.0
        self.version = None
        self.hash = None
        self.fps = 0.0

    def find_bone(self, name):
        for b in self.bones:
            if b.name == name:
                return b
        return None

    def find_skin(self, name):
        for s in self.skins:
            if s.name == name:
                return s
        return None

    def find_event(self, name):
        for e in self.events:
            if e.name == name:
                return e
        return None

    def find_animation(self, name):
        for a in self.animations:
            if a.name == name:
                return a
        return None


# ── 二进制读取器 ──────────────────────────────────────
class BinaryInput:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0
        self.strings = []

    def read_byte(self):
        v = self.data[self.pos]
        self.pos += 1
        return v

    def read_sbyte(self):
        v = self.data[self.pos]
        self.pos += 1
        return v - 256 if v > 127 else v

    def read_boolean(self):
        return self.read_byte() != 0

    def read_short(self):
        v = struct.unpack_from(">h", self.data, self.pos)[0]
        self.pos += 2
        return v

    def read_int(self, optimize_positive=False):
        b = self.read_byte()
        result = b & 0x7F
        if (b & 0x80) != 0:
            b = self.read_byte()
            result |= (b & 0x7F) << 7
            if (b & 0x80) != 0:
                b = self.read_byte()
                result |= (b & 0x7F) << 14
                if (b & 0x80) != 0:
                    b = self.read_byte()
                    result |= (b & 0x7F) << 21
                    if (b & 0x80) != 0:
                        b = self.read_byte()
                        result |= (b & 0x7F) << 28
        # JS 的 << 是 32 位有符号运算：高位溢出会变成负数（如绘制顺序的 -44 偏移）
        result &= 0xFFFFFFFF
        if result >= 0x80000000:
            result -= 0x100000000
        return result if optimize_positive else (result >> 1) ^ -(result & 1)

    def read_int32(self):
        v = struct.unpack_from(">i", self.data, self.pos)[0]
        self.pos += 4
        return v

    def read_float(self):
        v = struct.unpack_from(">f", self.data, self.pos)[0]
        self.pos += 4
        return v

    def read_string(self):
        n = self.read_int(True)
        if n == 0:
            return None
        if n == 1:
            return ""
        n -= 1
        s = self.data[self.pos:self.pos + n].decode("latin-1")
        self.pos += n
        return s

    def read_string_ref(self):
        idx = self.read_int(True)
        if idx == 0:
            return None
        idx -= 1
        if idx < len(self.strings):
            return self.strings[idx]
        return None


# ── 骨骼加载器 ────────────────────────────────────────
class SkeletonBinary:
    def __init__(self, attachment_loader: AttachmentLoader):
        self.scale = 1.0
        self.attachment_loader = attachment_loader
        self.linked_meshes = []

    def read_skeleton_data(self, data: bytes) -> SkeletonData:
        scale = self.scale
        sd = SkeletonData()
        inp = BinaryInput(data)
        sd.hash = inp.read_string()
        sd.version = inp.read_string()
        if sd.version == "3.8.75":
            raise ValueError("Unsupported skeleton data, please export with a newer version of Spine.")
        sd.x = inp.read_float()
        sd.y = inp.read_float()
        sd.width = inp.read_float()
        sd.height = inp.read_float()
        nonessential = inp.read_boolean()
        if nonessential:
            sd.fps = inp.read_float()
            inp.read_string()  # images path
            inp.read_string()  # audio path

        n = inp.read_int(True)
        for _ in range(n):
            inp.strings.append(inp.read_string())

        n = inp.read_int(True)
        for i in range(n):
            name = inp.read_string()
            parent = None if i == 0 else sd.bones[inp.read_int(True)]
            bd = BoneData(i, name, parent)
            bd.rotation = inp.read_float()
            bd.x = inp.read_float() * scale
            bd.y = inp.read_float() * scale
            bd.scale_x = inp.read_float()
            bd.scale_y = inp.read_float()
            bd.shear_x = inp.read_float()
            bd.shear_y = inp.read_float()
            bd.length = inp.read_float() * scale
            bd.transform_mode = inp.read_int(True)
            bd.skin_required = inp.read_boolean()
            if nonessential:
                Color.rgba8888(bd.color, inp.read_int32())
            sd.bones.append(bd)

        n = inp.read_int(True)
        for i in range(n):
            slot_name = inp.read_string()
            bone_data = sd.bones[inp.read_int(True)]
            sld = SlotData(i, slot_name, bone_data)
            Color.rgba8888(sld.color, inp.read_int32())
            dark = inp.read_int32()
            if dark != -1:
                sld.dark_color = Color()
                Color.rgb888(sld.dark_color, dark)
            sld.attachment_name = inp.read_string_ref()
            sld.blend_mode = inp.read_int(True)
            sd.slots.append(sld)

        n = inp.read_int(True)
        for _ in range(n):
            d = IkConstraintData(inp.read_string())
            d.order = inp.read_int(True)
            d.skin_required = inp.read_boolean()
            nn = inp.read_int(True)
            for _ in range(nn):
                d.bones.append(sd.bones[inp.read_int(True)])
            d.target = sd.bones[inp.read_int(True)]
            d.mix = inp.read_float()
            d.softness = inp.read_float() * scale
            d.bend_direction = inp.read_sbyte()
            d.compress = inp.read_boolean()
            d.stretch = inp.read_boolean()
            d.uniform = inp.read_boolean()
            sd.ik_constraints.append(d)

        n = inp.read_int(True)
        for _ in range(n):
            d = TransformConstraintData(inp.read_string())
            d.order = inp.read_int(True)
            d.skin_required = inp.read_boolean()
            nn = inp.read_int(True)
            for _ in range(nn):
                d.bones.append(sd.bones[inp.read_int(True)])
            d.target = sd.bones[inp.read_int(True)]
            d.local = inp.read_boolean()
            d.relative = inp.read_boolean()
            d.offset_rotation = inp.read_float()
            d.offset_x = inp.read_float() * scale
            d.offset_y = inp.read_float() * scale
            d.offset_scale_x = inp.read_float()
            d.offset_scale_y = inp.read_float()
            d.offset_shear_y = inp.read_float()
            d.rotate_mix = inp.read_float()
            d.translate_mix = inp.read_float()
            d.scale_mix = inp.read_float()
            d.shear_mix = inp.read_float()
            sd.transform_constraints.append(d)

        n = inp.read_int(True)
        for _ in range(n):
            d = PathConstraintData(inp.read_string())
            d.order = inp.read_int(True)
            d.skin_required = inp.read_boolean()
            nn = inp.read_int(True)
            for _ in range(nn):
                d.bones.append(sd.bones[inp.read_int(True)])
            d.target = sd.slots[inp.read_int(True)]
            d.position_mode = inp.read_int(True)
            d.spacing_mode = inp.read_int(True)
            d.rotate_mode = inp.read_int(True)
            d.offset_rotation = inp.read_float()
            d.position = inp.read_float()
            if d.position_mode == POSITION_FIXED:
                d.position *= scale
            d.spacing = inp.read_float()
            if d.spacing_mode in (SPACING_LENGTH, SPACING_FIXED):
                d.spacing *= scale
            d.rotate_mix = inp.read_float()
            d.translate_mix = inp.read_float()
            sd.path_constraints.append(d)

        default_skin = self._read_skin(inp, sd, True, nonessential)
        if default_skin is not None:
            sd.default_skin = default_skin
            sd.skins.append(default_skin)

        n = inp.read_int(True)
        for _ in range(n):
            sd.skins.append(self._read_skin(inp, sd, False, nonessential))

        # linked meshes
        for lm in self.linked_meshes:
            skin = sd.default_skin if lm["skin"] is None else sd.find_skin(lm["skin"])
            if skin is None:
                raise ValueError("Skin not found: " + str(lm["skin"]))
            parent = skin.get_attachment(lm["slot_index"], lm["parent"])
            if parent is None:
                raise ValueError("Parent mesh not found: " + str(lm["parent"]))
            lm["mesh"].deform_attachment = parent if lm["inherit_deform"] else lm["mesh"]
            lm["mesh"].parent_mesh = parent
            lm["mesh"].update_uvs()
        self.linked_meshes = []

        n = inp.read_int(True)
        for _ in range(n):
            d = EventData(inp.read_string_ref())
            d.int_value = inp.read_int(False)
            d.float_value = inp.read_float()
            d.string_value = inp.read_string()
            d.audio_path = inp.read_string()
            if d.audio_path is not None:
                d.volume = inp.read_float()
                d.balance = inp.read_float()
            sd.events.append(d)

        n = inp.read_int(True)
        for _ in range(n):
            sd.animations.append(self._read_animation(inp, inp.read_string(), sd))
        return sd

    def _read_skin(self, inp, sd, default, nonessential):
        skin = None
        slot_count = 0
        if default:
            slot_count = inp.read_int(True)
            if slot_count == 0:
                return None
            skin = Skin("default")
        else:
            skin = Skin(inp.read_string_ref())
            nb = inp.read_int(True)
            for _ in range(nb):
                inp.read_int(True)  # bone index (skin.bones not needed)
            for _ in range(inp.read_int(True)):
                inp.read_int(True)  # ik constraint
            for _ in range(inp.read_int(True)):
                inp.read_int(True)  # transform constraint
            for _ in range(inp.read_int(True)):
                inp.read_int(True)  # path constraint
            slot_count = inp.read_int(True)
        for _ in range(slot_count):
            slot_index = inp.read_int(True)
            nn = inp.read_int(True)
            for _ in range(nn):
                name = inp.read_string_ref()
                attachment = self._read_attachment(inp, sd, skin, slot_index, name, nonessential)
                if attachment is not None:
                    skin.set_attachment(slot_index, name, attachment)
        return skin

    def _read_attachment(self, inp, sd, skin, slot_index, attachment_name, nonessential):
        scale = self.scale
        name = inp.read_string_ref()
        if name is None:
            name = attachment_name
        type_index = inp.read_byte()
        loader = self.attachment_loader
        if type_index == ATTACHMENT_REGION:
            path = inp.read_string_ref()
            rotation = inp.read_float()
            x = inp.read_float()
            y = inp.read_float()
            sx = inp.read_float()
            sy = inp.read_float()
            width = inp.read_float()
            height = inp.read_float()
            color = inp.read_int32()
            if path is None:
                path = name
            a = loader.new_region_attachment(skin, name, path)
            if a is None:
                return None
            a.path = path
            a.x = x * scale
            a.y = y * scale
            a.scale_x = sx
            a.scale_y = sy
            a.rotation = rotation
            a.width = width * scale
            a.height = height * scale
            Color.rgba8888(a.color, color)
            a.update_offset()
            return a
        if type_index == ATTACHMENT_BOUNDING_BOX:
            vertex_count = inp.read_int(True)
            vertices, bones = self._read_vertices(inp, vertex_count)
            color = inp.read_int32() if nonessential else 0
            a = loader.new_bounding_box_attachment(skin, name)
            if a is None:
                return None
            a.world_vertices_length = vertex_count << 1
            a.vertices = vertices
            a.bones = bones
            if nonessential:
                Color.rgba8888(a.color, color)
            return a
        if type_index == ATTACHMENT_MESH:
            path = inp.read_string_ref()
            color = inp.read_int32()
            vertex_count = inp.read_int(True)
            uvs = self._read_float_array(inp, vertex_count << 1, 1.0)
            triangles = self._read_short_array(inp)
            vertices, bones = self._read_vertices(inp, vertex_count)
            hull_length = inp.read_int(True)
            edges = None
            width = height = 0.0
            if nonessential:
                edges = self._read_short_array(inp)
                width = inp.read_float()
                height = inp.read_float()
            if path is None:
                path = name
            a = loader.new_mesh_attachment(skin, name, path)
            if a is None:
                return None
            a.path = path
            Color.rgba8888(a.color, color)
            a.bones = bones
            a.vertices = vertices
            a.base_vertices = list(vertices)
            a.world_vertices_length = vertex_count << 1
            a.triangles = triangles
            a.region_uvs = uvs
            a.update_uvs()
            a.hull_length = hull_length << 1
            if nonessential:
                a.edges = edges
                a.width = width * scale
                a.height = height * scale
            return a
        if type_index == ATTACHMENT_LINKED_MESH:
            path = inp.read_string_ref()
            color = inp.read_int32()
            skin_name = inp.read_string_ref()
            parent = inp.read_string_ref()
            inherit_deform = inp.read_boolean()
            width = height = 0.0
            if nonessential:
                width = inp.read_float()
                height = inp.read_float()
            if path is None:
                path = name
            a = loader.new_mesh_attachment(skin, name, path)
            if a is None:
                return None
            a.path = path
            Color.rgba8888(a.color, color)
            if nonessential:
                a.width = width * scale
                a.height = height * scale
            self.linked_meshes.append({
                "mesh": a, "skin": skin_name, "slot_index": slot_index,
                "parent": parent, "inherit_deform": inherit_deform,
            })
            return a
        if type_index == ATTACHMENT_PATH:
            closed = inp.read_boolean()
            constant_speed = inp.read_boolean()
            vertex_count = inp.read_int(True)
            vertices, bones = self._read_vertices(inp, vertex_count)
            lengths = [inp.read_float() * scale for _ in range(vertex_count // 3)]
            color = inp.read_int32() if nonessential else 0
            a = loader.new_path_attachment(skin, name)
            if a is None:
                return None
            a.closed = closed
            a.constant_speed = constant_speed
            a.world_vertices_length = vertex_count << 1
            a.vertices = vertices
            a.bones = bones
            a.lengths = lengths
            if nonessential:
                Color.rgba8888(a.color, color)
            return a
        if type_index == ATTACHMENT_POINT:
            rotation = inp.read_float()
            x = inp.read_float()
            y = inp.read_float()
            color = inp.read_int32() if nonessential else 0
            a = loader.new_point_attachment(skin, name)
            if a is None:
                return None
            a.x = x * scale
            a.y = y * scale
            a.rotation = rotation
            if nonessential:
                Color.rgba8888(a.color, color)
            return a
        if type_index == ATTACHMENT_CLIPPING:
            end_slot_index = inp.read_int(True)
            vertex_count = inp.read_int(True)
            vertices, bones = self._read_vertices(inp, vertex_count)
            color = inp.read_int32() if nonessential else 0
            a = loader.new_clipping_attachment(skin, name)
            if a is None:
                return None
            a.end_slot = sd.slots[end_slot_index]
            a.world_vertices_length = vertex_count << 1
            a.vertices = vertices
            a.bones = bones
            if nonessential:
                Color.rgba8888(a.color, color)
            return a
        return None

    def _read_vertices(self, inp, vertex_count):
        vertices_length = vertex_count << 1
        scale = self.scale
        if not inp.read_boolean():
            return self._read_float_array(inp, vertices_length, scale), None
        weights = []
        bones = []
        for _ in range(vertex_count):
            bone_count = inp.read_int(True)
            bones.append(bone_count)
            for _ in range(bone_count):
                bones.append(inp.read_int(True))
                weights.append(inp.read_float() * scale)
                weights.append(inp.read_float() * scale)
                weights.append(inp.read_float())
        return weights, bones

    def _read_float_array(self, inp, n, scale):
        if scale == 1.0:
            return [inp.read_float() for _ in range(n)]
        return [inp.read_float() * scale for _ in range(n)]

    def _read_short_array(self, inp):
        n = inp.read_int(True)
        return [inp.read_short() for _ in range(n)]

    def _read_animation(self, inp, name, sd):
        # 时间线（完整解析，曲线暂存原始数据）
        animation = Animation(name)
        scale = self.scale
        duration = 0.0

        # 槽位时间线
        n = inp.read_int(True)
        for _ in range(n):
            slot_index = inp.read_int(True)
            nn = inp.read_int(True)
            for _ in range(nn):
                timeline_type = inp.read_byte()
                frame_count = inp.read_int(True)
                if timeline_type == SLOT_ATTACHMENT:
                    frames = []
                    for _ in range(frame_count):
                        t = inp.read_float()
                        frames.append((t, inp.read_string_ref()))
                    animation.slot_timelines.append({"type": "attachment", "slot": slot_index, "frames": frames})
                    duration = max(duration, frames[-1][0])
                elif timeline_type in (SLOT_COLOR, SLOT_TWO_COLOR):
                    frames = []
                    curves = []
                    for _ in range(frame_count):
                        t = inp.read_float()
                        c1 = Color()
                        Color.rgba8888(c1, inp.read_int32())
                        c2 = None
                        if timeline_type == SLOT_TWO_COLOR:
                            c2 = Color()
                            Color.rgb888(c2, inp.read_int32())
                        frames.append((t, c1, c2))
                        if len(frames) < frame_count:
                            curves.append(self._read_curve(inp))
                    animation.slot_timelines.append({"type": "color" if timeline_type == SLOT_COLOR else "twocolor",
                                                     "slot": slot_index, "frames": frames})
                    duration = max(duration, frames[-1][0])

        # 骨骼时间线（类型枚举独立：0=rotate 1=translate 2=scale 3=shear）
        n = inp.read_int(True)
        for _ in range(n):
            bone_index = inp.read_int(True)
            nn = inp.read_int(True)
            for _ in range(nn):
                timeline_type = inp.read_byte()
                frame_count = inp.read_int(True)
                if timeline_type == 0:  # rotate
                    frames = []
                    curves = []
                    for _ in range(frame_count):
                        t = inp.read_float()
                        frames.append((t, inp.read_float()))
                        if len(frames) < frame_count:
                            curves.append(self._read_curve(inp))
                    animation.bone_timelines.append({"type": "rotate", "bone": bone_index, "frames": frames, "curves": curves})
                    duration = max(duration, frames[-1][0])
                elif timeline_type in (1, 2, 3):  # translate / scale / shear
                    tscale = scale if timeline_type == 1 else 1.0
                    frames = []
                    curves = []
                    for _ in range(frame_count):
                        t = inp.read_float()
                        frames.append((t, inp.read_float() * tscale, inp.read_float() * tscale))
                        if len(frames) < frame_count:
                            curves.append(self._read_curve(inp))
                    animation.bone_timelines.append({
                        "type": {1: "translate", 2: "scale", 3: "shear"}[timeline_type],
                        "bone": bone_index, "frames": frames, "curves": curves})
                    duration = max(duration, frames[-1][0])

        # IK 约束时间线
        n = inp.read_int(True)
        for _ in range(n):
            index = inp.read_int(True)
            frame_count = inp.read_int(True)
            frames = []
            curves = []
            for _ in range(frame_count):
                t = inp.read_float()
                frames.append((t, inp.read_float(), inp.read_float() * scale, inp.read_sbyte(),
                               inp.read_boolean(), inp.read_boolean()))
                if len(frames) < frame_count:
                    curves.append(self._read_curve(inp))
            animation.ik_timelines.append({"index": index, "frames": frames, "curves": curves})
            duration = max(duration, frames[-1][0])

        # 变换约束时间线
        n = inp.read_int(True)
        for _ in range(n):
            index = inp.read_int(True)
            frame_count = inp.read_int(True)
            frames = []
            curves = []
            for _ in range(frame_count):
                t = inp.read_float()
                frames.append((t, inp.read_float(), inp.read_float(), inp.read_float(), inp.read_float()))
                if len(frames) < frame_count:
                    curves.append(self._read_curve(inp))
            animation.transform_timelines.append({"index": index, "frames": frames, "curves": curves})
            duration = max(duration, frames[-1][0])

        # 路径约束时间线（类型枚举独立：0=position 1=spacing 2=mix）
        n = inp.read_int(True)
        for _ in range(n):
            index = inp.read_int(True)
            data = sd.path_constraints[index]
            nn = inp.read_int(True)
            for _ in range(nn):
                timeline_type = inp.read_byte()
                frame_count = inp.read_int(True)
                if timeline_type in (0, 1):  # position / spacing
                    tscale = 1.0
                    if timeline_type == PATH_SPACING and data.spacing_mode in (SPACING_LENGTH, SPACING_FIXED):
                        tscale = scale
                    elif timeline_type == PATH_POSITION and data.position_mode == POSITION_FIXED:
                        tscale = scale
                    frames = []
                    for _ in range(frame_count):
                        t = inp.read_float()
                        frames.append((t, inp.read_float() * tscale))
                        if len(frames) < frame_count:
                            self._read_curve(inp)
                    animation.path_timelines.append({"type": "position" if timeline_type == 0 else "spacing",
                                                     "index": index, "frames": frames})
                    duration = max(duration, frames[-1][0])
                elif timeline_type == 2:  # mix
                    frames = []
                    for _ in range(frame_count):
                        t = inp.read_float()
                        frames.append((t, inp.read_float(), inp.read_float()))
                        if len(frames) < frame_count:
                            self._read_curve(inp)
                    animation.path_timelines.append({"type": "mix", "index": index, "frames": frames})
                    duration = max(duration, frames[-1][0])

        # 变形时间线：skin → nn(插槽数) → slotIndex → nnn(附件数) → 附件
        n = inp.read_int(True)
        for _ in range(n):
            skin = sd.skins[inp.read_int(True)]
            nn = inp.read_int(True)
            for _ in range(nn):
                slot_index = inp.read_int(True)
                nnn = inp.read_int(True)
                for _ in range(nnn):
                    att_name = inp.read_string_ref()
                    attachment = skin.get_attachment(slot_index, att_name)
                    weighted = attachment is not None and attachment.bones is not None
                    vertices = attachment.vertices if attachment is not None else None
                    if vertices is None:
                        deform_length = 0
                    elif weighted:
                        deform_length = len(vertices) // 3 * 2
                    else:
                        deform_length = len(vertices)
                    frame_count = inp.read_int(True)
                    frames = []
                    for _ in range(frame_count):
                        t = inp.read_float()
                        end = inp.read_int(True)
                        if end == 0:
                            # 空变形：加权=全零，非加权=原顶点
                            deform = [0.0] * deform_length if weighted else list(vertices)
                        else:
                            deform = [0.0] * deform_length
                            start = inp.read_int(True)
                            end += start
                            for v in range(start, min(end, deform_length)):
                                deform[v] = inp.read_float() * scale
                            if not weighted:
                                for v in range(deform_length):
                                    deform[v] += vertices[v]
                        frames.append((t, deform))
                        if len(frames) < frame_count:
                            self._read_curve(inp)
                    animation.deform_timelines.append({"skin": skin, "slot": slot_index,
                                                       "attachment": attachment, "frames": frames})
                    duration = max(duration, frames[-1][0])

        # 绘制顺序时间线（在事件之前）：drawOrderCount = 帧数，单时间线
        # 每帧：time + offsetCount + 每偏移 (slotIndex, offset) 两个 varint
        draw_order_count = inp.read_int(True)
        if draw_order_count > 0:
            frames = []
            for _ in range(draw_order_count):
                t = inp.read_float()
                offset_count = inp.read_int(True)
                offsets = []
                for _ in range(offset_count):
                    slot_i = inp.read_int(True)
                    off = inp.read_int(True)
                    offsets.append((slot_i, off))
                frames.append((t, offsets))
            animation.draw_order_timelines.append({"frames": frames})
            duration = max(duration, frames[-1][0])

        # 事件时间线：eventCount = 帧数，单时间线；时间只读一次
        event_count = inp.read_int(True)
        if event_count > 0:
            frames = []
            for _ in range(event_count):
                t = inp.read_float()
                d = sd.events[inp.read_int(True)]
                e = EventData(d.name)
                e.int_value = inp.read_int(False)
                e.float_value = inp.read_float()
                if inp.read_boolean():
                    e.string_value = inp.read_string()
                else:
                    e.string_value = d.string_value
                if d.audio_path is not None:
                    e.volume = inp.read_float()
                    e.balance = inp.read_float()
                frames.append((t, e))
            animation.event_timelines.append({"frames": frames})
            duration = max(duration, frames[-1][0])

        animation.duration = duration
        return animation

    def _read_curve(self, inp):
        """返回曲线数据：0=线性 1=阶梯 或 (cx1,cy1,cx2,cy2)"""
        curve_type = inp.read_byte()
        if curve_type == 0:  # linear
            return 0
        if curve_type == 1:  # stepped
            return 1
        # bezier: 单段贝塞尔，4 个控制点 float
        return (inp.read_float(), inp.read_float(), inp.read_float(), inp.read_float())


class Animation:
    def __init__(self, name):
        self.name = name
        self.duration = 0.0
        self.slot_timelines = []
        self.bone_timelines = []
        self.ik_timelines = []
        self.transform_timelines = []
        self.path_timelines = []
        self.deform_timelines = []
        self.event_timelines = []
        self.draw_order_timelines = []
