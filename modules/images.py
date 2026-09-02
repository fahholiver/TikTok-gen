"""
Busca e download de imagens da web, sem precisar de chave de API,
usando o pacote `ddgs` (DuckDuckGo Search).

pip install ddgs requests pillow
"""

import os
import requests
from PIL import Image
from io import BytesIO


def search_image_url(query: str, retries: int = 5) -> str | None:
    """Retorna a URL da primeira imagem utilizável encontrada para a query."""
    from ddgs import DDGS

    with DDGS() as ddgs:
        results = ddgs.images(query, max_results=retries)
        for r in results:
            url = r.get("image")
            if url:
                return url
    return None


def download_image(url: str, out_path: str, min_size: int = 300) -> bool:
    """Baixa e valida a imagem. Retorna True se deu certo."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content)).convert("RGB")
        if min(img.size) < min_size:
            return False
        img.save(out_path, "JPEG", quality=90)
        return True
    except Exception as e:
        print(f"[images] Falha ao baixar {url}: {e}")
        return False


def fetch_image_for_item(query: str, out_path: str, max_attempts: int = 5) -> bool:
    """Busca e baixa uma imagem, tentando várias URLs até uma funcionar."""
    from ddgs import DDGS

    with DDGS() as ddgs:
        results = list(ddgs.images(query, max_results=max_attempts))

    for r in results:
        url = r.get("image")
        if url and download_image(url, out_path):
            return True
    return False
