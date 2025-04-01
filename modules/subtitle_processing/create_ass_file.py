from pathlib import Path
from typing import Union

# Local Application Imports
from .config import (get_available_colors, validate_and_get_color)
from .utilities import get_ass_rounded_rectangle

# Şarkı başlığının ekranda kalma süresi
title_duration = 4

def format_time(seconds: float) -> str:
    """
    Float olarak gelen zamanı ASS formatına çevirir.
    Örnek: 0:00:05.20
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours}:{minutes:02}:{secs:05.2f}"

def write_section(file, section_name: str, content: str):
    file.write(f"[{section_name}]\n")
    file.write(content)
    file.write("\n")

def write_script_info(
    file,
    title: str = "Karaoke Subtitles",
    screen_width: int = 1280,
    screen_height: int = 720
):
    content = (
        f"Title: {title}\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {screen_width}\n"
        f"PlayResY: {screen_height}\n"
        "PlayDepth: 0\n"
    )
    write_section(file, "Script Info", content)

def write_style(
    style_name: str,
    font: str,
    fontsize: int,
    primary_color: str,
    secondary_color: str,
    outline_color: str,
    shadow_color: str,
    outline_size: int,
    shadow_size: int,
    margin_v: int
):
    """
    Tek bir stil satırı üretir.
    Alignment=2 => Ortada.
    """
    return (
        f"Style: {style_name},{font},{fontsize},{primary_color},{secondary_color},"
        f"{outline_color},{shadow_color},"
        "1,0,0,0,"  # Bold=1, Italic=0, Underline=0, StrikeOut=0
        "100,100,0,0,"  # ScaleX=100, ScaleY=100, Spacing=0, Angle=0
        f"1,{outline_size},{shadow_size},"  # BorderStyle=1, Outline, Shadow
        f"2,0,0,{margin_v},1\n"  # Alignment=2 (merkez), MarginV, Encoding=1
    )

def write_styles(
    file,
    font: str = "/app/fonts/Futura XBlkCnIt BT.ttf",
    fontsize: int = 60,
    primary_color: str = "&H0000A5FF",  # Turuncu vs. aktif satır rengi
    secondary_color: str = "&H00FFFFFF",
    outline_color: str = "&H00FF8080",
    outline_size: int = 3,
    shadow_color: str = "&H00FF8080",
    shadow_size: int = 0,
    screen_height: int = 720,
):
    style_content = (
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
    )

    # Stil 1: Üst satır (aktif) => Line1
    style_content += write_style(
        style_name="Line1",
        font=font,
        fontsize=fontsize,
        primary_color=secondary_color,   
        secondary_color=secondary_color,  # Karaoke highlight için
        outline_color=outline_color,
        shadow_color=shadow_color,
        outline_size=outline_size,
        shadow_size=shadow_size,
        margin_v=int(screen_height * 0.45),
    )

    # Stil 2: Alt satır (aktif) => Line2
    style_content += write_style(
        style_name="Line2",
        font=font,
        fontsize=fontsize,
        primary_color=primary_color,
        secondary_color=secondary_color,  # Karaoke highlight
        outline_color=outline_color,
        shadow_color=shadow_color,
        outline_size=outline_size,
        shadow_size=shadow_size,
        margin_v=int(screen_height * 0.55),
    )

    # Stil 3: Bekleyen satır => NextLine
    # Burada hem PrimaryColour hem SecondaryColour beyaz olsun
    # Böylece highlight aşamasında da beyaz görünecek.
    style_content += write_style(
        style_name="NextLine",
        font=font,
        fontsize=fontsize,
        primary_color="&H00FFFFFF",   # Beyaz
        secondary_color="&H00FFFFFF", # Highlight da beyaz
        outline_color=outline_color,
        shadow_color=shadow_color,
        outline_size=outline_size,
        shadow_size=shadow_size,
        margin_v=int(screen_height * 0.45),
    )

    write_section(file, "V4+ Styles", style_content)

def write_dialogue(
    file,
    start: float,
    end: float,
    text: str,
    style: str = "Default",
    margin_l: int = 0,
    margin_r: int = 0,
    margin_v: int = 0,
    position: str = None
):
    """
    Dialog satırını ASS formatında dosyaya yazar.
    
    Parameters:
    - file: Yazılacak dosya nesnesi
    - start: Başlangıç zamanı (saniye)
    - end: Bitiş zamanı (saniye)
    - text: Diyalog metni
    - style: Kullanılacak stil (varsayılan: "Default")
    - margin_l: Sol kenar boşluğu
    - margin_r: Sağ kenar boşluğu
    - margin_v: Dikey kenar boşluğu
    - position: Metin konumu (varsayılan: None, özel konum belirtilmediğinde stil konumu kullanılır)
    """
    # Pozisyon ayarları
    if position:
        if position == "center":
            # Ekranın tam ortasına yerleştir (\an5)
            text = f"{{\\an5}}{text}"
        elif position == "lower_center":
            # Ekranın alt-orta kısmına yerleştir (\an8)
            text = f"{{\\an8}}{text}"
    
    file.write(
        f"Dialogue: 0,{format_time(start)},{format_time(end)},{style},,{margin_l},{margin_r},{margin_v},,{text}\n"
    )

def parse_artist_title(text: str):
    """
    Metin içerisinden sanatçı ve şarkı başlığını ayırır.
    Format: "Sanatçı ~ Şarkı Başlığı [~ Karaoke]"
    
    Parameters:
    - text: Ayrıştırılacak metin
    
    Returns:
    - tuple: (sanatçı, şarkı_başlığı)
    """
    parts = text.split("~")
    parts = [p.strip() for p in parts]
    
    # "Karaoke" kelimesi varsa kaldır
    if parts and parts[-1].lower() == "karaoke":
        parts.pop()
    
    if len(parts) >= 2:
        artist = parts[0]
        song_title = parts[1]
    else:
        artist = "Unknown Artist"
        song_title = parts[0] if parts else "Unknown Title"
    
    return artist, song_title

def format_time(seconds: float) -> str:
    """
    Saniye cinsinden süreyi ASS format zamanına dönüştürür: 0:00:00.00
    
    Parameters:
    - seconds: Saniye cinsinden süre
    
    Returns:
    - str: ASS formatında zaman dizgisi
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds_int = int(seconds % 60)
    centiseconds = int((seconds % 1) * 100)
    
    return f"{hours}:{minutes:02d}:{seconds_int:02d}.{centiseconds:02d}"

