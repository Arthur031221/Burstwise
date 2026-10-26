[English](README.md) | **繁體中文** | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Português (Brasil)](README.pt-BR.md)

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/banner-dark.svg">
    <img src="assets/banner-light.svg" alt="Burstwise" width="720">
  </picture>
</p>

<p align="center">
  <a href="https://github.com/Arthur031221/Burstwise/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/Arthur031221/Burstwise/ci.yml?branch=main&label=tests&labelColor=0e1015&color=ffb020" alt="tests"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-ffb020?labelColor=0e1015" alt="python 3.10+">
  <img src="https://img.shields.io/badge/license-MIT-ffb020?labelColor=0e1015" alt="MIT license">
  <a href="https://arthur031221.github.io/Burstwise/"><img src="https://img.shields.io/badge/live%20demo-open-ffb020?labelColor=0e1015" alt="live demo"></a>
</p>

<p align="center">
  <img src="assets/demo.gif" alt="Burstwise demo" width="880">
</p>

Burstwise 在你自己的電腦上幫你挑照片。它把拍到同一刻的照片分成一組，標出模糊、閉眼和曝光溢出的畫面，從每組挑出最好的一張，並把結果以 XMP 評分和色標寫在原檔旁邊。不會上傳任何東西，也不會動到任何原始檔。

