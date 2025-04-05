"""
Şarkı sözleri için zaman düzenleme bileşeni
"""
import gradio as gr
import pandas as pd
import json
import logging
import re
from pathlib import Path

# Initialize Logger
logger = logging.getLogger(__name__)

def parse_ass_time(time_str):
    """
    ASS zaman formatını (0:00:00.00) saniyeye çevirir
    
    Args:
        time_str (str): ASS zaman formatı
        
    Returns:
        float: Saniye cinsinden zaman
    """
    try:
        h, m, s = time_str.split(':')
        return int(h) * 3600 + int(m) * 60 + float(s)
    except Exception as e:
        logger.error(f"Zaman formatı çevrilemedi: {time_str}, hata: {e}")
        return 0.0

def seconds_to_ass_time(seconds):
    """
    Saniyeyi ASS zaman formatına (0:00:00.00) çevirir
    
    Args:
        seconds (float): Saniye cinsinden zaman
        
    Returns:
        str: ASS zaman formatı
    """
    try:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        return f"{h}:{m:02d}:{s:05.2f}"
    except Exception as e:
        logger.error(f"Saniye formatı çevrilemedi: {seconds}, hata: {e}")
        return "0:00:00.00"

def read_ass_file(file_path):
    """
    ASS dosyasını okur ve satırları döndürür
    
    Args:
        file_path (str): ASS dosyasının yolu
        
    Returns:
        list: Dosya satırları
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.readlines()
    except Exception as e:
        logger.error(f"ASS dosyası okuma hatası: {e}")
        return []

def write_ass_file(file_path, lines):
    """
    ASS dosyasını yazar
    
    Args:
        file_path (str): ASS dosyasının yolu
        lines (list): Yazılacak satırlar
        
    Returns:
        bool: Başarılı ise True
    """
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        return True
    except Exception as e:
        logger.error(f"ASS dosyası yazma hatası: {e}")
        return False

def extract_dialogue_lines(ass_file_path):
    """
    ASS dosyasından Dialogue satırlarını çıkarır
    
    Args:
        ass_file_path (str): ASS dosyasının yolu
        
    Returns:
        list: Dialogue satırları ve indeksleri [(index, satır), ...]
    """
    try:
        lines = read_ass_file(ass_file_path)
        dialogue_lines = []
        
        for i, line in enumerate(lines):
            if line.startswith('Dialogue:'):
                dialogue_lines.append((i, line))
                
        return dialogue_lines
    except Exception as e:
        logger.error(f"Dialogue satırları çıkarılamadı: {e}")
        return []

def create_lyrics_timing_editor(working_dir, lyrics_json):
    """
    Şarkı sözleri için zaman düzenleme bileşenini oluşturur
    
    Args:
        working_dir: Çalışma dizini
        lyrics_json: Şarkı sözlerinin JSON verisi
        
    Returns:
        tuple: (lyrics_df, save_button)
    """
    if not working_dir:
        # Eğer working_dir yoksa boş bir dataframe döndür
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
            interactive=True
        )
        
        return lyrics_df, save_button
    
    rows = []
    # ASS dosyasını kontrol et
    ass_file = Path(working_dir) / "karaoke_subtitles.ass"
    
    if ass_file.exists():
        try:
            # ASS dosyasından Dialogue satırlarını çıkar
            dialogue_lines = extract_dialogue_lines(ass_file)
            
            for i, (_, line) in enumerate(dialogue_lines):
                # Dialogue: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
                parts = line.split(',', 9)
                if len(parts) >= 10:
                    # Zamanları al
                    start_time = parts[1].strip()
                    end_time = parts[2].strip()
                    text = parts[9].strip()
                    
                    # Zamanları saniyeye çevir
                    start_seconds = parse_ass_time(start_time)
                    end_seconds = parse_ass_time(end_time)
                    
                    # Metni temizle (stil komutlarını kaldır)
                    clean_text = re.sub(r'\\N', ' ', text)  # Yeni satır karakterlerini boşluğa dönüştür
                    clean_text = re.sub(r'{.*?}', '', clean_text)  # Stil komutlarını kaldır
                    
                    rows.append({
                        "Sıra": i + 1,
                        "Başlangıç (sn)": start_seconds,
                        "Bitiş (sn)": end_seconds,
                        "Sözler": clean_text
                    })
            
            logger.info(f"ASS dosyasından {len(rows)} satır okundu")
        except Exception as e:
            logger.error(f"ASS okuma hatası: {e}")
    
    # Eğer ASS'den satır okunamadıysa ve lyrics_json mevcutsa, ondan oku
    if not rows and lyrics_json:
        try:
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
            logger.info(f"JSON verisinden {len(rows)} satır okundu")
        except Exception as e:
            logger.error(f"JSON okuma hatası: {e}")
    
    # DataFrame oluştur
    if rows:
        df = pd.DataFrame(rows)
    else:
        # Boş DataFrame
        df = pd.DataFrame({
            "Sıra": [], 
            "Başlangıç (sn)": [], 
            "Bitiş (sn)": [], 
            "Sözler": []
        })
    
    # Gradio Dataframe bileşeni
    lyrics_df = gr.Dataframe(
        value=df,
        headers=["Sıra", "Başlangıç (sn)", "Bitiş (sn)", "Sözler"],
        datatype=["number", "number", "number", "str"],
        interactive=True,
        col_count=(4, "fixed")
    )
    
    # Kaydetme butonu
    save_button = gr.Button("Zaman Düzeltmelerini Kaydet", variant="primary", interactive=True)
    
    return lyrics_df, save_button

def save_timing_changes(df, working_dir, lyrics_json):
    """
    DataFrame'deki değişiklikleri lyrics JSON dosyasına ve ASS dosyasına kaydeder
    
    Args:
        df: Düzenlenmiş Dataframe
        working_dir: Çalışma dizini
        lyrics_json: Orijinal şarkı sözleri JSON verisi
        
    Returns:
        tuple: (Güncellenmiş lyrics JSON verisi, Durum mesajı)
    """
    try:
        # Eğer df bir dict ise (Gradio'nun davranışı nedeniyle), DataFrame'e çevir
        if isinstance(df, dict):
            df = pd.DataFrame(df)

        # Debug için
        print(f"DF tipi: {type(df)}")
        print(f"DF boş mu: {df.empty}")
        print(f"Working dir: {working_dir}")

        # Eğer working_dir yoksa veya dataframe boşsa, basit bir uyarı göster
        if not working_dir or df.empty:
            return lyrics_json, "Kaydedilecek veri yok. Önce ses dosyası yükleyin."
        
        working_dir = Path(working_dir)
        if not working_dir.exists():
            return lyrics_json, f"Hata: Çalışma dizini bulunamadı: {working_dir}"
        
        # 1. ASS dosyasını güncelle (eğer varsa)
        ass_file = working_dir / "karaoke_subtitles.ass"
        if ass_file.exists():
            try:
                # ASS dosyasını oku
                lines = read_ass_file(ass_file)
                
                # Dialogue satırlarının indekslerini bul
                dialogue_lines = extract_dialogue_lines(ass_file)
                
                # DataFrame'deki değişiklikleri ASS satırlarına uygula
                for i, row in df.iterrows():
                    if i < len(dialogue_lines):
                        line_idx, _ = dialogue_lines[i]
                        
                        # Satırı parse et
                        parts = lines[line_idx].split(',', 9)
                        if len(parts) >= 10:
                            # Yeni zamanları ASS formatına çevir
                            start_time = seconds_to_ass_time(float(row["Başlangıç (sn)"]))
                            end_time = seconds_to_ass_time(float(row["Bitiş (sn)"]))
                            
                            # Zamanları güncelle
                            parts[1] = start_time
                            parts[2] = end_time
                            
                            # Satırı yeniden oluştur
                            lines[line_idx] = ','.join(parts)
                
                # Değişiklikleri kaydet
                if write_ass_file(ass_file, lines):
                    logger.info(f"ASS dosyası güncellendi: {ass_file}")
                else:
                    logger.error(f"ASS dosyası güncellenemedi: {ass_file}")
            except Exception as e:
                logger.error(f"ASS güncelleme hatası: {e}")
        
        # 2. JSON dosyalarını da güncelle (geriye dönük uyumluluk için)
        if lyrics_json:
            updated_lyrics = []
            
            logger.debug(f"DF satır sayısı: {len(df.index)}")
            for idx, row in df.iterrows():
                try:
                    # Sıra sütununun değerini al, 1'den başladığı için 1 çıkar
                    if "Sıra" in row:
                        sira_idx = int(row["Sıra"]) - 1
                    else:
                        # Eğer Sıra sütunu yoksa, doğrudan indeksi kullan
                        sira_idx = idx
                    
                    # Eğer lyrics_json mevcutsa, orijinal verse'ü kullan
                    if isinstance(lyrics_json, list) and 0 <= sira_idx < len(lyrics_json):
                        original_verse = lyrics_json[sira_idx].copy()
                        
                        # Başlangıç ve bitiş değerlerini güncelle
                        original_verse["start"] = float(row["Başlangıç (sn)"])
                        original_verse["end"] = float(row["Bitiş (sn)"])
                        
                        updated_lyrics.append(original_verse)
                    else:
                        # Eğer lyrics_json mevcut değilse veya verse bulunamadıysa, yeni bir verse oluştur
                        new_verse = {
                            "start": float(row["Başlangıç (sn)"]),
                            "end": float(row["Bitiş (sn)"]),
                            "words": [{
                                "word": word.strip(), 
                                "start": float(row["Başlangıç (sn)"]), 
                                "end": float(row["Bitiş (sn)"])
                            } for word in row["Sözler"].split()]
                        }
                        updated_lyrics.append(new_verse)
                except Exception as e:
                    logger.error(f"Satır işlemede hata: {e}")
            
            # JSON dosyalarını güncelle
            try:
                # Önce raw_lyrics.json dosyasını güncelle
                raw_file = working_dir / "raw_lyrics.json"
                with open(raw_file, "w", encoding="utf-8") as f:
                    json.dump(updated_lyrics, f, indent=4, ensure_ascii=False)
                
                # Sonra modified_lyrics.json dosyasını güncelle
                output_file = working_dir / "modified_lyrics.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(updated_lyrics, f, indent=4, ensure_ascii=False)
                
                logger.info(f"JSON dosyaları güncellendi: {raw_file} ve {output_file}")
                return updated_lyrics, "Zaman düzeltmeleri başarıyla kaydedildi! ASS ve JSON dosyaları güncellendi."
            except Exception as e:
                logger.error(f"JSON kayıt hatası: {e}")
                return lyrics_json, f"JSON kayıt hatası: {e}"
        
        return lyrics_json, "Değişiklikler kaydedildi ancak JSON verisi güncellenemedi."
    
    except Exception as e:
        logger.error(f"Zaman düzeltmelerini kaydetme hatası: {e}")
        return lyrics_json, f"Hata: {e}"
