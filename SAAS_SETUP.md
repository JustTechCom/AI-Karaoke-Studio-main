# AI Karaoke Studio - SaaS Kurulum Kılavuzu

## Mimari Genel Bakış

```
┌─────────────────────────────────────────────────────────────┐
│                    AI Karaoke Studio SaaS                   │
├─────────────────┬───────────────────┬───────────────────────┤
│   FastAPI App   │  Celery Worker    │   Redis + PostgreSQL  │
│   (Port 8000)   │  (GPU Processing) │   (Infrastructure)    │
├─────────────────┴───────────────────┴───────────────────────┤
│              Mevcut Processing Modülleri (değişmedi)        │
│  Whisper · Demucs · Gemini · Genius · FFmpeg               │
└─────────────────────────────────────────────────────────────┘
```

## Yeni Dosya Yapısı

```
AI-Karaoke-Studio-main/
├── saas/                          # SaaS katmanı (YENİ)
│   ├── config.py                  # Yapılandırma & plan tanımları
│   ├── database.py                # SQLAlchemy kurulumu
│   ├── auth.py                    # JWT auth & şifre hash
│   ├── email_service.py           # SMTP e-posta servisi
│   ├── storage.py                 # Dosya depolama (local/S3)
│   ├── tasks.py                   # Celery görev tanımları
│   ├── main.py                    # FastAPI uygulama
│   ├── models/
│   │   ├── user.py                # Kullanıcı modeli
│   │   ├── subscription.py        # Abonelik modeli
│   │   ├── job.py                 # İş modeli
│   │   ├── usage.py               # Kullanım takibi
│   │   └── api_key.py             # API anahtarları
│   ├── routers/
│   │   ├── auth.py                # /api/auth/* endpoint'leri
│   │   ├── jobs.py                # /api/jobs/* endpoint'leri
│   │   ├── billing.py             # /api/billing/* endpoint'leri
│   │   ├── admin.py               # /api/admin/* endpoint'leri
│   │   └── api_keys.py            # /api/keys/* endpoint'leri
│   └── templates/                 # Jinja2 HTML şablonları
│       ├── base.html
│       ├── index.html             # Landing page
│       ├── login.html
│       ├── register.html
│       ├── dashboard.html
│       ├── pricing.html
│       ├── admin.html
│       └── ...
├── saas_app.py                    # FastAPI giriş noktası (YENİ)
├── celery_worker.py               # Celery worker (YENİ)
├── Dockerfile.saas                # SaaS Docker imajı (YENİ)
├── docker-compose.saas.yml        # SaaS compose dosyası (YENİ)
├── requirements_saas.txt          # SaaS bağımlılıkları (YENİ)
├── .env.saas.example              # SaaS env şablonu (YENİ)
└── app.py                         # Orijinal Gradio uygulaması (değişmedi)
```

## Hızlı Başlangıç

### 1. Bağımlılıkları Kur

```bash
pip install -r requirements_saas.txt
```

### 2. Ortam Değişkenlerini Yapılandır

```bash
cp .env.saas.example .env
# .env dosyasını düzenleyerek API anahtarlarınızı girin
```

### 3. Redis'i Başlat

```bash
# Docker ile:
docker run -d -p 6379:6379 redis:7-alpine

# Veya sistem paketi:
sudo apt install redis-server && sudo systemctl start redis
```

### 4. Veritabanını Oluştur ve Uygulamayı Başlat

```bash
# API sunucusu
uvicorn saas_app:app --reload --port 8000

# Yeni terminal: Celery worker
celery -A celery_worker.celery_app worker --loglevel=info --queues=karaoke
```

### 5. Erişim

- **Web Arayüzü**: http://localhost:8000
- **API Docs**: http://localhost:8000/api/docs
- **Admin Paneli**: http://localhost:8000/admin
  - Kullanıcı: admin@aikaraoke.studio
  - Şifre: admin123! *(ilk girişte değiştirin)*

---

## Docker ile Tam Kurulum (Önerilen)

```bash
cp .env.saas.example .env
# .env dosyasını düzenle

docker compose -f docker-compose.saas.yml up -d
```

Bu komut şunları başlatır:
- **PostgreSQL** (veritabanı)
- **Redis** (kuyruk & önbellek)
- **API Server** (FastAPI)
- **Celery Worker** (GPU işleme)
- **Flower** (kuyruk monitörü - port 5555)

---

## Abonelik Planları

| Plan | Fiyat | Şarkı/Ay | Çözünürlük | API |
|------|-------|-----------|------------|-----|
| Ücretsiz | $0 | 3 | 720p | ❌ |
| Başlangıç | $9.99 | 20 | 1080p | ❌ |
| Pro | $29.99 | 100 | 1080p | ✅ |
| Kurumsal | $99.99 | Sınırsız | 4K | ✅ |

---

## Stripe Entegrasyonu

1. [Stripe Dashboard](https://dashboard.stripe.com)'a gidin
2. Ürünler > Fiyatlar bölümünden planları oluşturun
3. Fiyat ID'lerini `.env` dosyasına ekleyin:
   ```
   STRIPE_PRICE_STARTER=price_xxx
   STRIPE_PRICE_PRO=price_xxx
   STRIPE_PRICE_ENTERPRISE=price_xxx
   ```
4. Webhook'u yapılandırın: `https://yourdomain.com/api/billing/webhook`
   - Olaylar: `checkout.session.completed`, `customer.subscription.*`, `invoice.payment_failed`

---

## API Kullanımı

### Kimlik Doğrulama

```bash
# Token al
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password"}'

# Token ile istek
curl http://localhost:8000/api/jobs \
  -H "Authorization: Bearer <token>"
```

### İş Gönder

```bash
curl -X POST http://localhost:8000/api/jobs/submit \
  -H "Authorization: Bearer <token>" \
  -F "audio_file=@song.mp3" \
  -F "language=turkish" \
  -F "use_ai_correction=true"
```

### İş Durumu Sorgula

```bash
curl http://localhost:8000/api/jobs/<job_id>/status \
  -H "Authorization: Bearer <token>"
```

### Video İndir

```bash
curl http://localhost:8000/api/jobs/<job_id>/download \
  -H "Authorization: Bearer <token>" \
  -o karaoke.mp4
```

---

## Üretim Ortamı İçin Öneriler

1. **SECRET_KEY** değerini güçlü rastgele bir değere değiştirin
2. **PostgreSQL** kullanın (SQLite yerine)
3. **HTTPS** için Nginx ters proxy kurun
4. **Admin şifresini** ilk girişte değiştirin
5. **Stripe** anahtarlarını canlı mod anahtarlarıyla değiştirin
6. **E-posta** SMTP ayarlarını yapılandırın
7. Düzenli **veritabanı yedeklemesi** planlayın

---

## Orijinal Gradio Uygulaması

Orijinal `app.py` Gradio uygulaması değiştirilmeden kalır ve hâlâ çalışabilir:

```bash
python app.py  # Gradio arayüzü (port 7860)
```

SaaS ve Gradio uygulamaları bağımsız olarak çalışabilir.
