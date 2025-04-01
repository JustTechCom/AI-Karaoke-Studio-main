# Standard Library Imports
from pathlib import Path
from typing import Union, Optional
import logging
import os
import tempfile
import shutil
import webbrowser
import time
import http.server
import socketserver
import threading
import urllib.parse

# Initialize Logger
logger = logging.getLogger(__name__)

# Basit HTTP sunucusu için handler
class EditorHTTPHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.editor_base_path = kwargs.pop('editor_base_path', '')
        super().__init__(*args, **kwargs)

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        if parsed_path.path == '/':
            self.path = '/subtitle_editor.html'
        
        # Yolu editor_base_path'e göre oluştur
        if self.editor_base_path:
            full_path = os.path.join(self.editor_base_path, self.path.lstrip('/'))
            if os.path.exists(full_path):
                self.path = full_path
        
        return http.server.SimpleHTTPRequestHandler.do_GET(self)

    def log_message(self, format, *args):
        # HTTP sunucu günlüklerini devre dışı bırak
        pass

class AssVisualEditor:
    """
    ASS dosyalarını görsel olarak düzenlemek için bir web tabanlı editör sağlar.
    """
    def __init__(self, static_path: Union[str, Path], port: int = 7880):
        """
        ASS görsel editörünü başlatır.
        
        Args:
            static_path: Statik dosyaların bulunduğu klasör
            port: Web sunucusunun çalışacağı port
        """
        self.static_path = Path(static_path)
        self.port = port
        self.server = None
        self.server_thread = None
        self.temp_dir = None
        
    def _start_server(self):
        """
        HTTP sunucusunu başlat
        """
        try:
            # Eğer sunucu zaten çalışıyorsa, durduralım
            if self.server:
                self.stop_server()
            
            # Geçici dizin oluştur
            self.temp_dir = tempfile.mkdtemp(prefix="karaoke_editor_")
            
            # Statik dosyaları geçici dizine kopyala
            editor_html = self.static_path / "subtitle_editor.html"
            if editor_html.exists():
                shutil.copy(editor_html, self.temp_dir)
            else:
                logger.error(f"Editor HTML dosyası bulunamadı: {editor_html}")
                return False
            
            # HTTP sunucusunu başlat
            handler = lambda *args, **kwargs: EditorHTTPHandler(*args, editor_base_path=str(self.static_path), **kwargs)
            self.server = socketserver.TCPServer(("0.0.0.0", self.port), handler)
            
            # Sunucuyu ayrı bir thread'da başlat
            self.server_thread = threading.Thread(target=self.server.serve_forever)
            self.server_thread.daemon = True
            self.server_thread.start()
            
            logger.info(f"ASS editör sunucusu başlatıldı: http://localhost:{self.port}")
            return True
            
        except Exception as e:
            logger.error(f"Sunucu başlatma hatası: {e}")
            return False
    
    def stop_server(self):
        """
        HTTP sunucusunu durdur
        """
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
            self.server_thread = None
            
            # Geçici dizini temizle
            if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                self.temp_dir = None
                
            logger.info("ASS editör sunucusu durduruldu")
    
    def edit_ass_file(self, ass_file_path: Union[str, Path], mp3_file_path: Optional[Union[str, Path]] = None) -> bool:
        """
        ASS dosyasını görsel editörle düzenler.
        
        Args:
            ass_file_path: Düzenlenecek ASS dosyasının yolu
            mp3_file_path: Ses dosyasının yolu (opsiyonel)
            
        Returns:
            bool: Düzenleme başarılı ise True, değilse False
        """
        try:
            ass_file_path = Path(ass_file_path)
            
            # ASS dosyasının var olup olmadığını kontrol et
            if not ass_file_path.exists():
                logger.error(f"ASS dosyası bulunamadı: {ass_file_path}")
                return False
            
            # Eğer sunucu başlatılmamışsa, başlat
            if not self.server:
                if not self._start_server():
                    return False
            
            # Tarayıcıyı aç
            webbrowser.open(f"http://localhost:{self.port}")
            
            print("\n=======================================")
            print("ASS altyazı düzenleyici tarayıcıda açıldı.")
            print("Düzenlemelerinizi yapın ve 'Değişiklikleri Kaydet' düğmesine tıklayın.")
            print("Düzenlemek üzere olan dosya:", ass_file_path)
            print("Düzenlemeyi tamamladıktan sonra 10 saniye bekleyin...")
            print("=======================================\n")
            
            # Kullanıcıya düzenleme yapmak için zaman tanı (Docker'da input() yerine time.sleep())
            time.sleep(10)
            
            # Düzenleyici kapatıldıktan sonra sunucuyu durdur
            self.stop_server()
            
            return True
            
        except Exception as e:
            logger.error(f"ASS görsel düzenleme hatası: {e}")
            self.stop_server()
            return False

# Tek bir istemci için kullanım örneği
def edit_ass_with_visual_editor(ass_file_path: Union[str, Path], mp3_file_path: Optional[Union[str, Path]] = None) -> bool:
    """
    ASS dosyasını görsel editörde düzenler.
    
    Args:
        ass_file_path: Düzenlenecek ASS dosyasının yolu
        mp3_file_path: Ses dosyasının yolu (opsiyonel)
        
    Returns:
        bool: Düzenleme başarılı ise True, değilse False
    """
    try:
        # Projenin root dizinini bul
        current_path = Path(__file__).resolve()
        project_root = current_path.parent.parent.parent
        static_path = project_root / "interface" / "static"
        
        editor = AssVisualEditor(static_path=static_path)
        
        # Docker ortamında çalışıp çalışmadığımızı kontrol etmek için bir ortam değişkeni kontrolü yap
        docker_env = os.environ.get('SYSTEM', '').lower() == 'spaces'
        
        if docker_env:
            # Docker ortamında çalışıyoruz, input() kullanma
            print("\n=======================================")
            print("ASS altyazı editörü açılıyor (Docker ortamı)...")
            print("Tarayıcı penceresi açılacak ve editör yüklenecek.")
            print("Düzenlemeyi tamamladıktan sonra 10 saniye bekleyin.")
            print("=======================================")
            
            # Sunucuyu başlat
            if not editor._start_server():
                return False
                
            # Docker ortamında, host ismini al
            docker_ip = os.environ.get('GRADIO_SERVER_NAME', '0.0.0.0')  # Docker Cloud'da IP olarak Gradio server nameı kullan
            url = f"http://{docker_ip}:{editor.port}"
            
            # URL'i temizle
            if docker_ip == '0.0.0.0':
                url = f"http://localhost:{editor.port}"  # Yerel geliştirme için
            
            print(f"Editör URL: {url}")
            
            # Uyarı göster
            print("\n\u26a0️ Docker ortamında çalışıldığında, lütfen web tarayıcınızda yukarıdaki URL'yi manuel olarak açın.")
            print("Düzenlemeyi tamamladıktan sonra bekleyiniz, 30 saniye sonra otomatik olarak kapanacaktır.")
            
            # Bekle
            time.sleep(30)  # Docker için daha uzun bir süre bekle
            
            # Sunucuyu durdur
            editor.stop_server()
            return True
        else:
            # Normal ortamda çalışıyoruz, normal yöntemi kullan
            return editor.edit_ass_file(ass_file_path, mp3_file_path)
        
    except Exception as e:
        logger.error(f"ASS görsel düzenleme hatası: {e}")
        return False
