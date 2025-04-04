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
            interactive=True
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
    save_button = gr.Button("Zaman Düzeltmelerini Kaydet", variant="primary", interactive=True)
    
    return lyrics_df, save_button

def save_timing_changes(df, working_dir, lyrics_json):
    """
    DataFrame'deki değişiklikleri lyrics JSON dosyasına kaydeder
    
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
        print(f"Lyrics JSON tipi: {type(lyrics_json)}")

        # Eğer working_dir veya lyrics_json yoksa, basit bir uyarı göster
        if not working_dir or not lyrics_json or df.empty:
            return lyrics_json, "Kaydedilecek veri yok. Önce ses dosyası yükleyin."
        
        # Lyrics_json stringse, JSON olarak parse et
        if isinstance(lyrics_json, str):
            try:
                lyrics_json = json.loads(lyrics_json)
            except:
                pass  # Hata alırsa, mevcut halini kullan
        
        working_dir = Path(working_dir)
        if not working_dir.exists():
            return lyrics_json, f"Hata: Çalışma dizini bulunamadı: {working_dir}"
        
        # Önceki ve sonraki JSON dosyalarının kopyasını al
        print(f"Orijinal lyrics JSON: {lyrics_json[:2] if isinstance(lyrics_json, list) else 'Not a list'}")
        
        # DataFrame'i işle
        updated_lyrics = []
        
        print(f"DF satır sayısı: {len(df.index)}")
        for idx, row in df.iterrows():
            try:
                # Sıra sütununun değerini al, 1'den başladığı için 1 çıkar
                print(f"Row columns: {row.index.tolist()}")
                if "Sıra" in row:
                    sira_idx = int(row["Sıra"]) - 1
                else:
                    # Eğer Sıra sütunu yoksa, doğrudan indeksi kullan
                    sira_idx = idx
                
                print(f"Sıra indeksi: {sira_idx}, Orijinal JSON uzunluğu: {len(lyrics_json)}")
                
                # Orijinal verse'ü al
                if 0 <= sira_idx < len(lyrics_json):
                    original_verse = lyrics_json[sira_idx].copy()  # Orijinal veriyi korumak için kopyasını al
                    
                    # Başlangıç ve bitiş değerlerini bul
                    baslangic_col = "Başlangıç (sn)" if "Başlangıç (sn)" in row else "start"
                    bitis_col = "Bitiş (sn)" if "Bitiş (sn)" in row else "end"
                    
                    # Zamanları güncelle
                    original_verse["start"] = float(row[baslangic_col])
                    original_verse["end"] = float(row[bitis_col])
                    
                    print(f"Güncellenmiş verse: start={original_verse['start']}, end={original_verse['end']}")
                    
                    # Sözlerin kendisini değiştirmedik, sadece zamanları güncelledik
                    updated_lyrics.append(original_verse)
            except Exception as e:
                logger.error(f"Satır işlemede hata: {e}")
                print(f"Satır işlemede hata: {e}")
        
        print(f"Güncellenmiş lyrics uzunluğu: {len(updated_lyrics)}")
        print(f"Güncellenmiş ilk 2 eleman: {updated_lyrics[:2] if updated_lyrics else 'Boş'}")
        
        # Güncellenmiş JSON'ı diske kaydet - hem raw_lyrics.json hem de modified_lyrics.json dosyalarını güncelle
        try:
            # Önce raw_lyrics.json dosyasını güncelle
            raw_file = working_dir / "raw_lyrics.json"
            with open(raw_file, "w", encoding="utf-8") as f:
                json.dump(updated_lyrics, f, indent=4, ensure_ascii=False)
            
            # Sonra modified_lyrics.json dosyasını güncelle
            output_file = working_dir / "modified_lyrics.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(updated_lyrics, f, indent=4, ensure_ascii=False)
            
            print(f"Dosyalar başarıyla güncellendi: {raw_file} ve {output_file}")
            logger.info(f"Zaman değişiklikleri kaydedildi. {len(updated_lyrics)} adet vers güncellendi.")
            return updated_lyrics, f"Zaman düzeltmeleri başarıyla kaydedildi! {len(updated_lyrics)} adet vers güncellendi."
        except Exception as e:
            logger.error(f"JSON kayıt hatası: {e}")
            print(f"JSON kayıt hatası: {e}")
            return lyrics_json, f"JSON kayıt hatası: {e}"
    
    except Exception as e:
        logger.error(f"Zaman düzeltmelerini kaydetme hatası: {e}")
        print(f"Genel hata: {e}")
        return lyrics_json, f"Hata: {e}"