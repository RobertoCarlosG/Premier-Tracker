import httpx
from typing import Optional, Dict, Any
from app.core.config import settings

# Henrik API base — versiones construidas limpiamente sin string-replace.
# VALORANT_API_BASE_URL puede ser cualquier versión; usamos siempre la raíz.
_HENRIK_ROOT = "https://api.henrikdev.xyz/valorant"
_V1 = f"{_HENRIK_ROOT}/v1"
_V2 = f"{_HENRIK_ROOT}/v2"


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

    async def get_seasons(self, affinity: str) -> Dict[str, Any]:
        return await self._get(f"{_V1}/premier/seasons/{affinity}")

    async def get_leaderboard(
        self,
        affinity: str,
        conference: Optional[str] = None,
        division: Optional[str] = None,
    ) -> Dict[str, Any]:
        if division and conference:
            url = f"{_V1}/premier/leaderboard/{affinity}/{conference}/{division}"
        elif conference:
            url = f"{_V1}/premier/leaderboard/{affinity}/{conference}"
        else:
            url = f"{_V1}/premier/leaderboard/{affinity}"
        return await self._get(url)

    async def search_teams(
        self,
        name: Optional[str] = None,
        tag: Optional[str] = None,
        division: Optional[str] = None,
        conference: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, str] = {}
        if name:
            params["name"] = name
        if tag:
            params["tag"] = tag
        if division:
            params["division"] = division
        if conference:
            params["conference"] = conference
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
    # MMR (v2) — v1 devuelve data null para MMR
    # ─────────────────────────────────────────

    async def get_mmr(self, affinity: str, name: str, tag: str) -> Dict[str, Any]:
        """MMR actual del jugador. Requiere v2."""
        return await self._get(f"{_V2}/mmr/{affinity}/{name}/{tag}")

    async def get_mmr_history(self, region: str, name: str, tag: str) -> Dict[str, Any]:
        """Historial de MMR del jugador (v1)."""
        return await self._get(f"{_V1}/mmr-history/{region}/{name}/{tag}")

    # ─────────────────────────────────────────
    # Partidas (v1 para lista, v2 para detalle)
    # ─────────────────────────────────────────

    async def get_match_history(
        self,
        affinity: str,
        name: str,
        tag: str,
        mode: Optional[str] = None,
        size: int = 20,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"size": size}
        if mode:
            params["mode"] = mode
        return await self._get(f"{_V1}/matches/{affinity}/{name}/{tag}", params=params)

    async def get_match_details(self, match_id: str) -> Dict[str, Any]:
        """Detalle completo de partida. Requiere v2."""
        return await self._get(f"{_V2}/match/{match_id}")
