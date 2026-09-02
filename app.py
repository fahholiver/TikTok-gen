import os
import streamlit as st
import pandas as pd

from modules.content import generate_script
from modules.images import fetch_image_for_item
from modules.tts_engine import synthesize
from modules.video_builder import build_video

st.set_page_config(page_title="Gerador de Vídeos Educativos", page_icon="🎬", layout="centered")
st.title("🎬 Gerador automático de vídeos (estilo TikTok)")

os.makedirs("output", exist_ok=True)
os.makedirs("output/images", exist_ok=True)
os.makedirs("output/audio", exist_ok=True)

# ---------- 1. Configuração ----------
st.header("1. Tema do vídeo")
topic = st.text_input("Sobre o que é o vídeo?", "Monstros clássicos de filmes de terror")
n_items = st.slider("Quantos itens/cards no vídeo?", 2, 10, 4)

anthropic_key = st.text_input(
    "Chave da API Anthropic (opcional, deixe em branco para gerar texto manualmente)",
    type="password",
)

st.header("2. Voz de narração")
voice_file = st.file_uploader(
    "Envie um áudio de referência (5-10s, .wav/.mp3) para clonar a voz. "
    "Deixe vazio para usar a voz padrão do modelo.",
    type=["wav", "mp3"],
)
reference_voice_path = None
if voice_file:
    reference_voice_path = os.path.join("assets/voice_samples", voice_file.name)
    with open(reference_voice_path, "wb") as f:
        f.write(voice_file.read())
    st.audio(reference_voice_path)

exaggeration = st.slider("Expressividade da voz", 0.0, 1.0, 0.5)

# ---------- 2. Gerar roteiro ----------
if "script" not in st.session_state:
    st.session_state.script = None

if st.button("📝 Gerar roteiro"):
    with st.spinner("Gerando roteiro..."):
        st.session_state.script = generate_script(topic, n_items, anthropic_key or None)

if st.session_state.script:
    st.header("3. Revise e edite o roteiro")
    df = pd.DataFrame(st.session_state.script)
    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
    st.session_state.script = edited_df.to_dict(orient="records")

    # ---------- 3. Renderizar ----------
    st.header("4. Gerar vídeo")
    if st.button("🎥 Renderizar vídeo final"):
        items = []
        progress = st.progress(0.0, text="Iniciando...")
        total = len(st.session_state.script)

        for i, row in enumerate(st.session_state.script):
            title = str(row["title"])
            narration = str(row["narration"])
            image_query = str(row.get("image_query", title))

            # 1. buscar imagem
            progress.progress(i / total, text=f"Buscando imagem: {title}")
            img_path = f"output/images/{i}.jpg"
            ok = fetch_image_for_item(image_query, img_path)
            if not ok:
                st.warning(f"Não achei imagem para '{title}', pulei esse item.")
                continue

            # 2. gerar áudio
            progress.progress(i / total, text=f"Gerando voz: {title}")
            audio_path = f"output/audio/{i}.wav"
            synthesize(narration, audio_path, reference_voice_path, exaggeration=exaggeration)

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

        st.success("Vídeo gerado com sucesso!")
        st.video(out_path)
        with open(out_path, "rb") as f:
            st.download_button("⬇️ Baixar vídeo", f, file_name="video_final.mp4")
