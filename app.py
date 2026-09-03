import os
import wave
import streamlit as st
import pandas as pd

from modules.content import (
    generate_script, estimate_item_count, is_ollama_available,
    generate_comparison_script,
)
from modules.images import fetch_image_for_item
from modules.tts_engine import synthesize, LANGUAGES
from modules.video_builder import build_video, build_comparison_video

st.set_page_config(page_title="Gerador de Vídeos Educativos", page_icon="🎬", layout="centered")
st.title("🎬 Gerador automático de vídeos (estilo TikTok)")

os.makedirs("output", exist_ok=True)
os.makedirs("output/images", exist_ok=True)
os.makedirs("output/audio", exist_ok=True)

# ---------------------------------------------------------------------------
# Configurações gerais (valem pros dois modos)
# ---------------------------------------------------------------------------
mode = st.radio(
    "Formato do vídeo",
    ["Lista de itens (vários cards)", "Comparação (coruja apontando)"],
    horizontal=False,
)

language_label = st.selectbox("Idioma falado da narração", list(LANGUAGES.keys()))
language = LANGUAGES[language_label]

st.subheader("IA para escrever o roteiro (gratuita)")

groq_api_key_input = st.text_input(
    "Chave da API Groq (gratuita, recomendada — funciona também na nuvem)",
    type="password",
    help="Crie de graça em https://console.groq.com/keys (sem cartão de crédito). "
         "Se você já está no Streamlit Cloud, salve a chave em Settings → Secrets "
         "como GROQ_API_KEY em vez de colar aqui toda vez.",
)
try:
    groq_api_key = groq_api_key_input or st.secrets.get("GROQ_API_KEY", "")
except Exception:
    groq_api_key = groq_api_key_input

ollama_ok = is_ollama_available()

if groq_api_key:
    st.success("✅ Groq configurado — roteiro será gerado por IA, de graça, funciona na nuvem também.")
elif ollama_ok:
    st.success("✅ Ollama detectado rodando localmente — roteiro será gerado por IA, de graça.")
else:
    st.warning(
        "⚠️ Nenhuma IA configurada. Opções gratuitas:\n"
        "- **Groq** (recomendado, funciona na nuvem): crie uma chave grátis em "
        "[console.groq.com/keys](https://console.groq.com/keys) e cole acima.\n"
        "- **Ollama** (só funciona rodando localmente): instale em "
        "[ollama.com](https://ollama.com) e rode `ollama pull llama3.1`.\n\n"
        "Sem nenhuma das duas, o roteiro sai como um placeholder simples pra você editar na mão."
    )

ollama_model = st.text_input(
    "Modelo do Ollama a usar (só é usado se você não colocou chave da Groq)", "llama3.1",
    help="Qualquer modelo que você já tenha baixado com `ollama pull <modelo>`. "
         "Ex: llama3.1, mistral, qwen2.5, gemma2.",
)

st.subheader("Voz de narração")
st.caption(
    "Motor de voz: **Kokoro** (leve, roda até em servidores gratuitos). "
    "Ele não clona a sua voz — usa vozes prontas, mas naturais."
)
VOICE_OPTIONS = {
    "pt": {"Feminina (Dora)": "pf_dora", "Masculina (Alex)": "pm_alex", "Masculina (Santa)": "pm_santa"},
    "en": {"Feminina (Heart)": "af_heart", "Feminina (Bella)": "af_bella", "Masculina (Michael)": "am_michael"},
    "es": {"Feminina (Dora)": "ef_dora", "Masculina (Alex)": "em_alex", "Masculina (Santa)": "em_santa"},
    "de": {"Padrão (espeak-ng, mais robótica)": None},
}
voice_choices = VOICE_OPTIONS.get(language, {})
voice_label = st.selectbox("Voz", list(voice_choices.keys()))
selected_voice = voice_choices[voice_label]
if language == "de":
    st.info(
        "ℹ️ O Kokoro não tem suporte nativo a alemão ainda, então esse idioma "
        "usa o espeak-ng como reserva — funciona, mas soa mais robótica que "
        "as vozes em português/inglês/espanhol."
    )

