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

Geração 100% gratuita, com duas opções de IA:
1. **Groq** (https://console.groq.com) — API na nuvem, gratuita, sem cartão
   de crédito. Funciona tanto local quanto no Streamlit Cloud (é a opção
   recomendada pra quem hospedou o app na nuvem).
2. **Ollama** (https://ollama.com) — IA local, sem chave, mas só funciona
   rodando o app na sua própria máquina (o Streamlit Cloud não enxerga o
   Ollama do seu computador).

Se nenhuma das duas estiver configurada, cai automaticamente num roteiro
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


def _build_prompt(topic: str, n_items: int, language: str) -> str:
    lang_name = LANGUAGE_NAMES.get(language, "português do Brasil")
    return f"""Crie um roteiro para um vídeo curto (estilo TikTok educativo) sobre o tema: "{topic}".

Gere exatamente {n_items} itens. Para cada item, retorne:
- "title": nome curto do item (1 a 3 palavras), escrito em {lang_name}
- "image_query": termo de busca em inglês para achar uma boa imagem do item (sempre em inglês)
- "narration": 1 a 2 frases curtas e didáticas, tom curioso, para narração em voz alta, escrita em {lang_name}

Responda APENAS com um JSON válido, uma lista de {n_items} objetos, sem nenhum texto antes ou depois, sem markdown, sem explicações."""


def _parse_json_list(text: str) -> list[dict]:
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    data = json.loads(text)
    # alguns modelos retornam {"items": [...]} em vez da lista direto
    if isinstance(data, dict):
        data = data.get("items") or next(iter(data.values()))
    return data


def generate_script_with_groq(topic: str, n_items: int, language: str, api_key: str,
                               model: str = GROQ_DEFAULT_MODEL) -> list[dict]:
    """Gera o roteiro usando a API gratuita da Groq (funciona na nuvem)."""
    prompt = _build_prompt(topic, n_items, language)
    resp = requests.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        },
        timeout=60,
    )
    if resp.status_code != 200:
        # Mostra o motivo real do erro (chave inválida, modelo errado,
        # limite excedido etc.) em vez de só "404 Not Found".
        raise RuntimeError(f"Groq API respondeu {resp.status_code}: {resp.text[:500]}")
    text = resp.json()["choices"][0]["message"]["content"]
    return _parse_json_list(text)


def generate_script_with_ollama(topic: str, n_items: int, language: str = "pt",
                                 model: str = "llama3.1") -> list[dict]:
    """Gera o roteiro usando um modelo local rodando no Ollama (gratuito)."""
    prompt = _build_prompt(topic, n_items, language)
    resp = requests.post(
        OLLAMA_URL,
        json={"model": model, "prompt": prompt, "stream": False, "format": "json"},
        timeout=120,
    )
    resp.raise_for_status()
    text = resp.json()["response"]
    return _parse_json_list(text)


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
                     groq_api_key: str | None = None,
                     use_ollama: bool = False, ollama_model: str = "llama3.1") -> list[dict]:
    if groq_api_key:
        try:
            return generate_script_with_groq(topic, n_items, language, groq_api_key)
        except Exception as e:
            print(f"[content] Falha ao usar Groq ({e}), tentando próxima opção.")
    if use_ollama:
        try:
            return generate_script_with_ollama(topic, n_items, language, ollama_model)
        except Exception as e:
            print(f"[content] Falha ao usar Ollama ({e}), usando fallback sem IA.")
    return generate_script_fallback(topic, n_items, language)
