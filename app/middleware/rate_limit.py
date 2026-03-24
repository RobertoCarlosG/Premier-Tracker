"""Rate limiting para /auth/login: 5 intentos por IP por minuto."""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List

# In-memory sliding window. En producción considerar Redis.
_login_attempts: Dict[str, List[datetime]] = defaultdict(list)
WINDOW_SECONDS = 60
MAX_ATTEMPTS = 5


def check_login_rate_limit(ip: str) -> bool:
    """
    Retorna True si la IP puede intentar login.
    Retorna False si excedió el límite (5/min).
    """
    now = datetime.utcnow()
    cutoff = now - timedelta(seconds=WINDOW_SECONDS)
    attempts = _login_attempts[ip]
    # Limpiar intentos antiguos
    attempts[:] = [t for t in attempts if t > cutoff]
    if len(attempts) >= MAX_ATTEMPTS:
        return False
    attempts.append(now)
    return True