在範例資料集上，它用 GPU 讀取、分組並評判 **166 張照片只要 1.9 秒**，只用 CPU 則是 10.5 秒。方法和其他數字請看[效能測試](docs/benchmark.md)。[試試線上示範](https://arthur031221.github.io/Burstwise/)。

## 處理前與處理後

範例資料夾是從四段短影片截出的 166 個畫面，所以很多張看起來很像，這是刻意的。

| | 處理前 | 執行 `burstwise cull --write-xmp` |
| --- | --- | --- |
| 順序 | 166 個檔案放在同一個資料夾 | 17 組，每個時刻一組 |
| 最佳畫面 | 你得自己捲動和比較 | 17 張精選，評 4 星並標綠色 |
| 壞畫面 | 要一張張放大才找得到 | 15 張淘汰（9 張閉眼、6 張模糊），評 -1 並標紅色 |
| 其餘 | 和要留的照片混在一起 | 134 張備選，完全不動 |
| 理由 | 沒有 | 每個判定都有數字，例如 `soft, 41% of the sharpest frame` |
| 你的原始檔 | 安全 | 安全。只會寫入 `.xmp` 檔，而且 `burstwise undo` 可以還原 |

挑片工具應該把過程攤開來。每個判定都有看得懂的理由，每個門檻都是明確的設定，沒有隱藏的分數。

## 快速開始

```
pipx install git+https://github.com/Arthur031221/Burstwise
burstwise cull ~/Pictures/shoot              # 只列出計畫，不做任何更動
burstwise cull ~/Pictures/shoot --write-xmp  # 寫入評分和色標
burstwise serve ~/Pictures/shoot             # 在瀏覽器裡檢視並覆寫
```

第一次執行會下載兩個模型檔，合計約 90 MB，並檢查 SHA-256。

<details>
<summary>在 Linux 安裝（已測試）</summary>

```
pipx install git+https://github.com/Arthur031221/Burstwise
```

要用 GPU，`onnxruntime-gpu` 需要可用的 CUDA 12 環境。沒有的話 Burstwise 會自動退回 CPU，也可以加上 `--cpu`。我是在有 NVIDIA GPU 的 Ubuntu 上開發和測試。 在精簡的伺服器、容器或 WSL 上，請先用 `sudo apt install libegl1 libgles2` 安裝圖形函式庫，否則 Burstwise 會停下並提示臉部模型無法啟動。

</details>

<details>
<summary>在 macOS 安裝（未測試）</summary>

```
pipx install git+https://github.com/Arthur031221/Burstwise
```

macOS 上套件會要求安裝 CPU 版的 onnxruntime。我沒有在 Mac 上跑過 Burstwise，請當作還沒試過。

</details>

<details>
<summary>在 Windows 安裝（未測試）</summary>

```
pipx install git+https://github.com/Arthur031221/Burstwise
```

我沒有在 Windows 上跑過 Burstwise，請當作還沒試過。

</details>

<details>
<summary>從原始碼安裝</summary>

```
git clone https://github.com/Arthur031221/Burstwise
cd Burstwise
pip install -e ".[dev]"
```

</details>

## 判斷方式

1. 拍攝時間相差超過 120 秒的地方，照片會被切成不同場景。
2. 在同一個場景內，DINOv2 嵌入向量相近（餘弦相似度高於 0.80，平均連結法）的照片組成一組。
3. 每張照片做三項檢查：每張臉的 MediaPipe 眨眼分數、臉部清晰度（如果群組裡有一張沒有臉，就改用最清晰的幾個區塊），以及高光或暗部是否溢出。
4. 一組內依照閉眼人數、其他問題的數量、清晰度排序。排第一的是精選，如果它本身有問題就標為待檢視。其餘的是備選，有問題的則是淘汰。

細節請看[架構](docs/architecture.md)，所有門檻列在[設定](docs/config.md)。

## 它會寫入什麼

| 判定 | XMP |
| --- | --- |
| pick | 評分 4，色標 Green |
| review | 色標 Yellow |
| alt | 不寫入 |
| reject | 評分 -1（已淘汰），色標 Red |

Sidecar 檔是合併而不是覆蓋。Lightroom 或 darktable 已經存在的編輯會保留，只會設定 `xmp:Rating`、`xmp:Label` 以及一組 `burstwise:Verdict` 和 `burstwise:Reason`。如果別人寫的 sidecar 已經有評分（包含已淘汰）或色標，該照片會被跳過，除非加上 `--overwrite`。Burstwise 之前寫的 sidecar 則會在下次執行時直接更新。

Lightroom Classic 只會對 raw 檔讀取 `.xmp` sidecar。JPEG、TIFF、PNG 和 HEIC 的 XMP 存在檔案內部，所以這裡寫入的評分和標籤不會在 Lightroom 裡顯示。darktable 對所有格式都會讀取 sidecar。這一點來自 Adobe 的文件，我沒有在 Lightroom 裡試過。

## 我檢查過什麼，沒檢查什麼

- 我用 ExifTool 13.59 把寫出的 sidecar 讀回來，比對評分、色標、淘汰值，並確認既有的 `crs:` 顯影設定會保留。這些都在測試套件裡。
- 我**沒有**在 Lightroom、Capture One 或 darktable 裡開過這些 sidecar。它們是標準 XMP，但我不宣稱各程式會如何處理。
- 我**沒有**量測準確率。這些檢查都是啟發式規則。眨眼分數可能把大笑或瞇眼當成閉眼，清晰度也分不出對焦模糊和動態模糊。範例結果我只用肉眼判斷過。
- 我只在 Linux 上測試過。速度數字來自同一台機器。
- 分組依據的是照片的外觀和拍攝時間。兩個不同的時刻如果外觀相近又落在場景間隔內，可能被分到同一組，所以請在檢視介面裡確認分組。
- Adobe 和付費工具（例如 Aftershoot、Narrative Select）也有挑片功能。Burstwise 給想要免費、在本機執行、看得懂規則，並以標準 XMP 作為輸出的人。

## 文件

- [安裝](docs/install.md)
- [使用方式與檢視介面](docs/usage.md)
- [設定](docs/config.md)
- [架構](docs/architecture.md)
- [效能測試](docs/benchmark.md)
- [參與貢獻](CONTRIBUTING.md)

檢視介面會把每組最好的一張放大顯示並收合過長的組別，方向鍵、P、X、U 與 1 到 5 可直接在格狀畫面操作。 檢視介面支援英文、繁體中文、簡體中文、日文、韓文、西班牙文、法文、德文和巴西葡萄牙文，並有深色和淺色主題。

## 範例資料

程式碼採用 MIT 授權。範例照片是從 Creative Commons 影片截出的畫面，列在 [examples/CREDITS.md](examples/CREDITS.md)。它們不放在這個儲存庫裡，其中有些是 CC BY-SA，重複使用時請保留署名。

## 名稱由來

Burstwise 是自創的副詞式複合詞：burst 指連拍的一串畫面，wise 有「明智」的意思，也有「一次一個連拍」的語感。

## 授權

MIT. [LICENSE](LICENSE).

Assisted by Claude/Codex.
