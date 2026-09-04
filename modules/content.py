"""
Geração automática do roteiro do vídeo. Dois modos:

1) MODO LISTA — vários "cards", um por item, formato:
    {
        "title": "Mummy",
        "image_query": "egyptian mummy movie",
        "narration": "This is a mummy. It's a corpse wrapped in cloth..."
    }

2) MODO COMPARAÇÃO — estilo "coruja apontando". Você dá um TEMA e uma
   duração, e a IA inventa vários PARES de comparação relacionados a esse
   tema (não apenas dois itens fixos esticados — vários pares diferentes,
   um atrás do outro), no formato:
    {
        "item1_title": "Vampiro", "item1_image_query": "vampire movie",
        "item2_title": "Lobisomem", "item2_image_query": "werewolf movie",
        "intro1_text": "...", "intro2_text": "...",
        "explain1_text": "...", "explain2_text": "...",
    }
   Cada par vira 4 cenas: mostra item 1 → mostra item 2 e pergunta a
   diferença → coruja aponta pro item 1 e explica → coruja vira e explica
   o item 2. Os pares são concatenados um atrás do outro no vídeo final.

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

# Segundos médios por PAR de comparação (4 falas curtas: intro1, intro2,
# explain1, explain2), usado só pra ESTIMAR quantos pares gerar a partir
# da duração desejada, no modo comparação. Calibrado pra um ritmo mais
# rápido (tipo lista) — cerca de 4 a 5 pares num vídeo de 60s.
AVG_SECONDS_PER_COMPARISON = 13

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


def estimate_comparison_count(duration_seconds: int) -> int:
    return max(1, round(duration_seconds / AVG_SECONDS_PER_COMPARISON))


def is_ollama_available() -> bool:
    try:
        requests.get("http://localhost:11434", timeout=1.5)
        return True
    except Exception:
        return False


def _parse_json_obj(text: str):
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


def _call_groq(prompt: str, api_key: str, model: str = GROQ_DEFAULT_MODEL) -> str:
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
    return resp.json()["choices"][0]["message"]["content"]


def _call_ollama(prompt: str, model: str = "llama3.1") -> str:
    resp = requests.post(
        OLLAMA_URL,
        json={"model": model, "prompt": prompt, "stream": False, "format": "json"},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["response"]


# ---------------------------------------------------------------------------
# MODO LISTA (vários cards)
# ---------------------------------------------------------------------------

def _build_list_prompt(topic: str, n_items: int, language: str) -> str:
    lang_name = LANGUAGE_NAMES.get(language, "português do Brasil")
    return f"""Crie um roteiro para um vídeo curto (estilo TikTok educativo) sobre o tema: "{topic}".

Gere exatamente {n_items} itens. Para cada item, retorne:
- "title": nome curto do item (1 a 3 palavras), escrito em {lang_name}
- "image_query": TERMO DE BUSCA MUITO DETALHADO em inglês (5-8 palavras) que ajude a encontrar 
  uma imagem CLARA E REPRESENTATIVA desse item específico. Inclua: tipo de imagem (photo, movie still, 
  illustration, portrait), contexto visual importante, cores ou características que ajudem a diferenciar 
  de outros itens. Ex: "classic horror movie mummy wrapped in bandages film still" em vez de só "mummy".
- "narration": 1 a 2 frases curtas e didáticas, tom curioso, para narração em voz alta, escrita em {lang_name}

Responda APENAS com um JSON válido, uma lista de {n_items} objetos, sem nenhum texto antes ou depois, sem markdown, sem explicações."""


def _parse_json_list(text: str) -> list[dict]:
    data = _parse_json_obj(text)
    if isinstance(data, dict):
        data = data.get("items") or next(iter(data.values()))
    return data


def generate_script_with_groq(topic: str, n_items: int, language: str, api_key: str,
                               model: str = GROQ_DEFAULT_MODEL) -> list[dict]:
    text = _call_groq(_build_list_prompt(topic, n_items, language), api_key, model)
    return _parse_json_list(text)


def generate_script_with_ollama(topic: str, n_items: int, language: str = "pt",
                                 model: str = "llama3.1") -> list[dict]:
    text = _call_ollama(_build_list_prompt(topic, n_items, language), model)
    return _parse_json_list(text)


def generate_script_fallback(topic: str, n_items: int, language: str = "pt") -> list[dict]:
    """Roteiro placeholder para quando nenhuma IA está disponível.
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


