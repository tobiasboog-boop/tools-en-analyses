"""FFmpeg operaties: video-info, thumbnails, trim en concatenatie."""

import json
import re
import subprocess
import tempfile
from pathlib import Path

from .config import get_hw_encoder
from .video_utils import seconds_to_timestamp


class FFmpegService:
    """Alle videoverwerkingsoperaties via FFmpeg subprocess."""

    def __init__(self, ffmpeg_path: str = "ffmpeg", ffprobe_path: str = "ffprobe"):
        self.ffmpeg = ffmpeg_path
        self.ffprobe = ffprobe_path

    def check_installed(self) -> bool:
        """Controleer of FFmpeg beschikbaar is op het systeem."""
        try:
            result = subprocess.run(
                [self.ffmpeg, "-version"],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def get_video_info(self, video_path: Path) -> dict:
        """Haal video-metadata op via ffprobe.

        Returns dict met: duration, width, height, fps, codec_video, codec_audio, filesize
        """
        cmd = [
            self.ffprobe,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(video_path),
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe fout: {result.stderr}")

        data = json.loads(result.stdout)
        info = {
            "duration": 0.0,
            "width": 0,
            "height": 0,
            "fps": 0.0,
            "codec_video": "",
            "codec_audio": "",
            "filesize": video_path.stat().st_size,
        }

        # Duur uit format
        if "format" in data:
            info["duration"] = float(data["format"].get("duration", 0))

        # Stream-info
        for stream in data.get("streams", []):
            if stream["codec_type"] == "video" and not info["codec_video"]:
                info["width"] = stream.get("width", 0)
                info["height"] = stream.get("height", 0)
                info["codec_video"] = stream.get("codec_name", "")
                # FPS uit r_frame_rate (bv. "30/1")
                fps_str = stream.get("r_frame_rate", "0/1")
                if "/" in fps_str:
                    num, den = fps_str.split("/")
                    info["fps"] = float(num) / float(den) if float(den) > 0 else 0
            elif stream["codec_type"] == "audio" and not info["codec_audio"]:
                info["codec_audio"] = stream.get("codec_name", "")

        return info

    def generate_thumbnails(
        self,
        video_path: Path,
        output_dir: Path,
        interval: int = 10,
        width: int = 320,
    ) -> list[Path]:
        """Genereer thumbnail-afbeeldingen op vaste intervallen.

        Returns lijst van thumbnail-paden.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        # Verwijder oude thumbnails zodat er geen stale bestanden overblijven
        # van een vorige video (die meer frames kon hebben)
        for old in output_dir.glob("thumb_*.jpg"):
            old.unlink(missing_ok=True)
        pattern = str(output_dir / "thumb_%04d.jpg")

        cmd = [
            self.ffmpeg,
            "-i", str(video_path),
            "-vf", f"fps=1/{interval},scale={width}:-1",
            "-q:v", "3",
            "-y",
            pattern,
        ]
        subprocess.run(
            cmd, capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        # Verzamel gegenereerde thumbnails
        thumbs = sorted(output_dir.glob("thumb_*.jpg"))
        return thumbs

    def generate_single_thumbnail(
        self, video_path: Path, timestamp: float, output_path: Path, width: int = 640
    ) -> Path:
        """Genereer een enkele thumbnail op een specifiek tijdstip."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        ts = seconds_to_timestamp(timestamp)

        cmd = [
            self.ffmpeg,
            "-ss", ts,
            "-i", str(video_path),
            "-frames:v", "1",
            "-vf", f"scale={width}:-1",
            "-y",
            str(output_path),
        ]
        subprocess.run(
            cmd, capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return output_path

    def trim_video(
        self,
        input_path: Path,
        output_path: Path,
        start: float,
        end: float,
        accurate: bool = False,
        crop: dict | None = None,
        watermark: Path | None = None,
        watermark_size: int = 120,
        watermark_padding: int = 30,
        progress_callback=None,
    ) -> Path:
        """Trim video tussen start- en eindtijd, optioneel met crop en watermark.

        accurate=False: stream copy (instant, keyframe-nauwkeurig)
        accurate=True: re-encode (langzamer, frame-nauwkeurig)
        crop: dict met {top, bottom, left, right} in pixels, of None
        watermark: pad naar watermark PNG (overlay rechtsbovenin), of None

        Als crop of watermark is opgegeven, wordt altijd re-encoded.
        progress_callback: callable(progress: float) met 0.0-1.0
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        duration = end - start
        needs_reencode = accurate or (crop is not None) or (watermark is not None)

        # Bouw crop filter string
        crop_filter = ""
        if crop:
            top = crop.get("top", 0)
            bottom = crop.get("bottom", 0)
            left = crop.get("left", 0)
            right = crop.get("right", 0)
            if top or bottom or left or right:
                crop_filter = (
                    f"crop=in_w-{left}-{right}:in_h-{top}-{bottom}:{left}:{top}"
                )

        if needs_reencode:
            # -ss VOOR -i = snelle input-seeking (decodeert niet alles vanaf begin)
            cmd = [
                self.ffmpeg,
                "-ss", seconds_to_timestamp(start),
                "-i", str(input_path),
            ]

            # Voeg watermark als tweede input toe
            if watermark:
                cmd.extend(["-i", str(watermark)])

            cmd.extend(["-t", seconds_to_timestamp(duration)])

            # Bouw video filter
            if watermark and crop_filter:
                # Crop eerst, dan watermark overlay
                filter_complex = (
                    f"[0:v]{crop_filter}[cropped];"
                    f"[1:v]scale={watermark_size}:-1,format=rgba[logo];"
                    f"[cropped][logo]overlay=main_w-overlay_w-{watermark_padding}:{watermark_padding}"
                )
                cmd.extend(["-filter_complex", filter_complex])
            elif watermark:
                # Alleen watermark overlay (geen crop)
                filter_complex = (
                    f"[1:v]scale={watermark_size}:-1,format=rgba[logo];"
                    f"[0:v][logo]overlay=main_w-overlay_w-{watermark_padding}:{watermark_padding}"
                )
                cmd.extend(["-filter_complex", filter_complex])
            elif crop_filter:
                # Alleen crop (geen watermark)
                cmd.extend(["-vf", crop_filter])

            # Encoder kiezen: hardware indien beschikbaar
            encoder = get_hw_encoder()
            if encoder == "libx264":
                cmd.extend(["-c:v", "libx264", "-preset", "fast"])
            else:
                cmd.extend(["-c:v", encoder])

            cmd.extend([
                "-c:a", "aac",
                "-progress", "pipe:1",
                "-y",
                str(output_path),
            ])
        else:
            # Stream copy (snel, geen re-encoding)
            cmd = [
                self.ffmpeg,
                "-ss", seconds_to_timestamp(start),
                "-t", seconds_to_timestamp(duration),
                "-i", str(input_path),
                "-c", "copy",
                "-avoid_negative_ts", "make_zero",
                "-y",
                str(output_path),
            ]

        if progress_callback and needs_reencode:
            self._run_with_progress(cmd, duration, progress_callback)
        else:
            subprocess.run(
                cmd, capture_output=True, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )

        return output_path

    def concatenate_videos(
        self,
        file_list: list[Path],
        output_path: Path,
        progress_callback=None,
    ) -> Path:
        """Voeg meerdere video's samen (intro + main + outro).

        Gebruikt de FFmpeg concat demuxer. Bestanden moeten compatibele
        codecs/resolutie hebben voor stream copy.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Maak tijdelijk concat-bestand
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, dir=output_path.parent
        ) as f:
            for path in file_list:
                # Escape enkele aanhalingstekens in pad
                escaped = str(path).replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")
            concat_file = f.name

        try:
            cmd = [
                self.ffmpeg,
                "-f", "concat",
                "-safe", "0",
                "-i", concat_file,
                "-c", "copy",
                "-y",
                str(output_path),
            ]
            subprocess.run(
                cmd, capture_output=True, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        finally:
            Path(concat_file).unlink(missing_ok=True)

        return output_path

    def _run_with_progress(self, cmd: list, total_duration: float, callback):
        """Voer FFmpeg uit en parse voortgang uit stdout (progress pipe).

        BELANGRIJK: stderr gaat naar DEVNULL. Als stderr naar PIPE gaat
        maar niet gelezen wordt, vult de buffer (4-64KB op Windows) zich
        en BLOKKEERT FFmpeg op elke write → extreem trage verwerking.
        """
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        time_pattern = re.compile(r"out_time_us=(\d+)")

        for line in process.stdout:
            match = time_pattern.search(line)
            if match and total_duration > 0:
                current_us = int(match.group(1))
                current_s = current_us / 1_000_000
                progress = min(current_s / total_duration, 1.0)
                callback(progress)

        process.wait()
