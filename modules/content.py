# Em """
Geração automática do roteiro do vídeo. Dois modos:

1) MODO LISTA — vários "cards", um por item, formato:
    {
        "title": "Mummy",
        "image_query": "egyptian mummy movie",
        "narration": "This is a mummy. It's a corpse wrapped in cloth..."
    }

2) MODO COMPARAÇÃO — estilo "coruja apontando", comparando 2 itens:
   mostra item 1 → mostra item 2 e pergunta a diferença → coruja aponta
   pro item 1 e explica → coruja vira e explica o item 2.

Geração 100% gratuita, com duas opções de IA:
1. **Groq** (https://console.groq.com) — API na nuvem, gratuita, sem cartão
   de crédito. Funciona tanto local quanto no Streamlit Cloud.
2. **Ollama** (https://ollama.com) — IA local, sem chave, só funciona
   rodando o app na sua própria máquina.

Sem nenhuma das duas, cai num roteiro placeholder simples que você edita na mão.
"""

import json
import requests

# Segundos médios de narração por item (título + frase), usado só pra
# ESTIMAR quantos itens gerar a partir da duração desejada, no modo lista.
AVG_SECONDS_PER_ITEM = 7

LANGUAGE_NAMES = {
    "pt": "português do Brasil",
    "en": "inglês",
    "es": "espanhol",
    "de": "alemão",
}

OLLAMA_URL = "http://localhost:11434/api/generate"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
# ATENÇÃO: a Groq desativa modelos periodicamente. Se este parar de
# funcionar, veja a lista atual em https://console.groq.com/docs/models
GROQ_DEFAULT_MODEL = "openai/gpt-oss-120b"


def estimate_item_count(duration_seconds: int) -> int:
    return max(2, round(duration_seconds / AVG_SECONDS_PER_ITEM))


def is_ollama_available() -> bool:
    try:
        requests.get("http://localhost:11434", timeout=1.5)
        return True
    except Exception:
        return False


def _parse_json_obj(text: str):
    text = text.strip().removeprefix("```json").removeprefix("
