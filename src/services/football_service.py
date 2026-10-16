import time
import logging
from typing import Optional, Dict, Any, List, Tuple
import aiohttp
from datetime import datetime

logger = logging.getLogger(__name__)

LEAGUES = {
    "eng.1": {"name": "Angliya Premyer-ligasi (APL)", "flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    "esp.1": {"name": "Ispaniya La Ligasi", "flag": "🇪🇸"},
    "ita.1": {"name": "Italiya A Seriyasi", "flag": "🇮🇹"},
    "ger.1": {"name": "Germaniya Bundesligasi", "flag": "🇩🇪"},
    "fra.1": {"name": "Fransiya 1-ligasi", "flag": "🇫🇷"},
    "uefa.champions": {"name": "UEFA Chempionlar Ligasi", "flag": "🏆"}
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

class FootballService:
    def __init__(self, cache_ttl: int = 300):
        self.cache_ttl = cache_ttl
        self._standings_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
        self._matches_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}

    async def get_standings(self, league_code: str = "eng.1", limit: int = 10) -> Optional[Dict[str, Any]]:
        """Turnir jadvalini oladi (5 daqiqa kesh bilan)"""
        cache_key = f"{league_code}_{limit}"
        now = time.time()
        if cache_key in self._standings_cache:
            ts, val = self._standings_cache[cache_key]
            if now - ts < self.cache_ttl:
                return val

        url = f"https://site.api.espn.com/apis/v2/sports/soccer/{league_code}/standings"
        try:
            async with aiohttp.ClientSession(headers=HEADERS) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        children = data.get("children", [])
                        if not children:
                            return None
                        entries = children[0].get("standings", {}).get("entries", [])
                        
                        table = []
                        for rank, entry in enumerate(entries[:limit], 1):
                            team_obj = entry.get("team", {})
                            team_name = team_obj.get("displayName", "Noma'lum")
                            logos = team_obj.get("logos", [])
                            logo_url = logos[0].get("href", "") if logos else ""
                            stats = entry.get("stats", [])
                            # stat indexlari: gamesPlayed, wins, ties, losses, points
                            stats_dict = {s.get("name"): s.get("value") for s in stats if "name" in s}
                            played = int(stats_dict.get("gamesPlayed", 0))
                            points = int(stats_dict.get("points", 0))
                            diff = int(stats_dict.get("pointDifferential", 0))

                            table.append({
                                "rank": rank,
                                "team": team_name,
                                "logo": logo_url,
                                "played": played,
                                "points": points,
                                "diff": diff
                            })

                        res = {
                            "league": LEAGUES.get(league_code, {}).get("name", league_code),
                            "flag": LEAGUES.get(league_code, {}).get("flag", "⚽"),
                            "table": table
                        }
                        self._standings_cache[cache_key] = (now, res)
                        return res
        except Exception as e:
            logger.error(f"Turnir jadvalini olishda xatolik ({league_code}): {e}")
        return None

    async def get_matches(self, league_code: str = "eng.1") -> Optional[Dict[str, Any]]:
        """Oxirgi va yaqin kunlardagi o'yinlar natijalari va taqvimi (5 daqiqa kesh bilan)"""
        cache_key = league_code
        now = time.time()
        if cache_key in self._matches_cache:
            ts, val = self._matches_cache[cache_key]
            if now - ts < self.cache_ttl:
                return val

        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_code}/scoreboard"
        try:
            async with aiohttp.ClientSession(headers=HEADERS) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        events = data.get("events", [])
                        matches = []
                        
                        for ev in events[:8]:  # 8 ta o'yin
                            status = ev.get("status", {}).get("type", {}).get("detail", "")
                            competitions = ev.get("competitions", [{}])[0]
                            competitors = competitions.get("competitors", [])

                            if len(competitors) >= 2:
                                home_obj = competitors[0].get("team", {})
                                home = home_obj.get("displayName", "")
                                home_logo = home_obj.get("logo", "")
                                home_score = competitors[0].get("score", "")

                                away_obj = competitors[1].get("team", {})
                                away = away_obj.get("displayName", "")
                                away_logo = away_obj.get("logo", "")
                                away_score = competitors[1].get("score", "")

                                if home_score != "" and away_score != "":
                                    score_display = f"{home_score} : {away_score}"
                                    score_str = f"<b>{home}</b> {home_score} : {away_score} <b>{away}</b>"
                                else:
                                    score_display = "vs"
                                    score_str = f"<b>{home}</b> vs <b>{away}</b>"

                                matches.append({
                                    "match": score_str,
                                    "home_team": home,
                                    "home_logo": home_logo,
                                    "home_score": home_score,
                                    "away_team": away,
                                    "away_logo": away_logo,
                                    "away_score": away_score,
                                    "score": score_display,
                                    "status": status
                                })

                        res = {
                            "league": LEAGUES.get(league_code, {}).get("name", league_code),
                            "flag": LEAGUES.get(league_code, {}).get("flag", "⚽"),
                            "matches": matches
                        }
                        self._matches_cache[cache_key] = (now, res)
                        return res
        except Exception as e:
            logger.error(f"O'yinlar natijalarini olishda xatolik ({league_code}): {e}")
        return None

    # Alias for compatibility
    get_recent_matches = get_matches

football_service = FootballService()