def write_title_event(
    file,
    title: str,
    title_duration: float,
    screen_width: int,
    screen_height: int,
    fontsize: int,
):
    # Margin ve padding'leri tamamen kaldırıyoruz
    left_margin = 200  # Mutlak değerle sabit sol boşluk
    margin_v = int(screen_height * 0.54)  # Üstten %15 aşağıda
    
    artist, song_title = parse_artist_title(title)
    text = (
        # Tam sola yapışık artist satırı (\\an7 = sol-üst hizalama)
        f"{{\\pos({left_margin},{margin_v})\\an7\\fs{fontsize}\\fn/app/fonts/Futura Md BT Bold.ttf\\b1\\1c&H0C79E3&}}{artist}"
        "\\N"
        # Tam sola yapışık şarkı adı (\\an7 ile aynı x pozisyonunda)
        f"{{\\pos({left_margin},{margin_v + int(fontsize*1.5)})\\an7\\fs{int(fontsize*0.8)}\\fn/app/fonts/Futura Heavy Italic.ttf\\b0\\1c&HFFFFFF&}}{song_title}"
    )
    write_dialogue(file, 0, title_duration, text, style="Line1")

def extend_last_event(
    file,
    verses,
    audio_duration
):
    """
    Eğer son verse’de 'Altyazı M .K.' ifadesi varsa,
    onun yerine 'Teşekkür Ederiz' yazar.
    Aksi durumda, son verse’in bitiminden videonun sonuna kadar
    'Teşekkür Ederiz' metnini ekler.
    """
    if not verses:
        # Eğer hiç verse yoksa, tüm video boyunca 'Teşekkür Ederiz' yaz
        write_dialogue(
            file,
            0,
            audio_duration,
            "{\\fad(300,0)}Teşekkür Ederiz",
            style="Line1"
        )
        return

    last_verse = verses[-1]
    # Son verse’in ham metnini oluştur
    last_verse_text = ' '.join(word.get('raw', word.get('word')) for word in last_verse["words"])

    if "Altyazı M .K." in last_verse_text:
        # Eğer son satırda istenen metin varsa, ilgili bölüm başından videonun sonuna kadar 'Teşekkür Ederiz' yazar
        write_dialogue(
            file,
            last_verse["start"],
            audio_duration,
            "{\\fad(300,0)}Teşekkür Ederiz",
            style="Line1"
        )
    else:
        # Eğer son satırda 'Altyazı M .K.' yoksa, sadece son verse bitiminden videonun sonuna kadar ekler
        if last_verse["end"] < audio_duration:
            write_dialogue(
                file,
                last_verse["end"],
                audio_duration,
                "{\\fad(300,0)}Teşekkür Ederiz",
                style="Line1"
            )

