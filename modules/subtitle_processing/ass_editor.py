# Standard Library Imports
from pathlib import Path
from typing import Union, Optional, List
import logging
import os
import re
import tempfile
import subprocess
import sys
import time

# Initialize Logger
logger = logging.getLogger(__name__)

def read_ass_file(file_path: Union[str, Path]) -> List[str]:
    """
    ASS dosyasının içeriğini satır satır okur ve bir liste olarak döndürür.
    
    Args:
        file_path: ASS dosyasının yolu
        
    Returns:
        List[str]: ASS dosyasının satırlarını içeren liste
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.readlines()
    except Exception as e:
        logger.error(f"ASS dosyası okuma hatası: {e}")
        return []

def write_ass_file(file_path: Union[str, Path], content: List[str]) -> bool:
    """
    İçeriği ASS dosyasına yazar.
    
    Args:
        file_path: ASS dosyasının yolu
        content: Yazılacak satırların listesi
        
    Returns:
        bool: İşlem başarılı ise True, değilse False
    """
    try:
        with open(file_path, 'w', encoding='utf-8') as file:
            file.writelines(content)
        return True
    except Exception as e:
        logger.error(f"ASS dosyası yazma hatası: {e}")
        return False

def create_temporary_ass_copy(original_path: Union[str, Path]) -> Optional[str]:
    """
    ASS dosyasının geçici bir kopyasını oluşturur.
    
    Args:
        original_path: Orijinal ASS dosyasının yolu
        
    Returns:
        Optional[str]: Geçici dosyanın yolu, hata durumunda None
    """
    try:
        original_content = read_ass_file(original_path)
        if not original_content:
            return None
            
        temp_dir = tempfile.gettempdir()
        temp_file = os.path.join(temp_dir, f"temp_edit_{os.path.basename(original_path)}")
        
        if write_ass_file(temp_file, original_content):
            return temp_file
            
        return None
    except Exception as e:
        logger.error(f"Geçici dosya oluşturma hatası: {e}")
        return None

def open_with_default_app(file_path: Union[str, Path]) -> bool:
    """
    Dosyayı varsayılan uygulamayla açar.
    
    Args:
        file_path: Açılacak dosyanın yolu
        
    Returns:
        bool: İşlem başarılı ise True, değilse False
    """
    try:
        file_path = Path(file_path).resolve()
        if not file_path.exists():
            logger.error(f"Dosya bulunamadı: {file_path}")
            return False
            
        # Platforma göre açma
        if sys.platform == 'win32':
            os.startfile(file_path)
        elif sys.platform == 'darwin':  # macOS
            subprocess.run(['open', file_path], check=True)
        else:  # Linux
            subprocess.run(['xdg-open', file_path], check=True)
            
        return True
    except Exception as e:
        logger.error(f"Dosya açma hatası: {e}")
        return False

def edit_and_save_ass(ass_file_path: Union[str, Path]) -> bool:
    """
    ASS dosyasını düzenlemeye açar ve kullanıcının düzenlemesini bekler.
    
    Args:
        ass_file_path: Düzenlenecek ASS dosyasının yolu
        
    Returns:
        bool: Düzenleme başarılı ise True, değilse False
    """
    ass_file_path = Path(ass_file_path)
    
    # Dosyanın var olup olmadığını kontrol et
    if not ass_file_path.exists():
        logger.error(f"ASS dosyası bulunamadı: {ass_file_path}")
        return False

    # Geçici dosya oluştur
    temp_file = create_temporary_ass_copy(ass_file_path)
    if not temp_file:
        logger.error("Geçici ASS dosyası oluşturulamadı")
        return False
        
    # Dosyayı varsayılan uygulamada aç
    if not open_with_default_app(temp_file):
        logger.error("ASS dosyası açılamadı")
        return False
    
    # Kullanıcıdan düzenlemeleri tamamlamasını iste
    print("\n=======================================")
    print("ASS altyazı dosyası varsayılan metin editöründe açıldı.")
    print("Lütfen düzenlemelerinizi yapın, dosyayı kaydedin ve kapatın.")
    print("Düzenlemeyi tamamladıktan sonra Enter tuşuna basın...")
    print("=======================================\n")
    input()
    
    # Dosyanın son değiştirilme zamanını kontrol et 
    # (kullanıcının gerçekten değişiklik yapıp yapmadığını anlamak için)
    if not Path(temp_file).exists():
        logger.warning("Geçici dosya bulunamadı. Düzenleme iptal edildi.")
        return False
    
    # Düzenlenen içeriği orijinal dosyaya kopyala
    edited_content = read_ass_file(temp_file)
    if not edited_content:
        logger.error("Düzenlenen ASS dosyası okunamadı")
        try:
            os.remove(temp_file)
        except:
            pass
        return False
        
    success = write_ass_file(ass_file_path, edited_content)
    
    # Geçici dosyayı sil
    try:
        os.remove(temp_file)
    except Exception as e:
        logger.warning(f"Geçici dosya silinirken hata oluştu: {e}")
    
    return success

def preview_ass_content(ass_file_path: Union[str, Path], max_lines: int = 20) -> str:
    """
    ASS dosyasının içeriğini önizleme olarak gösterir.
    
    Args:
        ass_file_path: ASS dosyasının yolu
        max_lines: Gösterilecek maksimum satır sayısı
        
    Returns:
        str: ASS dosyasının içeriğinden bir önizleme
    """
    try:
        content = read_ass_file(ass_file_path)
        if not content:
            return "Dosya içeriği okunamadı"
            
        # Dialogue: satırlarını bul
        dialogue_lines = [line for line in content if line.startswith("Dialogue:")]
        style_lines = [line for line in content if "Style:" in line]
        
        # Önizleme içeriği oluştur
        preview_lines = []
        
        # Stil bilgilerini ekle
        if style_lines:
            preview_lines.append("# Stil Bilgileri:\n")
            for i, line in enumerate(style_lines[:5]):
                preview_lines.append(f"{line.strip()}\n")
            if len(style_lines) > 5:
                preview_lines.append(f"... (toplam {len(style_lines)} stil)\n")
        
        # Dialogue satırlarını ekle
        if dialogue_lines:
            preview_lines.append("\n# Altyazı Satırları:\n")
            for i, line in enumerate(dialogue_lines[:max_lines]):
                preview_lines.append(f"{line.strip()}\n")
            if len(dialogue_lines) > max_lines:
                preview_lines.append(f"... (toplam {len(dialogue_lines)} altyazı satırından {max_lines} tanesi gösteriliyor)\n")
        
        # Diğer içerik hakkında bilgi
        total_lines = len(content)
        shown_lines = len(style_lines) + len(dialogue_lines)
        if total_lines > shown_lines:
            preview_lines.append(f"\n# Dosya içinde toplam {total_lines} satır bulunuyor.")
            
        return ''.join(preview_lines)
    except Exception as e:
        logger.error(f"ASS önizleme hatası: {e}")
        return f"ASS dosyası önizleme hatası: {e}"

def get_subtitle_format_help() -> str:
    """
    ASS formatı hakkında kullanıcıya yardımcı bilgiler döndürür.
    
    Returns:
        str: ASS formatı hakkında yardım bilgisi
    """
    return """
