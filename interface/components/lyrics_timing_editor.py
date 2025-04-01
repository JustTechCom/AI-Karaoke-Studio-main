"""
Şarkı sözleri için zaman düzenleme bileşeni
"""
import gradio as gr
import pandas as pd
import json
import logging
from pathlib import Path

# Initialize Logger
logger = logging.getLogger(__name__)

def create_lyrics_timing_editor(working_dir, lyrics_json):
    """
    Şarkı sözleri için zaman düzenleme bileşenini oluşturur
    
    Args:
        working_dir: Çalışma dizini
        lyrics_json: Şarkı sözlerinin JSON verisi
        
    Returns:
        tuple: (lyrics_df, save_button)
    """
    if not lyrics_json or not working_dir:
        # Eğer lyrics_json veya working_dir yoksa boş bir dataframe döndür
        empty_df = pd.DataFrame({
            "Sıra": [], 
            "Başlangıç (sn)": [], 
            "Bitiş (sn)": [], 
            "Sözler": []
        })
        
        lyrics_df = gr.Dataframe(
            value=empty_df,
            headers=["Sıra", "Başlangıç (sn)", "Bitiş (sn)", "Sözler"],
            datatype=["number", "number", "number", "str"],
            interactive=True,
            col_count=(4, "fixed"),
            row_count=1
        )
        
        save_button = gr.Button(
            "Zaman Düzeltmelerini Kaydet", 
            variant="primary",
            interactive=False
        )
        
        return lyrics_df, save_button
    
    # Lyrics JSON'dan veriyi çıkar
    rows = []
    for i, verse in enumerate(lyrics_json):
        # Her bir verse için kelimeleri birleştir
        if "words" in verse:
            words_text = " ".join([word.get("word", "") for word in verse["words"]])
            rows.append({
                "Sıra": i + 1,
                "Başlangıç (sn)": round(verse.get("start", 0), 2),
                "Bitiş (sn)": round(verse.get("end", 0), 2),
                "Sözler": words_text
            })
    
    # DataFrame oluştur
    df = pd.DataFrame(rows)
    
    # Gradio Dataframe bileşeni
    lyrics_df = gr.Dataframe(
        value=df,
        headers=["Sıra", "Başlangıç (sn)", "Bitiş (sn)", "Sözler"],
        datatype=["number", "number", "number", "str"],
        interactive=True,
        col_count=(4, "fixed")
    )
    
    # Kaydetme butonu
    save_button = gr.Button("Zaman Düzeltmelerini Kaydet", variant="primary")
    
    return lyrics_df, save_button

def save_timing_changes(df, working_dir, lyrics_json):
    """
    DataFrame'deki değişiklikleri lyrics JSON dosyasına kaydeder
    
    Args:
        df: Düzenlenmiş Dataframe
        working_dir: Çalışma dizini
        lyrics_json: Orijinal şarkı sözleri JSON verisi
        
    Returns:
        dict: Güncellenmiş lyrics JSON verisi
    """
    try:
        if not lyrics_json or df.empty:
            return lyrics_json, "Kaydedilecek veri yok."
        
        # DataFrame'i işle
        updated_lyrics = []
        
        for _, row in df.iterrows():
            idx = int(row["Sıra"]) - 1
            
            # Orijinal verse'ü al
            if 0 <= idx < len(lyrics_json):
                original_verse = lyrics_json[idx]
                
                # Zamanları güncelle
                original_verse["start"] = float(row["Başlangıç (sn)"])
                original_verse["end"] = float(row["Bitiş (sn)"])
                
                # Sözlerin kendisini değiştirmedik, sadece zamanları güncelledik
                updated_lyrics.append(original_verse)
        
        # Güncellenmiş JSON'ı diske kaydet
        output_file = Path(working_dir) / "modified_lyrics.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(updated_lyrics, f, indent=4, ensure_ascii=False)
        
        return updated_lyrics, "Zaman düzeltmeleri başarıyla kaydedildi!"
    
    except Exception as e:
        logger.error(f"Zaman düzeltmelerini kaydetme hatası: {e}")
        return lyrics_json, f"Hata: {e}"