def write_countdown_event(
    file,
    countdown_start: float,
    countdown_end: float,
    screen_width: int,
    screen_height: int,
    fontsize: int,
):
    total_seconds = int(countdown_end - countdown_start)
    pos_x = screen_width // 2
    pos_y = screen_height // 2
    for i in range(total_seconds, 0, -1):
        event_start = countdown_start + (total_seconds - i)
        event_end = event_start + 1
        if event_end > countdown_end:
            event_end = countdown_end
        text = f"{{\\pos({pos_x},{pos_y})\\fs{fontsize}\\b1}}{i}"
        write_dialogue(file, event_start, event_end, text, style="Line1")

def split_text_into_chunks(verse, max_chars_per_line=40):
    """
    Verse metnini yaklaşık olarak max_chars_per_line uzunluğundaki parçalara böler.
    Her parça en az bir kelime içerir ve kelimeleri bölmez.
    
    Parameters:
    - verse: Parçalanacak verse sözlük nesnesi (words listesini içerir)
    - max_chars_per_line: Bir satırdaki maksimum karakter sayısı
    
    Returns:
    - list: Her bir eleman bir chunk'ı temsil eden sözlüktür 
            (start, end, words, text_length bilgilerini içerir)
    """
    chunks = []
    current_chunk = {
        "start": verse["words"][0]["start"] if verse["words"] else verse["start"],
        "end": None,
        "words": [],
        "text_length": 0
    }
    
    for word in verse["words"]:
        # Kelimenin raw metni veya normal metni al
        word_text = word.get('raw', word['word'])
        word_length = len(word_text) + 1  # +1 boşluk için
        
        # Eğer mevcut chunk boşsa veya yeni kelime eklenince sınırı aşmıyorsa
        if not current_chunk["words"] or current_chunk["text_length"] + word_length <= max_chars_per_line:
            current_chunk["words"].append(word)
            current_chunk["text_length"] += word_length
            current_chunk["end"] = word["end"]
        else:
            # Chunk'ı tamamla ve yeni bir chunk başlat
            chunks.append(current_chunk)
            current_chunk = {
                "start": word["start"],
                "end": word["end"],
                "words": [word],
                "text_length": word_length
            }
    
    # Son chunk'ı da ekle (eğer boş değilse)
    if current_chunk["words"]:
        chunks.append(current_chunk)
    
    return chunks

def format_chunk_text(chunk, add_fade=True, add_loader=False):
    """
    Verilen chunk'ı ASS formatında metin olarak biçimlendirir.
    
    Parameters:
    - chunk: Metin parçası (kelimeleri ve zamanlamaları içerir)
    - add_fade: Fade efekti eklensin mi
    - add_loader: ➤➤➤➤ göstergesi eklensin mi
    
    Returns:
    - str: ASS formatında biçimlendirilmiş metin
    """
    text_parts = []
    
    # Loader ekle
    if add_loader:
        loader_kf = 200  # 2 saniyelik efekt (kf birimi ~ 0.01s)
        text_parts.append(f"{{\\kf{loader_kf}}}➤➤➤➤")
    
    # Kelimeleri ASS formatında ekle
    for word in chunk["words"]:
        word_duration_cs = int((word["end"] - word["start"]) * 100)
        text_parts.append(f"{{\\kf{word_duration_cs}}}{word.get('raw', word['word'])}")
    
    # Fade efekti ekle
    if add_fade:
        return f"{{\\fad(300,0)}}{' '.join(text_parts)}"
    else:
        return ' '.join(text_parts)

