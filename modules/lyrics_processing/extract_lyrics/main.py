# Standard Imports
from pathlib import Path
from typing import Union
import logging

# Third-Party Imports
from faster_whisper import WhisperModel

# Local Application Imports
from .config import MODEL_SIZE, DEVICE, COMPUTE_TYPE
from interface.helpers import get_available_languages

# Initialize Whisper model globally to avoid reloading it multiple times
MODEL = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)

# Initialize Logger
logger = logging.getLogger(__name__)

def apply_dtw_correction(word_times, mfcc, sr):
    """
    DTW (Dynamic Time Warping) algoritması kullanarak kelime zamanlarını düzeltir.

    MFCC üzerinden elde edilen ses etkinliği ile sözcük zamanlarının faaliyet
    dizisini hizalar ve daha iyi eşleşen yeni zamanlar üretir.

    Args:
        word_times (list[tuple]): Kelimelerin başlangıç ve bitiş zamanları
            listesi ``[(start1, end1), ...]``.
        mfcc (np.ndarray): Ses segmentine ait MFCC özellikleri.
        sr (int): Ses verisinin örnekleme oranı.

    Returns:
        list[tuple]: Düzeltilmiş zamanlar listesi ``[(start1, end1), ...]``.
    """
    import numpy as np
    import librosa
    from fastdtw import fastdtw

    # Tüm zamanları ilk kelimenin başlangıcına göre göreli hale getir
    base_time = word_times[0][0]
    frame_times = librosa.frames_to_time(range(mfcc.shape[1]), sr=sr)

    # Kelime zamanlarından ikili bir etkinlik dizisi oluştur
    word_activity = np.zeros(len(frame_times), dtype=np.float32)
    for start, end in word_times:
        s_idx = np.searchsorted(frame_times, start - base_time)
        e_idx = np.searchsorted(frame_times, end - base_time)
        word_activity[s_idx:e_idx] = 1.0

    # MFCC'leri ortalama alarak tek boyutlu ses etkinliği çıkar
    audio_activity = mfcc.mean(axis=0)

    # İki diziyi DTW ile hizala
    _, path = fastdtw(word_activity, audio_activity)
    mapping = dict(path)

    corrected = []
    for start, end in word_times:
        s_idx = np.searchsorted(frame_times, start - base_time)
        e_idx = np.searchsorted(frame_times, end - base_time)
        s_new = frame_times[mapping.get(s_idx, s_idx)] + base_time
        e_new = frame_times[mapping.get(e_idx, e_idx)] + base_time
        corrected.append((round(float(s_new), 2), round(float(e_new), 2)))

    return corrected

def filter_lyrics(verses):
    """
    Filters out verses containing unwanted phrases.
    
    Args:
        verses (list[dict]): List of verses with text and metadata.
        
    Returns:
        list[dict]: Filtered list of verses.
    """
    unwanted_phrases = ['abone ol', 'altyazı', 'm.k.', 'yorum yap','beğen butonuna','tıklamayı unutmayın']
    filtered_verses = []
    
    for verse in verses:
        # Reconstruct the full text from all words in the verse
        full_text = ' '.join([word_data['word'] for word_data in verse['words']])
        full_text_lower = full_text.lower()
        
        # Check if any unwanted phrase exists in the text
        should_include = True
        for phrase in unwanted_phrases:
            if phrase in full_text_lower:
                should_include = False
                break
        
        # If no unwanted phrases found, include this verse
        if should_include:
            filtered_verses.append(verse)
    
    return filtered_verses