st.divider()

# ---------------------------------------------------------------------------
# MODO 1: Lista de itens (vários cards)
# ---------------------------------------------------------------------------
if mode == "Lista de itens (vários cards)":
    st.header("1. Tema do vídeo")
    topic = st.text_input("Sobre o que é o vídeo?", "Monstros clássicos de filmes de terror")

    duration_seconds = st.slider("Duração aproximada do vídeo (segundos)", 10, 120, 30, step=5)
    n_items = estimate_item_count(duration_seconds)
    st.caption(
        f"Isso deve gerar em torno de **{n_items} itens/cards**. "
        "A duração final pode variar um pouco — só é conhecida com exatidão "
        "depois de gerar o áudio."
    )

    if "script" not in st.session_state:
        st.session_state.script = None

    if st.button("📝 Gerar roteiro"):
        with st.spinner("Gerando roteiro..."):
            st.session_state.script = generate_script(
                topic, n_items, language,
                groq_api_key=groq_api_key or None,
                use_ollama=ollama_ok, ollama_model=ollama_model,
            )

    if st.session_state.script:
        st.header("2. Revise e edite o roteiro")
        df = pd.DataFrame(st.session_state.script)
        edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
        st.session_state.script = edited_df.to_dict(orient="records")

        st.header("3. Gerar vídeo")
        if st.button("🎥 Renderizar vídeo final"):
            items = []
            progress = st.progress(0.0, text="Iniciando...")
            total = len(st.session_state.script)

            for i, row in enumerate(st.session_state.script):
                title = str(row["title"])
                narration = str(row["narration"])
                image_query = str(row.get("image_query", title))

                progress.progress(i / total, text=f"Buscando imagem: {title}")
                img_path = f"output/images/{i}.jpg"
                ok = fetch_image_for_item(image_query, img_path)
                if not ok:
                    st.warning(f"Não achei imagem para '{title}', pulei esse item.")
                    continue

                progress.progress(i / total, text=f"Gerando voz: {title}")
                audio_path = f"output/audio/{i}.wav"
                synthesize(narration, audio_path, language_id=language, voice=selected_voice)

                items.append({
                    "title": title,
                    "narration": narration,
                    "image_path": img_path,
                    "audio_path": audio_path,
                })

            progress.progress(0.95, text="Montando vídeo final...")
            out_path = "output/video_final.mp4"
            build_video(items, out_path)
            progress.progress(1.0, text="Pronto!")

            total_audio_s = sum(
                wave.open(item["audio_path"]).getnframes() / wave.open(item["audio_path"]).getframerate()
                for item in items
            )
            st.success(
                f"Vídeo gerado com sucesso! Duração real: ~{total_audio_s:.0f}s "
                f"(você pediu {duration_seconds}s)."
            )
            st.video(out_path)
            with open(out_path, "rb") as f:
                st.download_button("⬇️ Baixar vídeo", f, file_name="video_final.mp4")

