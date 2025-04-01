import gradio as gr
import pandas as pd
import os

# Local Application Imports
from .callbacks import (
    process_audio_callback,
    fetch_reference_lyrics_callback,
    save_fetched_lyrics_callback,
    modify_lyrics_callback,
    generate_font_preview_callback,
    generate_subtitles_and_video_callback,
    save_metadata_callback,
)
from .helpers import (
    check_modify_ai_availability,
    check_generate_karaoke_availability,
    get_effect_video_list,
    get_available_languages,
)
from modules import (
    get_available_colors,
    get_font_list,
)
from modules.subtitle_processing.ass_editor import get_subtitle_format_help
from .components.ass_editor_component import create_ass_editor_component

# Main App Interface
def main_app(cache_dir, fonts_dir, output_dir, project_root):
    gr.set_static_paths(fonts_dir)
    with gr.Blocks(theme='shivi/calm_seafoam') as app:
        effects_dir = project_root / "effects"

        # Altyazılar için mevcut yazı tipleri ve renkleri al
        available_fonts = get_font_list(fonts_dir)
        available_colors = get_available_colors()
        available_effects = ["Yok"] + get_effect_video_list(effects_dir)

        # get_available_languages() fonksiyonu bir sözlük döndürüyor.
        # Aşağıdaki kodda, sözlük anahtarlarını (dil isimlerini) önce listeye alıyoruz,
        # sonra "turkish" ve "english" (küçük harf karşılaştırmasıyla) varsa bunları listenin
        # başına yerleştiriyoruz.
        langs = list(get_available_languages().keys())

        langs_lower = [lang.lower() for lang in langs]
        if "turkish" in langs_lower:
            index = langs_lower.index("turkish")
            turkish_lang = langs.pop(index)
            langs.insert(0, turkish_lang)

        # "turkish" eklenmişse, "english" ikinci sıraya yerleştiriyoruz.
        langs_lower = [lang.lower() for lang in langs]
        if "english" in langs_lower:
            index = langs_lower.index("english")
            english_lang = langs.pop(index)
            langs.insert(1, english_lang)

        available_langs = ["Otomatik Algılama"] + langs
        ##############################################################################
        # DURUM DEĞİŞKENLERİ
        ##############################################################################
        state_working_dir = gr.State(value="")
        state_lyrics_json = gr.State(value=None)
        state_lyrics_display = gr.State(value="")
        state_fetched_lyrics_json = gr.State(value=None)
        state_fetched_lyrics_display = gr.State(value="")
        state_artist_name = gr.State(value="")
        state_song_name = gr.State(value="")
        ##############################################################################
        # SAYFA BAŞLIĞI
        ##############################################################################
        gr.HTML("<hr>")
        gr.Markdown("# 🎤 Karaoke Oluşturucu")
        gr.HTML("<hr>")
        ##############################################################################
        # BÖLÜM 1: SES İŞLEME VE TRANSKRİPSİYON
        ##############################################################################
        gr.Markdown("## 1) Ses İşleme ve Vokal Transkripsiyonu")
        gr.Markdown("### _Ses işleme ve vokal transkripsiyonu başlatmak için bir ses dosyası yükleyin._")
        with gr.Row():
            with gr.Column():
                audio_input = gr.Audio(
                    label="Ses Yükle",
                    type="filepath",
                    sources="upload",
                )
                # --- GELİŞTİRİCİ AYARLARI ---
                with gr.Accordion("Geliştirici Ayarları", open=False):
                    force_meta_fetch = gr.Checkbox(
                        label="Meta Veri Çekimini Tekrar Yap?",
                        value=False,
                        info="Meta verileri (sanatçı, şarkı adı vb.) yeniden çekmeyi zorlar."
                    )
                    force_audio_processing = gr.Checkbox(
                        label="Ses İşlemini Tekrar Yap?",
                        value=False,
                        info="Ses işlemini (stem ayrımı, stem birleştirme vb.) yeniden çalıştırmayı zorlar."
                    )
                    force_transcription = gr.Checkbox(
                        label="Vokal Transkripsiyonunu Tekrar Yap?",
                        value=False,
                        info="Vokal transkripsiyonunu yeniden çalıştırmayı zorlar."
                    )
                with gr.Accordion("Transkripsiyon Doğruluk Ayarları (Gelişmiş)", open=False):
                    with gr.Row():
                        with gr.Column():
                            beam_size_input = gr.Slider(
                                minimum=1, maximum=20, step=1, value=15,
                                label="Beam Boyutu (Yüksek = Daha Fazla Doğruluk, Daha Yavaş)"
                            )
                            best_of_input = gr.Slider(
                                minimum=1, maximum=10, step=1, value=5,
                                label="En İyisi (Yüksek = Daha Fazla Alternatif Değerlendirir)"
                            )
                        with gr.Column():
                            patience_input = gr.Number(
                                value=3.0, label="Sabır (Segmentler için Ek Süre)"
                            )
                            condition_toggle = gr.Checkbox(
                                label="Önceki Metni Koşul Olarak Kullan",
                                value=False,
                                info="Karaoke için, tekrar eden kelimeleri yakalamaya yardımcı olması açısından False olarak ayarlayın."
                            )
                        with gr.Column():
                            compression_threshold_input = gr.Slider(
                                minimum=1.0, maximum=2.0, step=0.1, value=1.3,
                                label="Sıkıştırma Oranı Eşiği"
                            )
                            temperature_input = gr.Slider(
                                minimum=0.0, maximum=1.0, step=0.1, value=0.0,
                                label="Sıcaklık (0 = Deterministik)"
                            )
                    with gr.Row():
                        language_input = gr.Dropdown(
                            choices=available_langs,
                            label="Transkripsiyon Dili",
                            value="Otomatik Algılama",
                            info="Otomatik algılama güvenilir değilse bir dil seçin; aksi takdirde 'Otomatik Algılama'yı seçin."
                        )
                # Sesi İşle butonu
                process_audio_button = gr.Button(
                    "Sesi İşle",
                    variant="primary"
                )
        gr.HTML("<hr>")
        ##############################################################################
        # BÖLÜM 2: ŞARKI SÖZÜ DÜZELTME VE YENİDEN HİZALAMA
        ##############################################################################
        gr.Markdown("## 2) Şarkı Sözü Düzeltme ve Yeniden Hizalama")
        gr.Markdown("### _Oluşturulan ve zamanlanmış vokal transkripsiyonu, güvenilir bir şarkı sözü kaynağı referansı kullanılarak düzeltilsin._")
        with gr.Row():
            with gr.Column():
                artist_name_input = gr.Textbox(
                    label="Sanatçı Adı",
                    lines=1,
                    interactive=True,
                )
            with gr.Column():
                song_name_input = gr.Textbox(
                    label="Şarkı Adı",
                    lines=1,
                    interactive=True,
                )
        save_metadata_button = gr.Button("💾 Sanatçı ve Şarkı Adını Kaydet")
        with gr.Row():
            with gr.Column():
                gr.Markdown("##### Düzeltme ve yeniden hizalama için referans şarkı sözleri.")
                fetched_lyrics_box = gr.Textbox(
                    label="Referans Şarkı Sözleri (Düzenlenebilir)",
                    lines=20,
                    interactive=True,
                )
                with gr.Row():
                    fetch_button = gr.Button("🌐 Referans Şarkı Sözlerini Al")
                    save_button = gr.Button("💾 Referans Şarkı Sözlerini Güncelle")
            with gr.Column():
                gr.Markdown("##### Kelime zamanlamalı Karaoke Altyazıları (düzeltilmiş).")
                raw_lyrics_box = gr.Dataframe(
                    value=pd.DataFrame({
                        "Karaoke için Kullanılan İşlenmiş Şarkı Sözleri": ["" for _ in range(12)]
                    }),
                    headers=["Karaoke için Kullanılan İşlenmiş Şarkı Sözleri"],
                    label="Karaoke için Kullanılan İşlenmiş Şarkı Sözleri",
                    datatype=["str"],
                    interactive=False,
                    show_label=False,
                    max_height=465,
                )
                with gr.Row():
                    modify_button = gr.Button(
                        "🪄 AI ile Düzenle",
                        variant="primary",
                        interactive=False
                    )
        # --- GELİŞTİRİCİ AYARLARI ---
        with gr.Row():
            with gr.Accordion("Geliştirici Ayarları", open=False):
                force_refetch_lyrics = gr.Checkbox(
                    label="Referans Şarkı Sözlerini Tekrar Al?",
                    value=False,
                    info="Yerel `reference_lyrics.json` dosyasını görmezden gelerek API'den yeni şarkı sözlerini çeker."
                )
                force_ai_modification = gr.Checkbox(
                    label="AI Şarkı Sözü Düzenlemesini Tekrar Yap?",
                    value=False,
                    info="Önceden AI tarafından oluşturulmuş `modified_lyrics.json` dosyasını görmezden gelerek şarkı sözlerini AI ile yeniden hizalar."
                )
        gr.HTML("<hr>")
        ##############################################################################
        # BÖLÜM 3: ALTYAZILAR VE VİDEO OLUŞTURMA
        ##############################################################################
        gr.Markdown("## 3) Altyazılar ve Video Oluşturma")
        with gr.Row():
            font_input = gr.Dropdown(
                choices=list(available_fonts.keys()),
                value="Futura XBlkCnIt BT",
                label="Yazı Tipi"
            )
            primary_color_input = gr.Dropdown(
                choices=available_colors,
                value="Orange",
                label="Yazı Rengi"
            )
            secondary_color_input = gr.Dropdown(
                choices=available_colors,
                value="White",
                label="Yazı Vurgulama Rengi"
            )
            effect_dropdown = gr.Dropdown(
                label="Arka Plan Video Efektleri",
                choices=available_effects,
                value="background-first.mp4",
            )
        subtitle_preview_output = gr.HTML(label="Altyazı Önizlemesi",)
        with gr.Accordion("Altyazı Özelleştirme Seçenekleri", open=False):
            with gr.Row():
                fontsize_input = gr.Slider(
                    minimum=12,
                    maximum=84,
                    step=1,
                    value=42,
                    label="Yazı Boyutu",
                )
                loader_threshold_input = gr.Slider(
                    minimum=5.0,
                    maximum=15.0,
                    step=0.5,
                    value=5.0,
                    label="Yükleme Eşiği (saniye)"
                )
            with gr.Row():
                with gr.Column():
                    outline_color_input = gr.Dropdown(
                        choices=available_colors,
                        value="Black",
                        label="Kenarlık Rengi"
                    )
                    outline_size_input = gr.Slider(
                        minimum=0,
                        maximum=7,
                        step=1,
                        value=1,
                        label="Kenarlık Kalınlığı",
                    )
                with gr.Column():
                    shadow_color_input = gr.Dropdown(
                        choices=available_colors,
                        value="Black",
                        label="Gölge Rengi"
                    )
                    shadow_size_input = gr.Slider(
                        minimum=0,
                        maximum=7,
                        step=1,
                        value=0,
                        label="Gölge Boyutu",
                    )
                with gr.Column():
                    verses_before_input = gr.Slider(
                        minimum=1,
                        maximum=3,
                        step=1,
                        value=2,
                        label="Önceki Verseler",
                    )
                    verses_after_input = gr.Slider(
                        minimum=1,
                        maximum=3,
                        step=1,
                        value=2,
                        label="Sonraki Verseler",
                    )
        with gr.Accordion("Gelişmiş Video Ayarları", open=False):
            with gr.Row():
                with gr.Column():
                    resolution_input = gr.Dropdown(
                        choices=["640x480", "1280x720", "1920x1080"],
                        value="1280x720",
                        label="Çözünürlük"
                    )
                    preset_input = gr.Dropdown(
                        choices=["ultrafast", "fast", "medium", "slow"],
                        value="fast",
                        label="FFmpeg Ön Ayarı"
                    )
                with gr.Column():
                    crf_input = gr.Slider(
                        minimum=0,
                        maximum=51,
                        step=1,
                        value=23,
                        label="CRF (Video Kalitesi)"
                    )
                    fps_input = gr.Slider(
                        minimum=15,
                        maximum=60,
                        step=1,
                        value=24,
                        label="Saniyedeki Kare Sayısı"
                    )
                with gr.Column():
                    bitrate_input = gr.Dropdown(
                        label="Video Bit Hızı",
                        choices=["1000k", "2000k", "3000k", "4000k", "5000k", "Auto"],
                        value="3000k",
                        interactive=True
                    )
                    audio_bitrate_input = gr.Dropdown(
                        label="Ses Bit Hızı",
                        choices=["64k", "128k", "192k", "256k", "320k", "Auto"],
                        value="192k",
                        interactive=True
                    )
        with gr.Accordion("Geliştirici Ayarları", open=False):
            with gr.Row():
                force_subtitles_overwrite = gr.Checkbox(
                    label="Karaoke Altyazılarını Yeniden Oluştur?",
                    value=True,
                    info="Eğer `karaoke_subtitles.ass` dosyası zaten varsa, yeni oluşturulan dosya ile üzerine yaz."
                )
                edit_ass_before_render = gr.Checkbox(
                    label="ASS Dosyasını Manuel Düzenle",
                    value=False,
                    info="Video oluşturmadan önce ASS dosyasını (altyazılar) manuel düzenlemeye izin ver."
                )

        gr.Markdown("#### ASS Altyazı Editörü")
        with gr.Accordion("ASS Altyazı Editörü", open=False) as ass_editor_accordion:
            # ASS Editör Bileşenlerini Ekle
            ass_editor_components = create_ass_editor_component(None)
        
        # Bileşenler listesini aç
        [html_view, ass_content_field, save_button, save_status] = ass_editor_components
        generate_karaoke_button = gr.Button("Karaoke Oluştur", variant="primary", interactive=False)
        karaoke_video_output = gr.Video(label="Karaoke Videosu", interactive=False)
        gr.HTML("<hr>")

        ##############################################################################
        # ALTYAZI STİL ÖNİZLEMESİ (renk/yazı tipi değişikliklerinde)
        ##############################################################################
        def update_subtitle_preview(*args):
            return generate_font_preview_callback(*args, available_fonts=available_fonts)

        font_preview_inputs = [
            font_input,
            primary_color_input,
            secondary_color_input,
            outline_color_input,
            outline_size_input,
            shadow_color_input,
            shadow_size_input,
        ]
        for component in font_preview_inputs:
            component.change(fn=update_subtitle_preview, inputs=font_preview_inputs, outputs=subtitle_preview_output)

        ####################################################################
        # MANUEL OLARAK BUTONU PASİFLEŞTİREN VE GERİ AÇAN FONKSİYONLAR
        ####################################################################
        def on_start():
            """Sesi İşle butonunu pasifleştirip, metnini 'Lütfen bekleyin...' yapar."""
            return gr.update(value="Lütfen bekleyin...", interactive=False)

        def on_finish():
            """İşlem bitince buton metnini eski hâline döndürüp tekrar tıklanabilir yapar."""
            return gr.update(value="Sesi İşle", interactive=True)

        ##############################################################################
        # SES, ŞARKI SÖZÜ, VİDEO İÇİN GERİ ARAMA BAĞLANTILARI
        ##############################################################################

        # (Birincil) Sesi İşle Butonu - Zincirli Kullanım
        process_audio_button.click(
            fn=on_start,
            inputs=None,
            outputs=process_audio_button # Butonu güncelleyeceğiz
        ).then(
            fn=lambda: gr.Info("Ses işleme başladı..."), # Başlangıç mesajı
            inputs=None,
            outputs=[]
        ).then(
            fn=process_audio_callback,
            inputs=[
                audio_input,
                force_meta_fetch,
                force_audio_processing,
                force_transcription,
                beam_size_input,
                best_of_input,
                patience_input,
                condition_toggle,
                compression_threshold_input,
                temperature_input,
                language_input,
                state_working_dir,
                state_lyrics_json,
                state_lyrics_display,
                gr.State(cache_dir),
            ],
            outputs=[
                state_working_dir,
                state_lyrics_json,
                state_lyrics_display,
                state_artist_name,
                state_song_name,
            ]
        ).then(
            fn=lambda disp, artist, song: (disp, artist, song),
            inputs=[
                state_lyrics_display,
                state_artist_name,
                state_song_name
            ],
            outputs=[
                raw_lyrics_box,
                artist_name_input,
                song_name_input
            ]
        ).then(
            fn=check_modify_ai_availability,
            inputs=[state_working_dir],
            outputs=modify_button
        ).then(
            fn=check_generate_karaoke_availability,
            inputs=[state_working_dir],
            outputs=generate_karaoke_button
        ).then(
            fn=on_finish,
            inputs=None,
            outputs=process_audio_button # Butonu eski hâline döndür
        ).then(
            fn=lambda: gr.Info("Ses işleme tamamlandı!"), # Bitiş mesajı
            inputs=None,
            outputs=[]
        )

        # (İkincil) 💾 Sanatçı ve Şarkı Adını Kaydet Butonu
        save_metadata_button.click(
            fn=lambda: gr.Info("Meta veri kaydetme başladı..."), # Başlangıç mesajı
            inputs=None,
            outputs=[]
        ).then(
            fn=save_metadata_callback,
            inputs=[
                state_working_dir,
                artist_name_input,
                song_name_input
            ],
            outputs=[]
        ).then(
            fn=lambda: gr.Info("Meta veri kaydetme tamamlandı!"), # Bitiş mesajı
            inputs=None,
            outputs=[]
        )

        # (İkincil) 🌐 Referans Şarkı Sözlerini Al Butonu
        fetch_button.click(
            fn=lambda: gr.Info("Referans şarkı sözleri çekme başladı..."), # Başlangıç mesajı
            inputs=None,
            outputs=[]
        ).then(
            fn=fetch_reference_lyrics_callback,
            inputs=[
                force_refetch_lyrics,
                state_working_dir,
                state_fetched_lyrics_json,
                state_fetched_lyrics_display
            ],
            outputs=[
                state_fetched_lyrics_json,
                state_fetched_lyrics_display
            ]
        ).then(
            fn=lambda disp: disp,
            inputs=state_fetched_lyrics_display,
            outputs=fetched_lyrics_box
        ).then(
            fn=check_modify_ai_availability,
            inputs=[state_working_dir],
            outputs=modify_button
        ).then(
            fn=lambda: gr.Info("Referans şarkı sözleri çekme tamamlandı!"), # Bitiş mesajı
            inputs=None,
            outputs=[]
        )

        # (İkincil) 💾 Referans Şarkı Sözlerini Güncelle Butonu
        save_button.click(
            fn=lambda: gr.Info("Referans şarkı sözleri güncelleme başladı..."), # Başlangıç mesajı
            inputs=None,
            outputs=[]
        ).then(
            fn=save_fetched_lyrics_callback,
            inputs=[
                fetched_lyrics_box,
                state_working_dir,
                state_fetched_lyrics_json,
                state_fetched_lyrics_display
            ],
            outputs=[
                state_fetched_lyrics_json,
                state_fetched_lyrics_display
            ]
        ).then(
            fn=check_modify_ai_availability,
            inputs=[state_working_dir],
            outputs=modify_button
        ).then(
            fn=lambda: gr.Info("Referans şarkı sözleri güncelleme tamamlandı!"), # Bitiş mesajı
            inputs=None,
            outputs=[]
        )

        # (İkincil) 🪄 AI ile Düzenle Butonu
        modify_button.click(
            fn=lambda: gr.Info("AI ile düzenleme başladı..."), # Başlangıç mesajı
            inputs=None,
            outputs=[]
        ).then(
            fn=modify_lyrics_callback,
            inputs=[
                force_ai_modification,
                state_working_dir,
                state_lyrics_json,
                state_lyrics_display
            ],
            outputs=[
                state_lyrics_json,
                state_lyrics_display
            ]
        ).then(
            fn=lambda disp: disp,
            inputs=state_lyrics_display,
            outputs=raw_lyrics_box
        ).then(
            fn=check_generate_karaoke_availability,
            inputs=[state_working_dir],
            outputs=generate_karaoke_button
        ).then(
            fn=lambda: gr.Info("AI ile düzenleme tamamlandı!"), # Bitiş mesajı
            inputs=None,
            outputs=[]
        )

        # Altyazı editörü güncelleme fonksiyonu
        def update_ass_editor(working_dir):
            return create_ass_editor_component(working_dir)
        
        # Check ASS Editor butonunu Ekle
        check_editor_button = gr.Button("Karaoke ASS Dosyasını Editöre Yükle", variant="secondary")
        
        # Check editor butonu tıklandığında ASS editörünü güncelle
        check_editor_button.click(
            fn=update_ass_editor,
            inputs=[state_working_dir],
            outputs=ass_editor_components
        ).then(
            fn=lambda: gr.update(open=True),
            inputs=[],
            outputs=[ass_editor_accordion]
        )

        # (Birincil) Karaoke Oluştur Butonu
        generate_karaoke_button.click(
            fn=lambda: gr.Info("Karaoke oluşturma başladı..."), # Başlangıç mesajı
            inputs=None,
            outputs=[]
        ).then(
            fn=generate_subtitles_and_video_callback,
            inputs=[
                state_working_dir,
                font_input,
                fontsize_input,
                primary_color_input,
                secondary_color_input,
                outline_color_input,
                outline_size_input,
                shadow_color_input,
                shadow_size_input,
                verses_before_input,
                verses_after_input,
                loader_threshold_input,
                effect_dropdown,
                resolution_input,
                preset_input,
                crf_input,
                fps_input,
                bitrate_input,
                audio_bitrate_input,
                force_subtitles_overwrite,
                edit_ass_before_render,
                gr.State(output_dir),
                gr.State(effects_dir)
            ],
            outputs=[karaoke_video_output]
        ).then(
            fn=lambda: gr.Info("Karaoke oluşturma tamamlandı!"), # Bitiş mesajı
            inputs=None,
            outputs=[]
        )

        return app