ASS Altyazı Düzenleme Rehberi:

# ASS Formatı Bölümleri:
1. [Script Info] - Script hakkında genel bilgiler
2. [V4+ Styles] - Stiller (yazı tipi, renk, vs.)
3. [Events] - Altyazı satırları (Dialogue)

# Altyazı Satırı (Dialogue) Formatı:
Dialogue: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text

# Sık Kullanılan ASS Stil Komutları:
- \\N - Yeni satır
- \\b1 - Kalın yazı (\\b0 normal)
- \\i1 - İtalik yazı (\\i0 normal)
- \\u1 - Altı çizili (\\u0 normal)
- \\s1 - Üstü çizili (\\s0 normal)
- \\fsBöyüt - Yazı büyüklüğü
- \\c&Hrrggbb& veya \\1c&Hrrggbb& - Birincil renk (BGR formatında)
- \\3c&Hrrggbb& - Dış çizgi rengi
- \\4c&Hrrggbb& - Gölge rengi
- \\alpha&Haa& - Genel şeffaflık (00=opak, FF=saydam)
- \\pos(x,y) - Pozisyon belirleme
- \\move(x1,y1,x2,y2) - Hareket
- \\fad(t1,t2) - Solma süresi (t1=girişte, t2=çıkışta)
- \\kf100 - Karaoke vurgusu (100=1 saniye)

# Örnek:
Dialogue: 0,0:00:05.00,0:00:10.00,Default,,0,0,0,,{\\fad(300,500)\\c&H0000FF&}Merhaba Dünya

Bu altyazı "Merhaba Dünya" metnini kırmızı renkte gösterir, 5-10 saniye arası ekranda kalır,
0.3 saniyede görünür, 0.5 saniyede kaybolur.
"""
