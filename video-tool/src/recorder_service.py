"""Scherm- en webcam-opname via FFmpeg, plus samenvoegen met Notifica-frame."""

import json
import subprocess
import time
from pathlib import Path

from .config import get_hw_encoder


class RecorderService:
    """Neemt scherm en webcam op als aparte streams, voegt ze samen."""

    def __init__(self, ffmpeg_path: str, temp_dir: Path, assets_dir: Path):
        self.ffmpeg = ffmpeg_path
        self.temp_dir = Path(temp_dir)
        self.assets_dir = Path(assets_dir)

        # Bestanden
        self.screen_output = self.temp_dir / "screen_raw.mkv"
        self.webcam_output = self.temp_dir / "webcam_raw.mkv"
        self.composite_output = self.temp_dir / "composite.mp4"
        self.status_file = self.temp_dir / "recording_status.json"

    # ------------------------------------------------------------------
    # Device en window detectie
    # ------------------------------------------------------------------

    def list_devices(self) -> dict:
        """Lijst beschikbare video- en audioapparaten (Windows DirectShow)."""
        cmd = [self.ffmpeg, "-list_devices", "true", "-f", "dshow", "-i", "dummy"]
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        output = result.stderr

        video_devices = []
        audio_devices = []

        for line in output.split("\n"):
            if "Alternative name" in line:
                continue
            if '"' not in line:
                continue

            parts = line.split('"')
            if len(parts) < 2:
                continue
            name = parts[1]

            # Type staat tussen haakjes aan het eind: (video), (audio), (none)
            if "(video)" in line:
                video_devices.append(name)
            elif "(audio)" in line:
                audio_devices.append(name)
            # (none) wordt genegeerd (bv. OBS Virtual Camera)

        return {"video": video_devices, "audio": audio_devices}

    def list_windows(self) -> list[str]:
        """Lijst zichtbare vensters met titels (voor window capture)."""
        import ctypes
        import ctypes.wintypes

        windows = []

        def callback(hwnd, _):
            if ctypes.windll.user32.IsWindowVisible(hwnd):
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                    title = buf.value
                    # Filter nutteloze entries
                    skip = ["Program Manager", "Settings", "Microsoft Text Input"]
                    if title and not any(s in title for s in skip):
                        windows.append(title)
            return True

        enum_func = ctypes.WINFUNCTYPE(
            ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
        )
        ctypes.windll.user32.EnumWindows(enum_func(callback), 0)
        return sorted(set(windows))

    # ------------------------------------------------------------------
    # Opname starten / stoppen
    # ------------------------------------------------------------------

    def start_recording(
        self, video_device: str, audio_device: str, window_title: str = ""
    ):
        """Start scherm- en webcam-opname als achtergrondprocessen.

        Neemt op in MKV-formaat (overleeft abrupte stop).
        """
        # Opruimen (negeer vergrendelde bestanden, worden overschreven met -y)
        for f in [self.screen_output, self.webcam_output, self.composite_output]:
            try:
                f.unlink(missing_ok=True)
            except PermissionError:
                pass

        # Schermbron: specifiek venster of heel bureaublad
        if window_title:
            screen_input = f"title={window_title}"
        else:
            screen_input = "desktop"

        # Gebruik hardware-encoder als beschikbaar
        encoder = get_hw_encoder()
        enc_opts = ["-c:v", encoder]
        if encoder == "libx264":
            enc_opts.extend(["-preset", "ultrafast"])

        screen_cmd = [
            self.ffmpeg,
            "-f", "gdigrab",
            "-framerate", "30",
            "-i", screen_input,
            *enc_opts,
            "-y",
            str(self.screen_output),
        ]

        # Webcam + microfoon
        dshow_input = f"video={video_device}"
        if audio_device:
            dshow_input += f":audio={audio_device}"

        webcam_cmd = [
            self.ffmpeg,
            "-f", "dshow",
            "-i", dshow_input,
            *enc_opts,
        ]
        if audio_device:
            webcam_cmd.extend(["-c:a", "aac"])
        webcam_cmd.extend(["-y", str(self.webcam_output)])

        # Start processen
        screen_proc = subprocess.Popen(
            screen_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        webcam_proc = subprocess.Popen(
            webcam_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        # Sla PIDs op
        self._write_status(
            recording=True,
            done=False,
            screen_pid=screen_proc.pid,
            webcam_pid=webcam_proc.pid,
            start_time=time.time(),
        )

    def stop_recording(self):
        """Stop de opname door processen te beeindigen."""
        status = self._read_status()
        if not status.get("recording"):
            return

        start_time = status.get("start_time", time.time())

        # Stop processen via taskkill (betrouwbaar op Windows)
        for key in ["screen_pid", "webcam_pid"]:
            pid = status.get(key)
            if pid:
                try:
                    subprocess.run(
                        ["taskkill", "/PID", str(pid), "/T", "/F"],
                        capture_output=True,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                except Exception:
                    pass

        # Wacht even zodat bestanden worden afgesloten
        time.sleep(1.5)

        duration = time.time() - start_time

        # Controleer of bestanden bestaan en niet leeg/beschadigd zijn
        error = ""
        has_files = True
        min_size = 1024  # minimaal 1KB voor een geldig bestand

        if not self.screen_output.exists():
            error = "Schermopname niet gevonden"
            has_files = False
        elif self.screen_output.stat().st_size < min_size:
            error = "Schermopname is leeg of beschadigd"
            has_files = False

        if not self.webcam_output.exists():
            error = "Webcam-opname niet gevonden — controleer of de webcam beschikbaar is"
            has_files = False
        elif self.webcam_output.stat().st_size < min_size:
            error = "Webcam-opname is leeg of beschadigd — mogelijk was de webcam bezet"
            has_files = False

        self._write_status(
            recording=False,
            done=has_files,
            duration=duration,
            error=error,
        )

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def is_recording(self) -> bool:
        return self._read_status().get("recording", False)

    def is_done(self) -> bool:
        return self._read_status().get("done", False)

    def get_elapsed(self) -> float:
        status = self._read_status()
        start = status.get("start_time", 0)
        if start and status.get("recording"):
            return time.time() - start
        return status.get("duration", 0)

    def get_error(self) -> str:
        return self._read_status().get("error", "")

    # ------------------------------------------------------------------
    # Samenvoegen (compositing)
    # ------------------------------------------------------------------

    def composite(
        self, webcam_size: int = 300, padding: int = 30, logo_size: int = 120,
        max_width: int = 1920,
    ) -> Path:
        """Voeg scherm + webcam samen met circulair frame en watermerk.

        Plaatst webcam in de Notifica-oranje ring linksonder over het scherm.
        Plaatst Notifica watermerk rechtsbovenin.
        Audio komt van de webcam-opname (microfoon).

        Performance-optimalisaties:
        - Scherm wordt geschaald naar max_width (standaard 1920px) → minder pixels
        - Webcam + masker + frame worden gecombineerd op klein canvas (300x300)
          voordat ze op het scherm worden gelegd → 2 overlays i.p.v. 3
        - Multithreading ingeschakeld
        """
        mask_path = self.assets_dir / "webcam-mask.png"
        frame_path = self.assets_dir / "webcam-frame.png"
        logo_path = self.assets_dir / "watermark-logo.png"
        has_logo = logo_path.exists()

        # De mask/frame PNGs zijn 400x400. Schaal naar gewenste grootte.
        # Binnendiameter van de cirkel is 344/400 van de totale grootte.
        inner = int(webcam_size * 344 / 400)
        pad_offset = (webcam_size - inner) // 2

        # OPTIMALISATIE 1: Schaal scherm naar max 1920 breed.
        # 2880x1800 → 1920x1200 = 55% minder pixels bij elke overlay.
        # -2 zorgt dat hoogte even is (vereist door encoders).
        #
        # OPTIMALISATIE 2: Combineer webcam + masker + frame op klein
        # canvas (300x300) VOORDAT het over het scherm wordt gelegd.
        # Reduceert dure full-resolution overlays van 3 naar 2.
        filter_complex = (
            # Schaal scherm naar werkbare resolutie
            f"[0:v]scale={max_width}:-2[screen];"
            # Schaal webcam: behoud aspect ratio, crop naar vierkant
            f"[1:v]scale=-1:{inner},crop={inner}:{inner},setsar=1,"
            f"pad={webcam_size}:{webcam_size}:{pad_offset}:{pad_offset}:"
            f"color=black@0.0,format=rgba[wc];"
            # Masker als grayscale
            f"[2:v]scale={webcam_size}:{webcam_size},format=gray[mask];"
            # Combineer webcam + masker
            f"[wc][mask]alphamerge[wc_masked];"
            # Leg oranje ring over webcam (GOEDKOOP: 300x300 op 300x300)
            f"[3:v]scale={webcam_size}:{webcam_size},format=rgba[frame];"
            f"[wc_masked][frame]overlay=0:0[wc_final];"
            # Leg gecombineerde webcam+frame in één keer over scherm
            f"[screen][wc_final]overlay={padding}:main_h-{webcam_size + padding}"
        )

        if has_logo:
            filter_complex += (
                f"[with_wc];"
                # Watermerk rechtsbovenin
                f"[4:v]scale={logo_size}:-1,format=rgba[logo];"
                f"[with_wc][logo]overlay=main_w-overlay_w-{padding}:{padding}[out]"
            )
        else:
            filter_complex += "[out]"

        cmd = [
            self.ffmpeg,
            # OPTIMALISATIE 3: Gebruik alle CPU-cores voor filterverwerking
            "-threads", "0",
            "-i", str(self.screen_output),
            "-i", str(self.webcam_output),
            "-i", str(mask_path),
            "-i", str(frame_path),
        ]
        if has_logo:
            cmd.extend(["-i", str(logo_path)])

        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-map", "1:a?",
        ])

        # Encoder kiezen: hardware indien beschikbaar
        encoder = get_hw_encoder()
        if encoder == "libx264":
            cmd.extend(["-c:v", "libx264", "-preset", "ultrafast"])
        else:
            # QSV/NVENC: snelste preset voor compositing
            cmd.extend(["-c:v", encoder, "-preset", "veryfast"])

        cmd.extend([
            "-c:a", "aac",
            "-shortest",
            "-y",
            str(self.composite_output),
        ])

        result = subprocess.run(
            cmd, capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Samenvoegen mislukt:\n{result.stderr[-800:]}"
            )

        return self.composite_output

    # ------------------------------------------------------------------
    # Hulpfuncties
    # ------------------------------------------------------------------

    def reset(self):
        """Verwijder alle opname-bestanden en status."""
        # Stop eventuele lopende opnames
        if self.is_recording():
            self.stop_recording()
        for f in [
            self.screen_output,
            self.webcam_output,
            self.composite_output,
            self.status_file,
        ]:
            try:
                f.unlink(missing_ok=True)
            except PermissionError:
                pass  # Vergrendeld door videospeler, wordt overschreven

    def _read_status(self) -> dict:
        if not self.status_file.exists():
            return {}
        try:
            return json.loads(self.status_file.read_text())
        except Exception:
            return {}

    def _write_status(self, **kwargs):
        status = self._read_status()
        status.update(kwargs)
        self.status_file.write_text(json.dumps(status))
