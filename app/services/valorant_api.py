import logging
import httpx
from typing import Optional, Dict, Any, Tuple
from urllib.parse import quote
from app.core.config import settings

logger = logging.getLogger(__name__)

# Códigos de región Premier (affinity). Henrik /premier/search espera `division` como entero 1–20,
# no como "NA"/"EU"; enviar la región ahí provoca 400 Bad Request.
_PREMIER_AFFINITY_CODES = frozenset({"NA", "EU", "AP", "KR", "LATAM", "BR"})


def _normalize_premier_search_division(division: Optional[str]) -> Optional[int]:
    """Convierte query `division` a entero 1–20 o None si es inválido / es en realidad una región."""
    if division is None or (isinstance(division, str) and not division.strip()):
        return None
    s = division.strip().upper()
    if s in _PREMIER_AFFINITY_CODES:
        return None
    if s.isdigit():
        n = int(s)
        if 1 <= n <= 20:
            return n
    return None


def _split_premier_name_tag(
    name: Optional[str], tag: Optional[str]
) -> Tuple[Optional[str], Optional[str]]:
    """Si el usuario escribe 'Nombre#TAG' en un solo campo, separa en name + tag."""
    if tag and tag.strip():
        return (name.strip() if name else None, tag.strip())
    if not name or "#" not in name:
        return (name.strip() if name else None, None)
    left, _, right = name.partition("#")
    n, t = left.strip(), right.strip()
    return (n or None, t or None)

# Henrik API base — versiones construidas limpiamente sin string-replace.
# VALORANT_API_BASE_URL puede ser cualquier versión; usamos siempre la raíz.
_HENRIK_ROOT = "https://api.henrikdev.xyz/valorant"
_V1 = f"{_HENRIK_ROOT}/v1"
_V2 = f"{_HENRIK_ROOT}/v2"
_V3 = f"{_HENRIK_ROOT}/v3"

# OpenAPI affinities: eu, na, latam, br, ap, kr (minúsculas). Enviar LATAM en mayúsculas suele dar 404.
_HENRIK_AFFINITIES = frozenset({"eu", "na", "latam", "br", "ap", "kr"})


def normalize_henrik_affinity(affinity: str) -> str:
    """Normaliza región al enum de Henrik (minúsculas)."""
    if not affinity or not str(affinity).strip():
        return "na"
    s = str(affinity).strip().lower()
    return s if s in _HENRIK_AFFINITIES else "na"


def _henrik_path_segment(value: str) -> str:
    """Codifica name/tag para path (espacios y caracteres especiales)."""
    return quote(str(value).strip(), safe="")


