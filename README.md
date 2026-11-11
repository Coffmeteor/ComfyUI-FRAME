# FRAME Nodes

**在电脑选择自己的 LoRA，在手机用命名开关生成。**

FRAME 把本机模型、LoRA 强度、触发词和分组保存为不可变配方，再生成只有
提示词与开关的 ComfyUI 工作流。公开包不带个人 LoRA 名单、权重或账号凭据。
基础节点可以接入标准 MODEL / CLIP / STRING 工作流；手机生成模板目前
支持 **Krea2**。在线 FRAME 词库可选，关闭时不请求网站。

## 安装

在 ComfyUI Manager 搜索 **FRAME Nodes**。Registry 版本若仍在审核，
可通过 **Install via Git URL** 安装：

```text
https://github.com/Coffmeteor/ComfyUI-FRAME
```

也可将仓库放入自己的 `ComfyUI/custom_nodes/`。需要 ComfyUI 0.43.0 或更新
版本；本包不安装或替换 PyTorch，不自动下载模型，不修改其他扩展。
安装后重启 ComfyUI、刷新浏览器。

## 电脑配方设置

1. 打开 ComfyUI 菜单中的 **FRAME → FRAME · 配方设置**。
2. 选择自己的 Krea2 主模型、文本编码器和 VAE。采样默认 8 步、CFG 1、
   Euler ancestral / beta；其他模型配方使用通用节点自行接线。
3. 添加 LoRA 分组，再从自己的注册模型目录选择文件。填写手机显示名称、
   模型/CLIP 强度及作用阶段。纯模型 LoRA 的 CLIP 强度使用零。
4. 触发词选择 `auto`、`manual` 或 `none`。自动读取支持明确的本地 sidecar
   触发词与 safetensors `modelspec.trigger_phrase`；不会根据文件名或训练
   标签猜测。没有元数据时，按作者说明手动填写或明确选择无需触发词。
5. 人物分组可设置“一次只允许开启一个”；风格分组可以叠加。
6. 点击 **保存配方并生成手机工作流**。工作流保存在设置的相对路径下，
   默认 `FRAME/FRAME Krea2 Mobile.json`。所有开关初始关闭，提示词留空。

配方保存在 ComfyUI 的 user 目录下的 `frame-nodes/`，升级包不覆盖它。
每次配置变化产生新版本，旧工作流继续使用旧版本。更换已配置文件后
重新保存配方；已启用但缺失/更换的 LoRA 不会被静默跳过。
上限为八组、每组 64 项，总计 128 项；空组不生成。

## 同步到 ComfyLink

保存配方后，**在队列空闲时重启 ComfyUI**，让 ComfyLink 重报新的节点
信息；然后在 ComfyLink 面板上传/更新该工作流，在手机同步导入。
桌面端新节点可即时注册，但 ComfyLink 云端节点快照需要这一步更新。

手机上只显示提示词、在线词库开关、画幅/画质开关和自己命名的 LoRA
开关。它不会出现 LoRA 文件路径、强度或触发词编辑框。一次开启多个
互斥人物或多个画幅会给出错误，需关闭冲突选项后重试。

工作流显示名保存在标准 UI 的 `extra.comfylink.name`。不支持此元数据的
ComfyLink 版本仍可能显示保存路径；命名、上传和同步行为取决于客户端
版本。本包不自动修改 ComfyLink。

## FRAME 在线词库

- **原版 / 改写版**：选择其中一类，从当前公开网站读取完整条目。
- **仅今日新增**：跟随网站最新公布的更新批次；关闭则从所选全库抽取。
  不是客户端过了午夜就清空。
- **固定随机种子**：同一库版本下使用固定抽取及采样种子；网站更新后
  条目位置可能变化。关闭时每次 Generate 都重新抽取。
- 最终顺序为 LoRA 自动触发词、完整 FRAME 条目、用户补充。关闭 LoRA
  只移除自动注入部分，保留用户自己输入的文字。

网络失败、空更新批次或版本不一致会明确报错，不会偷偷切到其他类别。
该功能只读取 `https://frame.coffmetoer.tech/frame-api/v1/` 的公开数据；
不上传用户提示词、图片或模型名单。没有后台全库爬取、遥测或模型下载。

## 可选增强

基础生成和通用 LoRA 节点只使用 ComfyUI。额外开关需要先安装对应扩展、
在电脑选择所需模型：

| 开关 | 依赖 |
|---|---|
| 高清重绘 | Ultimate SD Upscale 扩展、图像放大模型 |
| 面部细修 | Impact Pack / Subpack、Ultralytics 检测模型 |
| SeedVR2 修复 | 当前 ComfyUI 原生 SeedVR2 节点、相应模型及 VAE、图像放大模型 |
| 备用模型 | 电脑设置中选择的备用 Krea2 模型 |

未启用的增强不加载其依赖。启用但未配置时先报具体缺失项，不安装依赖，
不切换模型家族。保留用户 ComfyUI 的默认内存、设备和卸载策略。

## 分享与隐私

接收者安装本包后，使用电脑设置页绑定**自己的**模型并生成自己的手机
工作流。本机生成的快照节点属于本机配方，不能只把它的 JSON 发给另一台
电脑并期待找到相同配置。

分享代码包不包含配方。分享生成的手机工作流会显示该配方的 LoRA 名称，
但不含权重和账号凭据。生成图片保留 `frame` 提示词/配方记录及 ComfyUI
工作流元数据；公开图片前应检查这些文字。不要分享 ComfyLink 状态文件。

ComfyLink **共享后端**模式与在自己的电脑运行不同。部分插件版本只允许
标准文本节点修改文字，自定义 FRAME 提示词可能被共享校验拒绝。使用
`compat/` 中的有界适配补丁或支持该接口的后续插件版本；不应允许修改
任意图或所有字符串。本包不会自动开启共享、配对账户或修改插件源码。

## English

Configure your own local models and LoRAs on desktop, then export a phone workflow
with one prompt and named Boolean switches. The package contains no personal
presets, credentials or model weights. Generic LoRA/trigger nodes compose with
standard ComfyUI workflows; the complete mobile recipe currently targets Krea2.

Install from Manager or the Git URL above. Open **FRAME → FRAME · 配方设置** in
ComfyUI, select the Krea2 model/text encoder/VAE, create LoRA groups, and save.
Recipe versions are immutable and stored under the ComfyUI user directory.
Restart ComfyUI while idle to refresh ComfyLink's node snapshot, upload the saved
workflow, and sync it on the phone. Updating a desktop recipe requires syncing
the newly generated workflow; older queued jobs retain their original recipe.

Set CLIP strength to zero for model-only LoRAs. Automatic triggers come from
explicit local metadata, never guessed training tags. Manual/none modes are
available. FRAME original/rewrite catalogs are optional public read-only sources.
No user prompts, images or model inventory are sent to FRAME.

Optional enhancements require their listed extensions and local models. Windows
and Linux paths are covered by unit CI; GPU execution was verified on Linux.
Windows GPU and physical ComfyLink mobile rendering need local acceptance.

## Development and releases

```bash
python -m unittest discover -s tests -v
```

Versions use Comfy Registry metadata in `pyproject.toml`. Tests and runtime state
are excluded from the Registry archive through `.comfyignore`/`.gitignore`.
Publishing credentials belong in GitHub Actions secrets, never in this repository.
Registry upload and platform review/indexing are separate states. See
[`VALIDATION.md`](VALIDATION.md) for the tested scope.

MIT licensed package code. Model weights and public website content retain their
own terms; they are not redistributed in the node package.
