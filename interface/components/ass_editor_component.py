"""
ASS editör bileşeni, Gradio UI'a entegre edilebilir bir ASS düzenleyici sağlar.
"""
import gradio as gr
import os

def create_ass_editor_component(launch_editor_func):
    """
    ASS editör bileşenini oluşturur ve döndürür
    
    Args:
        launch_editor_func: ASS editörünü başlatan fonksiyon
        
    Returns:
        tuple: ASS editör düğmesi ve yardımcı işlevleri
    """
    
    # Docker ortamında çalışıp çalışmadığını kontrol et
    is_docker = os.environ.get('SYSTEM', '').lower() == 'spaces'
    docker_host = os.environ.get('GRADIO_SERVER_NAME', 'localhost')
    port = 7880
    
    # Buton için başlangıç metni oluştur
    button_text = "🔍 ASS Editörünü Aç"
    
    # ASS editör düğmesi
    editor_button = gr.Button(
        button_text,
        variant="secondary",
        size="sm"
    )
    
    # Docker ortamında URL bilgisini eklemek için
    def generate_editor_url(working_dir):
        """
        Editörü başlatır ve URL bilgisini döndürür
        """
        # Editörü başlat
        launch_editor_func(working_dir)
        
        if is_docker:
            # Docker uyarı mesajı ve URL
            url = f"http://{docker_host}:{port}/"
            if docker_host == '0.0.0.0':
                url = f"http://localhost:{port}/"
                
            # Kullanıcıya bilgi ver
            return gr.update(value=f"ASS Editör URL: {url}")
        else:
            # Normal modda
            return gr.update(value="ASS Editör Açıldı!")
    
    # Buton metnini sıfırla
    def reset_button_text():
        return gr.update(value=button_text)
    
    # Yardımcı metin (ASS formatı hakkında bilgi)
    help_text = r"""
### ASS Altyazı Formatı Kılavuzu

ASS (Advanced SubStation Alpha) altyazı dosyaları aşağıdaki bölümlerden oluşur:

1. **[Script Info]** - Script hakkında genel bilgiler
2. **[V4+ Styles]** - Stil tanımları (yazı tipi, renk vs.)
3. **[Events]** - Altyazı olayları (Dialogue)

**Altyazı satırı formatı:**
```
Dialogue: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
```

**Örnek altyazı satırı:**
```
Dialogue: 0,0:00:05.00,0:00:10.00,Default,,0,0,0,,{\fad(300,0)}Merhaba Dünya
```

**Sık kullanılan komutlar:**
- \N - Yeni satır
- \b1 - Kalın yazı (\b0 normal)
- \i1 - İtalik yazı (\i0 normal)
- \c&Hrrggbb& - Metin rengi
- \fad(t1,t2) - Solma efekti
- \pos(x,y) - Konumlandırma
"""
    
    # Yardım metni bileşeni
    ass_help = gr.Markdown(help_text, visible=False)
    
    # Yardım göster/gizle düğmesi
    help_toggle = gr.Button("❓ ASS Format Yardımı", size="sm")
    
    # Yardım göster/gizle işlevi
    def toggle_help(visible):
        return gr.update(visible=not visible)
    
    # Buton olayları
    editor_button.click(
        fn=generate_editor_url,
        inputs=[gr.State(lambda: None)],  # working_dir state değişkeni burada olmalı
        outputs=[editor_button]
    ).then(
        fn=reset_button_text,
        inputs=[],
        outputs=[editor_button]
    )
    
    # Yardım göster/gizle olayı
    help_toggle.click(
        fn=toggle_help,
        inputs=[ass_help],
        outputs=[ass_help]
    )
    
    return editor_button, ass_help, help_toggle