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
def post_process_sync(verses, audio_path):
    """
    DTW algoritması kullanarak senkronizasyonu düzeltir
    """
    import librosa
    import numpy as np
    from fastdtw import fastdtw
    
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
        # (Burada DTW uygulaması basitleştirilmiştir, gerçek uygulamada daha karmaşık olabilir)
        corrected_times = apply_dtw_correction(word_times, mfcc)
        
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
		vad_filter=True,
		vad_parameters=dict(min_silence_duration_ms=300, speech_pad_ms=100)
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

    verses = filter_lyrics(verses)
    logger.debug(f"Filtered out verses containing unwanted phrases. {len(verses)} verses remaining.")
    logger.debug(f"Transcribed {len(verses)} verses with words, timing, and predictions using the Whisper model.")
    return verses