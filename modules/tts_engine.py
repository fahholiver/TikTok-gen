"""
TTS leve com Kokoro-82M (open-source, Apache 2.0) — ~80MB, roda bem em CPU
com pouca RAM, ideal pra hospedagem gratuita (Streamlit Cloud).
Repo: https://github.com/hexgrad/kokoro

IMPORTANTE - diferença em relação ao Chatterbox usado antes:
Kokoro NÃO clona a sua voz a partir de um áudio de referência. Ele usa
vozes pré-treinadas (mas naturais, não robóticas). Se clonagem de voz for
essencial pra você, isso só é viável rodando local com GPU (Chatterbox),
não no plano grátis do Streamlit Cloud.

pip install kokoro soundfile numpy
Precisa também do pacote de sistema `espeak-ng` — no Streamlit Cloud,
crie um arquivo `packages.txt` na raiz do repo com a linha: espeak-ng
"""

import subprocess
import numpy as np
import soundfile as sf

LANGUAGES = {
    "Português (BR)": "pt",
    "English": "en",
    "Español": "es",
    "Deutsch": "de",
}

# Kokoro cobre pt/en/es nativamente e soa natural. Alemão NÃO é suportado
# oficialmente pelo Kokoro-82M -> usamos espeak-ng puro só pra alemão como
# fallback (funciona sempre, mas soa mais robótico que os outros 3 idiomas).
_KOKORO_LANG_CODE = {"pt": "p", "en": "a", "es": "e"}

_DEFAULT_VOICE = {"pt": "pf_dora", "en": "af_heart", "es": "ef_dora"}

_pipelines: dict = {}


def _get_pipeline(kokoro_lang_code: str):
    from kokoro import KPipeline
    if kokoro_lang_code not in _pipelines:
        _pipelines[kokoro_lang_code] = KPipeline(lang_code=kokoro_lang_code)
    return _pipelines[kokoro_lang_code]


def synthesize(text: str, out_path: str, reference_voice_path: str | None = None,
               language_id: str = "pt", voice: str | None = None, **_ignored) -> str:
    """
    Gera um arquivo de áudio .wav a partir do texto.

    reference_voice_path: ignorado (mantido só por compatibilidade com o
                           app.py) — Kokoro não clona voz a partir de áudio.
    language_id: "pt", "en", "es" ou "de".
    voice: nome de uma voz pré-treinada do Kokoro (ex: "af_heart", "pf_dora",
           "pm_alex"...). Se None, usa uma voz padrão adequada ao idioma.
    """
    if language_id == "de":
        return _synthesize_espeak(text, out_path)

    kokoro_lang = _KOKORO_LANG_CODE.get(language_id, "a")
    pipeline = _get_pipeline(kokoro_lang)
    voice_name = voice or _DEFAULT_VOICE.get(language_id, "af_heart")

    chunks = [audio for _, _, audio in pipeline(text, voice=voice_name)]
    full_audio = np.concatenate(chunks) if len(chunks) > 1 else chunks[0]
    sf.write(out_path, full_audio, 24000)
    return out_path


def _synthesize_espeak(text: str, out_path: str) -> str:
    """Fallback só pra alemão: Kokoro-82M não cobre 'de' oficialmente.
    Usa espeak-ng puro — sempre funciona, mas soa mais robótico que o Kokoro."""
    subprocess.run(["espeak-ng", "-v", "de", "-w", out_path, text], check=True)
    return out_path
