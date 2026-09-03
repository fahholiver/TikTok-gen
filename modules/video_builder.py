"""
Monta o vídeo final (formato 9:16, estilo TikTok) em dois modos:

1) build_video()            -> MODO LISTA, vários "cards" em sequência.
2) build_comparison_video() -> MODO COMPARAÇÃO, estilo "coruja apontando":
   mostra item1 -> mostra item2 + pergunta (coruja "pensativa") -> coruja
   aponta e explica item1 -> coruja vira e explica item2.

pip install moviepy pillow numpy
"""

import os
import numpy as np
from PIL import Image
from moviepy import (
    ImageClip, TextClip, CompositeVideoClip, AudioFileClip,
    concatenate_videoclips, ColorClip,
)

# Resolução vertical padrão (pode ser 1080x1920 se tiver RAM)
W, H = 720, 1280

# Fonte com suporte a acentos (á, é, ã, ç...). Sem isso o Pillow usa uma
# fonte padrão sem esses caracteres e eles aparecem como quadrados (▢).
# O pacote `fonts-dejavu-core` (já no packages.txt) instala nesse caminho
# tanto localmente (Linux) quanto no Streamlit Cloud.
_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    # Fallbacks comuns para Windows se rodar local
    "C:\\Windows\\Fonts\\arial.ttf",
    "C:\\Windows\\Fonts\\segoeui.ttf",
]


def _resolve_font(font: str | None) -> str | None:
    """Busca uma fonte no sistema que suporte acentos."""
    if font:
        return font
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    # Se não achar nenhuma, retorna None e o Pillow usa a padrão (com quadrados)
    print("⚠️ Aviso: Nenhuma fonte com suporte a acentos encontrada. Caracteres especiais podem falhar.")
    return None


# ===========================================================================
# MODO LISTA (Ajustado)
# ===========================================================================

def build_card_clip(image_path: str, title: str, narration_text: str,
                     audio_path: str, font: str = None) -> CompositeVideoClip:
    """Cria um clipe (1 'card') com fundo branco, título, imagem e legenda."""
    resolved_font = _resolve_font(font)
    audio = AudioFileClip(audio_path)
    duration = audio.duration + 0.4

    bg = ColorClip(size=(W, H), color=(255, 255, 255)).with_duration(duration)

    # AJUSTE: Empurrado para baixo (H * 0.35)
    img = (ImageClip(image_path)
           .resized(width=int(W * 0.8))
           .with_position(("center", int(H * 0.35)))
           .with_duration(duration))

    # AJUSTE: Empurrado para baixo (H * 0.20) e usando resolved_font
    title_clip = (TextClip(text=title, font_size=70, color="black", font=resolved_font,
                            method="caption", size=(int(W * 0.9), None))
                  .with_position(("center", int(H * 0.20)))
                  .with_duration(duration))

    # AJUSTE: Empurrado para baixo (H * 0.65) e usando resolved_font
    caption_clip = (TextClip(text=narration_text, font_size=48, color="black", font=resolved_font,
                              method="caption", size=(int(W * 0.85), int(H * 0.28)))
                    .with_position(("center", int(H * 0.65)))
                    .with_duration(duration))

    card = CompositeVideoClip([bg, img, title_clip, caption_clip], size=(W, H))
    card = card.with_audio(audio)
    return card


def build_video(items: list[dict], out_path: str, font: str = None) -> str:
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


# ===========================================================================
# MODO COMPARAÇÃO (Ajustado conforme feedback)
# ===========================================================================

# Dimensões das imagens (2 na tela)
_IMG_W, _IMG_H = int(W * 0.40), int(H * 0.20)
_LEFT_X, _RIGHT_X = int(W * 0.06), W - _IMG_W - int(W * 0.06)

# AJUSTE: Títulos estavam no topo cortados (Y=0.06). Descidos para Y=0.15.
_TITLE_Y = int(H * 0.15)

