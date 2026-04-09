"""
Telegram alerting manager for critical trading system events.

Author: Quantitative Trading Systems Engineer
Date: April 8, 2026
"""

import json
import logging
import os
import smtplib
import threading
import time
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

EMAIL_USER = os.environ.get('EMAIL_USER')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
EMAIL_RECIPIENT = os.environ.get('EMAIL_RECIPIENT', EMAIL_USER)
EMAIL_SMTP_HOST = os.environ.get('EMAIL_SMTP_HOST', 'smtp.gmail.com')
EMAIL_SMTP_PORT = int(os.environ.get('EMAIL_SMTP_PORT', '587'))
EMAIL_SMTP_USE_TLS = os.environ.get('EMAIL_SMTP_USE_TLS', 'true').lower() in ('1', 'true', 'yes')

ALLOWED_LEVELS = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}


def _safe_text(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)


class AlertManager:
    """Telegram alert manager with rate limiting and fail-safe behavior."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        rate_limit_seconds: float = 1.0,
        timeout_seconds: float = 5.0,
        email_user: Optional[str] = None,
        email_password: Optional[str] = None,
        email_recipient: Optional[str] = None,
        email_host: Optional[str] = None,
        email_port: Optional[int] = None,
        email_use_tls: Optional[bool] = None,
    ):
        self.bot_token = bot_token or TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or TELEGRAM_CHAT_ID
        self.rate_limit_seconds = rate_limit_seconds
        self.timeout_seconds = timeout_seconds
        self._last_sent_at = 0.0

        self.email_user = email_user or EMAIL_USER
        self.email_password = email_password or EMAIL_PASSWORD
        self.email_recipient = email_recipient or EMAIL_RECIPIENT
        self.email_host = email_host or EMAIL_SMTP_HOST
        self.email_port = email_port or EMAIL_SMTP_PORT
        self.email_use_tls = email_use_tls if email_use_tls is not None else EMAIL_SMTP_USE_TLS

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    @property
    def is_email_configured(self) -> bool:
        return bool(self.email_user and self.email_password and self.email_recipient)

    def _get_request_url(self) -> str:
        return f'https://api.telegram.org/bot{self.bot_token}/sendMessage'

    def _format_message(self, message: str, level: str, extra: Optional[Dict[str, Any]]) -> str:
        lines = [f'🚨 [{level}]', message.strip()]
        if extra:
            for key, value in extra.items():
                safe_key = str(key)
                safe_value = _safe_text(value)
                lines.append(f'{safe_key}: {safe_value}')
        return '\n'.join([line for line in lines if line])

    def _throttle(self) -> bool:
        now = time.time()
        if now - self._last_sent_at < self.rate_limit_seconds:
            return False
        self._last_sent_at = now
        return True

    def _send_request(self, payload: Dict[str, Any]) -> bool:
        if not self.is_configured:
            logger.warning('Telegram alert skipped: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing')
            return False

        try:
            data = json.dumps(payload).encode('utf-8')
            request = urllib.request.Request(
                self._get_request_url(),
                data=data,
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                },
            )
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                response.read()
            return True
        except Exception as exc:
            logger.error('Telegram alert send failed: %s', exc, exc_info=True)
            return False

    def _build_email_body(self, message: str, level: str, extra: Optional[Dict[str, Any]]) -> str:
        body = [f'[CRITICAL] {message.strip()}']
        if extra:
            for key, value in extra.items():
                body.append(f'{key}: {_safe_text(value)}')
        return '\n'.join(body)

    def _send_email(self, subject: str, body: str) -> bool:
        if not self.is_email_configured:
            logger.debug('Email alert skipped: EMAIL_USER, EMAIL_PASSWORD, or EMAIL_RECIPIENT missing')
            return False

        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_user
            msg['To'] = self.email_recipient
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            with smtplib.SMTP(self.email_host, self.email_port, timeout=self.timeout_seconds) as smtp:
                if self.email_use_tls:
                    smtp.starttls()
                smtp.login(self.email_user, self.email_password)
                smtp.sendmail(self.email_user, [self.email_recipient], msg.as_string())

            return True
        except Exception as exc:
            logger.error('Email alert send failed: %s', exc, exc_info=True)
            return False

    def _send_email_async(self, subject: str, body: str) -> bool:
        if not self.is_email_configured:
            return False

        thread = threading.Thread(
            target=self._send_email,
            args=(subject, body),
            daemon=True,
        )
        thread.start()
        return True

    def send(self, message: str, level: str = 'INFO', extra: Optional[Dict[str, Any]] = None) -> bool:
        """Send a Telegram alert message and email backup for CRITICAL events."""
        level = (level or 'INFO').upper()
        if level not in ALLOWED_LEVELS:
            logger.warning('Invalid alert level %s, falling back to INFO', level)
            level = 'INFO'

        if level == 'CRITICAL' and self.is_email_configured:
            subject = '🚨 [CRITICAL] Trading system alert'
            body = self._build_email_body(message, level, extra)
            self._send_email_async(subject, body)

        if not self._throttle():
            logger.debug('Telegram alert throttled: max 1 alert/sec')
            return level == 'CRITICAL' and self.is_email_configured

        payload = {
            'chat_id': self.chat_id,
            'text': self._format_message(message, level, extra),
            'disable_web_page_preview': True,
        }

        return self._send_request(payload)


class TelegramAlertHandler(logging.Handler):
    """Logging handler that sends ERROR/CRITICAL logs to Telegram."""

    def __init__(self, alert_manager: Optional[AlertManager] = None):
        super().__init__(level=logging.ERROR)
        self.alert_manager = alert_manager or AlertManager()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if record.levelno < logging.ERROR:
                return

            message = self.format(record)
            self.alert_manager.send(message, level=record.levelname)
        except Exception:
            self.handleError(record)


_alert_manager_instance: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    global _alert_manager_instance
    if _alert_manager_instance is None:
        _alert_manager_instance = AlertManager()
    return _alert_manager_instance
