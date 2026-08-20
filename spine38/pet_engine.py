"""SpinePet — 骨架动画桌宠引擎：三模型加载、状态映射、实时渲染."""
import math
import os

import numpy as np
from PIL import Image

from .loader import SkeletonBinary
from .atlas import TextureAtlas, AtlasAttachmentLoaderImpl
from .skeleton import Skeleton
from .animation import apply_animation
from .rasterize_fast import render_skeleton_fast

# 素材文件基名（spine 目录下 build/back/front 三个子目录）
MODEL_FILES = {
    "build": "build_char_1015_aglna2",
    "back": "char_1015_aglna2",
    "front": "char_1015_aglna2",
}

# 状态 → (模型, 动画名)
# build = 基建姿态（日常）；front = 战斗正面（桌宠陪伴场景，角色面对用户）
# back（战斗背面）模型保留加载但暂不映射——未来如需"背面视角"形态可切换
STATE_MAP = {
    "idle": ("build", "Relax"),
    "interact": ("build", "Interact"),
    "move": ("build", "Move"),
    "sit": ("build", "Sit"),
    "sleep": ("build", "Sleep"),
    "combat_idle": ("front", "Idle"),
    "combat_start": ("front", "Start"),
    "combat_start2": ("front", "Start_2"),
    "attack": ("front", "Attack"),
    "attack_down": ("front", "Attack_Down"),
    "skill1_idle": ("front", "Skill_1_Idle"),
    "skill1_loop": ("front", "Skill_1_Loop"),
    "skill1_end": ("front", "Skill_1_End"),
    "skill2_begin": ("front", "Skill_2_Begin"),
    "skill2_takeoff_begin": ("front", "Skill_2_Takeoff_Begin"),
    "skill2_takeoff_loop": ("front", "Skill_2_Takeoff_Loop"),
    "skill2_takeoff_end": ("front", "Skill_2_Takeoff_End"),
    "skill2_loop": ("front", "Skill_2_Loop"),
    "skill2_idle": ("front", "Skill_2_Idle"),
    "skill2_end": ("front", "Skill_2_End"),
    "skill_down_1": ("front", "Skill_Down_1_Loop"),
    "skill_down_2": ("front", "Skill_Down_2_Loop"),
    "fly_begin": ("front", "Skill_3_Begin"),
    "fly_loop": ("front", "Skill_3_Loop"),
    "fly_idle": ("front", "Skill_3_Idle"),
    "fly_combat": ("front", "Skill_3_Combat"),
    "fly_restart": ("front", "Skill_3_Restart_Begin"),
    "fly_end": ("front", "Skill_3_End"),
    "fly": ("front", "Skill_3_Move"),
}

TRANSFORM_SAMPLES = 24  # 每状态包围盒联合采样数（越多越不易漏极端姿态）
CHAR_SCALE = 0.5  # 角色显示尺寸 = FULL_SIZE × scale × RENDER_SCALE × CHAR_SCALE（对齐旧 WebP 版比例）

# 背面模型缺失的动画（切换背面视角时这些状态回退正面模型）
BACK_MISSING_ANIMS = {"attack_down", "skill_down_1", "skill_down_2"}


