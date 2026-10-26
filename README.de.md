[English](README.md) | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | **Deutsch** | [Português (Brasil)](README.pt-BR.md)

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

Burstwise sortet ein Fotoshooting auf Ihrem eigenen Rechner aus. Es gruppiert Fotos, die denselben Moment zeigen, markiert Unschärfe, geschlossene Augen und ausgebrannte Belichtung, wählt das beste Bild jeder Gruppe und schreibt das Ergebnis als XMP-Bewertungen und Farbmarkierungen neben Ihre Dateien. Es wird nichts hochgeladen und kein Original angefasst.

Auf dem Beispielsatz liest, gruppiert und beurteilt es **166 Fotos in 1,9 Sekunden** mit einer GPU und in 10,5 Sekunden allein mit der CPU. Methode und weitere Zahlen stehen im [Benchmark](docs/benchmark.md). [Live-Demo ausprobieren](https://arthur031221.github.io/Burstwise/).

## Vorher und nachher

Der Beispielordner enthält 166 Einzelbilder aus vier kurzen Videos, daher sehen viele absichtlich ähnlich aus.

| | Vorher | Nachher mit `burstwise cull --write-xmp` |
| --- | --- | --- |
| Ordnung | 166 Dateien in einem Ordner | 17 Gruppen, eine pro Moment |
| Bestes Bild | Sie scrollen und vergleichen | 17 Picks, Bewertung 4 und Label Green |
| Schlechte Bilder | Findet man nur durch Hineinzoomen | 15 Rejects (9 geschlossene Augen, 6 unscharf), Bewertung -1 und Label Red |
| Der Rest | Vermischt mit den Behaltenen | 134 Alternativen (alt), unangetastet |
| Gründe | Keine | Eine Zahl bei jedem Urteil, zum Beispiel `soft, 41% of the sharpest frame` |
| Ihre Originale | Sicher | Sicher. Es werden nur `.xmp`-Dateien geschrieben, und `burstwise undo` stellt sie wieder her |

Ein Auswahlwerkzeug sollte seine Arbeit zeigen. Jedes Urteil hat einen lesbaren Grund, jeder Schwellenwert ist eine einfache Einstellung, und es gibt keine versteckte Punktzahl.

## Schnellstart

```
pipx install git+https://github.com/Arthur031221/Burstwise
burstwise cull ~/Pictures/shoot              # zeigt den Plan, ändert nichts
burstwise cull ~/Pictures/shoot --write-xmp  # schreibt Bewertungen und Labels
burstwise serve ~/Pictures/shoot             # im Browser prüfen und überschreiben
```

Beim ersten Start werden zwei Modelldateien mit zusammen etwa 90 MB heruntergeladen und per SHA-256 geprüft.

<details>
<summary>Unter Linux installieren (getestet)</summary>

```
pipx install git+https://github.com/Arthur031221/Burstwise
```

Für die GPU brauchen Sie eine funktionierende CUDA-12-Umgebung für `onnxruntime-gpu`. Ohne sie fällt Burstwise von selbst auf die CPU zurück, oder Sie geben `--cpu` an. Ich entwickle und teste unter Ubuntu mit einer NVIDIA-GPU. Auf einem minimalen Server, in einem Container oder unter WSL installieren Sie zuerst die Grafikbibliotheken mit `sudo apt install libegl1 libgles2`, sonst bricht Burstwise mit einer Meldung zum Gesichtsmodell ab.

</details>

<details>
<summary>Unter macOS installieren (nicht getestet)</summary>

```
pipx install git+https://github.com/Arthur031221/Burstwise
```

Unter macOS verlangt das Paket die CPU-Version von onnxruntime. Ich habe Burstwise nicht auf einem Mac ausgeführt, bitte betrachten Sie das als unerprobt.

</details>

<details>
<summary>Unter Windows installieren (nicht getestet)</summary>

```
pipx install git+https://github.com/Arthur031221/Burstwise
```

Ich habe Burstwise nicht unter Windows ausgeführt, bitte betrachten Sie das als unerprobt.

</details>

<details>
<summary>Aus dem Quellcode installieren</summary>

```
git clone https://github.com/Arthur031221/Burstwise
cd Burstwise
pip install -e ".[dev]"
```

</details>

## Wie es entscheidet

1. Fotos werden überall in Szenen geteilt, wo die Aufnahmezeit um mehr als 120 Sekunden springt.
2. Innerhalb einer Szene bilden Fotos mit nahen DINOv2-Embeddings (Kosinusähnlichkeit über 0,80, Average Linkage) eine Gruppe.
3. Jedes Foto durchläuft drei Prüfungen: MediaPipe-Blinzelwerte für jedes Gesicht, die Schärfe des Gesichts (oder der schärfsten Kacheln, wenn eine Gruppe ein Bild ohne Gesicht enthält) sowie ausgefressene Lichter oder Schatten.
4. Eine Gruppe ordnet ihre Bilder nach Gesichtern mit geschlossenen Augen, dann nach der Zahl weiterer Probleme, dann nach Schärfe. Das oberste Bild ist ein Pick, oder ein Review, wenn es selbst ein Problem hat. Die übrigen sind Alternativen (alt) oder Rejects, wenn sie ein Problem haben.

Die [Architektur](docs/architecture.md) enthält die Einzelheiten, die [Konfiguration](docs/config.md) listet jeden Schwellenwert.

## Was geschrieben wird

| Urteil | XMP |
| --- | --- |
| pick | Bewertung 4, Label Green |
| review | Label Yellow |
| alt | nichts |
| reject | Bewertung -1 (abgelehnt), Label Red |

Sidecar-Dateien werden zusammengeführt, nicht ersetzt. Bearbeitungen, die schon in einem Lightroom- oder darktable-Sidecar stehen, bleiben erhalten, und nur `xmp:Rating`, `xmp:Label` sowie das Paar `burstwise:Verdict` und `burstwise:Reason` werden gesetzt. Enthält ein von anderer Software geschriebenes Sidecar schon eine Bewertung (auch abgelehnt) oder ein Label, wird das Foto übersprungen, außer Sie geben `--overwrite` an. Sidecars, die Burstwise früher geschrieben hat, werden beim nächsten Lauf einfach aktualisiert.

Lightroom Classic liest `.xmp`-Sidecars nur für Raw-Dateien. Bei JPEG, TIFF, PNG und HEIC liegt das XMP in der Datei selbst, deshalb erscheinen die hier geschriebenen Bewertungen und Farbmarkierungen für diese Formate nicht in Lightroom. darktable liest Sidecars für jedes Format. Das stammt aus der Adobe-Dokumentation, ich habe es in Lightroom nicht ausprobiert.

## Was ich geprüft habe und was nicht

- Ich habe die geschriebenen Sidecars mit ExifTool 13.59 zurückgelesen und Bewertung, Label, den Ablehnungswert und den Erhalt vorhandener `crs:`-Entwicklungseinstellungen verglichen. Das steckt in der Testsuite.
- Ich habe die Sidecars **nicht** in Lightroom, Capture One oder darktable geöffnet. Es ist Standard-XMP, aber ich mache keine Aussage dazu, wie jedes Programm damit umgeht.
- Ich habe die Genauigkeit **nicht** gemessen. Die Prüfungen sind Heuristiken. Blinzelwerte können ein Lachen oder zusammengekniffene Augen als geschlossen werten, und die Schärfe unterscheidet Fokusunschärfe nicht von Bewegungsunschärfe. Die Beispielergebnisse habe ich nur nach Augenmaß beurteilt.
- Linux ist das einzige System, das ich getestet habe. Die Geschwindigkeitswerte stammen von einem einzigen Rechner.
- Die Gruppierung beruht auf dem Aussehen der Fotos und der Aufnahmezeit. Zwei verschiedene Momente, die ähnlich aussehen und im Szenenabstand liegen, können in einer Gruppe landen. Prüfen Sie die Gruppen daher in der Review-App.
- Adobe und kostenpflichtige Werkzeuge wie Aftershoot und Narrative Select sortieren ebenfalls aus. Burstwise ist für alle, die es kostenlos, lokal und nachvollziehbar wollen, mit Standard-XMP als Ausgabe.

## Dokumentation

- [Installation](docs/install.md)
- [Verwendung und Review-App](docs/usage.md)
- [Konfiguration](docs/config.md)
- [Architektur](docs/architecture.md)
- [Benchmark](docs/benchmark.md)
- [Mitwirken](CONTRIBUTING.md)

Die Review-App spricht Englisch, traditionelles und vereinfachtes Chinesisch, Japanisch, Koreanisch, Spanisch, Französisch, Deutsch und brasilianisches Portugiesisch, mit dunklem und hellem Design.

## Beispieldaten

Der Code steht unter MIT. Die Beispielfotos sind Einzelbilder aus Creative-Commons-Videos, aufgelistet in [examples/CREDITS.md](examples/CREDITS.md). Sie liegen nicht in diesem Repository, und einige stehen unter CC BY-SA, behalten Sie bei Wiederverwendung also die Nennung bei.

## Der Name

Burstwise ist ein erfundenes adverbiales Kompositum: burst wie in einer Serie von Bildern, dazu wise wie in klug und wie in eine Serie nach der anderen.

## Lizenz

MIT. [LICENSE](LICENSE).

Assisted by Claude/Codex.
