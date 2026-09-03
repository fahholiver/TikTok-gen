"""
Geração automática do roteiro do vídeo.

Formato de saída (lista de dicts), um item por "card" do vídeo:
    {
        "title": "Mummy",              # texto grande que aparece sobre a imagem
        "image_query": "egyptian mummy movie", # o que buscar na web
        "narration": "This is a mummy. It's a corpse wrapped in cloth..."
    }

Duas formas de gerar:
1) Com uma API de LLM (Anthropic) — melhor qualidade, precisa de ANTHROPIC_API_KEY.
2) Fallback local simples — sem API, usa um template básico (edite manualmente).
"""

"""
Geração automática do roteiro do vídeo.

Formato de saída (lista de dicts), um item por "card" do vídeo:
    {
        "title": "Mummy",              # texto grande que aparece sobre a imagem
        "image_query": "egyptian mummy movie", # o que buscar na web
        "narration": "This is a mummy. It's a corpse wrapped in cloth..."
    }

Geração 100% gratuita, usando IA local via Ollama (https://ollama.com):
- Sem chave de API, sem custo, sem enviar nada pra fora do seu computador.
- Só precisa instalar o Ollama e baixar um modelo (ex: `ollama pull llama3.1`).

Se o Ollama não estiver rodando, cai automaticamente num roteiro
placeholder simples (fallback local, sem IA nenhuma) que você edita na mão.
"""

import json
import requests

# Segundos médios de narração por item (título + frase), usado só pra
# ESTIMAR quantos itens gerar a partir da duração desejada. A duração real
# do vídeo final depende do tamanho do texto e só é conhecida após gerar
# o áudio de cada item.
AVG_SECONDS_PER_ITEM = 7

LANGUAGE_NAMES = {
    "pt": "português do Brasil",
    "en": "inglês",
    "es": "espanhol",
    "de": "alemão",
}

OLLAMA_URL = "http://localhost:11434/api/generate"


def estimate_item_count(duration_seconds: int) -> int:
    return max(2, round(duration_seconds / AVG_SECONDS_PER_ITEM))


def is_ollama_available() -> bool:
    try:
        requests.get("http://localhost:11434", timeout=1.5)
        return True
    except Exception:
        return False


def generate_script_with_ollama(topic: str, n_items: int, language: str = "pt",
                                 model: str = "llama3.1") -> list[dict]:
    """Gera o roteiro usando um modelo local rodando no Ollama (gratuito)."""
    lang_name = LANGUAGE_NAMES.get(language, "português do Brasil")

    prompt = f"""Crie um roteiro para um vídeo curto (estilo TikTok educativo) sobre o tema: "{topic}".

Gere exatamente {n_items} itens. Para cada item, retorne:
- "title": nome curto do item (1 a 3 palavras), escrito em {lang_name}
- "image_query": termo de busca em inglês para achar uma boa imagem do item (sempre em inglês)
- "narration": 1 a 2 frases curtas e didáticas, tom curioso, para narração em voz alta, escrita em {lang_name}

Responda APENAS com um JSON válido, uma lista de {n_items} objetos, sem nenhum texto antes ou depois, sem markdown, sem explicações."""

    resp = requests.post(
        OLLAMA_URL,
        json={"model": model, "prompt": prompt, "stream": False, "format": "json"},
        timeout=120,
    )
    resp.raise_for_status()
    text = resp.json()["response"].strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    data = json.loads(text)
    # alguns modelos retornam {"items": [...]} em vez da lista direto
    if isinstance(data, dict):
        data = data.get("items") or next(iter(data.values()))
    return data


def generate_script_fallback(topic: str, n_items: int, language: str = "pt") -> list[dict]:
    """Roteiro placeholder para quando o Ollama não está disponível.
    Edite os textos manualmente na interface do Streamlit depois."""
    templates = {
        "pt": "Este é o item {i} sobre {topic}. Edite este texto antes de gerar o áudio.",
        "en": "This is item {i} about {topic}. Edit this text before generating the audio.",
        "es": "Este es el elemento {i} sobre {topic}. Edita este texto antes de generar el audio.",
        "de": "Dies ist Punkt {i} zum Thema {topic}. Bearbeite diesen Text, bevor du das Audio erzeugst.",
    }
    template = templates.get(language, templates["pt"])
    return [
        {
            "title": f"{topic} #{i+1}",
            "image_query": f"{topic} {i+1}",
            "narration": template.format(i=i + 1, topic=topic),
        }
        for i in range(n_items)
    ]


def generate_script(topic: str, n_items: int, language: str = "pt",
                     use_ollama: bool = True, ollama_model: str = "llama3.1") -> list[dict]:
    if use_ollama:
        try:
            return generate_script_with_ollama(topic, n_items, language, ollama_model)
        except Exception as e:
            print(f"[content] Falha ao usar Ollama ({e}), usando fallback sem IA.")
    return generate_script_fallback(topic, n_items, language)
