# Gerador Automático de Vídeos (estilo TikTok)

Gera vídeos curtos verticais automaticamente: busca imagens na web, cria
narração em voz realista (clonada) e monta tudo em um único `.mp4`, via
interface Streamlit.

**100% gratuito**: roteiro gerado por IA local (Ollama, sem chave de API),
busca de imagens sem API key (DuckDuckGo) e voz com o modelo open-source
**Kokoro-82M** — leve o bastante pra rodar até no plano grátis do
Streamlit Cloud. Nenhum serviço pago é necessário.

## Como rodar localmente

```bash
git clone <seu-repo>
cd tiktok-gen
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

pip install -r requirements.txt
streamlit run app.py
```

Abre em `http://localhost:8501`.

## Como rodar no Streamlit Cloud (grátis)

1. Suba o repositório no GitHub (já com `requirements.txt` e `packages.txt`).
2. Em [share.streamlit.io](https://share.streamlit.io), crie um novo app
   apontando pro seu repositório e pro arquivo `app.py`.
3. O `packages.txt` já está configurado com as dependências de sistema
   (`espeak-ng`, `imagemagick`) que o Streamlit Cloud instala sozinho.
4. Diferente do Chatterbox (usado antes), o **Kokoro é leve o bastante**
   para caber nos ~1GB de RAM do plano grátis.

## Requisitos importantes

- **Kokoro não precisa de GPU** — roda bem em CPU mesmo no plano grátis.
- **espeak-ng**: necessário como motor de fonética do Kokoro (e como
  fallback total para alemão). Já incluso no `packages.txt`.
- **Imagemagick**: o `moviepy` usa pra renderizar texto (`TextClip`). Já
  incluso no `packages.txt` — localmente, instale com
  `sudo apt install imagemagick` (Linux) ou baixe o instalador no
  Windows/Mac.
- **Ollama (opcional, 100% gratuito)**: gera o roteiro (títulos + falas)
  automaticamente a partir do tema, sem chave de API, sem custo.
  1. Baixe em [ollama.com](https://ollama.com) e instale.
  2. Rode `ollama pull llama3.1` (ou `mistral`, `qwen2.5`, `gemma2`, etc.)
  3. Deixe o Ollama rodando em segundo plano — o app detecta sozinho.
  4. **No Streamlit Cloud isso não funciona** (o servidor é isolado e não
     enxerga o Ollama da sua máquina) — lá o app sempre usa o roteiro
     placeholder simples, que você edita manualmente na interface.
  5. Sem o Ollama, o app usa o mesmo roteiro placeholder.

## Como funciona o pipeline

1. `modules/content.py` — gera a lista de itens (título, texto de busca de
   imagem, texto de narração) a partir do tema e do idioma escolhido. O número
   de itens é **estimado** a partir da duração desejada (segundos ÷ ~7s por item).
2. `modules/images.py` — busca e baixa uma imagem por item, via DuckDuckGo
   (sem precisar de chave de API).
3. `modules/tts_engine.py` — gera o áudio da narração no idioma escolhido
   (pt/en/es via Kokoro-82M; alemão via espeak-ng como reserva, já que o
   Kokoro ainda não cobre esse idioma oficialmente). Sem clonagem de voz —
   usa vozes prontas.
4. `modules/video_builder.py` — monta os "cards" (imagem + título + legenda)
   sincronizados com o áudio e concatena tudo em um vídeo vertical 1080x1920.

### Sobre a duração escolhida

A duração em segundos que você define na interface é usada só para **estimar**
quantos itens gerar. A duração final real depende de quanto texto cada
narração tem — ela só é conhecida com exatidão depois que o áudio de cada
item é gerado, e aparece na tela ao final da renderização.

### Sobre o idioma e as vozes

Português, inglês e espanhol usam o Kokoro-82M, com vozes naturais prontas
(não robotizadas). Alemão ainda não é suportado nativamente pelo Kokoro,
então usa espeak-ng como reserva — funciona, mas soa mais robótico. Se
alemão realista for essencial, a alternativa é usar o Chatterbox
Multilingual local (exige mais RAM/GPU — ver histórico de versões deste
projeto ou o repositório oficial em
[github.com/resemble-ai/chatterbox](https://github.com/resemble-ai/chatterbox)).

## Trocar o motor de voz

Se quiser usar outra engine (ex: voltar ao Chatterbox pra clonagem de voz,
rodando local com GPU), basta reescrever `modules/tts_engine.py` mantendo
a função `synthesize(text, out_path, language_id=..., voice=...)` com a
mesma assinatura — o resto do app não muda.

## Sobre imagens e direitos autorais

As imagens baixadas vêm de busca aberta na web e **podem ter direitos
autorais de terceiros**. Para uso comercial ou postagem em massa, prefira
bancos de imagem livres (Pexels, Unsplash, Pixabay) ou gere imagens com
IA (ex: Stable Diffusion) para evitar problemas de copyright.

## Sobre postar automaticamente no TikTok

Este projeto só gera o `.mp4`. Postar automaticamente exige a TikTok
Content Posting API (precisa de aprovação de app pelo TikTok for
Developers) — isso pode ser adicionado depois, num módulo separado.
