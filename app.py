import os
import streamlit as st
import pandas as pd

from modules.content import generate_script, estimate_item_count, is_ollama_available
from modules.images import fetch_image_for_item
from modules.tts_engine import synthesize, LANGUAGES
from modules.video_builder import build_video

st.set_page_config(page_title="Gerador de Vídeos Educativos", page_icon="🎬", layout="centered")
st.title("🎬 Gerador automático de vídeos (estilo TikTok)")

os.makedirs("output", exist_ok=True)
os.makedirs("output/images", exist_ok=True)
os.makedirs("output/audio", exist_ok=True)

# ---------- 1. Configuração ----------
st.header("1. Tema do vídeo")
topic = st.text_input("Sobre o que é o vídeo?", "Monstros clássicos de filmes de terror")

duration_seconds = st.slider("Duração aproximada do vídeo (segundos)", 10, 120, 30, step=5)
n_items = estimate_item_count(duration_seconds)
st.caption(
    f"Isso deve gerar em torno de **{n_items} itens/cards**. "
    "A duração final pode variar um pouco — ela depende do tamanho real do texto "
    "de cada narração, só é conhecida com exatidão depois de gerar o áudio."
)

language_label = st.selectbox("Idioma falado da narração", list(LANGUAGES.keys()))
language = LANGUAGES[language_label]

st.subheader("IA para escrever o roteiro (gratuita)")
ollama_ok = is_ollama_available()
if ollama_ok:
    st.success("✅ Ollama detectado rodando localmente — roteiro será gerado por IA, de graça.")
else:
    st.warning(
        "⚠️ Ollama não encontrado em localhost:11434. Instale grátis em "
        "[ollama.com](https://ollama.com) e rode `ollama pull llama3.1` para "
        "ativar a geração automática por IA. Por enquanto, o roteiro sairá "
        "como um placeholder simples pra você editar na mão."
    )
ollama_model = st.text_input(
    "Modelo do Ollama a usar", "llama3.1",
    help="Qualquer modelo que você já tenha baixado com `ollama pull <modelo>`. "
         "Ex: llama3.1, mistral, qwen2.5, gemma2.",
)

st.header("2. Voz de narração")
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

# ---------- 2. Gerar roteiro ----------
if "script" not in st.session_state:
    st.session_state.script = None

if st.button("📝 Gerar roteiro"):
    with st.spinner("Gerando roteiro..."):
        st.session_state.script = generate_script(
            topic, n_items, language,
            use_ollama=ollama_ok, ollama_model=ollama_model,
        )

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

        import wave
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
