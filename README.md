# Gerador Automático de Vídeos (estilo TikTok)

Gera vídeos curtos verticais automaticamente: busca imagens na web, cria
narração em voz realista (clonada) e monta tudo em um único `.mp4`, via
interface Streamlit.

## Como rodar

```bash
git clone <seu-repo>
cd tiktok-gen
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

pip install -r requirements.txt
streamlit run app.py
```

Abre em `http://localhost:8501`.

## Requisitos importantes

- **GPU recomendada**: Chatterbox TTS roda em CPU, mas fica bem mais lento
  (cada frase pode levar dezenas de segundos). Se não tiver GPU, considere
  trocar por [Kokoro-TTS](https://github.com/hexgrad/kokoro), mais leve.
- **Imagemagick**: o `moviepy` usa Imagemagick para renderizar texto
  (`TextClip`). Instale com `sudo apt install imagemagick` (Linux) ou
  baixe o instalador no Windows/Mac.
- **Chave da Anthropic (opcional)**: só é usada para gerar o roteiro
  (títulos + falas) automaticamente a partir do tema. Sem ela, o app usa
  um roteiro placeholder que você edita manualmente na interface.

## Como funciona o pipeline

1. `modules/content.py` — gera a lista de itens (título, texto de busca de
   imagem, texto de narração) a partir do tema.
2. `modules/images.py` — busca e baixa uma imagem por item, via DuckDuckGo
   (sem precisar de chave de API).
3. `modules/tts_engine.py` — gera o áudio da narração clonando a voz de
   referência que você enviar (ChatterboxTTS).
4. `modules/video_builder.py` — monta os "cards" (imagem + título + legenda)
   sincronizados com o áudio e concatena tudo em um vídeo vertical 1080x1920.

## Trocar o motor de voz

Se quiser usar outra engine (ex: Coqui XTTS-v2), basta reescrever
`modules/tts_engine.py` mantendo a função `synthesize(text, out_path,
reference_voice_path)` com a mesma assinatura — o resto do app não muda.

## Sobre imagens e direitos autorais

As imagens baixadas vêm de busca aberta na web e **podem ter direitos
autorais de terceiros**. Para uso comercial ou postagem em massa, prefira
bancos de imagem livres (Pexels, Unsplash, Pixabay) ou gere imagens com
IA (ex: Stable Diffusion) para evitar problemas de copyright.

## Sobre postar automaticamente no TikTok

Este projeto só gera o `.mp4`. Postar automaticamente exige a TikTok
Content Posting API (precisa de aprovação de app pelo TikTok for
Developers) — isso pode ser adicionado depois, num módulo separado.
