from typing import Optional
import subprocess
import re
from pathlib import Path


def get_youtube_metadata(url: str) -> dict:
    """Fetch video title and uploader via yt-dlp."""
    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--skip-download",
                "--print", "%(title)s",
                "--print", "%(uploader)s",
                url,
            ],
            capture_output=True, text=True, timeout=30,
        )
        lines = result.stdout.strip().split("\n")
        title = lines[0] if len(lines) > 0 else "Unbekannt"
        uploader = lines[1] if len(lines) > 1 else "Unbekannt"
        return {"title": title, "uploader": uploader}
    except Exception:
        return {"title": "Unbekannt", "uploader": "Unbekannt"}


def parse_youtube(url: str, language: str = "de") -> Optional[str]:
    """Extract subtitles from a YouTube video. Returns None if no subtitles available."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        langs = [language, "en"] if language != "en" else ["en", "de"]

        for lang in langs:
            # Clean up any files from previous language attempt
            for old_file in Path(tmpdir).glob("*.*"):
                old_file.unlink()

            sub_path = Path(tmpdir) / "sub"
            subprocess.run(
                [
                    "yt-dlp",
                    "--skip-download",
                    "--write-sub",
                    "--write-auto-sub",
                    "--sub-lang", lang,
                    "--sub-format", "vtt",
                    "--convert-subs", "srt",
                    "-o", str(sub_path),
                    url,
                ],
                capture_output=True, text=True, timeout=60,
            )

            # Look for downloaded subtitle file
            for srt_file in Path(tmpdir).glob("*.srt"):
                text = _parse_srt(srt_file)
                if text:
                    return text

            for vtt_file in Path(tmpdir).glob("*.vtt"):
                text = _parse_vtt(vtt_file)
                if text:
                    return text

    return None


def _parse_srt(file_path) -> str:
    """Parse SRT subtitle file into plain text."""
    content = Path(file_path).read_text(encoding="utf-8-sig", errors="ignore")
    lines = []
    for line in content.split("\n"):
        line = line.strip()
        if not line or line.isdigit() or "-->" in line:
            continue
        clean = re.sub(r"<[^>]+>", "", line)
        if clean and clean not in lines[-1:]:
            lines.append(clean)
    return " ".join(lines)


def _parse_vtt(file_path) -> str:
    """Parse VTT subtitle file into plain text."""
    content = Path(file_path).read_text(encoding="utf-8-sig", errors="ignore")
    lines = []
    for line in content.split("\n"):
        line = line.strip()
        if not line or line == "WEBVTT" or "-->" in line or line.startswith("NOTE"):
            continue
        clean = re.sub(r"<[^>]+>", "", line)
        if clean and clean not in lines[-1:]:
            lines.append(clean)
    return " ".join(lines)
