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

import json
import os

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


def estimate_item_count(duration_seconds: int) -> int:
    return max(2, round(duration_seconds / AVG_SECONDS_PER_ITEM))


def generate_script_with_llm(topic: str, n_items: int, api_key: str, language: str = "pt") -> list[dict]:
    """Usa a API da Anthropic para gerar o roteiro automaticamente."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    lang_name = LANGUAGE_NAMES.get(language, "português do Brasil")

    prompt = f"""Crie um roteiro para um vídeo curto (estilo TikTok educativo) sobre o tema: "{topic}".

Gere exatamente {n_items} itens. Para cada item, retorne:
- "title": nome curto do item (1 a 3 palavras), escrito em {lang_name}
- "image_query": termo de busca em inglês para achar uma boa imagem do item (sempre em inglês, mesmo que o resto não seja)
- "narration": 1 a 2 frases curtas e didáticas, tom curioso, para narração em voz alta, escrita em {lang_name}

Responda APENAS com um JSON válido, uma lista de objetos, sem nenhum texto antes ou depois, sem markdown."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )

    text = "".join(block.text for block in response.content if block.type == "text")
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


def generate_script_fallback(topic: str, n_items: int, language: str = "pt") -> list[dict]:
    """Roteiro placeholder para quando não há API configurada.
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


def generate_script(topic: str, n_items: int, api_key: str | None = None, language: str = "pt") -> list[dict]:
    if api_key:
        try:
            return generate_script_with_llm(topic, n_items, api_key, language)
        except Exception as e:
            print(f"[content] Falha ao usar LLM ({e}), usando fallback.")
    return generate_script_fallback(topic, n_items, language)
