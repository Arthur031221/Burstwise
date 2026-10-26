[English](README.md) | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md) | **日本語** | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Português (Brasil)](README.pt-BR.md)

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

Burstwise は、あなた自身のマシンで撮影データの選別を行います。同じ瞬間を写した写真をグループにまとめ、ブレ、目つぶり、露出の飛びを見つけ、各グループから最良の 1 枚を選び、その結果を XMP の評価とカラーラベルとして元ファイルの隣に書き出します。何もアップロードせず、元のファイルには一切触れません。

サンプルセットでは、GPU で **166 枚を 1.9 秒** で読み込み、グループ化し、判定します。CPU のみでは 10.5 秒です。方法とその他の数値は[ベンチマーク](docs/benchmark.md)にあります。[ライブデモを試す](https://arthur031221.github.io/Burstwise/)。

## Before と After

サンプルフォルダは 4 本の短い動画から切り出した 166 フレームです。似たフレームが多いのは意図的です。

| | Before | 実行後 `burstwise cull --write-xmp` |
| --- | --- | --- |
| 並び | 166 ファイルが 1 つのフォルダに入っている | 17 グループ、瞬間ごとに 1 つ |
| ベストの 1 枚 | スクロールして比べる | 17 枚を pick に選び、評価 4、ラベル Green |
| 失敗フレーム | 1 枚ずつ拡大して探す | 15 枚を reject（目つぶり 9、ソフト 6）、評価 -1、ラベル Red |
| それ以外 | 残す写真と混ざっている | 134 枚は alt として、そのまま |
| 理由 | なし | すべての判定に数値つきの理由。例: `soft, 41% of the sharpest frame` |
| 元ファイル | 安全 | 安全。書き込むのは `.xmp` ファイルだけで、`burstwise undo` で元に戻せます |

選別ツールは根拠を見せるべきだと考えています。どの判定にも読める理由があり、どのしきい値も単純な設定で、隠れたスコアはありません。

## クイックスタート

```
pipx install git+https://github.com/Arthur031221/Burstwise
burstwise cull ~/Pictures/shoot              # 計画を表示するだけで、何も変更しない
burstwise cull ~/Pictures/shoot --write-xmp  # 評価とラベルを書き込む
burstwise serve ~/Pictures/shoot             # ブラウザで確認して上書きする
```

初回の実行では、合計約 90 MB の 2 つのモデルファイルをダウンロードし、SHA-256 を検証します。

<details>
<summary>Linux にインストール（テスト済み）</summary>

```
pipx install git+https://github.com/Arthur031221/Burstwise
```

GPU を使うには、`onnxruntime-gpu` が動作する CUDA 12 環境が必要です。ない場合は自動的に CPU に切り替わります。`--cpu` を付けても構いません。開発とテストは NVIDIA GPU を積んだ Ubuntu で行っています。 最小構成のサーバー、コンテナ、WSL では、先に `sudo apt install libegl1 libgles2` でグラフィックスライブラリを入れてください。入っていないと Burstwise は顔モデルについてのメッセージを出して止まります。

</details>

<details>
<summary>macOS にインストール（未テスト）</summary>

```
pipx install git+https://github.com/Arthur031221/Burstwise
```

macOS では、パッケージは CPU 版の onnxruntime を要求します。Mac で Burstwise を動かしたことはないため、未検証として扱ってください。

</details>

<details>
<summary>Windows にインストール（未テスト）</summary>

```
pipx install git+https://github.com/Arthur031221/Burstwise
```

Windows で Burstwise を動かしたことはないため、未検証として扱ってください。

</details>

<details>
<summary>ソースからインストール</summary>

```
git clone https://github.com/Arthur031221/Burstwise
cd Burstwise
pip install -e ".[dev]"
```

</details>

## 判定のしくみ

1. 撮影時刻が 120 秒を超えて飛ぶところで、写真をシーンに分けます。
2. 同じシーン内で、DINOv2 の埋め込みが近い写真（コサイン類似度が 0.80 より高い、平均連結法）を 1 つのグループにします。
3. 各写真に 3 つのチェックをします。顔ごとの MediaPipe のまばたきスコア、顔のシャープさ（グループに顔のないフレームがある場合は最もシャープなタイル）、ハイライトとシャドウの飛びです。
4. グループ内では、目を閉じた顔の数、その他の問題の数、シャープさの順に並べます。先頭は pick になり、本人に問題があれば review になります。それ以外は alt で、問題があれば reject です。

詳細は[アーキテクチャ](docs/architecture.md)、すべてのしきい値は[設定](docs/config.md)にあります。

## 書き出す内容

| 判定 | XMP |
| --- | --- |
| pick | 評価 4、ラベル Green |
| review | ラベル Yellow |
| alt | なし |
| reject | 評価 -1（リジェクト）、ラベル Red |

サイドカーは置き換えではなくマージします。Lightroom や darktable のサイドカーにすでにある編集は残り、設定するのは `xmp:Rating`、`xmp:Label`、そして `burstwise:Verdict` と `burstwise:Reason` の組だけです。他のソフトが書いたサイドカーにすでに評価（リジェクトを含む）かラベルがある写真は、`--overwrite` を付けない限りスキップされます。Burstwise が以前に書いたサイドカーは、次の実行でそのまま更新されます。

Lightroom Classic が `.xmp` サイドカーを読むのは raw ファイルだけです。JPEG、TIFF、PNG、HEIC では XMP をファイルの中に持つため、ここで書き込んだ評価とラベルはこれらの形式では Lightroom に表示されません。darktable はすべての形式でサイドカーを読みます。これは Adobe のドキュメントに基づくもので、Lightroom では試していません。

## 確認したことと、していないこと

- 書き出したサイドカーを ExifTool 13.59 で読み戻し、評価、ラベル、リジェクト値を照合し、既存の `crs:` 現像設定が残ることを確認しました。これはテストスイートに含まれています。
- サイドカーを Lightroom、Capture One、darktable で開いては**いません**。標準的な XMP ですが、各ソフトがどう扱うかについては何も主張しません。
- 精度は**測っていません**。チェックはヒューリスティックです。笑顔や細めた目を目つぶりと判定することがあり、シャープさでは焦点ブレと動きブレを区別できません。サンプルの結果は目視で確認しただけです。
- テストしたのは Linux だけです。速度の数値は 1 台のマシンのものです。
- グループ化は写真の見た目と撮影時刻に基づきます。見た目が似ていてシーン間隔内にある別々の瞬間は、1 つのグループになることがあります。確認アプリでグループを見てください。
- Adobe や、Aftershoot、Narrative Select などの有料ツールにも選別機能があります。Burstwise は、無料でローカルで動き、ルールが読め、標準的な XMP を出力するものがほしい人向けです。

## ドキュメント

- [インストール](docs/install.md)
- [使い方と確認アプリ](docs/usage.md)
- [設定](docs/config.md)
- [アーキテクチャ](docs/architecture.md)
- [ベンチマーク](docs/benchmark.md)
- [コントリビュート](CONTRIBUTING.md)

レビュー画面ではグループごとにベストの 1 枚を大きく表示し、長いグループは折りたたみます。矢印キー、P、X、U、1 から 5 はグリッドからそのまま使えます。 確認アプリは英語、繁体字中国語、簡体字中国語、日本語、韓国語、スペイン語、フランス語、ドイツ語、ブラジルのポルトガル語に対応し、ダークとライトのテーマがあります。

## サンプルデータ

コードは MIT ライセンスです。サンプル写真は Creative Commons の動画から切り出したフレームで、[examples/CREDITS.md](examples/CREDITS.md) に一覧があります。このリポジトリには含まれていません。一部は CC BY-SA なので、再利用するときはクレジットを残してください。

## 名前について

Burstwise は作った副詞の複合語です。burst は連写のひとまとまり、wise は「賢く」の意味で、「連写を 1 つずつ」という響きも込めています。

## ライセンス

MIT. [LICENSE](LICENSE).

Assisted by Claude/Codex.
