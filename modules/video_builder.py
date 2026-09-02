"""
Monta o vídeo final (formato 9:16, estilo TikTok) juntando:
- imagem de cada item
- título em texto
- narração em áudio (realista, gerada pelo tts_engine)

pip install moviepy
"""

import os
from moviepy import (
    ImageClip, TextClip, CompositeVideoClip, AudioFileClip,
    concatenate_videoclips, ColorClip,
)

W, H = 1080, 1920  # formato vertical TikTok


def build_card_clip(image_path: str, title: str, narration_text: str,
                     audio_path: str, font: str = None) -> CompositeVideoClip:
    """Cria um clipe (1 'card') com fundo branco, título, imagem e legenda,
    com duração igual à do áudio de narração."""
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

    caption_clip = (TextClip(text=narration_text, font_size=55, color="black", font=font,
                              method="caption", size=(int(W * 0.85), None))
                    .with_position(("center", int(H * 0.62)))
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
    final.write_videofile(out_path, fps=30, codec="libx264", audio_codec="aac")
    return out_path
