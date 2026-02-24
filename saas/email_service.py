"""
Email service for sending transactional emails.
Falls back to logging if SMTP is not configured.
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from .config import settings

logger = logging.getLogger(__name__)


def _send_email(to_email: str, subject: str, html_body: str, text_body: str = "") -> bool:
    """Send an email via SMTP. Returns True on success."""
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.info(f"[EMAIL MOCK] To: {to_email} | Subject: {subject}")
        logger.debug(f"[EMAIL MOCK] Body: {text_body}")
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        msg["To"] = to_email

        if text_body:
            msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM_EMAIL, to_email, msg.as_string())

        logger.info(f"Email sent to {to_email}: {subject}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False


def send_verification_email(email: str, username: str, token: str) -> bool:
    """Send email verification link."""
    verify_url = f"{settings.APP_URL}/api/auth/verify-email?token={token}"

    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #6c5ce7;">🎤 AI Karaoke Studio</h2>
        <h3>E-posta Adresinizi Doğrulayın</h3>
        <p>Merhaba <strong>{username}</strong>,</p>
        <p>AI Karaoke Studio'ya hoş geldiniz! Hesabınızı aktifleştirmek için aşağıdaki butona tıklayın:</p>
        <p style="text-align: center; margin: 30px 0;">
            <a href="{verify_url}"
               style="background: #6c5ce7; color: white; padding: 12px 30px;
                      border-radius: 6px; text-decoration: none; font-size: 16px;">
                E-postamı Doğrula
            </a>
        </p>
        <p style="color: #666; font-size: 14px;">
            Bu link 24 saat geçerlidir. Eğer bu hesabı siz oluşturmadıysanız bu e-postayı görmezden gelin.
        </p>
        <p style="color: #666; font-size: 12px;">
            Link çalışmıyorsa: <a href="{verify_url}">{verify_url}</a>
        </p>
    </div>
    """

    text_body = f"""
    AI Karaoke Studio - E-posta Doğrulama

    Merhaba {username},

    Hesabınızı doğrulamak için aşağıdaki linki kullanın:
    {verify_url}

    Bu link 24 saat geçerlidir.
    """

    return _send_email(email, "🎤 AI Karaoke Studio - E-postanızı Doğrulayın", html_body, text_body)


def send_password_reset_email(email: str, username: str, token: str) -> bool:
    """Send password reset link."""
    reset_url = f"{settings.APP_URL}/reset-password?token={token}"

    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #6c5ce7;">🎤 AI Karaoke Studio</h2>
        <h3>Şifre Sıfırlama</h3>
        <p>Merhaba <strong>{username}</strong>,</p>
        <p>Şifre sıfırlama talebiniz alındı. Aşağıdaki butona tıklayarak yeni şifrenizi belirleyin:</p>
        <p style="text-align: center; margin: 30px 0;">
            <a href="{reset_url}"
               style="background: #e17055; color: white; padding: 12px 30px;
                      border-radius: 6px; text-decoration: none; font-size: 16px;">
                Şifremi Sıfırla
            </a>
        </p>
        <p style="color: #666; font-size: 14px;">
            Bu link 2 saat geçerlidir. Eğer bu talebi siz yapmadıysanız güvenli olabilirsiniz.
        </p>
    </div>
    """

    text_body = f"""
    AI Karaoke Studio - Şifre Sıfırlama

    Merhaba {username},

    Şifre sıfırlama linkiniz:
    {reset_url}

    Bu link 2 saat geçerlidir.
    """

    return _send_email(email, "🔑 AI Karaoke Studio - Şifre Sıfırlama", html_body, text_body)


def send_job_completion_email(email: str, username: str, song_title: str, job_id: str) -> bool:
    """Send notification when karaoke job is complete."""
    job_url = f"{settings.APP_URL}/dashboard?job={job_id}"

    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #6c5ce7;">🎤 AI Karaoke Studio</h2>
        <h3>Karaoke Videonuz Hazır! 🎉</h3>
        <p>Merhaba <strong>{username}</strong>,</p>
        <p><strong>"{song_title}"</strong> şarkısının karaoke videosu oluşturuldu!</p>
        <p style="text-align: center; margin: 30px 0;">
            <a href="{job_url}"
               style="background: #00b894; color: white; padding: 12px 30px;
                      border-radius: 6px; text-decoration: none; font-size: 16px;">
                Videoyu İndir
            </a>
        </p>
    </div>
    """

    return _send_email(email, f"🎤 Karaoke Videonuz Hazır: {song_title}", html_body)
