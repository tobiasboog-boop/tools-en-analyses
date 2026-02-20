"""Notifica Video Tool - Opnemen, bewerken en uploaden naar Vimeo."""

import logging
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

# Onderdruk Streamlit-foutmelding bij stale media-bestanden na herstart
logging.getLogger("streamlit.web.server.media_file_handler").setLevel(logging.CRITICAL)

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
from PIL import Image

from src.config import (
    ASSETS_DIR,
    OUTPUT_DIR,
    TEMP_DIR,
    get_ffmpeg_path,
    get_ffprobe_path,
    get_hw_encoder,
    get_intro_path,
    get_obs_folder,
    get_outro_path,
    get_vimeo_token,
)
from src.ffmpeg_service import FFmpegService
from src.recorder_service import RecorderService
from src.vimeo_service import PRIVACY_OPTIONS, VimeoService
from src.video_utils import (
    cleanup_temp_files,
    estimate_trimmed_size,
    format_duration,
    format_filesize,
    get_mp4_files,
)

# ---------------------------------------------------------------------------
# Pagina-config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Notifica Video Tool", page_icon=":clapper:", layout="wide")

# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------
TEMP_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ffmpeg = FFmpegService(ffmpeg_path=get_ffmpeg_path(), ffprobe_path=get_ffprobe_path())
recorder = RecorderService(
    ffmpeg_path=get_ffmpeg_path(), temp_dir=TEMP_DIR, assets_dir=ASSETS_DIR
)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
DEFAULTS = {
    "step": 1,
    "source": None,           # "record" of "file"
    "selected_video": None,   # Path naar video (composite of bestaand bestand)
    "video_info": None,
    "trim_start": 0.0,
    "trim_end": 0.0,
    "output_path": None,
    "thumbnails": [],
    "vimeo_title": "",
    "vimeo_description": "",
    "vimeo_privacy": "Alleen via privelink",
    "vimeo_password": "",
    "upload_result": None,
    "local_copy": None,
    "obs_folder": str(get_obs_folder()),
    "vimeo_folder": "",          # URI van geselecteerde Vimeo-map
}
for key, val in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val


def get_vimeo_service() -> VimeoService | None:
    token = get_vimeo_token()
    return VimeoService(token) if token else None


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    logo_path = ASSETS_DIR / "notifica-logo-kleur.svg"
    if logo_path.exists():
        st.image(str(logo_path), width=160)
    st.markdown("---")

    steps = ["Opnemen", "Bewerken", "Upload", "Klaar"]
    for i, label in enumerate(steps, 1):
        if i < st.session_state.step:
            st.markdown(f"~~Stap {i}~~ :white_check_mark: {label}")
        elif i == st.session_state.step:
            st.markdown(f"**Stap {i} :arrow_right: {label}**")
        else:
            st.markdown(f"Stap {i} :black_small_square: {label}")

    st.markdown("---")

    ffmpeg_ok = ffmpeg.check_installed()
    st.markdown(
        f"FFmpeg: {'Geinstalleerd :white_check_mark:' if ffmpeg_ok else ':x: Niet gevonden'}"
    )
    if ffmpeg_ok:
        encoder = get_hw_encoder()
        if encoder != "libx264":
            hw_label = {"h264_nvenc": "NVIDIA", "h264_qsv": "Intel QSV", "h264_amf": "AMD"}
            st.markdown(f"GPU: {hw_label.get(encoder, encoder)} :white_check_mark:")
        else:
            st.markdown("GPU: Niet beschikbaar (software)")

    vimeo_svc = get_vimeo_service()
    if vimeo_svc:
        account = vimeo_svc.check_connection()
        if account:
            st.markdown(f"Vimeo: {account['name']} :white_check_mark:")
        else:
            st.markdown("Vimeo: Token ongeldig :x:")
            vimeo_svc = None
    else:
        st.markdown("Vimeo: Geen token :x:")

    if recorder.is_recording():
        st.markdown("---")
        st.markdown(":red_circle: **Opname loopt...**")
        if st.button("Noodstop opname", type="secondary"):
            recorder.stop_recording()
            st.rerun()

    st.markdown("---")
    if st.button("Opnieuw beginnen", use_container_width=True):
        cleanup_temp_files(TEMP_DIR)
        recorder.reset()
        for key, val in DEFAULTS.items():
            st.session_state[key] = val
        st.rerun()


