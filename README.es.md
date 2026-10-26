[English](README.md) | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | **Español** | [Français](README.fr.md) | [Deutsch](README.de.md) | [Português (Brasil)](README.pt-BR.md)

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

Burstwise selecciona fotos de una sesión en tu propio equipo. Agrupa las fotos que muestran el mismo momento, marca el desenfoque, los ojos cerrados y la exposición quemada, elige el mejor fotograma de cada grupo y escribe el resultado como valoraciones y etiquetas de color XMP junto a tus archivos. No se sube nada y no se toca ningún original.

En el conjunto de ejemplo lee, agrupa y juzga **166 fotos en 1,9 segundos** con una GPU, y en 10,5 segundos solo con la CPU. El método y el resto de las cifras están en el [benchmark](docs/benchmark.md). [Prueba la demo en vivo](https://arthur031221.github.io/Burstwise/).

## Antes y después

La carpeta de ejemplo tiene 166 fotogramas sacados de cuatro vídeos cortos, así que muchos se parecen a propósito.

| | Antes | Después de `burstwise cull --write-xmp` |
| --- | --- | --- |
| Orden | 166 archivos en una carpeta | 17 grupos, uno por momento |
| Mejor fotograma | Tú desplazas y comparas | 17 elegidas (pick), valoración 4 y etiqueta Green |
| Fotogramas malos | Se encuentran ampliando cada uno | 15 descartadas (reject: 9 con ojos cerrados, 6 borrosas), valoración -1 y etiqueta Red |
| El resto | Mezclado con las que se quedan | 134 alternativas (alt), sin tocar |
| Motivos | Ninguno | Una cifra en cada veredicto, por ejemplo `soft, 41% of the sharpest frame` |
| Tus originales | A salvo | A salvo. Solo se escriben archivos `.xmp` y `burstwise undo` los restaura |

Creo que una herramienta de selección debe mostrar su trabajo. Cada veredicto tiene un motivo legible, cada umbral es un ajuste claro y no hay ninguna puntuación oculta.

## Inicio rápido

```
pipx install git+https://github.com/Arthur031221/Burstwise
burstwise cull ~/Pictures/shoot              # muestra el plan, no cambia nada
burstwise cull ~/Pictures/shoot --write-xmp  # escribe valoraciones y etiquetas
burstwise serve ~/Pictures/shoot             # revisa y corrige en el navegador
```

La primera ejecución descarga dos archivos de modelo, unos 90 MB en total, y comprueba su SHA-256.

<details>
<summary>Instalar en Linux (probado)</summary>

```
pipx install git+https://github.com/Arthur031221/Burstwise
```

Para la GPU necesitas un entorno CUDA 12 que funcione con `onnxruntime-gpu`. Sin él, Burstwise vuelve a la CPU por su cuenta, o puedes pasar `--cpu`. Desarrollo y pruebo en Ubuntu con una GPU NVIDIA. En un servidor mínimo, un contenedor o WSL, instala antes las bibliotecas gráficas con `sudo apt install libegl1 libgles2`; si no, Burstwise se detiene con un mensaje sobre el modelo de rostros.

</details>

<details>
<summary>Instalar en macOS (sin probar)</summary>

```
pipx install git+https://github.com/Arthur031221/Burstwise
```

En macOS el paquete pide la versión de onnxruntime para CPU. No he ejecutado Burstwise en un Mac, así que tómalo como no probado.

</details>

<details>
<summary>Instalar en Windows (sin probar)</summary>

```
pipx install git+https://github.com/Arthur031221/Burstwise
```

No he ejecutado Burstwise en Windows, así que tómalo como no probado.

</details>

<details>
<summary>Instalar desde el código fuente</summary>

```
git clone https://github.com/Arthur031221/Burstwise
cd Burstwise
pip install -e ".[dev]"
```

</details>

## Cómo decide

1. Las fotos se dividen en escenas donde la hora de captura salta más de 120 segundos.
2. Dentro de una escena, las fotos cuyos embeddings de DINOv2 están cerca (similitud del coseno superior a 0,80, enlace promedio) forman un grupo.
3. Cada foto pasa tres comprobaciones: las puntuaciones de parpadeo de MediaPipe para cada rostro, la nitidez del rostro (o de los mosaicos más nítidos cuando un grupo tiene un fotograma sin rostro) y las altas luces o sombras recortadas.
4. Un grupo ordena sus fotogramas por rostros con ojos cerrados, luego por el número de otros problemas y luego por nitidez. El primero es un pick, o un review si tiene un problema propio. Los demás son alt, o reject si tienen un problema.

La [arquitectura](docs/architecture.md) tiene los detalles y la [configuración](docs/config.md) lista cada umbral.

## Qué escribe

| Veredicto | XMP |
| --- | --- |
| pick | valoración 4, etiqueta Green |
| review | etiqueta Yellow |
| alt | nada |
| reject | valoración -1 (rechazada), etiqueta Red |

Los archivos sidecar se combinan, no se reemplazan. Las ediciones que ya estén en un sidecar de Lightroom o darktable se conservan, y solo se establecen `xmp:Rating`, `xmp:Label` y el par `burstwise:Verdict` y `burstwise:Reason`. Si un sidecar escrito por otro programa ya tiene una valoración (la de rechazada cuenta) o una etiqueta, la foto se omite salvo que pases `--overwrite`. Los sidecars que Burstwise escribió antes se actualizan en la siguiente ejecución.

Lightroom Classic lee los sidecars `.xmp` solo para archivos raw. En JPEG, TIFF, PNG y HEIC guarda el XMP dentro del propio archivo, así que las valoraciones y etiquetas escritas aquí no aparecerán en Lightroom para esos formatos. darktable lee sidecars de cualquier formato. Esto viene de la documentación de Adobe y no lo he probado en Lightroom.

## Qué comprobé y qué no

- Leí de vuelta los sidecars escritos con ExifTool 13.59 y comparé la valoración, la etiqueta, el valor de rechazo y que los ajustes de revelado `crs:` existentes se conserven. Eso está en la batería de pruebas.
- **No** he abierto los sidecars en Lightroom, Capture One ni darktable. Son XMP estándar, pero no afirmo nada sobre cómo los trata cada programa.
- **No** he medido la precisión. Las comprobaciones son heurísticas. Las puntuaciones de parpadeo pueden tomar una risa o un entrecerrar de ojos por ojos cerrados, y la nitidez no distingue el desenfoque de enfoque del de movimiento. Juzgué los resultados de ejemplo a simple vista y nada más.
- Linux es el único sistema que probé. Las cifras de velocidad salen de una sola máquina.
- La agrupación usa el aspecto de las fotos y la hora de captura. Dos momentos distintos que se parecen y caen dentro del intervalo de escena pueden acabar en un grupo, así que revisa los grupos en la app.
- Adobe y herramientas de pago como Aftershoot y Narrative Select también hacen selección. Burstwise es para quien la quiere gratis, local y legible, con XMP estándar como salida.

## Documentación

- [Instalación](docs/install.md)
- [Uso y app de revisión](docs/usage.md)
- [Configuración](docs/config.md)
- [Arquitectura](docs/architecture.md)
- [Benchmark](docs/benchmark.md)
- [Contribuir](CONTRIBUTING.md)

La app de revisión muestra en grande el mejor fotograma de cada grupo y pliega los grupos largos, y las flechas, P, X, U y 1 a 5 funcionan directamente desde la cuadrícula. La app de revisión habla inglés, chino tradicional y simplificado, japonés, coreano, español, francés, alemán y portugués de Brasil, con tema oscuro y claro.

## Datos de ejemplo

El código es MIT. Las fotos de ejemplo son fotogramas de vídeos con licencia Creative Commons, listados en [examples/CREDITS.md](examples/CREDITS.md). No están guardadas en este repositorio y algunas son CC BY-SA, así que conserva sus créditos si las reutilizas.

## El nombre

Burstwise es un compuesto adverbial inventado: burst, como en una ráfaga de fotogramas, más wise, como en sensato y como en «una ráfaga cada vez».

## Licencia

MIT. [LICENSE](LICENSE).

Assisted by Claude/Codex.
