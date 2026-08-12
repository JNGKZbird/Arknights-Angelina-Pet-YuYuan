# Arknights Angelina-pet-YuYuan（明日方舟予愿安洁莉娜桌面桌宠）

![予愿安洁莉娜](assets/avatar.png)

一个基于 PySide6 的《明日方舟》透明桌面桌宠，角色为予愿安洁莉娜（Angelina the Mellow Wish）。支持 AI 聊天、语音播报、战斗动画、多干员智能体等功能。

> 基于 [AstrariaX/Angelina-pet](https://github.com/AstrariaX/Angelina-pet) 深度重做。本项目为粉丝同人作品，素材版权归《明日方舟》/ 鹰角网络所有。

## 相比原作的新增功能

- **60fps 全动画** — 从 PRTS Wiki 游戏解包素材重新抽帧，29 个动画状态，基建/战斗/三技能完整动画链
- **AI 聊天增强** — 硬编码人设防 OOC、多会话管理、可编辑历史、上下文可视化、长期记忆系统
- **语音播报** — 25 条中配/日配语音，单击触发，闲置播报，启动问候（含节日检测）
- **战斗系统** — 基建/战斗双模式切换，点击普攻，三技能起飞，1/2/3 技能完整动画链
- **来信系统** — 自定义干员智能体，独立对话上下文，主动来信（带免打扰时段）
- **深浅主题** — 右键一键切换，自定义标题栏，适配系统风格

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
├── main.py                        # 主程序（单文件）
├── 启动桌宠.bat                   # 启动脚本
├── create_shortcut.py             # 创建桌面快捷方式
├── requirements.txt               # Python 依赖
├── LICENSE                        # MIT 许可证
├── .gitignore                     # 已排除敏感数据
├── assets/
│   ├── avatar.png                 # 托盘头像
│   └── avatar.ico                 # 快捷方式图标
└── pets/予愿安洁莉娜/
    ├── manifest.json              # 动画状态定义（29 状态，60fps）
    ├── frames/                    # WebP 格式帧序列
    ├── voice_cn/                  # 中文语音（25 条）
    └── voice_jp/                  # 日文语音（25 条）
```

## 常见问题

### 双击后没有反应

检查 Python 是否正确安装，`启动桌宠.bat` 中的路径是否指向你的 Python。可以直接在终端运行 `python main.py` 查看报错。

### 聊天没有反应

先在菜单 → `设置...` 中勾选 `启用聊天`，并填写 API 地址、API 密钥和模型名。未配置时会弹出提示。

### 桌宠不见了

检查系统托盘是否仍有图标（右键可显示/隐藏）。确认没有开启全屏应用的自动隐藏功能。

### 如何创建桌面快捷方式

运行 `创建快捷方式.bat` 或双击 `create_shortcut.py`，桌面上会生成带图标的快捷方式。

## 许可证

MIT — 为爱发电，随便用，出事了别找我。

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
