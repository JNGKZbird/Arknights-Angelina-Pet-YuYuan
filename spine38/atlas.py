"""Spine 3.8 图集解析 — ported from spine-ts 3.8 TextureAtlas."""
from .loader import AtlasRegion


class AtlasPage:
    def __init__(self, name):
        self.name = name
        self.width = 0
        self.height = 0
        self.texture = None  # 渲染器填充


class TextureAtlas:
    def __init__(self, atlas_text: str, texture_loader=None):
        """texture_loader(page_path) -> texture 对象（渲染器提供）"""
        self.pages = []
        self.regions = []
        lines = atlas_text.splitlines()
        page = None
        region = None
        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            # 键值对：冒号前的部分是已知属性键
            colon = line.find(":")
            if colon != -1:
                key = line[:colon].strip()
                value = line[colon + 1:].strip()
                if key == "size" and page is not None and region is None:
                    parts = value.split(",")
                    page.width = int(parts[0])
                    page.height = int(parts[1])
                elif key == "rotate" and region is not None:
                    region.rotate = value == "true"
                elif key == "xy" and region is not None:
                    parts = value.split(",")
                    region.x = int(parts[0])
                    region.y = int(parts[1])
                elif key == "size" and region is not None:
                    parts = value.split(",")
                    region.width = int(parts[0])
                    region.height = int(parts[1])
                elif key == "orig" and region is not None:
                    parts = value.split(",")
                    region.original_width = int(parts[0])
                    region.original_height = int(parts[1])
                elif key == "offset" and region is not None:
                    parts = value.split(",")
                    region.offset_x = int(parts[0])
                    region.offset_y = int(parts[1])
                # 其余键（format/filter/repeat/index/split/pad/pma）忽略
                continue
            # 非键值行：页面名或区域名
            if page is None:
                page = AtlasPage(line)
                self.pages.append(page)
                if texture_loader is not None:
                    page.texture = texture_loader(line)
            else:
                region = AtlasRegion()
                region.name = line
                region.page = page
                self.regions.append(region)

        # 计算 UV（照 spine-ts 3.8 TextureAtlas：旋转区域 u2 用 height、v2 用 width；
        # width/height 保持 atlas 原文语义不交换）
        for region in self.regions:
            page = region.page
            pw = page.width or 1
            ph = page.height or 1
            region.page_width = page.width
            region.page_height = page.height
            if not region.original_width:
                region.original_width = region.width
            if not region.original_height:
                region.original_height = region.height
            region.u = region.x / pw
            region.v = region.y / ph
            if region.rotate:
                region.u2 = (region.x + region.height) / pw
                region.v2 = (region.y + region.width) / ph
                region.degrees = 90
            else:
                region.u2 = (region.x + region.width) / pw
                region.v2 = (region.y + region.height) / ph

    def find_region(self, name):
        for r in self.regions:
            if r.name == name:
                return r
        return None


class AtlasAttachmentLoaderImpl:
    """按图集解析附件，填充 region 引用。"""

    def __init__(self, atlas: TextureAtlas):
        self.atlas = atlas

    def new_region_attachment(self, skin, name, path):
        region = self.atlas.find_region(path)
        if region is None:
            raise ValueError(f"Region not found in atlas: {path} (region attachment: {name})")
        from .loader import RegionAttachment
        a = RegionAttachment(name)
        a.region = region
        return a

    def new_mesh_attachment(self, skin, name, path):
        region = self.atlas.find_region(path)
        if region is None:
            raise ValueError(f"Region not found in atlas: {path} (mesh attachment: {name})")
        from .loader import MeshAttachment
        a = MeshAttachment(name)
        a.region = region
        return a

    def new_bounding_box_attachment(self, skin, name):
        from .loader import BoundingBoxAttachment
        return BoundingBoxAttachment(name)

    def new_path_attachment(self, skin, name):
        from .loader import PathAttachment
        return PathAttachment(name)

    def new_point_attachment(self, skin, name):
        from .loader import PointAttachment
        return PointAttachment(name)

    def new_clipping_attachment(self, skin, name):
        from .loader import ClippingAttachment
        return ClippingAttachment(name)
