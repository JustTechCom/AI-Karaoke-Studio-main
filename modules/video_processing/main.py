import re
from pathlib import Path
from typing import Union, Optional, Tuple
import subprocess
import logging
import torch

from .utilities import extract_audio_duration, validate_file

logger = logging.getLogger(__name__)

def parse_ass_time(time_str: str) -> float:
    """
    ASS zaman formatını (örn. "0:00:04.00") saniyeye çevirir.
    """
    try:
        parts = time_str.strip().split(":")
        if len(parts) == 3:
            hours = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])
            return hours * 3600 + minutes * 60 + seconds
    except Exception as e:
        logger.error(f"Time parse error for '{time_str}': {e}")
    return 0.0

def parse_countdown_times(ass_path: Union[str, Path]) -> Optional[Tuple[float, float]]:
    """
    ASS dosyasındaki ilk iki Dialogue satırından:
      - first_end: ilk dialogue’un bitiş zamanı,
      - second_start: ikinci dialogue’un başlangıç zamanı
    değerlerini saniye cinsinden döner.
    """
    first_end = None
    second_start = None
    try:
        with open(ass_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("Dialogue:"):
                    parts = line.split(",", 9)
                    if len(parts) < 10:
                        continue
                    start_time = parse_ass_time(parts[1])
                    end_time = parse_ass_time(parts[2])
                    if first_end is None:
                        first_end = end_time
                    else:
                        second_start = start_time
                        break
        if first_end is not None and second_start is not None and second_start > first_end:
            return (first_end, second_start)
    except Exception as e:
        logger.error(f"Failed to parse countdown times from {ass_path}: {e}")
    return None

def find_countdown_video(directory: Union[str, Path], countdown: int) -> Optional[str]:
    """
    Belirtilen dizinde, 'gerisayım {countdown}.mov' formatına uygun dosyayı arar.
    Uygun dosya bulunursa yolunu döndürür, aksi halde None.
    """
    dir_path = Path(directory)
    pattern = re.compile(r"gerisay.?m\s*{}\.(mov)$".format(countdown), re.IGNORECASE)
    for file in dir_path.iterdir():
        if file.is_file() and pattern.search(file.name):
            return str(file)
    return None

def select_countdown_video(directory: Union[str, Path], duration: float) -> Optional[str]:
    """
    Countdown süresini (duration) tam sayıya yuvarlar ve /app/gerisayim dizininde
    'gerisayım {N}.mov' dosyasını arar.
    """
    count = int(round(duration))
    video_path = find_countdown_video(directory, count)
    if video_path:
        logger.info(f"Selected countdown video: {video_path} for duration: {duration}")
    else:
        logger.warning(f"No countdown video found for duration: {duration}")
    return video_path

def generate_karaoke_video(
    audio_path: Union[str, Path],
    ass_path: Union[str, Path],
    output_path: Union[str, Path],
    video_effect: Optional[Union[str, Path]] = "/app/effects/background-first.mp4",
    background_rest: Optional[Union[str, Path]] = "/app/effects/background.mp4",
    countdown_video: Optional[Union[str, Path]] = None,
    resolution: str = "1280x720",
    preset: str = "fast",
    crf: Optional[int] = 23,
    fps: int = 24,
    bitrate: str = "3000k",
    audio_bitrate: str = "192k",
) -> Optional[str]:
    """
    Karaoke videosunu aşağıdaki adımlarla oluşturur:
      1) ASS dosyasındaki ilk dialogue’un bitiş (first_end) ve ikinci dialogue’un başlangıç (second_start)
         zamanlarına göre:  
         - 0'dan second_start'a kadar: background-first (video_effect) kullanılır,
         - second_start'dan itibaren: background_rest kullanılır (bu video kendi 0. saniyesinden başlar).
      2) İstenilen çözünürlüğe ölçekleme ve pad ile uyum sağlanır.
      3) Countdown zamanları bulunamazsa veya countdown süresi 2 saniyeden az ise,
         countdown overlay eklenmez.
      4) Eğer countdown_video mevcutsa, countdown overlay;
         overlay, ASS dosyasındaki first_end ile second_start aralığında (enable='between(t,first_end,second_start)')
         görünür olacak şekilde, [2:v] üzerinden setpts ile eklenir.
      5) En son, ASS altyazıları eklenir, logo overlay yapılır, audio eklenir ve final video output_path'e yazılır.
    """
    # Dosya doğrulamaları
    if not validate_file(audio_path):
        logger.error(f"Invalid audio file: {audio_path}")
        return None
    if not validate_file(ass_path):
        logger.error(f"Invalid .ass subtitles: {ass_path}")
        return None

    # ASS dosyasından countdown zamanlarını ayrıştır (first_end, second_start)
    times = parse_countdown_times(ass_path)
    if times is None:
        logger.info("Countdown times not found in ASS file. Skipping countdown overlay and two-background split.")
        countdown_video = None
        # Eğer ASS zaman bilgileri bulunamadıysa, iki background'lı işleme yapılamayacağından background_rest'i yoksayalım.
        background_rest = None
    else:
        first_end, second_start = times
        cd_duration = second_start - first_end  # Countdown overlay süresi

        # Countdown süresi 2 saniyeden az ise, overlay eklemeden devam et.
        if cd_duration < 2:
            logger.info("Countdown duration is less than 2 seconds. Skipping countdown overlay.")
            countdown_video = None
        elif countdown_video is None:
            countdown_video = select_countdown_video("/app/gerisayim", cd_duration)

    # GPU kontrolü
    if torch.cuda.is_available():
        device_name = torch.cuda.get_device_name(0)
        logger.info(f"GPU found: {device_name} (NVENC).")
        video_codec = "h264_nvenc"
        use_crf = False
    else:
        logger.warning("No GPU found, using libx264 (CPU).")
        video_codec = "libx264"
        use_crf = True

    audio_dur = extract_audio_duration(audio_path)
    if audio_dur is None:
        logger.error("Cannot detect audio duration, aborting.")
        return None

    # FFmpeg komutunu oluşturuyoruz.
    cmd = ["ffmpeg", "-y"]

    # İki farklı background kullanılıyor: Eğer ASS zaman bilgileri varsa ve background_rest geçerliyse iki background kullanılacak.
    if background_rest is not None:
        if not validate_file(video_effect):
            logger.error(f"Background-first video (video_effect) is invalid: {video_effect}")
            return None
        if not validate_file(background_rest):
            logger.error(f"Background_rest video is invalid: {background_rest}")
            return None
        # Input 0: background-first
        cmd.extend(["-i", str(video_effect)])
    else:
        # Tek background: video_effect ya da renkli arka plan
        if video_effect is not None:
            if not validate_file(video_effect):
                logger.error(f"Video_effect is invalid: {video_effect}")
                return None
            cmd.extend(["-stream_loop", "-1", "-i", str(video_effect)])
        else:
            cmd.extend(["-f", "lavfi", "-i", f"color=c=black:s={resolution}:d={audio_dur}"])
    
    # Input 1: audio
    cmd.extend(["-i", str(audio_path)])
    
    # Input 2: countdown video (varsa, loop olmadan)
    if countdown_video is not None:
        if not validate_file(countdown_video):
            logger.error(f"Countdown video is invalid: {countdown_video}")
            return None
        cmd.extend(["-i", str(countdown_video)])
    
    # Eğer iki background kullanılacaksa, background_rest'i ekleyelim.
    if background_rest is not None:
        cmd.extend(["-i", str(background_rest)])
        # Input sırası: 0: background-first, 1: audio, 2: countdown, 3: background_rest.
        bg_rest_index = "3"
    else:
        bg_rest_index = None

    width, height = resolution.split("x")
    # Eğer ASS zaman bilgileri varsa ve iki background kullanılacaksa, split işlemi yapılır.
    if times is not None and background_rest is not None:
        filter_chain = (
            f"[0:v]trim=duration={second_start},setpts=PTS-STARTPTS,"
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad=w={width}:h={height}:x='(ow-iw)/2':y='(oh-ih)/2'[bg1];"
            f"[{bg_rest_index}:v]trim=duration={audio_dur - second_start},setpts=PTS-STARTPTS,"
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad=w={width}:h={height}:x='(ow-iw)/2':y='(oh-ih)/2'[bg2];"
            f"[bg1][bg2]concat=n=2:v=1:a=0[bg]"
        )
    else:
        # Tek background kullanılıyor.
        filter_chain = (
            f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad=w={width}:h={height}:x='(ow-iw)/2':y='(oh-ih)/2'[bg]"
        )
    
    # Altyazıları background üzerine ekle.
    filter_chain += f"; [bg]subtitles={ass_path}:fontsdir=/app/fonts[vsub_bg]"
    
    # Countdown overlay: Eğer countdown_video mevcutsa ve ASS zaman bilgileri varsa overlay ekle.
    if countdown_video is not None and times is not None:
        filter_chain += (
            "; [2:v]setpts=PTS+{offset}/TB,scale=300:240[countdown];"
            " [vsub_bg][countdown]overlay=530:4:enable='between(t,{start},{end})'[vsub]"
            .format(offset=first_end, start=first_end, end=second_start)
        )
    else:
        filter_chain += "; [vsub_bg]copy[vsub]"

    # Logo overlay: osslogo.png 4 saniye boyunca ekranda görünsün, 4. saniyeden sonra aniden kaybolsun.
    logo_path = "/app/public/osslogo.png"
    if not validate_file(logo_path):
        logger.error(f"Logo file is invalid: {logo_path}")
        return None
    cmd.extend(["-i", logo_path])
    # Logo input'un index'i; cmd'deki tüm "-i" seçeneklerini sayarak hesaplıyoruz.
    logo_index = len([arg for arg in cmd if arg == "-i"]) - 1

    filter_chain += (
        f"; [{logo_index}:v]scale=160:180[logo_scaled]"
        "; [vsub][logo_scaled]overlay=48:337:enable='lt(t,4)'[vfinal]"
    )
    final_video_stream = "[vfinal]"

    cmd.extend([
        "-filter_complex", filter_chain,
        "-map", final_video_stream,
        "-map", "1:a"
    ])

    cmd.extend([
        "-pix_fmt", "yuv420p",
        "-c:v", video_codec,
        "-preset", preset
    ])
    if use_crf and crf is not None:
        cmd.extend(["-crf", str(crf)])
    cmd.extend([
        "-r", str(fps),
        "-b:v", str(bitrate),
        "-c:a", "aac",
        "-b:a", str(audio_bitrate),
        "-shortest",
        str(output_path)
    ])

    logger.debug("FFmpeg command: %s", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True)
        logger.info(f"Karaoke video created at: {output_path}")
        return str(output_path)
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return None
