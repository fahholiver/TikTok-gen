"""
Monta o vídeo final (formato 9:16, estilo TikTok) em dois modos:

1) build_video()               -> MODO LISTA, vários "cards" em sequência.
2) build_multi_comparison_video() -> MODO COMPARAÇÃO, estilo "coruja
   apontando": para CADA PAR de itens, mostra item1 -> mostra item2 +
   pergunta (coruja "pensativa") -> coruja aponta e explica item1 -> coruja
   vira e explica item2. Os pares são concatenados um atrás do outro pra
   formar o vídeo final (vários pares = vários "blocos" de 4 cenas).
   build_comparison_video() é mantida como atalho pra um único par, e só
   chama build_multi_comparison_video() com uma lista de 1 item.

pip install moviepy pillow numpy
"""

import os
import subprocess
import numpy as np
from PIL import Image
from moviepy import (
    ImageClip, TextClip, CompositeVideoClip, AudioFileClip,
    concatenate_videoclips, ColorClip,
)

W, H = 720, 1280  # formato vertical, resolução reduzida pra caber no plano
                   # grátis do Streamlit Cloud (1080x1920 costuma estourar
                   # RAM/tempo durante a renderização). Se rodar local com
                   # mais RAM, pode voltar pra 1080x1920 sem problema.

# Fonte com suporte a acentos (á, é, ã, ç...). Sem isso o Pillow usa uma
# fonte padrão sem esses caracteres e eles aparecem como quadrados (▢).
# O pacote `fonts-dejavu-core` (já no packages.txt) instala nesse caminho
# tanto localmente (Linux) quanto no Streamlit Cloud. Adicionamos também
# caminhos comuns de Mac/Windows (pra quando o app roda localmente fora do
# Linux) e, por fim, uma consulta ao `fontconfig` (fc-match), que descobre
# dinamicamente uma fonte com acentos em qualquer distro/sistema onde o
# fontconfig esteja instalado (também incluso no packages.txt).
_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    # macOS
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    # Windows
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
]

_resolved_font_cache: str | None = None
_font_lookup_warned = False


def _fc_match_font() -> str | None:
    """Pergunta ao fontconfig (fc-match) por uma fonte que cubra português,
    como último recurso antes de desistir. Funciona em qualquer distro
    Linux que tenha o pacote `fontconfig` instalado."""
    try:
        result = subprocess.run(
            ["fc-match", ":lang=pt", "-f", "%{file}"],
            capture_output=True, text=True, timeout=3,
        )
        path = result.stdout.strip()
        if path and os.path.exists(path):
            return path
    except Exception:
        pass
    return None


def _resolve_font(font: str | None) -> str | None:
    global _resolved_font_cache, _font_lookup_warned
    if font:
        return font
    if _resolved_font_cache:
        return _resolved_font_cache

    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            _resolved_font_cache = path
            return path

    fc_path = _fc_match_font()
    if fc_path:
        _resolved_font_cache = fc_path
        return fc_path

    if not _font_lookup_warned:
        print(
            "[video_builder] AVISO: nenhuma fonte com suporte a acentos foi "
            "encontrada (á, ç, ã etc. vão aparecer como quadrados ▢). "
            "Instale o pacote 'fonts-dejavu-core' (e 'fontconfig') no "
            "sistema, ou passe explicitamente o caminho de uma fonte via "
            "o parâmetro `font=`."
        )
        _font_lookup_warned = True
    return None  # último recurso: Pillow usa a fonte padrão (sem acentos)


def build_card_clip(image_path: str, title: str, narration_text: str,
                     audio_path: str, font: str = None) -> CompositeVideoClip:
    """Cria um clipe (1 'card') com fundo branco, título, imagem e legenda,
    com duração igual à do áudio de narração."""
    font = _resolve_font(font)
    audio = AudioFileClip(audio_path)
    duration = audio.duration + 0.4  # pequena folga no fim

    bg = ColorClip(size=(W, H), color=(255, 255, 255)).with_duration(duration)

    img = (ImageClip(image_path)
           .resized(width=int(W * 0.8))
           .with_position(("center", int(H * 0.28)))
           .with_duration(duration))

    title_clip = (TextClip(text=title, font_size=70, color="black", font=font,
                            method="caption", size=(int(W * 0.9), None))
                  .with_position(("center", int(H * 0.12)))
                  .with_duration(duration))

    caption_clip = (TextClip(text=narration_text, font_size=48, color="black", font=font,
                              method="caption", size=(int(W * 0.85), int(H * 0.28)))
                    .with_position(("center", int(H * 0.60)))
                    .with_duration(duration))

    card = CompositeVideoClip([bg, img, title_clip, caption_clip], size=(W, H))
    card = card.with_audio(audio)
    return card