# ---------------------------------------------------------------------------
# MODO COMPARAÇÃO (estilo "coruja apontando") — vários pares a partir de um TEMA
# ---------------------------------------------------------------------------

COMPARISON_FIELDS = [
    "item1_title", "item1_image_query",
    "item2_title", "item2_image_query",
    "intro1_text", "intro2_text",
    "explain1_text", "explain2_text",
]


def _build_comparison_topic_prompt(topic: str, n_pairs: int, language: str,
                                    target_seconds: int | None = None) -> str:
    lang_name = LANGUAGE_NAMES.get(language, "português do Brasil")

    length_hint = ""
    if target_seconds:
        per_pair_seconds = max(6, round(target_seconds / n_pairs))
        per_line_seconds = max(2, round(per_pair_seconds / 4))
        approx_words = max(5, round(per_line_seconds * 2.3))
        length_hint = (
            f"\nCada uma das 4 falas de cada par (intro1_text, intro2_text, "
            f"explain1_text, explain2_text) deve ter por volta de "
            f"{approx_words} palavras (~{per_line_seconds}s falado), pra cada "
            f"par durar perto de {per_pair_seconds}s e o vídeo inteiro durar "
            f"perto de {target_seconds}s no total."
        )

    return f"""Crie o roteiro de um vídeo curto (estilo TikTok educativo, formato "coruja \
professora" comparando pares de conceitos, um par de cada vez) sobre o tema: "{topic}".

Invente exatamente {n_pairs} pares de comparação DIFERENTES e interessantes relacionados a \
esse tema (por exemplo, se o tema for "monstros clássicos", pares como vampiro x lobisomem, \
zumbi x múmia, fantasma x poltergeist — sempre pares distintos entre si, sem repetir o mesmo \
item em pares diferentes sempre que possível).

Para cada par, retorne um objeto JSON com exatamente estes campos, todos escritos em {lang_name} \
(exceto os dois campos que terminam em *_image_query, que devem ser em inglês):
- "item1_title": nome curto de exibição do primeiro item do par (1 a 2 palavras)
- "item1_image_query": TERMO DE BUSCA MUITO DETALHADO em inglês (5-8 palavras) que ajude a \
encontrar uma imagem CLARA do item 1. Inclua: tipo (photo, movie, illustration), contexto, \
características visuais. Ex: "classic vampire dracula movie still portrait" em vez de só "vampire".
- "item2_title": nome curto de exibição do segundo item do par (1 a 2 palavras)
- "item2_image_query": TERMO DE BUSCA MUITO DETALHADO em inglês (5-8 palavras) que ajude a \
encontrar uma imagem CLARA do item 2, visualmente DISTINTO do item 1. Ex: se item1 é vampiro, \
item2_image_query pode ser "werewolf transformation horror film still" para evitar confusão.
- "intro1_text": frase curta apresentando o item 1 (ex: "Este é o(a) X.")
- "intro2_text": frase curta apresentando o item 2 e perguntando a diferença \
(ex: "Este é o(a) Y. Qual a diferença?")
- "explain1_text": 1 a 2 frases curtas e didáticas explicando o item 1. IMPORTANTE: a frase \
DEVE começar citando o nome do item 1 (igual a "item1_title"), nunca começar direto com o verbo \
sem sujeito. Ex certo: "Lobisomem: transformam-se em fera durante a lua cheia." ou "O lobisomem \
se transforma em fera durante a lua cheia." Ex ERRADO (não faça): "Transformam-se em fera \
durante a lua cheia." (sem dizer o nome, fica confuso pra quem está assistindo)
- "explain2_text": mesma regra do explain1_text, mas para o item 2 — DEVE começar citando o \
nome do item 2 (igual a "item2_title")
{length_hint}
Responda APENAS com um JSON válido no formato {{"comparisons": [ ... ]}}, contendo uma lista \
com exatamente {n_pairs} objetos como descrito acima, sem nenhum texto antes ou depois, sem \
markdown, sem explicações."""


