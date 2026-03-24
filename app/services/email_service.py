"""Servicio de emails transaccionales (verificación de cuenta)."""

from app.core.config import settings


async def send_verification_email(email: str, verification_url: str) -> bool:
    """
    Envía email de verificación de cuenta.
    Retorna True si se envió correctamente.
    """
    if not settings.RESEND_API_KEY:
        return False
    try:
        import resend
        resend.api_key = settings.RESEND_API_KEY
        result = resend.Emails.send({
            "from": settings.EMAIL_FROM,
            "to": [email],
            "subject": "Verifica tu cuenta - ValoTracker Premier",
            "html": f"""
            <p>Hola,</p>
            <p>Haz clic en el siguiente enlace para verificar tu cuenta:</p>
            <p><a href="{verification_url}">{verification_url}</a></p>
            <p>El enlace expira en 24 horas.</p>
            <p>Si no creaste esta cuenta, ignora este correo.</p>
            """,
        })
        return result.get("id") is not None
    except Exception:
        return False
