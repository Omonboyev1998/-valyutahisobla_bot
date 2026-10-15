import logging
from typing import Optional, Dict, Any, List
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
    async def get_standings(self, league_code: str = "eng.1") -> Optional[Dict[str, Any]]:
        """Turnir jadvalini oladi"""
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
                        for rank, entry in enumerate(entries[:10], 1): # Top 10 jamoa
                            team_name = entry.get("team", {}).get("displayName", "Noma'lum")
                            stats = entry.get("stats", [])
                            # stat indexlari: gamesPlayed, wins, ties, losses, points
                            stats_dict = {s.get("name"): s.get("value") for s in stats if "name" in s}
                            played = int(stats_dict.get("gamesPlayed", 0))
                            points = int(stats_dict.get("points", 0))
                            diff = int(stats_dict.get("pointDifferential", 0))

                            table.append({
                                "rank": rank,
                                "team": team_name,
                                "played": played,
                                "points": points,
                                "diff": diff
                            })

                        return {
                            "league": LEAGUES.get(league_code, {}).get("name", league_code),
                            "flag": LEAGUES.get(league_code, {}).get("flag", "⚽"),
                            "table": table
                        }
        except Exception as e:
            logger.error(f"Turnir jadvalini olishda xatolik ({league_code}): {e}")
        return None

    async def get_matches(self, league_code: str = "eng.1") -> Optional[Dict[str, Any]]:
        """Oxirgi va yaqin kunlardagi o'yinlar natijalari va taqvimi"""
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_code}/scoreboard"
        try:
            async with aiohttp.ClientSession(headers=HEADERS) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        events = data.get("events", [])
                        matches = []
                        
                        for ev in events[:8]:  # 8 ta o'yin
                            name = ev.get("name", "")
                            status = ev.get("status", {}).get("type", {}).get("detail", "")
                            competitions = ev.get("competitions", [{}])[0]
                            competitors = competitions.get("competitors", [])

                            if len(competitors) >= 2:
                                home = competitors[0].get("team", {}).get("displayName", "")
                                home_score = competitors[0].get("score", "")
                                away = competitors[1].get("team", {}).get("displayName", "")
                                away_score = competitors[1].get("score", "")

                                if home_score and away_score:
                                    score_str = f"<b>{home}</b> {home_score} : {away_score} <b>{away}</b>"
                                else:
                                    score_str = f"<b>{home}</b> vs <b>{away}</b>"

                                matches.append({
                                    "match": score_str,
                                    "status": status
                                })

                        return {
                            "league": LEAGUES.get(league_code, {}).get("name", league_code),
                            "flag": LEAGUES.get(league_code, {}).get("flag", "⚽"),
                            "matches": matches
                        }
        except Exception as e:
            logger.error(f"O'yinlar natijalarini olishda xatolik ({league_code}): {e}")
        return None

football_service = FootballService()