def write_scrolling_lyrics_events(
    file,
    verses: list,
    screen_width: int,
    screen_height: int,
    fontsize: int = 60,
):
    r"""
    Her iki consecutive (ardışık) verse'i tek bir dialogue event'inde birleştirir.
    Orijinalde:
      - even index (Line1): plain metin (üst satır)
      - odd index (Line2): karaoke efektli metin (alt satır)
    Şimdi:
      Sadece "Line2" stili kullanılarak, even index'teki (plain) metin üst satıra,
      odd index'teki (karaoke efektli) metin ise alt satıra yerleştirilir.
    Event'in başlangıç zamanı even index'in start'ı,
    bitiş zamanı ise odd index'in end'i olarak ayarlanır.
    """
    loader_threshold = 5.0  # saniye

    i = 0
    while i < len(verses):
        # Mevcut verse ile bir önceki verse arasında 5+ saniye boşluk varsa "MELODI" göster
        if i > 0:
            current_verse = verses[i]
            prev_verse = verses[i-1]
            gap = current_verse["start"] - prev_verse["end"]
            
            if gap >= loader_threshold:
                melodi_start = prev_verse["end"] + 0.3  # küçük bir gecikme ekle
                melodi_end = current_verse["start"] - 0.3  # erken bitir
                
                # "MELODI" yazısını beyaz renkle göster
                melodi_text = "{\\fad(300,300)\\c&HFFFFFF&}MELODI"
                write_dialogue(file, melodi_start, melodi_end, melodi_text, style="Line2", position="center")

        if i + 1 < len(verses) and verses[i + 1]["start"] - verses[i]["end"] < loader_threshold:
            # İki verse'i birleştir
            # even index: plain (original Line1), odd index: karaoke (original Line2)
            verse_plain = verses[i]
            verse_karaoke = verses[i + 1]

            # Karaoke efekt için loader kontrolü:
            if i == 0:
                add_loader = True
            else:
                prev_verse_karaoke = verses[i - 1]  # önceki çiftin karaoke versiyonu
                gap = verse_karaoke["start"] - prev_verse_karaoke["end"]
                add_loader = (gap >= loader_threshold)

            # Loader efekti için süre ve başlangıç zamanı hesaplaması:
            if add_loader:
                # ➤➤➤➤ göstereceğiz, başlangıcı 2 saniye öne al
                t_start_combined = max(0, verse_plain["start"] - 2)
                loader_kf = 200  # 2 saniyelik efekt (kf birimi ~ 0.01s)
            else:
                t_start_combined = verse_plain["start"]
                loader_kf = 0

            # Plain metni oluştur (verse_plain'dan)
            plain_text_parts = []

            # "➤➤➤➤" üst satıra eklenecek
            if loader_kf > 0:
                plain_text_parts.append(f"{{\\kf{loader_kf}}}➤➤➤➤")

            for word in verse_plain["words"]:
                word_duration_cs = int((word["end"] - word["start"]) * 100)
                plain_text_parts.append(f"{{\\kf{word_duration_cs}}}{word.get('raw', word['word'])}")
            plain_text = f"{{\\fad(300,0)}}{' '.join(plain_text_parts)}"

            # Karaoke efektli metni oluştur (verse_karaoke'dan)
            karaoke_parts = []
            
            for word in verse_karaoke["words"]:
                word_duration_cs = int((word["end"] - word["start"]) * 100)
                karaoke_parts.append(f"{{\\kf{word_duration_cs}}}{word.get('raw', word['word'])}")
            karaoke_text = f"{{\\fad(300,0)}}{' '.join(karaoke_parts)}"
            
            # Birleştirilmiş metin: Üst satırda plain metin, alt satırda karaoke efektli metin
            combined_text = plain_text + "\\N" + karaoke_text

            # Event zamanlaması: başlama uygun şekilde ayarlandı, bitiş odd index'in end'i
            combined_end = verse_karaoke["end"]

            write_dialogue(file, t_start_combined, combined_end, combined_text, style="Line2")
            i += 2
        else:
            # Tek verse göster (çünkü sonraki verse ile arasında 5 saniyeden fazla süre var veya son verse)
            verse = verses[i]
            
            # Bir sonraki verse ile arasında 5+ saniye var mı kontrol et (eğer mevcut değilse zaten tek gösterilecek)
            next_verse_far = (i + 1 >= len(verses)) or (verses[i + 1]["start"] - verse["end"] >= loader_threshold)
            
            if i == 0:
                add_loader = True
            else:
                prev_verse = verses[i - 1]
                gap = verse["start"] - prev_verse["end"]
                add_loader = (gap >= loader_threshold)
            
            # ➤➤➤➤ için başlangıç zamanını ayarla
            if add_loader:
                t_start = max(0, verse["start"] - 2)
                loader_kf = 200  # 2 saniyelik efekt (kf birimi ~ 0.01s)
            else:
                t_start = verse["start"]
                loader_kf = 0

            text_parts = []
            
            # Sadece başlangıçta veya boşluk varsa ➤➤➤➤ ekle
            if loader_kf > 0:
                text_parts.append(f"{{\\kf{loader_kf}}}➤➤➤➤")
                
            for word in verse["words"]:
                word_duration_cs = int((word["end"] - word["start"]) * 100)
                text_parts.append(f"{{\\kf{word_duration_cs}}}{word.get('raw', word['word'])}")
                
            text = f"{{\\fad(300,0)}}{' '.join(text_parts)}"
            
            # Tek satır olduğunda ve bir sonraki verse uzaktaysa, metni daha aşağıda göster
            position = "lower_center" if next_verse_far else "Line2"
            
            write_dialogue(file, t_start, verse["end"], text, style="Line2", position=position)
            i += 1