# ---------------------------------------------------------------------------
# MODO 2: Comparação estilo "coruja apontando"
# ---------------------------------------------------------------------------
else:
    st.header("1. O que comparar?")
    col1, col2 = st.columns(2)
    item1 = col1.text_input("Item 1", "Mummy")
    item2 = col2.text_input("Item 2", "Zombie")

    st.subheader("Apresentador (coruja)")
    owl_file = st.file_uploader(
        "Envie uma imagem do apresentador (opcional — fundo branco funciona melhor). "
        "Se não enviar, o app busca uma imagem de coruja com cartola e monóculo na web.",
        type=["jpg", "jpeg", "png"],
    )
    if owl_file:
        os.makedirs("assets", exist_ok=True)
        owl_path = "assets/owl_custom.jpg"
        with open(owl_path, "wb") as f:
            f.write(owl_file.read())
        st.image(owl_path, width=150)
    else:
        owl_path = None  # será buscado na hora de renderizar

    if "comparison_script" not in st.session_state:
        st.session_state.comparison_script = None

    if st.button("📝 Gerar roteiro da comparação"):
        with st.spinner("Gerando roteiro..."):
            st.session_state.comparison_script = generate_comparison_script(
                item1, item2, language,
                groq_api_key=groq_api_key or None,
                use_ollama=ollama_ok, ollama_model=ollama_model,
            )

    if st.session_state.comparison_script:
        st.header("2. Revise e edite as falas")
        d = st.session_state.comparison_script
        c1, c2 = st.columns(2)
        d["item1_title"] = c1.text_input("Título exibido - item 1", d["item1_title"])
        d["item2_title"] = c2.text_input("Título exibido - item 2", d["item2_title"])
        d["item1_image_query"] = c1.text_input("Busca de imagem - item 1 (inglês)", d["item1_image_query"])
        d["item2_image_query"] = c2.text_input("Busca de imagem - item 2 (inglês)", d["item2_image_query"])
        d["intro1_text"] = st.text_area("Fala 1 — apresenta o item 1", d["intro1_text"])
        d["intro2_text"] = st.text_area("Fala 2 — apresenta o item 2 e pergunta a diferença", d["intro2_text"])
        d["explain1_text"] = st.text_area("Fala 3 — explica o item 1 (coruja aponta pra ele)", d["explain1_text"])
        d["explain2_text"] = st.text_area("Fala 4 — explica o item 2 (coruja vira pro outro lado)", d["explain2_text"])
        st.session_state.comparison_script = d

        st.header("3. Gerar vídeo")
        if st.button("🎥 Renderizar vídeo final"):
            progress = st.progress(0.0, text="Iniciando...")

            progress.progress(0.1, text=f"Buscando imagem: {d['item1_title']}")
            img1_path = "output/images/item1.jpg"
            ok1 = fetch_image_for_item(d["item1_image_query"], img1_path)

            progress.progress(0.2, text=f"Buscando imagem: {d['item2_title']}")
            img2_path = "output/images/item2.jpg"
            ok2 = fetch_image_for_item(d["item2_image_query"], img2_path)

            if not owl_path:
                progress.progress(0.3, text="Buscando imagem do apresentador (coruja)...")
                owl_path = "output/images/owl.jpg"
                fetch_image_for_item(
                    "cute cartoon owl professor top hat monocle white background", owl_path
                )

            if not (ok1 and ok2):
                st.error("Não consegui achar imagem pra um dos dois itens. Ajuste os termos de busca e tente de novo.")
            else:
                labels = ["intro1", "intro2", "explain1", "explain2"]
                texts = [d["intro1_text"], d["intro2_text"], d["explain1_text"], d["explain2_text"]]
                audio_paths = {}
                for i, (label, text) in enumerate(zip(labels, texts)):
                    progress.progress(0.35 + i * 0.12, text=f"Gerando voz: {label}")
                    path = f"output/audio/{label}.wav"
                    synthesize(text, path, language_id=language, voice=selected_voice)
                    audio_paths[f"{label}_audio"] = path

                video_data = {
                    "item1_title": d["item1_title"],
                    "item1_image_path": img1_path,
                    "item2_title": d["item2_title"],
                    "item2_image_path": img2_path,
                    "intro1_text": d["intro1_text"],
                    "intro2_text": d["intro2_text"],
                    "explain1_text": d["explain1_text"],
                    "explain2_text": d["explain2_text"],
                    **audio_paths,
                }

                progress.progress(0.9, text="Montando vídeo final...")
                out_path = "output/video_final.mp4"
                build_comparison_video(video_data, owl_path, out_path)
                progress.progress(1.0, text="Pronto!")

                st.success("Vídeo gerado com sucesso!")
                st.video(out_path)
                with open(out_path, "rb") as f:
                    st.download_button("⬇️ Baixar vídeo", f, file_name="video_final.mp4")