# AJUSTE: Imagens estavam muito altas (Y=0.20). Descidas para Y=0.30.
_IMG_Y = int(H * 0.30)


# Dimensões da imagem única (Cena 1)
_SINGLE_W, _SINGLE_H = int(W * 0.78), int(H * 0.28)
_SINGLE_X = (W - _SINGLE_W) // 2
# AJUSTE: Imagem única estava muito alta (Y=0.16). Descida para Y=0.25.
_SINGLE_Y = int(H * 0.25)


# Caixa de legenda
# AJUSTE: Legenda estava muito alta (Y=0.42). Descida para Y=0.55.
_CAPTION_Y = int(H * 0.55)
_CAPTION_W = int(W * 0.88)
_CAPTION_H = int(H * 0.18) # Reduzida levemente a altura para não brigar com a coruja

# Posição da Coruja
# AJUSTE: Coruja estava no Y=0.64. Subida levemente para Y=0.62 para dar espaço
# ao texto que agora está mais baixo.
_OWL_Y = int(H * 0.62)


def _bg(duration):
    return ColorClip(size=(W, H), color=(255, 255, 255)).with_duration(duration)


def _title_clip(text, x, w, y, duration, font=None):
    # AJUSTE: Usando resolved_font e font_size ligeiramente menor (40)
    return (TextClip(text=text, font_size=40, color="black", font=_resolve_font(font),
                      method="caption", size=(w, None))
            .with_position((x, y))
            .with_duration(duration))


def _image_clip(path, x, y, w, h, duration):
    return (ImageClip(path)
            .resized(new_size=(w, h))
            .with_position((x, y))
            .with_duration(duration))


def _highlight_clip(x, y, w, h, duration, pad=14, color=(255, 205, 0)):
    return (ColorClip(size=(w + pad * 2, h + pad * 2), color=color)
            .with_position((x - pad, y - pad))
            .with_duration(duration))


def _owl_clip(owl_image_path, duration, flip=False, width_frac=0.5):
    img = Image.open(owl_image_path).convert("RGB")
    if flip:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    arr = np.array(img)
    return (ImageClip(arr)
            .resized(width=int(W * width_frac))
            .with_position(("center", _OWL_Y))
            .with_duration(duration))


def _caption_clip(text, duration, font=None):
    # AJUSTE: Usando resolved_font
    return (TextClip(text=text, font_size=38, color="black", font=_resolve_font(font),
                      method="caption", size=(_CAPTION_W, _CAPTION_H))
            .with_position(("center", _CAPTION_Y))
            .with_duration(duration))


def build_comparison_video(data: dict, owl_image_path: str, out_path: str,
                            owl_thinking_path: str | None = None,
                            font: str = None) -> str:
    thinking_path = owl_thinking_path or owl_image_path
    scenes = []

    # Cena 1: só o item 1 aparece
    a1 = AudioFileClip(data["intro1_audio"])
    d1 = a1.duration + 0.4
    scenes.append(CompositeVideoClip([
        _bg(d1),
        # AJUSTE: Título único descido
        _title_clip(data["item1_title"], _SINGLE_X, _SINGLE_W, int(H * 0.12), d1, font),
        _image_clip(data["item1_image_path"], _SINGLE_X, _SINGLE_Y, _SINGLE_W, _SINGLE_H, d1),
        _caption_clip(data["intro1_text"], d1, font),
        _owl_clip(owl_image_path, d1, flip=False),
    ], size=(W, H)).with_audio(a1))

    # Cena 2: item 2 aparece, coruja PENSATIVA
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

    # Cena 3: aponta pro item 1
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

    # Cena 4: explica o item 2
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

    final = concatenate_videoclips(scenes, method="compose")
    final.write_videofile(out_path, fps=24, codec="libx264", audio_codec="aac",
                           preset="ultrafast", threads=2)
    return out_path
