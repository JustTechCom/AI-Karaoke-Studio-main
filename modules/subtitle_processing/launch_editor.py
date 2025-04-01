# Standard Library Imports
from pathlib import Path
from typing import Union, Optional
import logging
import webbrowser
import tempfile
import shutil
import os
import json

# Local Application Imports
from .visual_editor import edit_ass_with_visual_editor
from ..utilities import ensure_directory_exists

# Initialize Logger
logger = logging.getLogger(__name__)

def launch_visual_ass_editor(working_dir: Optional[Union[str, Path]] = None):
    """
    Görsel ASS editörünü başlatır. Eğer working_dir verilmişse, o dizindeki
    ASS dosyasını editörde açar. Değilse, boş bir editör başlatır.
    
    Args:
        working_dir: Çalışma dizini (ASS dosyasının bulunduğu yer)
        
    Returns:
        bool: İşlem başarılı ise True, değilse False
    """
    try:
        if working_dir:
            # Eğer çalışma dizini verilmişse, ilgili ASS dosyasını bul
            working_dir = Path(working_dir)
            ass_file = working_dir / "karaoke_subtitles.ass"
            audio_file = working_dir / "karaoke_audio.mp3"
            
            if ass_file.exists():
                # ASS ve müzik dosyaları mevcutsa, görsel editörü başlat
                return edit_ass_with_visual_editor(ass_file, audio_file if audio_file.exists() else None)
            else:
                # ASS dosyası yoksa, default/örnek bir ASS dosyası oluştur
                return _launch_demo_editor()
        else:
            # Çalışma dizini verilmemişse, demo editörü aç
            return _launch_demo_editor()
            
    except Exception as e:
        logger.error(f"ASS editör başlatma hatası: {e}")
        return False

def _launch_demo_editor():
    """
    Demo ASS editörünü içinde örnek içerikle başlatır.
    
    Returns:
        bool: İşlem başarılı ise True, değilse False
    """
    try:
        # Projenin root dizinini bul
        current_path = Path(__file__).resolve()
        project_root = current_path.parent.parent.parent
        static_path = project_root / "interface" / "static"
        
        # Örnek ASS içeriği
        example_ass = """[Script Info]
Title: Example Karaoke
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:05.00,Default,,0,0,0,,Örnek Altyazı 1
Dialogue: 0,0:00:06.00,0:00:10.00,Default,,0,0,0,,Örnek Altyazı 2
Dialogue: 0,0:00:11.00,0:00:15.00,Default,,0,0,0,,Örnek Altyazı 3
"""
        
        # Geçici dizinde dosya oluştur
        temp_dir = tempfile.mkdtemp(prefix="karaoke_editor_demo_")
        temp_ass_file = Path(temp_dir) / "example.ass"
        
        with open(temp_ass_file, "w", encoding="utf-8") as f:
            f.write(example_ass)
        
        # Editörü başlat
        result = edit_ass_with_visual_editor(temp_ass_file)
        
        # Geçici dosyaları temizle
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        return result
        
    except Exception as e:
        logger.error(f"Demo ASS editör başlatma hatası: {e}")
        return False
