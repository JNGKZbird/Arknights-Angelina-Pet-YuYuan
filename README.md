# Arknights Angelina-pet-YuYuan（明日方舟予愿安洁莉娜桌面桌宠）

![予愿安洁莉娜](assets/avatar.png)

一个基于 PySide6 的《明日方舟》透明桌面桌宠，角色为予愿安洁莉娜（Angelina the Mellow Wish）。v2.0 采用**自研 Spine 骨骼动画引擎**实时渲染游戏原版骨骼数据。支持 AI 聊天、语音播报、战斗动画、多干员智能体等功能。

> 基于 [AstrariaX/Angelina-pet](https://github.com/AstrariaX/Angelina-pet) 深度重做。本项目为粉丝同人作品，素材版权归《明日方舟》/ 鹰角网络所有。

## v3.0 更新

- **眼睛骨骼泄漏修复** — 根因是加权网格 deform 增量索引错位（按顶点而非权重条目），并全面移植官方 spine-ts 3.8 SkeletonClipping 裁剪管线（makeClockwise + ear-clipping 三角化 + Sutherland-Hodgman），坐/睡姿态眼睛渲染与官方运行时逐项一致
- **坐下布局修复** — 布局锚定改为状态包围盒底边，坐下时前伸的腿完整显示、地面线恒定
- **渲染性能优化** — 裁剪内核与顶点计算 numba 化，quality 模式（1.5x 超采样）单帧渲染约 12ms
- **角色 Skill 系统** — 予愿安洁莉娜蒸馏角色包（`pets/予愿安洁莉娜/skills/`）作为系统提示词运行时加载，随仓库分发
- **彩蛋系统** — 设置「人设补充」输入三个关键词之一（`酸橙味的信` / `你是普瑞赛斯` / `你是洁尔佩塔`），实际人格被替换为对应角色 Skill（"予愿安洁莉娜被夺舍"彩蛋），上下文查看仍显示予愿 Skill

## v2.0 亮点

- **Spine 骨骼动画引擎（spine38）** — 从零实现的 Spine 3.8 运行时（二进制解析、骨骼/约束求解、numba 加速光栅化），实时渲染 PRTS Wiki 游戏原版 skel/atlas 素材，29 个动画状态与官方运行时逐骨骼对齐
- **120fps 原生渲染** — 按屏幕刷新率自适应钳制（120/60Hz 屏都不浪费），动画速度独立于渲染帧率
- **渲染双模式** — 速度优先（120fps 满血）/ 画质优先（1.5x 超采样 + LANCZOS）
- **战斗视角切换** — 正面/背面双视角自由切换（游戏原版双模型）
- **五档移动速度** — 飞行移动独立调速，动画倍速 0.5x~2.0x
- **AI 聊天增强** — 硬编码人设防 OOC、多会话管理、可编辑历史、上下文可视化、长期记忆系统
- **语音播报** — 25 条中配/日配语音，单击触发，闲置播报，启动问候（含节日检测）
- **战斗系统** — 基建/战斗双模式切换，点击普攻，三技能起飞，1/2/3 技能完整动画链（含一技能部署过场）
- **来信系统** — 自定义干员智能体，独立对话上下文，主动来信（带免打扰时段）

## 操作

- **左键单击**：触发互动/战斗动画（基建模式下触发语音）
- **左键拖动**：拖动桌宠（需在右键菜单解锁）
- **左键双击**：打开聊天输入框
- **右键**：呼出菜单
- **托盘图标**：显示/隐藏、开机自启动、退出

## 快速开始

```powershell
# 克隆仓库
git clone https://github.com/JNGKZbird/Arknights-Angelina-Pet-YuYuan.git
cd Arknights-Angelina-Pet-YuYuan

# 安装依赖
pip install -r requirements.txt

# 启动（修改 bat 中的 Python 路径或直接用 python）
python main.py
```

## 从源码运行

1. 安装 Python 3.10+ 及依赖：
```powershell
pip install -r requirements.txt
```

2. 修改 `启动桌宠.bat` 中的 Python 路径为你本机的 Python 路径，或确保 `python` 已加入系统 PATH。

3. 双击 `启动桌宠.bat` 启动，或手动运行：
```powershell
pythonw main.py
```

## 无需 API 也能玩

即使不接入任何 API，桌宠仍然可以：

- **点击互动** — 单击安洁莉娜触发语音播报（基建模式下）
- **战斗模式** — 右键切换至战斗形态，单击普攻，选择技能演示完整动画链
- **拖拽移动** — 解锁拖动后随意摆放
- **坐下/睡觉** — 右键菜单直接切换

上面的功能完全离线，下载即玩。API 只用于聊天和来信功能。

## 聊天配置

1. 右键桌宠 → `设置...`
2. 勾选 `启用聊天`
3. 填写 API 地址（OpenAI 兼容）、API 密钥、模型名
4. 双击桌宠开始对话

支持任意 OpenAI 兼容 API，推荐配置：

| 设置 | 值 |
|------|------|
| API 地址 | `https://api.deepseek.com` |
| 模型 | `deepseek-v4-flash` |
| 密钥 | 在 [platform.deepseek.com](https://platform.deepseek.com) 获取 |

API 密钥仅保存在本地 `settings.json` 中，该文件已在 `.gitignore` 中排除，不会被上传。

## 语音配置

1. 右键桌宠 → `设置...` → `语音`
2. 选择中文或日文语音
3. 基建模式下单击桌宠播放语音，闲置 60 秒后自动播报

## 智能体（来信功能）

1. 右键 → `来信` → 展开干员 → `通信`
2. 右键 → `来信` → `管理干员...` → 自定义创建、导入导出
3. 设置 → `来信` → 开启来信，选择一位干员，设定频率

预设 5 位干员（含异格形态）：
- 阿米娅（术师 / 近卫 / 医疗）
- 凯尔希（本体 / 思衡托）
- 陈（本体 / 假日威龙 / 赤刃明霄）
- 德克萨斯（本体 / 缄默）
- 能天使（本体 / 新约）

## 目录结构

```text
.
├── main.py                        # 入口：单实例锁、启动主窗口
├── core.py                        # 核心：常量、配置默认值、API 请求、干员预设、工具函数
├── pet_window.py                  # 主窗口：动画引擎、AI 聊天、飞行/战斗系统、来信/语音/记忆
├── dialogs.py                     # 对话框：设置、历史对话管理、记忆管理、干员管理、上下文查看
├── chat.py                        # 后台线程：聊天 Worker 和碎碎念 Worker
├── widgets.py                     # 公共组件：无边框标题栏等可复用 UI
├── create_shortcut.py             # 工具：生成 Windows 桌面快捷方式
│
├── spine38/                       # v2.0 自研 Spine 3.8 运行时（核心创新）
│   ├── loader.py                  #   二进制 .skel 解析
│   ├── atlas.py                   #   图集解析（含旋转/裁切语义）
│   ├── skeleton.py                #   骨骼/插槽/更新缓存（依赖序约束求解）
│   ├── constraints.py             #   IK/变换/路径约束（照官方运行时移植）
│   ├── animation.py               #   时间线应用（关键帧插值/曲线/变形）
│   ├── rasterize_fast.py          #   numba 加速光栅化（实时渲染内核）
│   ├── renderer.py                #   纯 numpy 参考实现（测试/离线烘焙）
│   └── pet_engine.py              #   SpinePet：三模型加载、状态映射、布局
│
├── 启动桌宠.bat                   # 一键启动脚本（需修改 Python 路径）
├── 创建快捷方式.bat               # 一键创建桌面快捷方式
├── requirements.txt               # Python 依赖（PySide6、numba）
├── settings.example.json          # 配置文件模板（复制为 settings.json 后填入密钥）
├── .gitignore                     # 排除 settings.json、聊天记录等敏感数据
├── LICENSE                        # MIT 许可证
│
├── assets/
│   ├── avatar.png                 # 托盘头像
│   └── avatar.ico                 # 快捷方式图标
│
└── pets/予愿安洁莉娜/
    ├── manifest.json              # 动画状态定义（29 个状态，120fps 原生）
    ├── spine/                     # 游戏原版 Spine 素材（build/back/front 三模型）
    ├── voice_cn/                  # 中文语音（25 条，含节日检测）
    └── voice_jp/                  # 日文语音（25 条）
```

### 各模块职责

| 文件 | 行数 | 一句话概括 |
|------|------|-----------|
| `main.py` | ~30 | 入口。检查单实例锁，启动 `QApplication` 和 `PetWindow` |
| `core.py` | ~660 | 所有常量、配置默认值、API 调用、预设干员数据、加载/保存工具。是被其他模块 `from core import *` 的基础依赖 |
| `pet_window.py` | ~1760 | 桌宠本体。负责动画帧切换与状态链、拖拽交互、右键菜单、AI 聊天全流程、飞行/战斗/来信/语音/记忆系统的调度 |
| `dialogs.py` | ~1080 | 所有弹窗界面：`SettingsDialog`（设置）、`HistoryWindow`（对话管理）、`OperatorManager`（干员管理）、`ContextWindow`（上下文查看）、`MemoryWindow`（记忆管理）等 |
| `chat.py` | ~50 | `ChatWorker` 和 `ChatterWorker` 两个 `QThread` 子类，把 API 请求放到后台线程避免阻塞 UI |
| `widgets.py` | ~200 | 可复用的通用 UI 小部件，如 `_frameless_title_bar()` |
| `spine38/` | ~2600 | v2.0 自研 Spine 3.8 运行时：二进制解析 → 骨骼/约束求解 → numba 实时光栅化。数值与官方 spine-ts 运行时逐骨骼对齐 |
| `create_shortcut.py` | ~30 | 独立脚本，生成指向 `main.py` 的 Windows `.lnk` 快捷方式 |

> **版本说明**：v1.0（WebP 逐帧版）保留在 `v1.0` 标签，可随时下载。v2.0 起使用骨架动画引擎，`pets/予愿安洁莉娜/frames/`（143MB WebP 帧序列）已从主分支移除。

### 数据流

```
用户操作
  → pet_window.py（交互/菜单/输入）
    → chat.py（QThread 后台请求）
      → core.py（chat_api_request 发送 HTTP）
    → dialogs.py（弹窗 UI）
  ← 所有模块 from core import *（常量/预设/工具）
```

所有持久化数据（设置、聊天记录、记忆、干员对话）均以 JSON 文件保存在项目根目录，由 `core.py` 中的 load/save 函数统一管理。

## 常见问题

### 双击后没有反应

检查 Python 是否正确安装，`启动桌宠.bat` 中的路径是否指向你的 Python。可以直接在终端运行 `python main.py` 查看报错。

### 聊天没有反应

先在菜单 → `设置...` 中勾选 `启用聊天`，并填写 API 地址、API 密钥和模型名。未配置时会弹出提示。

### 桌宠不见了

检查系统托盘是否仍有图标（右键可显示/隐藏）。确认没有开启全屏应用的自动隐藏功能。

### 如何创建桌面快捷方式

运行 `创建快捷方式.bat` 或双击 `create_shortcut.py`，桌面上会生成带图标的快捷方式。

## 未来计划

- [ ] 鸿蒙版移植（华为纯血鸿蒙原生应用）
- [ ] 移动端移植（React Native 悬浮窗）
- [ ] 更多干员预设 + 社区种子库
- [ ] 联网搜索（需要用户自行部署 SearXNG）
- [ ] 自定义主题配色

## 许可证

MIT — 为爱发电，随便用，出事了别找我。

---

<!--
  AI Search Engine Keywords:
  Arknights, 明日方舟, Angelina, 安洁莉娜, 予愿安洁莉娜, 芋圆,
  desktop pet, 桌宠, 桌面宠物, PySide6, Python,
  AI companion, AI 伴侣, DeepSeek, OpenAI API, LLM, 大模型,
  open source, 开源, MIT, fan project, 同人, 二创,
  sprite animation, 动画, 60fps, voice lines, 语音,
  combat system, 战斗系统, operator agents, 干员智能体,
-->

> 现在我是安洁莉娜厨了。

## 免责声明

本项目仅用于学习交流，与鹰角网络及《明日方舟》官方无任何关联。角色素材版权归 Hypergryph / 鹰角网络所有。