def _unpremultiply(tex):
    """wiki 导出的 PNG 是预乘 alpha：反预乘成直通 alpha，供直通合成管线使用。

    不做此步会二次变暗——半透明粉色腮红显示成灰色（黑眼圈错觉）。
    """
    a = tex[:, :, 3].astype(np.float32)
    rgb = tex[:, :, :3].astype(np.float32)
    mask = a > 0
    rgb[mask] = rgb[mask] * (255.0 / a[mask, None])
    tex[:, :, :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    return tex


class SpinePet:
    def __init__(self, spine_dir):
        self.combat_view = "front"  # "front" | "back"（战斗视角，用户可切换）
        self.models = {}
        for key, base in MODEL_FILES.items():
            root = os.path.join(spine_dir, key)
            with open(os.path.join(root, base + ".atlas"), encoding="utf-8") as f:
                atlas_text = f.read()
            tex_img = np.asarray(Image.open(os.path.join(root, base + ".png")).convert("RGBA")).copy()
            _unpremultiply(tex_img)
            atlas = TextureAtlas(atlas_text, lambda path: tex_img)
            with open(os.path.join(root, base + ".skel"), "rb") as f:
                data = f.read()
            sd = SkeletonBinary(AtlasAttachmentLoaderImpl(atlas)).read_skeleton_data(data)
            self.models[key] = (Skeleton(sd), sd, atlas)
        self.state_info = {}
        self._layout_cache = {}
        self._bounds_cache = {}
        # 每模型基准角色尺寸与锚点（setup 姿态包围盒）——固定缩放与固定锚点的基准
        self._model_extent = {}
        self._model_setup_bounds = {}
        for key, (skeleton, sd, _) in self.models.items():
            self._preconvert_attachments(sd)
            skeleton.set_to_setup_pose()
            skeleton.update_world_transform()
            ox, oy, w, h = skeleton.get_bounds()
            self._model_extent[key] = max(w, h)
            self._model_setup_bounds[key] = (ox, oy, ox + w, oy + h)

    @staticmethod
    def _preconvert_attachments(sd):
        """附件顶点/骨骼数组预转换为 numpy（渲染路径零转换开销）。"""
        for skin in sd.skins:
            for att in skin.attachments.values():
                if (hasattr(att, "vertices") and att.vertices is not None
                        and isinstance(att.vertices, list)):
                    att.vertices = np.asarray(att.vertices, dtype=np.float64)
                if (hasattr(att, "bones") and att.bones is not None
                        and isinstance(att.bones, list)):
                    att.bones = np.asarray(att.bones, dtype=np.int64)

    def _resolve_model(self, state):
        model_key, _ = STATE_MAP[state]
        # 战斗视角切换：正面/背面动画名一致；背面缺失的动画回退正面模型
        if (model_key == "front" and self.combat_view == "back"
                and state not in BACK_MISSING_ANIMS):
            return "back"
        return model_key

    def _get(self, state):
        model_key = self._resolve_model(state)
        anim_name = STATE_MAP[state][1]
        skeleton, sd, atlas = self.models[model_key]
        anim = sd.find_animation(anim_name)
        return skeleton, sd, atlas, anim

    def anim_duration(self, state):
        _, _, _, anim = self._get(state)
        return anim.duration if anim else 0.0

    def _state_bounds(self, state):
        """状态包围盒联合（缓存，用于布局与字幕头顶）。"""
        key = (state, self.combat_view)
        cached = self._bounds_cache.get(key)
        if cached is not None:
            return cached
        skeleton, _, _, anim = self._get(state)
        xs = []
        ys = []
        if anim is None or anim.duration <= 0:
            skeleton.set_to_setup_pose()
            skeleton.update_world_transform()
            ox, oy, w, h = skeleton.get_bounds()
            xs = [ox, ox + w]
            ys = [oy, oy + h]
        else:
            n = max(2, TRANSFORM_SAMPLES)
            for i in range(n):
                t = anim.duration * i / n
                skeleton.set_to_setup_pose()
                apply_animation(anim, skeleton, t, True, 1.0)
                skeleton.update_world_transform()
                ox, oy, w, h = skeleton.get_bounds()
                xs.append(ox)
                xs.append(ox + w)
                ys.append(oy)
                ys.append(oy + h)
        cached = (min(xs), min(ys), max(xs), max(ys))
        self._bounds_cache[key] = cached
        return cached

    def layout_for(self, state, char_px, margin=8):
        """状态布局：固定缩放 + 锚定状态包围盒底边，画布覆盖"动画联合 ∪ setup"。

        角色在所有动画下大小恒定；画布尺寸随动画包围盒变化。
        垂直锚定用状态包围盒底边（bottom）：站立时 bottom=setup 脚 → 脚贴底；
        坐下动画腿前伸下探（骨架 y≈-140），bottom 随之降低 → 腿完整显示且
        贴画布底（地面线恒定）。若锚定 setup 底边，坐下时腿会超出画布被裁。
        返回 {"scale", "tx", "ty", "w", "h"}，其中 w/h 为画布像素尺寸。"""
        key = (state, char_px, self.combat_view)
        cached = self._layout_cache.get(key)
        if cached is not None:
            return cached
        model_key = self._resolve_model(state)
        scale = char_px / max(self._model_extent.get(model_key, 1.0), 1.0)
        sx0, sy0, sx1, sy1 = self._model_setup_bounds[model_key]
        min_x, min_y, max_x, max_y = self._state_bounds(state)
        left = min(min_x, sx0)
        right = max(max_x, sx1)
        bottom = min(min_y, sy0)
        top = max(max_y, sy1)
        w = max(1, int(math.ceil((right - left) * scale)) + margin * 2)
        h = max(1, int(math.ceil((top - bottom) * scale)) + margin * 2)
        tx = w / 2 - ((sx0 + sx1) / 2) * scale
        ty = margin - bottom * scale
        cached = {"scale": scale, "tx": tx, "ty": ty, "w": w, "h": h}
        self._layout_cache[key] = cached
        return cached

    def char_top_in_canvas(self, state, char_px):
        """角色头顶在画布中的 y 像素（画布 y 向下）。"""
        layout = self.layout_for(state, char_px)
        min_x, min_y, max_x, max_y = self._state_bounds(state)
        return layout["h"] - (max_y * layout["scale"] + layout["ty"])

    def render(self, state, t, char_px, mirror=False, bilinear=False, loop=True):
        """渲染状态在时刻 t 的画面，返回 RGBA uint8 数组（尺寸随状态布局变化）。

        char_px：角色目标显示像素（画布按此等比生成）；mirror 水平镜像。
        """
        skeleton, _, atlas, anim = self._get(state)
        layout = self.layout_for(state, char_px)
        out = np.zeros((layout["h"], layout["w"], 4), dtype=np.uint8)
        skeleton.set_to_setup_pose()
        apply_animation(anim, skeleton, t, loop, 1.0)
        skeleton.update_world_transform()
        render_skeleton_fast(skeleton, atlas, out,
                             (layout["scale"], layout["tx"], layout["ty"]),
                             bilinear=bilinear)
        if mirror:
            out[:, :, :] = out[:, ::-1, :]
        return out
