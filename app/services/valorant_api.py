import httpx
from typing import Optional, Dict, Any, List
from app.core.config import settings


class ValorantAPIClient:
    def __init__(self):
        self.base_url = settings.VALORANT_API_BASE_URL
        self.api_key = settings.VALORANT_API_KEY
        self.headers = {
            "Authorization": self.api_key
        }
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=self.headers,
                **kwargs
            )
            response.raise_for_status()
            return response.json()
    
    async def get_conferences(self) -> Dict[str, Any]:
        return await self._request("GET", "/premier/conferences")
    
    async def get_seasons(self, affinity: str) -> Dict[str, Any]:
        return await self._request("GET", f"/premier/seasons/{affinity}")
    
    async def get_leaderboard(
        self, 
        affinity: str,
        conference: Optional[str] = None,
        division: Optional[str] = None
    ) -> Dict[str, Any]:
        if division and conference:
            endpoint = f"/premier/leaderboard/{affinity}/{conference}/{division}"
        elif conference:
            endpoint = f"/premier/leaderboard/{affinity}/{conference}"
        else:
            endpoint = f"/premier/leaderboard/{affinity}"
        
        return await self._request("GET", endpoint)
    
    async def search_teams(
        self,
        name: Optional[str] = None,
        tag: Optional[str] = None,
        division: Optional[str] = None,
        conference: Optional[str] = None
    ) -> Dict[str, Any]:
        params = {}
        if name:
            params["name"] = name
        if tag:
            params["tag"] = tag
        if division:
            params["division"] = division
        if conference:
            params["conference"] = conference
        
        return await self._request("GET", "/premier/search", params=params)
    
    async def get_team_by_name(self, team_name: str, team_tag: str) -> Dict[str, Any]:
        return await self._request("GET", f"/premier/{team_name}/{team_tag}")
    
    async def get_team_history_by_name(self, team_name: str, team_tag: str) -> Dict[str, Any]:
        return await self._request("GET", f"/premier/{team_name}/{team_tag}/history")
    
    async def get_team_by_id(self, team_id: str) -> Dict[str, Any]:
        return await self._request("GET", f"/premier/{team_id}")
    
    async def get_team_history_by_id(self, team_id: str) -> Dict[str, Any]:
        return await self._request("GET", f"/premier/{team_id}/history")
    
    async def get_account_by_name(self, name: str, tag: str) -> Dict[str, Any]:
        url = settings.VALORANT_API_BASE_URL.replace("/v3", "/v1")
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{url}/account/{name}/{tag}",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def get_mmr(self, affinity: str, name: str, tag: str) -> Dict[str, Any]:
        url = settings.VALORANT_API_BASE_URL.replace("/v3", "/v2")
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{url}/mmr/{affinity}/{name}/{tag}",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def get_match_history(
        self, 
        affinity: str, 
        name: str, 
        tag: str,
        mode: Optional[str] = None,
        size: int = 20
    ) -> Dict[str, Any]:
        url = settings.VALORANT_API_BASE_URL
        params = {"size": size}
        if mode:
            params["mode"] = mode
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{url}/matches/{affinity}/{name}/{tag}",
                headers=self.headers,
                params=params
            )
            response.raise_for_status()
            return response.json()
    
    async def get_match_details(self, match_id: str) -> Dict[str, Any]:
        url = settings.VALORANT_API_BASE_URL.replace("/v3", "/v2")
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{url}/match/{match_id}",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