def filter_early_vocals(verses, threshold_seconds=15.0, min_word_count=4):
    """
    Şarkının başındaki ilk birkaç saniyedeki arka vokalleri veya sesleri filtrele.
    Genellikle intro sırasında duyulan "hadi, gel, hey" gibi sesleri çıkarır.
    
    Args:
        verses (list[dict]): Açıklamalı verse'lerin listesi.
        threshold_seconds (float): Başta dikkate alınmayacak süre (saniye).
        min_word_count (int): Filtreleme için geçerli bir verse için minimum kelime sayısı.
        
    Returns:
        list[dict]: Filtre sonrası kalan verse'lerin listesi.
    """
    if not verses:
        return []
    
    # Eğer verses boş değilse, başlangıç zamanını al
    filtered_verses = []
    
    # Her verse için
    for verse in verses:
        # Şarkının başındaki eşik değerinden önce mi?
        if verse["start"] < threshold_seconds:
            # Kısa ve başta ise (muhtemelen arka ses veya intro), kontrol et
            # Kelime sayısı çok azsa, muhtemelen arka vokal
            if len(verse["words"]) < min_word_count:
                logger.debug(f"Filtering out early verse at {verse['start']}s with {len(verse['words'])} words")
                continue
                
            # Eğer kelime sayısı yeterliyse bile ama 10 saniyeden önce başlıyorsa 
            # ve kısa süre devam ediyorsa (intro/solo scream, hay, hey, vs. gibi) hala filtrele
            if verse["start"] < 10.0 and (verse["end"] - verse["start"]) < 2.0:
                logger.debug(f"Filtering out early short-duration verse at {verse['start']}s with duration {verse['end'] - verse['start']:.2f}s")
                continue
                
            # Sözlerin içeriğine bak, anlamsız sesleri filtrele
            verse_text = " ".join([word["word"] for word in verse["words"]]).lower()
            noise_patterns = ["ahh", "hah", "hayy", "hmm", "oh", "huh", "yeah", "woo", "woah", "hey", "heya", "oohh"]
            
            if any(pattern in verse_text for pattern in noise_patterns) and verse["start"] < 10.0:
                logger.debug(f"Filtering out early noise-like verse at {verse['start']}s: '{verse_text}'")
                continue
        
        # Eşikten sonra veya yeterince kelime içeren verse'leri kabul et
        filtered_verses.append(verse)
    
    return filtered_verses

def filter_short_verses(verses, min_duration=0.5, min_word_count=2):
    """
    Çok kısa verse'leri filtrele. Bu genellikle arka vokalleri veya hatalı algılanmış sesleri temsil eder.
    
    Args:
        verses (list[dict]): Verse'lerin listesi.
        min_duration (float): Minimum verse süresi (saniye).
        min_word_count (int): Minimum kelime sayısı.
        
    Returns:
        list[dict]: Filtre sonrası kalan verse'lerin listesi.
    """
    if not verses:
        return []
    
    filtered_verses = []
    
    for verse in verses:
        # Verse süresi kontrolü
        duration = verse["end"] - verse["start"]
        
        # Çok kısa verse mi?
        if duration < min_duration:
            logger.debug(f"Filtering out short verse at {verse['start']}s with duration {duration:.2f}s")
            continue
            
        # Çok az kelime içeriyor mu?
        if len(verse["words"]) < min_word_count:
            logger.debug(f"Filtering out verse at {verse['start']}s with only {len(verse['words'])} words")
            continue
        
        # Yeterince uzun verse'leri kabul et
        filtered_verses.append(verse)
    
    return filtered_verses

def post_process_sync(verses, audio_path):
    """DTW algoritması kullanarak kelime zamanlarını sesle hizalar."""
    import librosa
    
    # Ses dosyasını yükle
    y, sr = librosa.load(audio_path)
    
    # Her bir dize için
    for verse in verses:
        # Dizeden alınan zaman damgalarını kullan
        word_times = [(word['start'], word['end']) for word in verse['words']]
        
        # Bu zaman aralığındaki ses verisini al
        start_idx = int(verse['start'] * sr)
        end_idx = int(verse['end'] * sr)
        audio_segment = y[start_idx:end_idx]
        
        # MFCC özelliklerini çıkar
        mfcc = librosa.feature.mfcc(y=audio_segment, sr=sr)
        
        # DTW'yi uygula ve düzeltilmiş zamanları al
        corrected_times = apply_dtw_correction(word_times, mfcc, sr)
        
        # Zaman damgalarını güncelle
        for i, word in enumerate(verse['words']):
            word['start'] = corrected_times[i][0]
            word['end'] = corrected_times[i][1]
    
    return verses

