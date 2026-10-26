[English](README.md) | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | **Français** | [Deutsch](README.de.md) | [Português (Brasil)](README.pt-BR.md)

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

Burstwise trie une séance photo sur votre propre machine. Il regroupe les photos qui montrent le même instant, signale le flou, les yeux fermés et l'exposition brûlée, choisit la meilleure image de chaque groupe et écrit le résultat sous forme de notes et d'étiquettes de couleur XMP à côté de vos fichiers. Rien n'est envoyé en ligne et aucun original n'est modifié.

Sur l'ensemble d'exemple, il lit, regroupe et juge **166 photos en 1,9 seconde** avec un GPU, et en 10,5 secondes avec le seul CPU. La méthode et les autres chiffres se trouvent dans le [benchmark](docs/benchmark.md). [Essayez la démo en ligne](https://arthur031221.github.io/Burstwise/).

## Avant et après

Le dossier d'exemple contient 166 images tirées de quatre courtes vidéos, donc beaucoup se ressemblent volontairement.

| | Avant | Après `burstwise cull --write-xmp` |
| --- | --- | --- |
| Ordre | 166 fichiers dans un dossier | 17 groupes, un par instant |
| Meilleure image | Vous faites défiler et comparez | 17 choix (pick), note 4 et étiquette Green |
| Mauvaises images | Trouvées en zoomant sur chacune | 15 rejets (reject : 9 yeux fermés, 6 floues), note -1 et étiquette Red |
| Le reste | Mélangé aux photos à garder | 134 alternatives (alt), laissées intactes |
| Raisons | Aucune | Un chiffre pour chaque verdict, par exemple `soft, 41% of the sharpest frame` |
| Vos originaux | Intacts | Intacts. Seuls des fichiers `.xmp` sont écrits, et `burstwise undo` les restaure |

Je pense qu'un outil de tri doit montrer son travail. Chaque verdict a une raison lisible, chaque seuil est un réglage simple et il n'y a aucun score caché.

## Démarrage rapide

```
pipx install git+https://github.com/Arthur031221/Burstwise
burstwise cull ~/Pictures/shoot              # affiche le plan, ne change rien
burstwise cull ~/Pictures/shoot --write-xmp  # écrit notes et étiquettes
burstwise serve ~/Pictures/shoot             # vérifiez et corrigez dans le navigateur
```

Le premier lancement télécharge deux fichiers de modèle, environ 90 Mo au total, et vérifie leur SHA-256.

<details>
<summary>Installer sous Linux (testé)</summary>

```
pipx install git+https://github.com/Arthur031221/Burstwise
```

Pour le GPU, il faut une installation CUDA 12 fonctionnelle pour `onnxruntime-gpu`. Sans elle, Burstwise bascule seul sur le CPU, ou ajoutez `--cpu`. Je développe et teste sous Ubuntu avec un GPU NVIDIA. Sur un serveur minimal, dans un conteneur ou sous WSL, installez d'abord les bibliothèques graphiques avec `sudo apt install libegl1 libgles2`, sinon Burstwise s'arrête avec un message sur le modèle de visages.

</details>

<details>
<summary>Installer sous macOS (non testé)</summary>

```
pipx install git+https://github.com/Arthur031221/Burstwise
```

Sous macOS, le paquet demande la version CPU d'onnxruntime. Je n'ai pas lancé Burstwise sur un Mac, considérez donc cela comme non essayé.

</details>

<details>
<summary>Installer sous Windows (non testé)</summary>

```
pipx install git+https://github.com/Arthur031221/Burstwise
```

Je n'ai pas lancé Burstwise sous Windows, considérez donc cela comme non essayé.

</details>

<details>
<summary>Installer depuis les sources</summary>

```
git clone https://github.com/Arthur031221/Burstwise
cd Burstwise
pip install -e ".[dev]"
```

</details>

## Comment il décide

1. Les photos sont séparées en scènes partout où l'heure de prise de vue saute de plus de 120 secondes.
2. Dans une scène, les photos dont les embeddings DINOv2 sont proches (similarité cosinus supérieure à 0,80, liaison moyenne) forment un groupe.
3. Chaque photo passe trois contrôles : les scores de clignement MediaPipe pour chaque visage, la netteté du visage (ou des tuiles les plus nettes quand un groupe contient une image sans visage) et les hautes lumières ou les ombres écrêtées.
4. Un groupe classe ses images par visages aux yeux fermés, puis par nombre d'autres problèmes, puis par netteté. La première est un pick, ou un review si elle a un problème. Les autres sont des alt, ou des reject si elles ont un problème.

L'[architecture](docs/architecture.md) donne les détails et la [configuration](docs/config.md) liste chaque seuil.

## Ce qu'il écrit

| Verdict | XMP |
| --- | --- |
| pick | note 4, étiquette Green |
| review | étiquette Yellow |
| alt | rien |
| reject | note -1 (rejetée), étiquette Red |

Les fichiers sidecar sont fusionnés, pas remplacés. Les modifications déjà présentes dans un sidecar Lightroom ou darktable sont conservées, et seuls `xmp:Rating`, `xmp:Label` et le couple `burstwise:Verdict` et `burstwise:Reason` sont définis. Si un sidecar écrit par un autre logiciel contient déjà une note (rejetée comprise) ou une étiquette, la photo est ignorée, sauf avec `--overwrite`. Les sidecars que Burstwise a écrits avant sont mis à jour au lancement suivant.

Lightroom Classic ne lit les sidecars `.xmp` que pour les fichiers raw. Pour JPEG, TIFF, PNG et HEIC, il garde le XMP dans le fichier lui-même, donc les notes et les étiquettes écrites ici n'apparaîtront pas dans Lightroom pour ces formats. darktable lit les sidecars pour tous les formats. Cela vient de la documentation d'Adobe et je ne l'ai pas essayé dans Lightroom.

## Ce que j'ai vérifié et ce que je n'ai pas vérifié

- J'ai relu les sidecars écrits avec ExifTool 13.59 et comparé la note, l'étiquette, la valeur de rejet, et vérifié que les réglages de développement `crs:` existants survivent. C'est dans la suite de tests.
- Je n'ai **pas** ouvert les sidecars dans Lightroom, Capture One ni darktable. Ce sont des XMP standard, mais je n'affirme rien sur la façon dont chaque logiciel les traite.
- Je n'ai **pas** mesuré la précision. Les contrôles sont des heuristiques. Les scores de clignement peuvent prendre un rire ou des yeux plissés pour des yeux fermés, et la netteté ne distingue pas un flou de mise au point d'un flou de bougé. J'ai jugé les résultats d'exemple à l'œil, rien de plus.
- Linux est le seul système que j'ai testé. Les chiffres de vitesse viennent d'une seule machine.
- Le regroupement s'appuie sur l'aspect des photos et l'heure de prise de vue. Deux instants différents qui se ressemblent et tombent dans l'intervalle de scène peuvent finir dans un même groupe, vérifiez donc les groupes dans l'application.
- Adobe et des outils payants comme Aftershoot et Narrative Select font aussi du tri. Burstwise s'adresse à ceux qui le veulent gratuit, local et lisible, avec du XMP standard en sortie.

## Documentation

- [Installation](docs/install.md)
- [Utilisation et application de revue](docs/usage.md)
- [Configuration](docs/config.md)
- [Architecture](docs/architecture.md)
- [Benchmark](docs/benchmark.md)
- [Contribuer](CONTRIBUTING.md)

L'application de revue affiche en grand la meilleure image de chaque groupe et replie les longs groupes, et les flèches, P, X, U et 1 à 5 fonctionnent directement depuis la grille. L'application de revue parle anglais, chinois traditionnel et simplifié, japonais, coréen, espagnol, français, allemand et portugais du Brésil, avec un thème sombre et un thème clair.

## Données d'exemple

Le code est sous licence MIT. Les photos d'exemple sont des images de vidéos Creative Commons, listées dans [examples/CREDITS.md](examples/CREDITS.md). Elles ne sont pas stockées dans ce dépôt et certaines sont en CC BY-SA, conservez donc leurs crédits si vous les réutilisez.

## Le nom

Burstwise est un composé adverbial inventé : burst, comme dans une rafale d'images, plus wise, comme dans sensé et comme dans « une rafale à la fois ».

## Licence

MIT. [LICENSE](LICENSE).

Assisted by Claude/Codex.
