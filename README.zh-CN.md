[English](README.md) | [繁體中文](README.zh-TW.md) | **简体中文** | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Português (Brasil)](README.pt-BR.md)

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/banner-dark.svg">
    <img src="assets/banner-light.svg" alt="Burstwise" width="720">
  </picture>
</p>

<p align="center">
  <a href="https://github.com/Arthur031221/Burstwise/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/Arthur031221/Burstwise/ci.yml?branch=master&label=tests&labelColor=0e1015&color=ffb020" alt="tests"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-ffb020?labelColor=0e1015" alt="python 3.10+">
  <img src="https://img.shields.io/badge/license-MIT-ffb020?labelColor=0e1015" alt="MIT license">
  <a href="https://arthur031221.github.io/Burstwise/"><img src="https://img.shields.io/badge/live%20demo-open-ffb020?labelColor=0e1015" alt="live demo"></a>
</p>

<p align="center">
  <img src="assets/demo.gif" alt="Burstwise demo" width="880">
</p>

Burstwise 在你自己的电脑上帮你挑照片。它把拍到同一刻的照片分成一组，标出模糊、闭眼和曝光溢出的画面，从每组挑出最好的一张，并把结果以 XMP 评分和色标写在原文件旁边。不会上传任何内容，也不会改动任何原始文件。

在示例数据集上，它用 GPU 读取、分组并评判 **166 张照片只需 1.9 秒**，只用 CPU 则是 10.5 秒。方法和其他数字见[性能测试](docs/benchmark.md)。[试试在线演示](https://arthur031221.github.io/Burstwise/)。

## 处理前与处理后

示例文件夹是从四段短视频截出的 166 个画面，所以很多张看起来很像，这是有意为之。

| | 处理前 | 运行 `burstwise cull --write-xmp` |
| --- | --- | --- |
| 顺序 | 166 个文件放在同一个文件夹 | 17 组，每个时刻一组 |
| 最佳画面 | 你得自己滚动和比较 | 17 张精选，评 4 星并标绿色 |
| 坏画面 | 要逐张放大才能找到 | 15 张淘汰（9 张闭眼、6 张模糊），评 -1 并标红色 |
| 其余 | 和要留的照片混在一起 | 134 张备选，完全不动 |
| 理由 | 没有 | 每个判定都有数字，例如 `soft, 41% of the sharpest frame` |
| 你的原始文件 | 安全 | 安全。只会写入 `.xmp` 文件，而且 `burstwise undo` 可以还原 |

选片工具应该把过程摊开来。每个判定都有看得懂的理由，每个阈值都是明确的设置，没有隐藏的分数。

## 快速开始

```
pipx install git+https://github.com/Arthur031221/Burstwise
burstwise cull ~/Pictures/shoot              # 只列出计划，不做任何更改
burstwise cull ~/Pictures/shoot --write-xmp  # 写入评分和色标
burstwise serve ~/Pictures/shoot             # 在浏览器里查看并覆盖
```

第一次运行会下载两个模型文件，合计约 90 MB，并校验 SHA-256。

<details>
<summary>在 Linux 安装（已测试）</summary>

```
pipx install git+https://github.com/Arthur031221/Burstwise
```

要使用 GPU，`onnxruntime-gpu` 需要可用的 CUDA 12 环境。没有的话 Burstwise 会自动回退到 CPU，也可以加上 `--cpu`。我是在带 NVIDIA GPU 的 Ubuntu 上开发和测试的。

</details>

<details>
<summary>在 macOS 安装（未测试）</summary>

```
pipx install git+https://github.com/Arthur031221/Burstwise
```

在 macOS 上，软件包会要求安装 CPU 版的 onnxruntime。我没有在 Mac 上运行过 Burstwise，请当作还没试过。

</details>

<details>
<summary>在 Windows 安装（未测试）</summary>

```
pipx install git+https://github.com/Arthur031221/Burstwise
```

我没有在 Windows 上运行过 Burstwise，请当作还没试过。

</details>

<details>
<summary>从源码安装</summary>

```
git clone https://github.com/Arthur031221/Burstwise
cd Burstwise
pip install -e ".[dev]"
```

</details>

## 判断方式

1. 拍摄时间相差超过 120 秒的地方，照片会被切分为不同场景。
2. 在同一个场景内，DINOv2 嵌入向量相近（余弦相似度高于 0.80，平均连接法）的照片组成一组。
3. 每张照片做三项检查：每张脸的 MediaPipe 眨眼分数、脸部清晰度（如果一组里有一张没有脸，就改用最清晰的几个区块），以及高光或暗部是否溢出。
4. 一组内按闭眼人数、其他问题的数量、清晰度排序。排第一的是精选，如果它本身有问题就标为待查看。其余的是备选，有问题的则是淘汰。

细节见[架构](docs/architecture.md)，所有阈值列在[配置](docs/config.md)。

## 它会写入什么

| 判定 | XMP |
| --- | --- |
| pick | 评分 4，色标 Green |
| review | 色标 Yellow |
| alt | 不写入 |
| reject | 评分 -1（已淘汰），色标 Red |

Sidecar 文件是合并而不是覆盖。Lightroom 或 darktable 里已有的编辑会保留，只会设置 `xmp:Rating`、`xmp:Label` 以及一组 `burstwise:Verdict` 和 `burstwise:Reason`。如果别人写的 sidecar 已经有评分（包含已淘汰）或色标，该照片会被跳过，除非加上 `--overwrite`。Burstwise 之前写的 sidecar 则会在下次运行时直接更新。

## 我检查过什么，没检查什么

- 我用 ExifTool 13.59 把写出的 sidecar 读回来，核对评分、色标、淘汰值，并确认已有的 `crs:` 显影设置会保留。这些都在测试套件里。
- 我**没有**在 Lightroom、Capture One 或 darktable 里打开过这些 sidecar。它们是标准 XMP，但我不声称各程序会如何处理。
- 我**没有**测量准确率。这些检查都是启发式规则。眨眼分数可能把大笑或眯眼当成闭眼，清晰度也分不清对焦模糊和动态模糊。示例结果我只用肉眼判断过。
- 我只在 Linux 上测试过。速度数字来自同一台机器。
- 分组依据的是照片的外观和拍摄时间。两个不同的时刻如果外观相近又落在场景间隔内，可能被分到同一组，所以请在查看界面里确认分组。
- Adobe 和付费工具（例如 Aftershoot、Narrative Select）也有选片功能。Burstwise 面向想要免费、在本机运行、看得懂规则，并以标准 XMP 作为输出的人。

## 文档

- [安装](docs/install.md)
- [使用方法与查看界面](docs/usage.md)
- [配置](docs/config.md)
- [架构](docs/architecture.md)
- [性能测试](docs/benchmark.md)
- [参与贡献](CONTRIBUTING.md)

查看界面支持英文、繁体中文、简体中文、日文、韩文、西班牙文、法文、德文和巴西葡萄牙文，并有深色和浅色主题。

## 示例数据

代码采用 MIT 许可。示例照片是从 Creative Commons 视频截出的画面，列在 [examples/CREDITS.md](examples/CREDITS.md)。它们不放在这个仓库里，其中有些是 CC BY-SA，重复使用时请保留署名。

## 名称由来

Burstwise 是自造的副词式复合词：burst 指连拍的一串画面，wise 有「明智」的意思，也有「一次一个连拍」的语感。

## 许可证

MIT. [LICENSE](LICENSE).

Assisted by Claude/Codex.