def _extract_lyrics_with_timing(
        audio_path: Union[str, Path],
        beam_size_input: int = 15,
        best_of_input: int = 5,
        patience_input: float = 3.0,
        condition_toggle: bool = False,
        compression_threshold_input: float = 1.3,
        temperature_input: float = 0.0,
        language_option: str = "Auto Detect"
    ):
    """
    Extracts and groups lyrics into verses with timing and word details.

    Args:
        audio_path (str): Path to the audio file.

    Returns:
        list[dict]: List of verses with text and metadata.
    """
    # If the user chooses Auto Detect, we let Whisper decide (or pass None)
    if language_option == "Auto Detect":
        lang = None
    else:
        available_langs = get_available_languages()
        lang = available_langs.get(language_option, None)

    # Transcribe the audio and extract word-level timestamps
    segments, info = MODEL.transcribe(
        audio_path,
        word_timestamps=True,              # Extract word-level timestamps
        beam_size=int(beam_size_input),    # Increase beam search for better word accuracy
        best_of=int(best_of_input),        # Pick the best transcription from multiple runs
        patience=patience_input,           # Allow more time before closing segments
        condition_on_previous_text=condition_toggle,             # Ensure no contextual bias from previous words
        compression_ratio_threshold=compression_threshold_input, # Force Whisper to retain more words
        temperature=temperature_input,       # Eliminate randomness in transcription
        language=lang,                       # Language code for transcription
        vad_filter=True,                     # Ses Aktivite Algılama filtresini etkinleştir
        vad_parameters=dict(
            min_silence_duration_ms=800,     # Sessizlik süresini uzat (arka vokaller arasında daha fazla boşluk olmasını sağlar)
            speech_pad_ms=25,               # Vokal kenarlarındaki padding süresini azalt
            threshold=0.6                   # Daha yüksek ses eşiği (0.5'den büyük olmalı)
        )
    )

    logger.debug(f"Transcription of the vocals audio segments completed.")

    # Initialize an empty list to hold the processed verses
    verses = []

    # Process each segment into a structured verse
    logger.debug(f"Formatting segments into verses with words, timing, and predictions using the Whisper model.")
    for segment in segments:

        # Create metadata for each word in the segment
        words_metadata = []

        for word in segment.words:
            word_data = {
                "word": word.word.strip(),
                "start": round(word.start, 2),
                "end": round(word.end, 2),
                # "probability": round(word.probability, 2)
            }
            words_metadata.append(word_data)

        # Create the verse-level metadata dictionary
        verse_data = {
            "start": round(segment.start, 2),       # Start time of the verse
            "end": round(segment.end, 2),           # End time of the verse
            "words": words_metadata       # Word-level metadata
        }

        # Append the verse metadata to the list of verses
        verses.append(verse_data)

    # Filtrele: istenmeyen kelimeleri içeren dizeleri çıkar
    verses = filter_lyrics(verses)
    logger.debug(f"Filtered out verses containing unwanted phrases. {len(verses)} verses remaining.")
    
    # Şarkının başındaki erken sesleri filtrele
    verses = filter_early_vocals(verses)
    logger.debug(f"Filtered out early verses that might be background vocals. {len(verses)} verses remaining.")
    
    # Çok kısa verse'leri filtrele (arka vokaller veya hatalar)
    verses = filter_short_verses(verses)
    logger.debug(f"Filtered out very short verses that might be errors. {len(verses)} verses remaining.")
    
    logger.debug(f"Transcribed {len(verses)} verses with words, timing, and predictions using the Whisper model.")
    return verses
