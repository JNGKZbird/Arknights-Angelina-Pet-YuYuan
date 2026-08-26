# 予愿安洁莉娜桌宠（Windows 版）

![予愿安洁莉娜](assets/avatar.png)

> 一只住在你 Windows 桌面上的安洁莉娜。她会陪在你身边：走来走去、坐下休息、回应你的点击、和你聊天。不需要任何游戏本体，下载就能养。

> 本项目由 **JNGKZbird**（GitHub @JNGKZbird）开发，基于 [AstrariaX/Angelina-pet](https://github.com/AstrariaX/Angelina-pet) 深度重做——原作者采用逐帧 PNG 动画，本项目改用**骨骼动画**方案：实际体积大幅缩减、动画更加丝滑，这是站在巨人肩膀上的优化。由衷感谢原作者的创意与工作。本项目为粉丝同人作品，素材版权归《明日方舟》/ 鹰角网络所有。

---

## 目录

- [这是什么？](#这是什么)
- [一、安装运行（手把手五步）](#一安装运行手把手五步)
- [二、怎么和她玩](#二怎么和她玩)
- [三、（可选）让她开口聊天](#三可选让她开口聊天)
- [四、常见问题（FAQ）](#四常见问题faq)
- [五、给开发者](#五给开发者)
- [致谢与版权](#致谢与版权)

---

## 这是什么？

一个**桌面桌宠**：一个透明小窗口，里面住着《明日方舟》的干员**予愿安洁莉娜**。她会：

- 在你屏幕上**走来走去**（不挡你的工作）
- 自己**坐下、睡觉**，也会随机做小动作
- **回应你的点击**：戳她会说话（有中文/日文语音）
- **和你聊天**（接入 AI 后，双击她就能对话）
- 切到**战斗形态**，演示她的全部技能动画

她由**骨骼动画**实时驱动——不是视频、不是 GIF，是游戏同款 Spine 动画数据在本地渲染，**支持最高 120 帧**（随屏幕刷新率自适应），丝滑流畅。

---

## 一、安装运行（手把手五步）

> 完全零基础也能照着做。全程大约 10 分钟。

### 第 1 步：安装 Python

1. 打开 Python 官网下载页：<https://www.python.org/downloads/>
2. 点击黄色按钮 **Download Python 3.x.x** 下载安装包
3. 双击安装包，**最重要的一步**：勾选窗口底部的 **"Add python.exe to PATH"**，然后点 **Install Now**
4. 装完后，按下键盘 **Win + R**，输入 `cmd` 回车，在弹出的黑色窗口里输入：

```bat
python --version
```

如果显示 `Python 3.x.x`，说明装好了。**注意**：请使用 Python 3.10 ~ 3.12（最新 3.13 可能和依赖不兼容）。

### 第 2 步：下载本项目

1. 回到本页面（GitHub 仓库页）
2. 点击绿色的 **`<> Code`** 按钮
3. 选择 **Download ZIP**
4. 把下载的压缩包**解压**到一个你找得到的地方（比如桌面），解压后是一个名为 `Arknights-Angelina-Pet-YuYuan-main` 的文件夹

### 第 3 步：安装依赖

1. 打开解压出来的文件夹
2. 在文件夹地址栏输入 `cmd` 回车（黑色窗口会在这个文件夹打开）
3. 输入下面这行命令并回车（可以复制粘贴，右键粘贴）：

```bat
pip install -r requirements.txt
```

等待安装完成（约 1~3 分钟，需要联网）。如果下载很慢或失败，换用国内镜像：

```bat
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 第 4 步：启动

双击文件夹里的 **`启动桌宠.bat`**。

> 如果双击后一闪而过、没有桌宠出现：右键 `启动桌宠.bat` → 编辑，把里面的 Python 路径改成你自己的。不知道路径？在第 1 步的黑色窗口里输入 `where python` 就能看到。

### 第 5 步：确认她来了

桌面上出现一只安洁莉娜，屏幕右下角的**系统托盘**（时间旁边的小图标区）里也有她的图标——安装完成，开养！

---

## 二、怎么和她玩

### 基本操作

| 操作 | 效果 |
|---|---|
| **左键单击** | 戳她一下——触发互动动作，基建模式下会说话 |
| **左键双击** | 打开聊天输入框（需要先配置 AI，见下一节） |
| **左键拖动** | 把她拖到喜欢的位置（需先在右键菜单"解锁拖动"） |
| **右键** | 呼出完整菜单 |
| **托盘图标** | 显示/隐藏、开机自启动、退出 |

### 右键菜单能做什么

- **坐下 / 放松 / 睡觉**：让她休息（她过一会儿自己也会去坐）
- **形态**：固定形态（原地不动）/ 自由移动形态（满屏幕溜达）
- **聊天**：打开聊天、新对话、历史对话、上下文查看、记忆管理
- **全屏应用时自动隐藏**：打游戏/看视频时她自动躲起来
- **切换至战斗形态**：进入战斗模式，可以：
  - 单击 = 普通攻击连击
  - 技能菜单 = 演示三个技能的完整动画（起飞、重力、酸橙的心事）
  - 切换正面/背面视角
- **来信**：管理你的干员智能体（详见下文）
- **解锁拖动 / 设置 / 退出**

### 她自己的小生活

不用管她的时候，她会自己找事做：在屏幕间飞行巡逻、随机坐下或睡觉、偶尔主动找你说话（配置 AI 后）。

---

## 三、（可选）让她开口聊天

不配置 AI 也能玩（动作、语音、战斗都离线可用），但**双击聊天**需要接入一个大模型 API。

### 什么是 API？

简单说：AI 大模型的"网上接口"。你需要在一个 AI 服务商那里**注册账号 → 充值 → 拿到一串密钥（API Key）**，把密钥填进桌宠设置，她就能用那个 AI 的大脑和你聊天。

### 以 DeepSeek 为例（性价比推荐）

1. 打开 <https://platform.deepseek.com> 注册并登录
2. 在左侧"充值"里充一点钱（几块钱就能聊很久）
3. 在左侧"API Keys"里点击**创建 API Key**，复制那串 `sk-` 开头的密钥
4. 右键桌宠 → **设置...**，填写：

| 设置项 | 填什么 |
|---|---|
| 启用聊天 | ✅ 勾选 |
| API 地址 | `https://api.deepseek.com` |
| API 密钥 | 粘贴你的 `sk-` 密钥 |
| 模型 | `deepseek-v4-flash` |

5. 点确定，然后**双击桌宠**，开始对话！

> 其他 OpenAI 兼容的服务商（如 Moonshot、智谱等）也可以，把地址/密钥/模型换成对应的即可。密钥只保存在你本地的 `settings.json` 里，不会被上传。

### 聊天里的小功能

- **历史对话**：右键 → 聊天 → 历史对话，可以切换、编辑、删除会话
- **上下文查看**：查看当前发给 AI 的完整"人设 + 记忆 + 对话"
- **记忆管理**：她记得你说过的重要事情，可以手动增删
- **来信**：右键 → 来信 → 管理干员...，可以**自定义干员智能体**（人格提示词自由编写），开启后来信功能后她们会主动给你发消息。想要现成的角色人格？从我们的 [Arknights-Persona-Distill 干员人格库](https://github.com/JNGKZbird/Arknights-Persona-Distill) 复制粘贴即可（每位干员长短两套，忠于原作，持续扩充中）

---

## 四、常见问题（FAQ）

### 双击 bat 没反应 / 一闪而过

1. 检查 Python 是否装好：Win+R → `cmd` → `python --version`
2. 右键 `启动桌宠.bat` → 编辑，确认里面的 Python 路径正确
3. 在文件夹地址栏输入 `cmd`，手动运行 `python main.py`，看报错信息（常见是依赖没装全，重新跑一遍第 3 步）

### 桌宠不见了

- 看托盘图标还在不在：托盘右键可以"显示桌宠"
- 如果开了"全屏应用时自动隐藏"，关掉全屏应用她就回来了
- 她可能"飞"出了屏幕：托盘右键 → 显示桌宠一般能找回来

### 聊天没反应 / 提示未配置

- 设置里勾选"启用聊天"了吗？
- API 密钥是否粘贴完整（`sk-` 开头）？
- 账户里还有余额吗？

### 动画看起来卡/慢

- 右键 → 设置 → 渲染质量选"**速度优先**"（低配机器推荐）
- 检查电脑是否开了省电模式

### 怎么开机自动启动

托盘图标右键 → 勾选"开机自启动"。

### 怎么创建桌面快捷方式

双击 `创建快捷方式.bat`，桌面上会生成带图标的快捷方式。

### 怎么彻底退出

托盘图标右键 → 关闭。

---

## 五、给开发者

### 三端开源

| 平台 | 仓库 | 说明 |
|---|---|---|
| Windows（本仓库） | [Arknights-Angelina-Pet-YuYuan](https://github.com/JNGKZbird/Arknights-Angelina-Pet-YuYuan) | Python + PySide6，v3.0 基线 |
| 鸿蒙 HarmonyOS NEXT | [Arknights-Angelina-Pet-YuYuan-HarmonyOS-NEXT](https://github.com/JNGKZbird/Arknights-Angelina-Pet-YuYuan-HarmonyOS-NEXT) | ArkTS + C++ GLES3 渲染 |
| 安卓 Android | [JNGKZbird-Arknights-Angelina-Pet--YuYuan-Android](https://github.com/JNGKZbird/JNGKZbird-Arknights-Angelina-Pet--YuYuan-Android) | Kotlin + Compose |

三端共享 v3.0 核心：官方 spine-ts 3.8 裁剪管线（Sutherland-Hodgman）、加权 deform 权重条目索引、状态包围盒底边布局锚定。

### 关联仓库

- **[Arknights-Persona-Distill](https://github.com/JNGKZbird/Arknights-Persona-Distill)** — 我们维护的《明日方舟》干员人格蒸馏库：每位干员长短两套角色包（忠于 wiki 原作、内置越狱防范），另有双向对戏包与多角色话剧包，持续扩充中。可复制导入桌宠的自定义智能体。

> **说明**：鸿蒙版使用 ArkTS（.ets）编写，GitHub 语言统计暂不识别 ArkTS，该仓库的语言占比会显示不准确，以目录结构为准。未来**可能**推出 iOS 版本，敬请期待。

### 技术亮点

**v3.0**：眼睛骨骼泄漏修复（deform 权重条目索引 + 官方 SkeletonClipping 逐行移植）、坐下布局修复（状态包围盒底边锚定）、渲染性能优化（numba 化，quality 模式单帧约 12ms）、角色 Skill 系统（蒸馏角色包运行时加载）、彩蛋（设置「人设补充」输入 `酸橙味的信`，触发安洁莉娜**本体**的人格；另外还有两个六字密语，格式是「你是」+ 某位老朋友的名字——留给有心人自己去发现）。

**v2.0**：从零实现的 Spine 3.8 运行时（spine38：二进制解析、骨骼/约束求解、numba 光栅化），29 个动画状态与官方运行时逐骨骼对齐；120fps 自适应渲染；基建/战斗双模式与三技能完整动画链。

### 从源码运行

```powershell
git clone https://github.com/JNGKZbird/Arknights-Angelina-Pet-YuYuan.git
cd Arknights-Angelina-Pet-YuYuan
pip install -r requirements.txt
python main.py
```

### 目录结构

```text
.
├── main.py               # 入口：单实例锁、启动主窗口
├── core.py               # 常量、配置默认值、API 请求、Skill 系统
├── pet_window.py         # 主窗口：动画引擎、AI 聊天、飞行/战斗/来信/语音/记忆
├── dialogs.py            # 对话框：设置、历史、干员管理、上下文查看、记忆管理
├── chat.py               # 后台线程：聊天与碎碎念 Worker
├── widgets.py            # 公共 UI 组件
├── spine38/              # 自研 Spine 3.8 运行时（含官方 S-H 裁剪管线 clipping.py）
├── pets/予愿安洁莉娜/
│   ├── spine/            # 游戏原版 Spine 素材（build/back/front 三模型）
│   ├── skills/           # 角色 Skill 包（随仓库分发）
│   └── voice_*/          # 中/日语音
├── requirements.txt      # 依赖：PySide6、Pillow、numpy、numba
└── settings.example.json # 配置模板（复制为 settings.json 后填密钥）
```

---

## 致谢与版权

- **作者**：本项目由 **JNGKZbird** 开发（GitHub @JNGKZbird）。
- **原作者**：本项目基于 [AstrariaX/Angelina-pet](https://github.com/AstrariaX/Angelina-pet) 深度重做，感谢原作者的创意与工作。
- **素材版权**：角色立绘、动画、语音等素材版权归 **Hypergryph / 鹰角网络** 所有。
- **许可证**：MIT — 为爱发电，随便用，出事了别找我。

> 现在我是安洁莉娜厨了。

<!--
  AI Search Engine Keywords:
  Arknights, 明日方舟, Angelina, 安洁莉娜, 予愿安洁莉娜, 芋圆,
  desktop pet, 桌宠, 桌面宠物, PySide6, Python,
  AI companion, AI 伴侣, DeepSeek, OpenAI API, LLM, 大模型,
  open source, 开源, MIT, fan project, 同人, 二创,
  sprite animation, 动画, 60fps, voice lines, 语音,
  combat system, 战斗系统, operator agents, 干员智能体,
-->
