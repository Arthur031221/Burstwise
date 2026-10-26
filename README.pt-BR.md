[English](README.md) | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | **Português (Brasil)**

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

O Burstwise seleciona as fotos de um ensaio no seu próprio computador. Ele agrupa as fotos que mostram o mesmo momento, marca desfoque, olhos fechados e exposição estourada, escolhe o melhor quadro de cada grupo e grava o resultado como avaliações e rótulos de cor XMP ao lado dos seus arquivos. Nada é enviado e nenhum original é tocado.

No conjunto de exemplo, ele lê, agrupa e julga **166 fotos em 1,9 segundo** com uma GPU, e em 10,5 segundos só com a CPU. O método e os outros números estão no [benchmark](docs/benchmark.md). [Experimente a demonstração online](https://arthur031221.github.io/Burstwise/).

## Antes e depois

A pasta de exemplo tem 166 quadros tirados de quatro vídeos curtos, então muitos se parecem de propósito.

| | Antes | Depois de `burstwise cull --write-xmp` |
| --- | --- | --- |
| Ordem | 166 arquivos em uma pasta | 17 grupos, um por momento |
| Melhor quadro | Você rola e compara | 17 escolhidas (pick), avaliação 4 e rótulo Green |
| Quadros ruins | Achados ampliando um por um | 15 rejeitadas (reject: 9 de olhos fechados, 6 sem foco), avaliação -1 e rótulo Red |
| O resto | Misturado com as que ficam | 134 alternativas (alt), intocadas |
| Motivos | Nenhum | Um número em cada veredito, por exemplo `soft, 41% of the sharpest frame` |
| Seus originais | Seguros | Seguros. Só arquivos `.xmp` são gravados e `burstwise undo` os restaura |

Acho que uma ferramenta de seleção deve mostrar seu trabalho. Cada veredito tem um motivo legível, cada limite é um ajuste simples e não há nenhuma pontuação escondida.

## Início rápido

```
pipx install git+https://github.com/Arthur031221/Burstwise
burstwise cull ~/Pictures/shoot              # mostra o plano, não muda nada
burstwise cull ~/Pictures/shoot --write-xmp  # grava avaliações e rótulos
burstwise serve ~/Pictures/shoot             # revise e corrija no navegador
```

A primeira execução baixa dois arquivos de modelo, cerca de 90 MB no total, e confere o SHA-256 deles.

<details>
<summary>Instalar no Linux (testado)</summary>

```
pipx install git+https://github.com/Arthur031221/Burstwise
```

Para usar a GPU, é preciso um ambiente CUDA 12 funcionando para o `onnxruntime-gpu`. Sem ele, o Burstwise volta para a CPU sozinho, ou use `--cpu`. Desenvolvo e testo no Ubuntu com uma GPU NVIDIA. Em um servidor mínimo, em um contêiner ou no WSL, instale antes as bibliotecas gráficas com `sudo apt install libegl1 libgles2`; caso contrário o Burstwise para com uma mensagem sobre o modelo de rostos.

</details>

<details>
<summary>Instalar no macOS (não testado)</summary>

```
pipx install git+https://github.com/Arthur031221/Burstwise
```

No macOS o pacote pede a versão de CPU do onnxruntime. Nunca executei o Burstwise em um Mac, então trate isso como não testado.

</details>

<details>
<summary>Instalar no Windows (não testado)</summary>

```
pipx install git+https://github.com/Arthur031221/Burstwise
```

Nunca executei o Burstwise no Windows, então trate isso como não testado.

</details>

<details>
<summary>Instalar a partir do código-fonte</summary>

```
git clone https://github.com/Arthur031221/Burstwise
cd Burstwise
pip install -e ".[dev]"
```

</details>

## Como ele decide

1. As fotos são divididas em cenas sempre que o horário de captura salta mais de 120 segundos.
2. Dentro de uma cena, as fotos cujos embeddings do DINOv2 são próximos (similaridade de cosseno acima de 0,80, ligação média) formam um grupo.
3. Cada foto passa por três verificações: as pontuações de piscada do MediaPipe para cada rosto, a nitidez do rosto (ou dos blocos mais nítidos quando um grupo tem um quadro sem rosto) e as altas luzes ou sombras estouradas.
4. Um grupo ordena seus quadros por rostos de olhos fechados, depois pelo número de outros problemas e depois pela nitidez. O primeiro é um pick, ou um review se tiver um problema próprio. Os demais são alt, ou reject se tiverem um problema.

A [arquitetura](docs/architecture.md) tem os detalhes e a [configuração](docs/config.md) lista cada limite.

## O que ele grava

| Veredito | XMP |
| --- | --- |
| pick | avaliação 4, rótulo Green |
| review | rótulo Yellow |
| alt | nada |
| reject | avaliação -1 (rejeitada), rótulo Red |

Os arquivos sidecar são mesclados, não substituídos. As edições que já estão em um sidecar do Lightroom ou do darktable permanecem, e apenas `xmp:Rating`, `xmp:Label` e o par `burstwise:Verdict` e `burstwise:Reason` são definidos. Se um sidecar escrito por outro programa já tem uma avaliação (rejeitada conta) ou um rótulo, a foto é ignorada, a menos que você use `--overwrite`. Os sidecars que o Burstwise escreveu antes são atualizados na execução seguinte.

O Lightroom Classic lê sidecars `.xmp` apenas para arquivos raw. Em JPEG, TIFF, PNG e HEIC ele guarda o XMP dentro do próprio arquivo, então as notas e etiquetas gravadas aqui não aparecerão no Lightroom para esses formatos. O darktable lê sidecars de qualquer formato. Isso vem da documentação da Adobe e não testei no Lightroom.

## O que verifiquei e o que não verifiquei

- Li de volta os sidecars gravados com o ExifTool 13.59 e comparei a avaliação, o rótulo, o valor de rejeição e se as configurações de revelação `crs:` existentes sobrevivem. Isso está na suíte de testes.
- **Não** abri os sidecars no Lightroom, no Capture One nem no darktable. São XMP padrão, mas não afirmo nada sobre como cada programa os trata.
- **Não** medi a precisão. As verificações são heurísticas. As pontuações de piscada podem tratar uma risada ou olhos semicerrados como fechados, e a nitidez não distingue desfoque de foco de desfoque de movimento. Julguei os resultados do exemplo a olho e só isso.
- Linux é o único sistema que testei. Os números de velocidade vêm de uma única máquina.
- O agrupamento usa a aparência das fotos e o horário de captura. Dois momentos diferentes que se parecem e caem dentro do intervalo de cena podem acabar em um grupo, então confira os grupos no app de revisão.
- A Adobe e ferramentas pagas como Aftershoot e Narrative Select também fazem seleção. O Burstwise é para quem a quer gratuita, local e legível, com XMP padrão como saída.

## Documentação

- [Instalação](docs/install.md)
- [Uso e app de revisão](docs/usage.md)
- [Configuração](docs/config.md)
- [Arquitetura](docs/architecture.md)
- [Benchmark](docs/benchmark.md)
- [Contribuir](CONTRIBUTING.md)

O app de revisão fala inglês, chinês tradicional e simplificado, japonês, coreano, espanhol, francês, alemão e português do Brasil, com tema escuro e claro.

## Dados de exemplo

O código é MIT. As fotos de exemplo são quadros de vídeos Creative Commons, listados em [examples/CREDITS.md](examples/CREDITS.md). Elas não ficam neste repositório e algumas são CC BY-SA, então mantenha os créditos se for reutilizá-las.

## O nome

Burstwise é um composto adverbial inventado: burst, como em uma rajada de quadros, mais wise, como em sensato e como em «uma rajada de cada vez».

## Licença

MIT. [LICENSE](LICENSE).

Assisted by Claude/Codex.
