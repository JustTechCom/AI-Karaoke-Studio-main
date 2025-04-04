# Standard Library Imports
from pathlib import Path
from typing import Union
import logging
import traceback
import os
from datetime import datetime

# Local Application Imports
from .utilities import extract_audio_duration
from ..utilities import load_json
from .create_ass_file import create_ass_file

# Initialize Logger
logger = logging.getLogger(__name__)


def process_karaoke_subtitles(
    output_path: Union[str, Path],
    override: bool = False,
    file_name: str = "karaoke_subtitles.ass",
    font: str = "/app/fonts/Futura XBlkCnIt BT.ttf",  # Güncellenmiş: Kaydırmalı sözler için özel font
    fontsize: int = 60,
    primary_color: str = "Orange",
    secondary_color: str = "White",
    outline_color: str = "Light Blue",
    outline_size: int = 3,
    shadow_color: str = "Light Blue",
    shadow_size: int = 0,
    screen_width: int = 1280,
    screen_height: int = 720,
    verses_before: int = 1,
    verses_after: int = 1,
    loader_threshold: int = 5.0,
):
    try:
        logger.info("Creating karaoke subtitle file referencing timed lyrics")
        logger.info(f"Output path: {output_path}")
        logger.info(f"Override: {override}")
        logger.info(f"Output file name: {file_name}")

        metadata = Path(output_path) / "metadata.json"
        modified_lyrics_file = Path(output_path) / "modified_lyrics.json"
        raw_lyrics_file = Path(output_path) / "raw_lyrics.json"
        audio_file = Path(output_path) / "karaoke_audio.mp3"
        output_file = Path(output_path) / file_name

        # ASS dosyası varsa sil
        if output_file.exists() and override:
            try:
                logger.info(f"Removing existing ASS file: {output_file}")
                output_file.unlink()
            except Exception as e:
                logger.warning(f"Could not delete existing ASS file: {e}")

        # Mevcut modified_lyrics.json dosyası var mı kontrol et
        if Path(modified_lyrics_file).exists():
            logger.info(f"Modified lyrics file exists at: {modified_lyrics_file}")
            # Dosyanın son güncellenme zamanını al
            try:
                mod_time = os.path.getmtime(modified_lyrics_file)
                mod_time_str = datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S')
                logger.info(f"Modified lyrics file last updated at: {mod_time_str}")
            except Exception as e:
                logger.warning(f"Could not get file stats: {e}")
        else:
            logger.warning(f"Modified lyrics file does not exist at: {modified_lyrics_file}")

        # Force reload the lyrics data from disk
        if Path(modified_lyrics_file).exists():
            logger.info("Modified lyrics file exists. Using it for subtitle generation.")
            lyrics_file = Path(modified_lyrics_file)
        else:
            logger.info("Modified lyrics file does not exist. Using raw lyrics file.")
            lyrics_file = Path(raw_lyrics_file)
            
        logger.info(f"Using lyrics file: {lyrics_file}")

        if not lyrics_file.exists():
            logger.error("Lyrics file does not exist. Skipping subtitle generation...")
            raise FileNotFoundError(f"Lyrics file '{lyrics_file}' does not exist.")

        # Load the artist info
        artist_info = load_json(metadata)
        song_name = artist_info.get("title", "Unknown Title")
        artist_name = artist_info.get("artists", ["Unknown Artist"])[0]
        title = f"{artist_name}\n~ {song_name} ~\nKaraoke"
        title = title.replace("\n", r"\N")

        # Load the lyrics
        verses_data = load_json(lyrics_file)
        logger.info(f"Loaded {len(verses_data)} verses from {lyrics_file.name}")
        
        # Log some sample verse timing data
        if verses_data and len(verses_data) > 0:
            sample_verse = verses_data[0]
            logger.info(f"Sample verse timing - start: {sample_verse.get('start')}, end: {sample_verse.get('end')}")

        # Extract audio duration (assuming you have an input file for the instrumental audio)
        audio_duration = extract_audio_duration(audio_file)

        if audio_duration is None:
            raise ValueError(f"Could not extract audio duration from {audio_file}")

        try:
            create_ass_file(
                verses_data,
                output_path=output_file,
                audio_duration=audio_duration,
                font=font,  # Bu font, kaydırmalı sözler için kullanılacak.
                fontsize=fontsize,
                primary_color=primary_color,
                secondary_color=secondary_color,
                outline_color=outline_color,
                outline_size=outline_size,
                shadow_color=shadow_color,
                shadow_size=shadow_size,
                title=title,
                screen_width=screen_width,
                screen_height=screen_height,
                verses_before=verses_before,
                verses_after=verses_after,
                loader_threshold=loader_threshold
            )
            
            # ASS dosyasının oluşturulup oluşturulmadığını kontrol et
            if output_file.exists():
                file_size = output_file.stat().st_size
                logger.info(f"ASS file successfully created: {output_file} (Size: {file_size} bytes)")
            else:
                logger.warning(f"ASS file was not created: {output_file}")
                
        except Exception:
            print(traceback.format_exc())
            raise

        logger.info(f"Karaoke subtitles file created: {output_file}")
        return output_file

    except Exception as e:
        logger.error(f"An error occurred during subtitle generation: {e}")
        raise
