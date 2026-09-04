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
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import (
    ImageClip, TextClip, CompositeVideoClip, AudioFileClip,
    concatenate_videoclips, ColorClip,
)

W, H = 720, 1280  # formato vertical, resolução reduzida pra caber no plano
                   # grátis do Streamlit Cloud (1080x1920 costuma estourar
                   # RAM/tempo durante a renderização). Se rodar local com
                   # mais RAM, pode voltar pra 1080x1920 sem problema.

# Fonte com suporte a acentos (á, é, ã, ç...). Sem isso o Pillow/moviepy usa
# uma fonte padrão sem esses caracteres e eles aparecem como quadrados (▢)
# ou, pior, a fonte bitmap padrão do PIL (minúscula, sem acentuação correta).
#
# ESTRATÉGIA: a fonte DejaVuSans.ttf fica BUNDLED (incluída) dentro da pasta
# assets/fonts/ deste projeto. Assim, o app NUNCA depende de o usuário ter
# instalado fontes no sistema operacional — funciona sempre, em qualquer
# máquina, local ou no Streamlit Cloud, sem nenhum passo extra de instalação.
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_BUNDLED_FONT_REGULAR = os.path.join(_MODULE_DIR, "..", "assets", "fonts", "DejaVuSans.ttf")
_BUNDLED_FONT_BOLD = os.path.join(_MODULE_DIR, "..", "assets", "fonts", "DejaVuSans-Bold.ttf")

_FONT_CANDIDATES = [
    # 1) Fonte embutida no projeto (SEMPRE funciona, prioridade máxima)
    _BUNDLED_FONT_BOLD,
    _BUNDLED_FONT_REGULAR,
    # 2) Fontes do sistema (fallback, caso a pasta assets/ não exista)
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/DejaVuSans.ttf",  # macOS
    "C:\\Windows\\Fonts\\DejaVuSans.ttf",    # Windows
]

_FONT_FOUND = None


def _resolve_font(font: str | None) -> str | None:
    """Encontra uma fonte com suporte a acentos. Prioriza a fonte embutida
    no projeto (assets/fonts/), que sempre existe, antes de procurar no
    sistema operacional."""
    global _FONT_FOUND
    if font:
        return font
    if _FONT_FOUND:
        return _FONT_FOUND
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            print(f"[DEBUG] ✅ Fonte encontrada: {path}")
            _FONT_FOUND = path
            return path
    print("[DEBUG] ⚠️  Nenhuma fonte encontrada (nem embutida, nem do sistema).")
    print("[DEBUG]    Verifique se a pasta assets/fonts/ foi copiada junto do projeto.")
    return None