def create_ass_file(
    verses_data: list,
    output_path: Union[str, Path],
    audio_duration: float,
    font: str = "/app/fonts/Futura XBlkCnIt BT.ttf",
    fontsize: int = 60,
    primary_color: str = "&H0000A5FF",
    secondary_color: str = "&H00FFFFFF",
    outline_color: str = "&H00FF8080",
    outline_size: int = 3,
    shadow_color: str = "&H00FF8080",
    shadow_size: int = 0,
    title: str = "Karaoke",
    screen_width: int = 1280,
    screen_height: int = 720,
    verses_before: int = 1,
    verses_after: int = 1,
    loader_threshold: float = 5.0,
):
    """
    Tüm .ass dosyasını oluşturur:
      - Başlık gösterimi
      - Countdown
      - 2 satırlı verse yapısı (alternatif olarak satır 1 ve satır 2'de sırayla gösterim)
      - Gap < 5 ise üst satır kaybolmadan bekler
    """
    try:
        available_colors = get_available_colors()
        primary_color = validate_and_get_color(primary_color, "&H0000A5FF", available_colors)
        secondary_color = validate_and_get_color(secondary_color, "&H00FFFFFF", available_colors)
        outline_color = validate_and_get_color(outline_color, "&H00FF8080", available_colors)
        shadow_color = validate_and_get_color(shadow_color, "&H00FF8080", available_colors)

        with open(output_path, "w", encoding="utf-8") as file:
            # Script Info
            write_script_info(file, title=title, screen_width=screen_width, screen_height=screen_height)
            # Styles
            write_styles(
                file,
                font=font,
                fontsize=fontsize,
                primary_color=primary_color,
                secondary_color=secondary_color,
                outline_color=outline_color,
                outline_size=outline_size,
                shadow_color=shadow_color,
                shadow_size=shadow_size,
                screen_height=screen_height
            )
            # Events Header
            write_section(file, "Events", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text")
            # Title
            write_title_event(file, title, title_duration, screen_width, screen_height, fontsize=fontsize + 12)

            # 2 satırlı verse yapısı (mod kontrolü ile sırayla)
            write_scrolling_lyrics_events(file, verses_data, screen_width, screen_height, fontsize=fontsize)

            # Son satırı uzat veya değiştir
            extend_last_event(file, verses_data, audio_duration)

    except Exception as e:
        raise RuntimeError(f"Failed to create ASS file: {e}") from e