def _extract_comparison_list(data) -> list[dict] | None:
    """Aceita tanto {"comparisons": [...]}, quanto {"algumaChave": [...]},
    quanto uma lista JSON "solta" no topo. Retorna None se não achar nada
    utilizável (todos os campos obrigatórios presentes em cada item)."""
    items = None
    if isinstance(data, dict):
        items = data.get("comparisons")
        if items is None:
            for v in data.values():
                if isinstance(v, list):
                    items = v
                    break
    elif isinstance(data, list):
        items = data

    if not isinstance(items, list):
        return None

    valid = [it for it in items if isinstance(it, dict) and all(k in it for k in COMPARISON_FIELDS)]
    return valid or None


def _comparison_pair_fallback(item1: str, item2: str, language: str = "pt") -> dict:
    t = {
        "pt": {
            "intro1": "Este é o(a) {x}.",
            "intro2": "Este é o(a) {x}. Qual a diferença?",
            "explain": "{x}: edite este texto explicando o que é, antes de gerar o áudio.",
        },
        "en": {
            "intro1": "This is the {x}.",
            "intro2": "This is the {x}. What's the difference?",
            "explain": "{x}: edit this text explaining what it is, before generating the audio.",
        },
        "es": {
            "intro1": "Este es el/la {x}.",
            "intro2": "Este es el/la {x}. ¿Cuál es la diferencia?",
            "explain": "{x}: edita este texto explicando qué es, antes de generar el audio.",
        },
        "de": {
            "intro1": "Das ist {x}.",
            "intro2": "Das ist {x}. Was ist der Unterschied?",
            "explain": "{x}: Bearbeite diesen Text, um zu erklären was das ist, bevor du das Audio erzeugst.",
        },
    }.get(language, None) or {
        "intro1": "Este é o(a) {x}.",
        "intro2": "Este é o(a) {x}. Qual a diferença?",
        "explain": "Edite este texto explicando o que é {x} antes de gerar o áudio.",
    }
    return {
        "item1_title": item1,
        "item1_image_query": item1,
        "item2_title": item2,
        "item2_image_query": item2,
        "intro1_text": t["intro1"].format(x=item1),
        "intro2_text": t["intro2"].format(x=item2),
        "explain1_text": t["explain"].format(x=item1),
        "explain2_text": t["explain"].format(x=item2),
    }


def generate_comparison_topics_fallback(topic: str, n_pairs: int, language: str = "pt") -> list[dict]:
    """Roteiro placeholder (sem IA) — cada par usa nomes genéricos derivados
    do tema, pra você editar na mão na tabela."""
    return [
        _comparison_pair_fallback(f"{topic} A{i+1}", f"{topic} B{i+1}", language)
        for i in range(n_pairs)
    ]


def generate_comparison_topics(topic: str, n_pairs: int, language: str = "pt",
                                target_seconds: int | None = None,
                                groq_api_key: str | None = None,
                                use_ollama: bool = False,
                                ollama_model: str = "llama3.1") -> list[dict]:
    """Gera N pares de comparação sobre um TEMA (não 2 itens fixos).
    Cada par vira 4 cenas no vídeo final (build_multi_comparison_video)."""
    prompt = _build_comparison_topic_prompt(topic, n_pairs, language, target_seconds)

    if groq_api_key:
        try:
            data = _parse_json_obj(_call_groq(prompt, groq_api_key))
            items = _extract_comparison_list(data)
            if items:
                return items[:n_pairs] if len(items) > n_pairs else items
            print("[content] Groq retornou JSON incompleto/sem pares válidos, tentando próxima opção.")
        except Exception as e:
            print(f"[content] Falha ao usar Groq ({e}), tentando próxima opção.")

    if use_ollama:
        try:
            data = _parse_json_obj(_call_ollama(prompt, ollama_model))
            items = _extract_comparison_list(data)
            if items:
                return items[:n_pairs] if len(items) > n_pairs else items
            print("[content] Ollama retornou JSON incompleto/sem pares válidos, usando fallback sem IA.")
        except Exception as e:
            print(f"[content] Falha ao usar Ollama ({e}), usando fallback sem IA.")

    return generate_comparison_topics_fallback(topic, n_pairs, language)