def _render_text_to_image(text: str, font_size: int, width: int, height: int,
                          color: str = "black", font_path: str = None) -> np.ndarray:
    """
    Renderiza texto centralizado como imagem usando PIL, com quebra de linha
    automática (word wrap) para caber na largura disponível. Usado como
    último recurso caso NENHUMA fonte TrueType seja encontrada (o que não
    deveria acontecer, já que a fonte vem embutida no projeto).
    """
    img = Image.new('RGB', (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    font_obj = None
    if font_path and os.path.exists(font_path):
        try:
            font_obj = ImageFont.truetype(font_path, font_size)
        except Exception:
            font_obj = None

    if font_obj is None:
        # Último recurso absoluto: fonte bitmap padrão do PIL (pequena, mas
        # pelo menos não quebra o programa). Tenta usar tamanho customizado
        # se a versão do Pillow suportar (Pillow >= 10.1).
        try:
            font_obj = ImageFont.load_default(size=font_size)
        except TypeError:
            font_obj = ImageFont.load_default()

    # Quebra de linha automática (word wrap) baseada na largura em pixels
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        test_line = f"{current_line} {word}".strip()
        bbox = draw.textbbox((0, 0), test_line, font=font_obj)
        if bbox[2] - bbox[0] <= width - 20:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)

    # Calcula altura total do bloco de texto pra centralizar verticalmente
    line_heights = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_obj)
        line_heights.append(bbox[3] - bbox[1])
    line_spacing = int(font_size * 0.35)
    total_text_height = sum(line_heights) + line_spacing * max(0, len(lines) - 1)

    y = max(0, (height - total_text_height) // 2)
    for line, lh in zip(lines, line_heights):
        bbox = draw.textbbox((0, 0), line, font=font_obj)
        line_width = bbox[2] - bbox[0]
        x = max(0, (width - line_width) // 2)
        draw.text((x, y), line, fill=color, font=font_obj)
        y += lh + line_spacing

    return np.array(img)


def build_card_clip(image_path: str, title: str, narration_text: str,
                     audio_path: str, font: str = None) -> CompositeVideoClip:
    """Cria um clipe (1 'card') com fundo branco, título, imagem e legenda,
    com duração igual à do áudio de narração. Usa PIL se font TrueType não existir."""
    font = _resolve_font(font)
    audio = AudioFileClip(audio_path)
    duration = audio.duration + 0.4  # pequena folga no fim

    bg = ColorClip(size=(W, H), color=(255, 255, 255)).with_duration(duration)

    img = (ImageClip(image_path)
           .resized(width=int(W * 0.8))
           .with_position(("center", int(H * 0.30)))
           .with_duration(duration))

    # Título
    if font is None:
        # Renderiza como imagem PIL
        title_img = _render_text_to_image(title, font_size=80, width=int(W * 0.90), height=int(H * 0.15), color="black", font_path=font)
        title_clip = (ImageClip(title_img)
                      .with_position(("center", int(H * 0.08)))
                      .with_duration(duration))
    else:
        # Usa TextClip do moviepy
        title_clip = (TextClip(text=title, font_size=80, color="black", font=font,
                                method="caption", size=(int(W * 0.90), int(H * 0.15)))
                      .with_position(("center", int(H * 0.08)))
                      .with_duration(duration))

    # Legenda
    if font is None:
        # Renderiza como imagem PIL
        caption_img = _render_text_to_image(narration_text, font_size=50, width=int(W * 0.85), height=int(H * 0.28), color="black", font_path=font)
        caption_clip = (ImageClip(caption_img)
                        .with_position(("center", int(H * 0.58)))
                        .with_duration(duration))
    else:
        # Usa TextClip do moviepy
        caption_clip = (TextClip(text=narration_text, font_size=50, color="black", font=font,
                                  method="caption", size=(int(W * 0.85), int(H * 0.28)))
                        .with_position(("center", int(H * 0.58)))
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

# ===== POSICIONAMENTO DO MODO COMPARAÇÃO (2 imagens lado a lado) =====
_IMG_W, _IMG_H = int(W * 0.35), int(H * 0.18)  # Imagens um pouco menores
_LEFT_X, _RIGHT_X = int(W * 0.08), W - _IMG_W - int(W * 0.08)
_IMG_Y = int(H * 0.26)  # Imagens mais para baixo
_TITLE_Y = int(H * 0.10)  # MUITO mais para baixo (era 0.14) — mais espaço no topo

# ===== POSICIONAMENTO DO MODO LISTA (1 imagem grande) =====
_SINGLE_W, _SINGLE_H = int(W * 0.75), int(H * 0.26)
_SINGLE_X = (W - _SINGLE_W) // 2
_SINGLE_Y = int(H * 0.14)  # Um pouco mais para baixo

# ===== POSICIONAMENTO DA LEGENDA/NARRAÇÃO =====
_CAPTION_Y = int(H * 0.35)  # Legenda mais alta (era 0.38)
_CAPTION_W = int(W * 0.90)
_CAPTION_H = int(H * 0.22)  # Um pouco maior

# ===== POSICIONAMENTO DA CORUJA =====
_OWL_Y = int(H * 0.64)


def _bg(duration):
    return ColorClip(size=(W, H), color=(255, 255, 255)).with_duration(duration)


def _title_clip(text, x, w, y, duration, font=None):
    """Cria um clipe de texto para título. Usa PIL se fonte TrueType não existir."""
    resolved_font = _resolve_font(font)
    
    # Se não achou fonte TrueType, renderiza como imagem com PIL
    if resolved_font is None:
        img_array = _render_text_to_image(text, font_size=56, width=w, height=int(H * 0.12), color="black", font_path=resolved_font)
        return (ImageClip(img_array)
                .with_position((x, y))
                .with_duration(duration))
    
    # Se achou font TrueType, usa moviepy TextClip (mais eficiente)
    return (TextClip(text=text, font_size=56, color="black", font=resolved_font,
                      method="caption", size=(w, int(H * 0.12)))
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
    """Cria um clipe de legenda/narração. Usa PIL se fonte TrueType não existir."""
    resolved_font = _resolve_font(font)
    
    # Se não achou fonte TrueType, renderiza como imagem com PIL
    if resolved_font is None:
        img_array = _render_text_to_image(text, font_size=40, width=_CAPTION_W, height=_CAPTION_H, color="black", font_path=resolved_font)
        return (ImageClip(img_array)
                .with_position(("center", _CAPTION_Y))
                .with_duration(duration))
    
    # Se achou font TrueType, usa moviepy TextClip (mais eficiente)
    return (TextClip(text=text, font_size=40, color="black", font=resolved_font,
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
        _title_clip(data["item1_title"], _SINGLE_X, _SINGLE_W, int(H * 0.04), d1, font),
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