def build_video(items: list[dict], out_path: str, font: str = None) -> str:
    """
    items: lista de dicts, cada um com:
        image_path, title, narration, audio_path (já preenchidos pelo app.py)
    """
    clips = [
        build_card_clip(
            image_path=item["image_path"],
            title=item["title"],
            narration_text=item["narration"],
            audio_path=item["audio_path"],
            font=font,
        )
        for item in items
    ]

    final = concatenate_videoclips(clips, method="compose")
    final.write_videofile(out_path, fps=24, codec="libx264", audio_codec="aac",
                           preset="ultrafast", threads=2)
    return out_path


# ---------------------------------------------------------------------------
# MODO COMPARAÇÃO (estilo "coruja apontando") — um ou vários pares
# ---------------------------------------------------------------------------

_IMG_W, _IMG_H = int(W * 0.40), int(H * 0.20)
_LEFT_X, _RIGHT_X = int(W * 0.06), W - _IMG_W - int(W * 0.06)
_IMG_Y = int(H * 0.18)     # era 0.20 — sobe um pouco a imagem, dando mais
                           # espaço de respiro pro título logo acima
_TITLE_Y = int(H * 0.08)   # era 0.06 — título descia perto demais do topo
                           # e ficava cortado; agora tem mais margem

# Imagem única (cena 1 do par, quando só o item 1 aparece)
_SINGLE_W, _SINGLE_H = int(W * 0.78), int(H * 0.22)  # altura reduzida (era
                                                       # 0.28) pra não bater
                                                       # na caixa de legenda
_SINGLE_X = (W - _SINGLE_W) // 2
_SINGLE_Y = int(H * 0.16)

# Caixa de legenda com altura FIXA e generosa (2-4 linhas cabem sem
# sobrepor a coruja, que fica logo abaixo dela). Subida um pouco (era
# 0.42) pra ficar mais perto das imagens, como pedido.
_CAPTION_Y = int(H * 0.40)
_CAPTION_W = int(W * 0.88)
_CAPTION_H = int(H * 0.20)

_OWL_Y = int(H * 0.62)


def _bg(duration):
    return ColorClip(size=(W, H), color=(255, 255, 255)).with_duration(duration)


def _title_clip(text, x, w, y, duration, font=None):
    return (TextClip(text=text, font_size=44, color="black", font=_resolve_font(font),
                      method="caption", size=(w, None))
            .with_position((x, y))
            .with_duration(duration))


def _image_clip(path, x, y, w, h, duration):
    return (ImageClip(path)
            .resized(new_size=(w, h))
            .with_position((x, y))
            .with_duration(duration))


def _highlight_clip(x, y, w, h, duration, pad=14, color=(255, 205, 0)):
    """Retângulo colorido atrás da imagem ativa, pra indicar o que a coruja
    está explicando no momento."""
    return (ColorClip(size=(w + pad * 2, h + pad * 2), color=color)
            .with_position((x - pad, y - pad))
            .with_duration(duration))


def _owl_clip(owl_image_path, duration, flip=False, width_frac=0.5):
    """A coruja fica sempre na mesma posição (parte de baixo do quadro);
    espelhamos horizontalmente pra dar a impressão de que ela 'virou' pra
    apontar pro outro lado."""
    img = Image.open(owl_image_path).convert("RGB")
    if flip:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    arr = np.array(img)
    return (ImageClip(arr)
            .resized(width=int(W * width_frac))
            .with_position(("center", _OWL_Y))
            .with_duration(duration))


def _caption_clip(text, duration, font=None):
    return (TextClip(text=text, font_size=38, color="black", font=_resolve_font(font),
                      method="caption", size=(_CAPTION_W, _CAPTION_H))
            .with_position(("center", _CAPTION_Y))
            .with_duration(duration))


