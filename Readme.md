🎤 AI Karaoke Studio

AI Karaoke Studio, herhangi bir şarkı dosyasını alıp tamamen otomatik şekilde:
✅ Vokali ve altyapıyı ayıran,
✅ Vokal kısmından otomatik şarkı sözlerini çıkaran,
✅ Orijinal sözlerle kıyaslayarak AI ile düzelten,
✅ Ve son olarak altyazılı karaoke videosu üreten açık kaynak bir uygulamadır.


---

🚀 Özellikler

🎶 Vokal ve Enstrümantal Ayırma (Source Separation)
Demucs modeli kullanılarak ses kanalları ayrılır.

🗣️ Otomatik Şarkı Sözü Çıkartma (Speech-to-Text)
OpenAI Whisper ile vokal kanalından zaman kodlu şarkı sözleri otomatik çıkarılır.

🎼 Şarkı ve Sanatçı Adı Tespiti
Whisper çıktısından veya dosya isminden otomatik belirlenir.

📝 Genius API ile Orijinal Lyrics Çekme
Şarkının orijinal sözleri Genius üzerinden alınır.

🤖 Gemini LLM ile Lyrics Düzeltme ve Zaman Kodlama Korumalı Senkronizasyon
Whisper çıktısı ile Genius lyrics karşılaştırılır, AI destekli düzeltme yapılır.
(Timecode bozulmadan içerik düzeltilir.)

📋 SRT Formatında Altyazı Üretimi
Düzeltilmiş lyrics .srt formatında altyazı dosyasına dönüştürülür.

🎥 FFmpeg ile Otomatik Karaoke Video Üretimi
Enstrümantal altyapı ve altyazı birleştirilerek karaoke videosu hazırlanır.



---

🧱 Kullanılan Teknolojiler

Python (AI işlemleri, API entegrasyonları)

.NET Framework / Windows Forms (Kullanıcı arayüzü, işlem kontrolü)

FFmpeg (Audio/Video işleme)

Demucs (Source Separation)

OpenAI Whisper (Speech Recognition)

Genius API (Orijinal şarkı sözleri)

Gemini API (AI destekli lyrics düzeltme)



---

🛠️ Kurulum

1. Gerekli Python bağımlılıklarını yükleyin:



pip install -r requirements.txt

2. FFmpeg sisteminizde kurulu olmalı. FFmpeg İndir


3. Demucs ve Whisper için gerekli model dosyalarını indirin.


4. API Anahtarlarınızı ayarlayın:



Genius API

Gemini API (Google AI)


5. .NET projesini derleyip başlatın.




---

📌 Kullanım

1. Şarkınızı yükleyin (MP3 formatında).


2. “İşle” butonuna tıklayın.


3. İşlem tamamlanınca çıkış klasöründe:



Vokal

Enstrümantal

SRT altyazı dosyası

Final karaoke videosu (mp4)
…bulunacaktır.



---

🧪 Yol Haritası (To Do)

Çoklu dil desteği

Batch Processing (Toplu işlem)

Daha gelişmiş UI iyileştirmeleri

FFmpeg parametrelerinin UI’dan ayarlanabilir olması



---

📄 Lisans

MIT Lisansı


---

👋 Katkıda Bulunmak İster misiniz?

Pull Request’ler ve önerilere her zaman açığım.
Proje ile ilgileniyorsanız issue açabilir, fork edip geliştirebilir, ya da yorum bırakabilirsiniz.


---

📫 İletişim

Her türlü soru, öneri ve geri bildirim için:
LinkedIn Profilim
veya
kadirertancam@gmail.com
