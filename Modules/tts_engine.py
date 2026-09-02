"""
Text-to-Speech realista usando Chatterbox TTS (open-source, MIT license).
Repo: https://github.com/resemble-ai/chatterbox

Clona uma voz a partir de um áudio de referência de poucos segundos (.wav/.mp3)
e gera narrações naturais para cada frase do roteiro.

pip install chatterbox-tts

OBS: precisa de GPU (CUDA) pra rodar rápido. Em CPU funciona, porém mais lento.
Se preferir CPU-only e mais leve, dá pra trocar por Kokoro-TTS (ver README).
"""

import torchaudio as ta
import torch

_model = None


def _load_model():
    global _model
    if _model is None:
        from chatterbox.tts import ChatterboxTTS
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _model = ChatterboxTTS.from_pretrained(device=device)
    return _model


def synthesize(text: str, out_path: str, reference_voice_path: str | None = None,
               exaggeration: float = 0.5, cfg_weight: float = 0.5) -> str:
    """
    Gera um arquivo de áudio .wav a partir do texto.

    reference_voice_path: caminho de um áudio (5-10s) com a voz a clonar.
                           Se None, usa a voz padrão do modelo.
    exaggeration: 0.0-1.0, quanto mais alto, mais expressivo/dramático.
    cfg_weight: controla o quanto a geração segue o texto vs a naturalidade.
    """
    model = _load_model()

    kwargs = {"exaggeration": exaggeration, "cfg_weight": cfg_weight}
    if reference_voice_path:
        kwargs["audio_prompt_path"] = reference_voice_path

    wav = model.generate(text, **kwargs)
    ta.save(out_path, wav, model.sr)
    return out_path