if not ffmpeg_ok:
    st.error("FFmpeg niet gevonden. Voer `install.bat` uit of herstart de app.")
    st.stop()


# ===================================================================
# STAP 1: OPNEMEN
# ===================================================================
if st.session_state.step == 1:
    st.title(":clapper: Notifica Video Tool")

    tab_record, tab_file = st.tabs(["Nieuwe opname", "Bestaande video"])

    # ----- Tab: Nieuwe opname -----
    with tab_record:

        if not recorder.is_recording() and not recorder.is_done():
            st.subheader("Opname instellen")

            devices = recorder.list_devices()
            video_devs = devices.get("video", [])
            audio_devs = devices.get("audio", [])

            if not video_devs:
                st.warning("Geen webcam gevonden. Sluit een webcam aan.")
                st.stop()

            col1, col2 = st.columns(2)
            with col1:
                cam = st.selectbox("Webcam", video_devs)
            with col2:
                mic = st.selectbox("Microfoon", ["(geen)"] + audio_devs)
                mic_selected = mic if mic != "(geen)" else ""

            st.markdown("---")
            st.subheader("Wat wil je opnemen?")

            capture_mode = st.radio(
                "Opnamebron",
                ["Heel scherm (bureaublad)", "Specifiek venster"],
                horizontal=True,
                label_visibility="collapsed",
            )

            window_title = ""
            if capture_mode == "Specifiek venster":
                windows = recorder.list_windows()
                if windows:
                    window_title = st.selectbox(
                        "Kies het venster",
                        windows,
                        help="Open eerst je Power BI dashboard, dan verschijnt het hier.",
                    )
                else:
                    st.info("Geen vensters gevonden.")

            st.markdown("---")
            st.info(
                "**Tip:** Open je dashboard voordat je op Start drukt. "
                "Minimaliseer dit browservenster tijdens de opname."
            )

            if st.button(
                "🔴 Start opname",
                type="primary",
                use_container_width=True,
            ):
                # 3-seconden countdown zodat je naar het juiste tabblad kunt schakelen
                countdown_box = st.empty()
                for sec in range(3, 0, -1):
                    countdown_box.warning(
                        f"⏳ Opname start over **{sec}** seconde{'n' if sec > 1 else ''}... "
                        f"Schakel nu naar je dashboard!"
                    )
                    time.sleep(1)
                countdown_box.success("🔴 Opname gestart!")

                recorder.start_recording(cam, mic_selected, window_title)
                time.sleep(1)
                st.rerun()

        elif recorder.is_recording():
            st.subheader(":red_circle: Opname bezig...")

            elapsed = recorder.get_elapsed()
            st.metric("Opnameduur", format_duration(elapsed))
            st.warning("Minimaliseer dit venster en presenteer je dashboard.")

            if st.button(
                "⏹ Stop opname",
                type="primary",
                use_container_width=True,
            ):
                with st.spinner("Opname stoppen..."):
                    recorder.stop_recording()
                st.rerun()

            time.sleep(3)
            st.rerun()

        elif recorder.is_done():
            st.subheader(":white_check_mark: Opname voltooid!")

            elapsed = recorder.get_elapsed()
            st.success(f"Opnameduur: **{format_duration(elapsed)}**")

            error = recorder.get_error()
            if error:
                st.error(f"Fout: {error}")
                if st.button("Opnieuw proberen"):
                    recorder.reset()
                    st.rerun()
                st.stop()

            st.info("Scherm en webcam worden samengevoegd met het Notifica-frame...")

            if st.button(
                "Samenvoegen en doorgaan",
                type="primary",
                use_container_width=True,
            ):
                with st.spinner("Samenvoegen... Dit kan even duren."):
                    try:
                        composite_path = recorder.composite(webcam_size=300, padding=30)
                        st.session_state.selected_video = str(composite_path)
                        st.session_state.source = "record"

                        info = ffmpeg.get_video_info(composite_path)
                        st.session_state.video_info = info
                        st.session_state.trim_start = 0.0
                        # Laatste 3 seconden automatisch aftrimmen (terugschakelen naar opnametab)
                        st.session_state.trim_end = max(info["duration"] - 3.0, 0.5)
                        st.session_state.vimeo_title = (
                            f"Notifica Dashboard {datetime.now().strftime('%d-%m-%Y')}"
                        )
                        st.session_state.step = 2
                        st.rerun()
                    except Exception as e:
                        st.error(f"Samenvoegen mislukt: {e}")

    # ----- Tab: Bestaande video -----
    with tab_file:
        st.subheader("MP4 selecteren")

        folder = st.text_input("Map met video's", value=st.session_state.obs_folder)
        folder_path = Path(folder)

        if not folder_path.exists():
            st.warning(f"Map niet gevonden: `{folder_path}`")
        else:
            mp4_files = get_mp4_files(folder_path)
            if not mp4_files:
                st.info(f"Geen MP4-bestanden in `{folder_path}`")
            else:
                selected_name = st.selectbox("Kies een video", [f["name"] for f in mp4_files])
                selected = next(f for f in mp4_files if f["name"] == selected_name)

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Grootte", format_filesize(selected["size"]))
                with col2:
                    st.metric("Datum", selected["modified"].strftime("%d %b %Y, %H:%M"))

                try:
                    info = ffmpeg.get_video_info(selected["path"])
                    with col3:
                        st.metric("Duur", format_duration(info["duration"]))
                except Exception:
                    info = None

                st.video(str(selected["path"]))

                if st.button("Selecteer deze video", type="primary", use_container_width=True):
                    # Reset eventuele stale recorder status van eerdere opname
                    recorder.reset()
                    st.session_state.selected_video = str(selected["path"])
                    st.session_state.source = "file"
                    st.session_state.video_info = info
                    if info:
                        st.session_state.trim_start = 0.0
                        st.session_state.trim_end = info["duration"]
                    st.session_state.vimeo_title = selected["path"].stem.replace("_", " ")
                    st.session_state.thumbnails = []
                    st.session_state.step = 2
                    st.rerun()


