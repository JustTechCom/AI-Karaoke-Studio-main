
# Standard Library Imports
from pathlib import Path
from typing import Union, Optional
import logging

# Third-Party Imports
import re

# Local Application Imports
from .main import generate_karaoke_video
from ..utilities import load_json
from ..subtitle_processing.ass_editor import edit_and_save_ass, preview_ass_content
from ..subtitle_processing.visual_editor import edit_ass_with_visual_editor

# Initialize Logger
logger = logging.getLogger(__name__)


def process_karaoke_video(
    working_dir: Union[str, Path],
    output_path: Union[str, Path],
    effect_path: Optional[Union[str, Path]],
    resolution: str = "1280x720",
    preset: str = "fast",
    crf: int = 23,
    fps: int = 24,
    bitrate: str = "3000k",
    audio_bitrate: str = "192k",
    edit_ass_before_render: bool = False,
):
    metadata_file = Path(working_dir) / "metadata.json"
    karaoke_audio = Path(working_dir) / "karaoke_audio.mp3"
    karaoke_subtitles = Path(working_dir) / "karaoke_subtitles.ass"

    try:
        # Load the audio metadata file
        metadata = load_json(metadata_file)

        # Remove parentheses and their contents
        title = re.sub(r"\(.*?\)", "", metadata["title"]).strip()

        # Replace non-alphanumeric characters with underscores and convert to lowercase
        sanitized_title = re.sub(r'[^a-zA-Z0-9]+', '-', title).lower()

        # Relative paths for FFmpeg
        relative_subtitles = karaoke_subtitles.relative_to(
            working_dir.parent.parent)
        relative_output = Path(output_path.name) / \
            f"{sanitized_title}.mp4"

        # ASS dosyasını düzenleme seçeneği aktifse
        if edit_ass_before_render and karaoke_subtitles.exists():
            logger.info("ASS dosyası düzenleme modu aktif. Kullanıcı düzenlemesi bekleniyor...")
            preview = preview_ass_content(karaoke_subtitles)
            logger.info(f"ASS Dosya Önizlemesi:\n{preview}\n")
            
            # Basit metin editörü kullan
            if edit_and_save_ass(karaoke_subtitles):
                logger.info("ASS dosyası başarıyla düzenlendi. Video oluşturuluyor...")
            else:
                logger.warning("ASS dosyası düzenlenemedi. Orijinal dosya kullanılarak devam ediliyor.")

        generate_karaoke_video(
            audio_path=karaoke_audio.as_posix(),
            ass_path=relative_subtitles.as_posix(),
            output_path=relative_output.as_posix(),
            video_effect=effect_path.as_posix() if effect_path is not None else None,
            resolution=resolution,
            preset=preset,
            crf=crf,
            fps=fps,
            bitrate=bitrate,
            audio_bitrate=audio_bitrate,
        )

        return relative_output

    except Exception as e:
        logger.error(f"Error loading metadata: {e}")
        raise