def _build_comparison_pair_scenes(data: dict, owl_image_path: str, thinking_path: str,
                                   font: str = None) -> list[CompositeVideoClip]:
    """Monta as 4 cenas (intro1, intro2, explain1, explain2) de UM par de
    comparação. Usado tanto por build_comparison_video() (1 par) quanto por
    build_multi_comparison_video() (vários pares concatenados)."""
    scenes = []

    # Cena 1: só o item 1 aparece, coruja apresenta
    a1 = AudioFileClip(data["intro1_audio"])
    d1 = a1.duration + 0.4
    scenes.append(CompositeVideoClip([
        _bg(d1),
        _title_clip(data["item1_title"], _SINGLE_X, _SINGLE_W, _TITLE_Y, d1, font),
        _image_clip(data["item1_image_path"], _SINGLE_X, _SINGLE_Y, _SINGLE_W, _SINGLE_H, d1),
        _caption_clip(data["intro1_text"], d1, font),
        _owl_clip(owl_image_path, d1, flip=False),
    ], size=(W, H)).with_audio(a1))

    # Cena 2: item 2 aparece do outro lado, coruja PENSATIVA pergunta a diferença
    a2 = AudioFileClip(data["intro2_audio"])
    d2 = a2.duration + 0.4
    scenes.append(CompositeVideoClip([
        _bg(d2),
        _title_clip(data["item1_title"], _LEFT_X, _IMG_W, _TITLE_Y, d2, font),
        _title_clip(data["item2_title"], _RIGHT_X, _IMG_W, _TITLE_Y, d2, font),
        _image_clip(data["item1_image_path"], _LEFT_X, _IMG_Y, _IMG_W, _IMG_H, d2),
        _image_clip(data["item2_image_path"], _RIGHT_X, _IMG_Y, _IMG_W, _IMG_H, d2),
        _caption_clip(data["intro2_text"], d2, font),
        _owl_clip(thinking_path, d2, flip=False),
    ], size=(W, H)).with_audio(a2))

    # Cena 3: coruja aponta pro item 1 (destaque à esquerda) e explica
    a3 = AudioFileClip(data["explain1_audio"])
    d3 = a3.duration + 0.4
    scenes.append(CompositeVideoClip([
        _bg(d3),
        _highlight_clip(_LEFT_X, _IMG_Y, _IMG_W, _IMG_H, d3),
        _title_clip(data["item1_title"], _LEFT_X, _IMG_W, _TITLE_Y, d3, font),
        _title_clip(data["item2_title"], _RIGHT_X, _IMG_W, _TITLE_Y, d3, font),
        _image_clip(data["item1_image_path"], _LEFT_X, _IMG_Y, _IMG_W, _IMG_H, d3),
        _image_clip(data["item2_image_path"], _RIGHT_X, _IMG_Y, _IMG_W, _IMG_H, d3),
        _caption_clip(data["explain1_text"], d3, font),
        _owl_clip(owl_image_path, d3, flip=False),
    ], size=(W, H)).with_audio(a3))

    # Cena 4: coruja vira e explica o item 2 (destaque à direita)
    a4 = AudioFileClip(data["explain2_audio"])
    d4 = a4.duration + 0.4
    scenes.append(CompositeVideoClip([
        _bg(d4),
        _highlight_clip(_RIGHT_X, _IMG_Y, _IMG_W, _IMG_H, d4),
        _title_clip(data["item1_title"], _LEFT_X, _IMG_W, _TITLE_Y, d4, font),
        _title_clip(data["item2_title"], _RIGHT_X, _IMG_W, _TITLE_Y, d4, font),
        _image_clip(data["item1_image_path"], _LEFT_X, _IMG_Y, _IMG_W, _IMG_H, d4),
        _image_clip(data["item2_image_path"], _RIGHT_X, _IMG_Y, _IMG_W, _IMG_H, d4),
        _caption_clip(data["explain2_text"], d4, font),
        _owl_clip(owl_image_path, d4, flip=True),
    ], size=(W, H)).with_audio(a4))

    return scenes


def build_multi_comparison_video(pairs: list[dict], owl_image_path: str, out_path: str,
                                  owl_thinking_path: str | None = None,
                                  font: str = None) -> str:
    """
    pairs: lista de dicts, um por PAR de comparação, cada um com:
        item1_title, item1_image_path, item2_title, item2_image_path,
        intro1_text,   intro1_audio,
        intro2_text,   intro2_audio,
        explain1_text, explain1_audio,
        explain2_text, explain2_audio,

    Todos os pares são renderizados em sequência (4 cenas cada) e
    concatenados num único vídeo final, reusando as mesmas imagens da
    coruja em todos os pares.

    owl_thinking_path: imagem opcional da coruja em pose "pensativa", usada
    só na cena 2 de cada par (quando ela pergunta "qual a diferença?"). Se
    não for passada, reusa a imagem normal (owl_image_path).
    """
    thinking_path = owl_thinking_path or owl_image_path
    all_scenes = []
    for pair_data in pairs:
        all_scenes.extend(_build_comparison_pair_scenes(pair_data, owl_image_path, thinking_path, font))

    final = concatenate_videoclips(all_scenes, method="compose")
    final.write_videofile(out_path, fps=24, codec="libx264", audio_codec="aac",
                           preset="ultrafast", threads=2)
    return out_path


def build_comparison_video(data: dict, owl_image_path: str, out_path: str,
                            owl_thinking_path: str | None = None,
                            font: str = None) -> str:
    """Atalho pra renderizar um vídeo com um ÚNICO par de comparação.
    Mantido por compatibilidade — internamente chama
    build_multi_comparison_video() com uma lista de 1 item."""
    return build_multi_comparison_video([data], owl_image_path, out_path,
                                         owl_thinking_path=owl_thinking_path, font=font)