# ===================================================================
# STAP 2: BEWERKEN
# ===================================================================
elif st.session_state.step == 2:
    st.title(":scissors: Video bewerken")

    video_path = Path(st.session_state.selected_video)
    info = st.session_state.video_info
    if not video_path.exists():
        st.error("Video niet gevonden.")
        st.session_state.step = 1
        st.rerun()

    duration = info["duration"] if info else 0
    st.caption(
        f"**{video_path.name}** — {format_duration(duration)} — "
        f"{info['width']}x{info['height']}" if info else ""
    )

    # Thumbnails
    if not st.session_state.thumbnails:
        with st.spinner("Thumbnails genereren..."):
            thumb_dir = TEMP_DIR / "thumbs"
            thumb_dir.mkdir(exist_ok=True)
            thumbs = ffmpeg.generate_thumbnails(video_path, thumb_dir, interval=10)
            st.session_state.thumbnails = thumbs

    thumbs = st.session_state.thumbnails
    if thumbs:
        cols_per_row = min(len(thumbs), 8)
        cols = st.columns(cols_per_row)
        for i, thumb in enumerate(thumbs[: cols_per_row * 2]):
            with cols[i % cols_per_row]:
                st.image(str(thumb), caption=format_duration(i * 10), use_container_width=True)

    # Trimmen
    st.subheader("Trimmen")
    col_s, col_e = st.columns(2)
    with col_s:
        trim_start = st.slider(
            "Start (sec)", 0.0, max(duration - 1, 0.1),
            value=st.session_state.trim_start, step=0.5, format="%.1f",
        )
    with col_e:
        trim_end = st.slider(
            "Einde (sec)", trim_start + 0.5, duration,
            value=min(st.session_state.trim_end, duration), step=0.5, format="%.1f",
        )

    st.session_state.trim_start = trim_start
    st.session_state.trim_end = trim_end
    trim_duration = trim_end - trim_start

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Resultaat", format_duration(trim_duration))
    with c2:
        if info:
            st.metric("Geschat", format_filesize(
                estimate_trimmed_size(info["filesize"], duration, trim_duration)
            ))
    with c3:
        st.metric("Verwijderd", format_duration(duration - trim_duration))

    st.video(str(video_path), start_time=int(trim_start))

    # Croppen
    st.subheader("Bijsnijden (crop)")
    use_crop = st.checkbox("Video bijsnijden")

    crop_values = None
    if use_crop and info:
        vid_w, vid_h = info["width"], info["height"]
        st.caption(f"Origineel: {vid_w} x {vid_h} px")

        col_l, col_r = st.columns(2)
        with col_l:
            crop_left = st.slider("Links afsnijden (px)", 0, vid_w // 2, 0, step=10)
            crop_top = st.slider("Boven afsnijden (px)", 0, vid_h // 2, 0, step=10)
        with col_r:
            crop_right = st.slider("Rechts afsnijden (px)", 0, vid_w // 2, 0, step=10)
            crop_bottom = st.slider("Onder afsnijden (px)", 0, vid_h // 2, 0, step=10)

        new_w = vid_w - crop_left - crop_right
        new_h = vid_h - crop_top - crop_bottom

        if crop_left or crop_right or crop_top or crop_bottom:
            crop_values = {
                "top": crop_top, "bottom": crop_bottom,
                "left": crop_left, "right": crop_right,
            }

        # Crop preview op een thumbnail (compact weergegeven)
        if thumbs:
            preview_thumb = thumbs[len(thumbs) // 2]
            preview_img = Image.open(str(preview_thumb))
            pw, ph = preview_img.size
            # Schaal crop-waarden naar thumbnail-afmeting
            sx, sy = pw / vid_w, ph / vid_h
            cl = int(crop_left * sx)
            ct = int(crop_top * sy)
            cr = pw - int(crop_right * sx)
            cb = ph - int(crop_bottom * sy)
            if cr > cl and cb > ct:
                cropped_preview = preview_img.crop((cl, ct, cr, cb))
                # Toon in een kleinere kolom zodat het compacter oogt
                _, col_preview, _ = st.columns([1, 2, 1])
                with col_preview:
                    st.image(
                        cropped_preview,
                        caption=f"Zo ziet de video eruit na bijsnijden ({new_w}x{new_h} px)",
                        use_container_width=True,
                    )
            else:
                st.warning("Crop-waarden te groot — er blijft niets over.")
        else:
            st.info(f"Resultaat: **{new_w} x {new_h} px**")

    accurate = st.checkbox(
        "Frame-nauwkeurig knippen (langzamer)",
        help="Bij crop wordt altijd re-encoded.",
    )

    # Intro/outro
    intro_path = get_intro_path()
    outro_path = get_outro_path()
    use_intro = use_outro = False
    if intro_path or outro_path:
        st.subheader("Intro & Outro")
        if intro_path:
            use_intro = st.checkbox(f"Intro toevoegen ({intro_path.name})")
        if outro_path:
            use_outro = st.checkbox(f"Outro toevoegen ({outro_path.name})")

    col_back, col_go = st.columns(2)
    with col_back:
        if st.button("Terug"):
            # Reset recorder status zodat stale recording_status.json
            # niet de oude opname toont bij terugkeer naar stap 1
            if st.session_state.source == "record":
                recorder.reset()
            st.session_state.step = 1
            st.session_state.thumbnails = []
            st.rerun()

    with col_go:
        # Watermark alleen meegeven bij crop (bij crop wordt sowieso re-encoded,
        # en het watermark uit de composite kan wegvallen door bijsnijden).
        # Zonder crop zit het watermark al in de composite → stream copy is snel.
        watermark_path = ASSETS_DIR / "watermark-logo.png"
        needs_watermark_redo = (
            crop_values is not None
            and st.session_state.source == "record"
            and watermark_path.exists()
        )
        wm = watermark_path if needs_watermark_redo else None

        needs_reencode = accurate or crop_values is not None
        if st.button("Verwerk video", type="primary", use_container_width=True):
            trimmed_path = TEMP_DIR / f"trimmed_{video_path.stem}.mp4"

            with st.spinner("Video verwerken..."):
                if needs_reencode:
                    bar = st.progress(0.0, text="Verwerken...")
                    ffmpeg.trim_video(
                        video_path, trimmed_path, trim_start, trim_end,
                        accurate=True, crop=crop_values, watermark=wm,
                        progress_callback=lambda p: bar.progress(p, f"Verwerken... {int(p*100)}%"),
                    )
                else:
                    ffmpeg.trim_video(video_path, trimmed_path, trim_start, trim_end)

            final_path = trimmed_path
            if use_intro or use_outro:
                parts = []
                if use_intro and intro_path:
                    parts.append(intro_path)
                parts.append(trimmed_path)
                if use_outro and outro_path:
                    parts.append(outro_path)
                if len(parts) > 1:
                    concat_path = TEMP_DIR / f"final_{video_path.stem}.mp4"
                    with st.spinner("Samenvoegen..."):
                        ffmpeg.concatenate_videos(parts, concat_path)
                    final_path = concat_path

            st.session_state.output_path = str(final_path)
            st.session_state.step = 3
            st.rerun()


# ===================================================================
# STAP 3: UPLOAD
# ===================================================================
elif st.session_state.step == 3:
    st.title(":outbox_tray: Upload naar Vimeo")

    output_path = Path(st.session_state.output_path)
    if not output_path.exists():
        st.error("Verwerkt bestand niet gevonden.")
        st.session_state.step = 2
        st.rerun()

    output_size = output_path.stat().st_size
    try:
        out_info = ffmpeg.get_video_info(output_path)
        out_dur = out_info["duration"]
    except Exception:
        out_dur = 0

    st.success(f"Video klaar: **{format_duration(out_dur)}** — **{format_filesize(output_size)}**")
    st.video(str(output_path))

    # Lokale kopie
    st.subheader("Lokale kopie")
    default_name = f"{st.session_state.vimeo_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.mp4"
    save_name = st.text_input("Bestandsnaam", value=default_name)

    if st.button("Bewaar lokale kopie"):
        local_path = OUTPUT_DIR / save_name
        shutil.copy2(str(output_path), str(local_path))
        st.session_state.local_copy = str(local_path)
        st.success(f"Opgeslagen: `{local_path}`")

    if st.session_state.local_copy:
        st.caption(f"Lokale kopie: `{st.session_state.local_copy}`")

    # Vimeo metadata
    st.markdown("---")
    st.subheader("Vimeo gegevens")

    title = st.text_input("Titel", value=st.session_state.vimeo_title)
    st.session_state.vimeo_title = title

    description = st.text_area(
        "Beschrijving", value=st.session_state.vimeo_description,
        placeholder="Optionele beschrijving...",
    )
    st.session_state.vimeo_description = description

    privacy = st.selectbox(
        "Privacy", list(PRIVACY_OPTIONS.keys()),
        index=list(PRIVACY_OPTIONS.keys()).index(st.session_state.vimeo_privacy),
    )
    st.session_state.vimeo_privacy = privacy

    password = ""
    if privacy == "Wachtwoord":
        password = st.text_input("Video wachtwoord", type="password")

    vimeo_svc = get_vimeo_service()
    folder_uri = ""
    if vimeo_svc:
        # Map selectie (team library / persoonlijk)
        folders = vimeo_svc.list_folders()
        if folders:
            folder_options = ["(Geen map — persoonlijk)"] + [f["name"] for f in folders]
            # Zoek huidige selectie terug
            current_idx = 0
            if st.session_state.vimeo_folder:
                for i, f in enumerate(folders):
                    if f["uri"] == st.session_state.vimeo_folder:
                        current_idx = i + 1
                        break
            selected_folder = st.selectbox("Vimeo-map", folder_options, index=current_idx)
            if selected_folder != "(Geen map — persoonlijk)":
                folder_match = next(f for f in folders if f["name"] == selected_folder)
                folder_uri = folder_match["uri"]
            st.session_state.vimeo_folder = folder_uri

        quota = vimeo_svc.get_upload_quota()
        if quota:
            st.caption(f"Upload quota: {format_filesize(quota['free_space'])} beschikbaar")
    else:
        st.warning("Geen Vimeo-token geconfigureerd.")

    col_back, col_upload = st.columns(2)
    with col_back:
        if st.button("Terug"):
            st.session_state.step = 2
            st.rerun()

    with col_upload:
        can_upload = vimeo_svc is not None and title.strip()
        if st.button(
            "Upload naar Vimeo", type="primary",
            use_container_width=True, disabled=not can_upload,
        ):
            # Auto-save lokale kopie
            if not st.session_state.local_copy:
                local_path = OUTPUT_DIR / save_name
                shutil.copy2(str(output_path), str(local_path))
                st.session_state.local_copy = str(local_path)

            with st.spinner("Uploaden naar Vimeo... Dit kan enkele minuten duren."):
                try:
                    result = vimeo_svc.upload_video(
                        file_path=str(output_path), title=title,
                        description=description, privacy=PRIVACY_OPTIONS[privacy],
                        password=password, folder_uri=folder_uri,
                    )
                    st.session_state.upload_result = result
                    st.session_state.step = 4
                    st.rerun()
                except Exception as e:
                    st.error(f"Upload mislukt: {e}")


# ===================================================================
# STAP 4: KLAAR
# ===================================================================
elif st.session_state.step == 4:
    st.title(":white_check_mark: Klaar!")
    st.balloons()

    result = st.session_state.upload_result
    if not result:
        st.session_state.step = 1
        st.rerun()

    st.success(f"**{result.get('name', 'Video')}** staat op Vimeo!")

    link = result.get("link", "")
    if link:
        st.markdown(f"### :link: [{link}]({link})")
        st.code(link, language=None)

    status = result.get("transcode_status", "unknown")
    if status == "in_progress":
        st.info("Vimeo verwerkt de video. De link werkt zodra dat klaar is.")
        vimeo_svc = get_vimeo_service()
        if vimeo_svc and st.button("Status verversen"):
            new_status = vimeo_svc.get_transcode_status(result["uri"])
            st.info(f"Status: {'Klaar!' if new_status == 'complete' else new_status}")
    elif status == "complete":
        st.info("Video is klaar voor afspelen.")

    if st.session_state.local_copy:
        st.caption(f"Lokale kopie: `{st.session_state.local_copy}`")

    st.markdown("---")
    if st.button("Nieuwe video maken", type="primary", use_container_width=True):
        cleanup_temp_files(TEMP_DIR)
        recorder.reset()
        for key, val in DEFAULTS.items():
            st.session_state[key] = val
        st.rerun()