class ValorantAPIClient:
    def __init__(self) -> None:
        self.api_key = settings.VALORANT_API_KEY
        self.headers = {
            "Authorization": self.api_key,
            "Accept": "*/*",
        }

    async def _get(self, url: str, **kwargs) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self.headers, **kwargs)
            response.raise_for_status()
            return response.json()

    # ─────────────────────────────────────────
    # Premier (v1 — única versión disponible)
    # ─────────────────────────────────────────

    async def get_conferences(self) -> Dict[str, Any]:
        return await self._get(f"{_V1}/premier/conferences")

    async def get_seasons(self, region: str) -> Dict[str, Any]:
        """Henrik: GET /valorant/v1/premier/seasons/{region} (region = eu/na/latam/…)."""
        aff = normalize_henrik_affinity(region)
        return await self._get(f"{_V1}/premier/seasons/{aff}")

    async def get_leaderboard(
        self,
        region: str,
        conference: Optional[str] = None,
        division: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Henrik: GET /valorant/v1/premier/leaderboard/{region}[/{conference}[/{division}]]."""
        aff = normalize_henrik_affinity(region)
        if division and conference:
            url = f"{_V1}/premier/leaderboard/{aff}/{conference}/{division}"
        elif conference:
            url = f"{_V1}/premier/leaderboard/{aff}/{conference}"
        else:
            url = f"{_V1}/premier/leaderboard/{aff}"
        return await self._get(url)

    async def search_teams(
        self,
        name: Optional[str] = None,
        tag: Optional[str] = None,
        division: Optional[str] = None,
        conference: Optional[str] = None,
    ) -> Dict[str, Any]:
        n, t = _split_premier_name_tag(name, tag)
        params: Dict[str, Any] = {}
        if n:
            params["name"] = n
        if t:
            params["tag"] = t
        div_n = _normalize_premier_search_division(division)
        if div_n is not None:
            params["division"] = div_n
        if conference:
            params["conference"] = conference
        # Henrik devuelve 400 si no hay ningún filtro válido (p. ej. solo division=NA mal usado).
        if not params:
            return {"data": [], "total": 0}
        return await self._get(f"{_V1}/premier/search", params=params)

    async def get_team_by_name(self, team_name: str, team_tag: str) -> Dict[str, Any]:
        return await self._get(f"{_V1}/premier/{team_name}/{team_tag}")

    async def get_team_history_by_name(self, team_name: str, team_tag: str) -> Dict[str, Any]:
        return await self._get(f"{_V1}/premier/{team_name}/{team_tag}/history")

    async def get_team_by_id(self, team_id: str) -> Dict[str, Any]:
        return await self._get(f"{_V1}/premier/{team_id}")

    async def get_team_history_by_id(self, team_id: str) -> Dict[str, Any]:
        return await self._get(f"{_V1}/premier/{team_id}/history")

    # ─────────────────────────────────────────
    # Cuentas (v1)
    # ─────────────────────────────────────────

    async def get_account_by_name(self, name: str, tag: str) -> Dict[str, Any]:
        """Perfil básico de cuenta: level, name, tag, puuid."""
        return await self._get(f"{_V1}/account/{name}/{tag}")

    # ─────────────────────────────────────────
    # MMR — docs recomiendan v3 (incluye platform); v2 como respaldo
    # ─────────────────────────────────────────

    async def get_mmr(self, region: str, name: str, tag: str) -> Dict[str, Any]:
        """
        Henrik: GET /valorant/v3/mmr/{region}/pc/{name}/{tag} (recomendado),
        fallback GET /valorant/v2/mmr/{region}/{name}/{tag}.
        """
        aff = normalize_henrik_affinity(region)
        n = _henrik_path_segment(name)
        t = _henrik_path_segment(tag)
        url_v3 = f"{_V3}/mmr/{aff}/pc/{n}/{t}"
        try:
            return await self._get(url_v3)
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 404:
                raise
            logger.warning(
                "Henrik v3 MMR 404, trying v2: aff=%s name=%s tag=%s",
                aff,
                name,
                tag,
            )
            return await self._get(f"{_V2}/mmr/{aff}/{n}/{t}")

    async def get_mmr_history(self, region: str, name: str, tag: str) -> Dict[str, Any]:
        """Historial de MMR del jugador (v1)."""
        aff = normalize_henrik_affinity(region)
        n = _henrik_path_segment(name)
        t = _henrik_path_segment(tag)
        return await self._get(f"{_V1}/mmr-history/{aff}/{n}/{t}")

    # ─────────────────────────────────────────
    # Partidas (v3 lista por nombre; v1 deprecado / 404 en muchas regiones; v2 detalle)
    # ─────────────────────────────────────────

    async def get_match_history(
        self,
        region: str,
        name: str,
        tag: str,
        mode: Optional[str] = None,
        size: int = 20,
    ) -> Dict[str, Any]:
        """Henrik: GET /valorant/v3/matches/{region}/{name}/{tag}."""
        aff = normalize_henrik_affinity(region)
        # OpenAPI v3: size máximo 10
        sz = max(1, min(int(size), 10))
        params: Dict[str, Any] = {"size": sz}
        if mode:
            params["mode"] = mode
        url = f"{_V3}/matches/{aff}/{name}/{tag}"
        try:
            return await self._get(url, params=params)
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (400, 404):
                logger.warning(
                    "Henrik match history vacío o no encontrado: aff=%s name=%s tag=%s status=%s",
                    aff,
                    name,
                    tag,
                    e.response.status_code,
                )
                return {"data": [], "total": 0}
            raise

    async def get_match_details(self, match_id: str) -> Dict[str, Any]:
        """Detalle completo de partida. Requiere v2."""
        return await self._get(f"{_V2}/match/{match_id}")
