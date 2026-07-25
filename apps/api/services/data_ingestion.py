import logging
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.models.league import League
from apps.api.models.match import Match
from apps.api.models.team import Team
from apps.api.repositories.league_repository import LeagueRepository
from apps.api.repositories.match_repository import MatchRepository
from apps.api.repositories.team_repository import TeamRepository
from apps.api.services.api_football import APIFootballService
from apps.api.services.providers.base_provider import DataProviderPort, RawFixture, RawTeam
from apps.api.services.providers.provider_registry import get_provider_for_league

logger = logging.getLogger(__name__)

API_FOOTBALL_TO_FOOTBALL_DATA: dict[int, str] = {
    39: "PL",
    140: "PD",
}

FOOTBALL_DATA_LEAGUE_NAMES: dict[str, str] = {
    "PL": "Premier League",
    "PD": "LaLiga",
}

FOOTBALL_DATA_LEAGUE_IDS: dict[str, int] = {
    "PL": 39,
    "PD": 140,
}


@dataclass
class SyncResult:
    leagues_synced: int = 0
    teams_synced: int = 0
    matches_synced: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0

    def to_dict(self) -> dict:
        return {
            "leagues_synced": self.leagues_synced,
            "teams_synced": self.teams_synced,
            "matches_synced": self.matches_synced,
            "errors": self.errors,
            "success": self.success,
        }


class DataIngestionService:
    def __init__(
        self,
        session: AsyncSession,
        api_service: APIFootballService | None = None,
    ):
        self._session = session
        self._api = api_service or APIFootballService()
        self._league_repo = LeagueRepository(session)
        self._team_repo = TeamRepository(session)
        self._match_repo = MatchRepository(session)

    def _resolve_provider(self, league_id: int) -> tuple[DataProviderPort | None, str | None]:
        code = API_FOOTBALL_TO_FOOTBALL_DATA.get(league_id)
        if code:
            provider = get_provider_for_league(code)
            return provider, code
        return None, None

    async def sync_league(self, external_league_id: int) -> League | None:
        provider, league_code = self._resolve_provider(external_league_id)

        if provider and league_code:
            return await self._sync_league_from_provider(provider, external_league_id, league_code)

        return await self._sync_league_from_api_football(external_league_id)

    async def _sync_league_from_provider(
        self,
        provider: DataProviderPort,
        external_league_id: int,
        league_code: str,
    ) -> League | None:
        try:
            league_name = FOOTBALL_DATA_LEAGUE_NAMES.get(league_code, league_code)

            leagues_data = await provider.get_leagues()
            league_info = next(
                (lg for lg in leagues_data if lg.get("code") == league_code),
                None,
            )

            country = league_info.get("country") if league_info else None

            league = await self._league_repo.create_or_update(
                external_id=external_league_id,
                name=league_name,
                country=country,
                logo_url=None,
            )

            logger.info(f"Synced league via {provider.provider_name}: {league.name} (ID: {league.id})")
            return league

        except Exception as e:
            logger.error(f"Error syncing league {external_league_id} via provider: {e}")
            return None

    async def _sync_league_from_api_football(self, external_league_id: int) -> League | None:
        try:
            leagues_data = await self._api.get_leagues(league_id=external_league_id)

            if not leagues_data:
                logger.warning(f"League {external_league_id} not found in API-Football")
                return None

            league_data = leagues_data[0].get("league", {})
            country_data = leagues_data[0].get("country", {})

            league = await self._league_repo.create_or_update(
                external_id=league_data.get("id"),
                name=league_data.get("name", "Unknown"),
                country=country_data.get("name"),
                logo_url=league_data.get("logo"),
            )

            logger.info(f"Synced league via API-Football: {league.name} (ID: {league.id})")
            return league

        except Exception as e:
            logger.error(f"Error syncing league {external_league_id}: {e}")
            return None

    async def sync_teams_for_league(
        self, league_id: int, season: int
    ) -> list[Team]:
        provider, league_code = self._resolve_provider(league_id)

        if provider and league_code:
            return await self._sync_teams_from_provider(provider, league_id, league_code, season)

        return await self._sync_teams_from_api_football(league_id, season)

    async def _sync_teams_from_provider(
        self,
        provider: DataProviderPort,
        league_id: int,
        league_code: str,
        season: int,
    ) -> list[Team]:
        teams: list[Team] = []

        try:
            raw_teams = await provider.get_teams(league_code, season)

            logger.info(
                f"[sync_teams] {provider.provider_name}: {len(raw_teams)} teams "
                f"for {league_code} season {season}"
            )

            for raw_team in raw_teams:
                team = await self._team_repo.create_or_update(
                    external_id=raw_team.external_id,
                    name=raw_team.name,
                    logo_url=raw_team.logo_url,
                    country=raw_team.country,
                )
                teams.append(team)

            logger.info(f"Synced {len(teams)} teams for league {league_id} via {provider.provider_name}")

        except Exception as e:
            logger.error(f"Error syncing teams for league {league_id}: {e}")

        return teams

    async def _sync_teams_from_api_football(
        self, league_id: int, season: int
    ) -> list[Team]:
        teams: list[Team] = []

        try:
            teams_data = await self._api.get_teams_by_league(league_id, season)

            for team_entry in teams_data:
                team_data = team_entry.get("team", {})

                team = await self._team_repo.create_or_update(
                    external_id=team_data.get("id"),
                    name=team_data.get("name", "Unknown"),
                    logo_url=team_data.get("logo"),
                    country=team_data.get("country"),
                )
                teams.append(team)

            logger.info(f"Synced {len(teams)} teams for league {league_id} via API-Football")

        except Exception as e:
            logger.error(f"Error syncing teams for league {league_id}: {e}")

        return teams

    async def sync_matches_for_league(
        self, league_id: int, season: int, last_n: int = 50
    ) -> list[Match]:
        provider, league_code = self._resolve_provider(league_id)

        if provider and league_code:
            return await self._sync_matches_from_provider(
                provider, league_id, league_code, season, last_n
            )

        return await self._sync_matches_from_api_football(league_id, season, last_n)

    async def _sync_matches_from_provider(
        self,
        provider: DataProviderPort,
        league_id: int,
        league_code: str,
        season: int,
        last_n: int,
    ) -> list[Match]:
        matches: list[Match] = []

        try:
            league = await self._league_repo.get_by_external_id(league_id)
            if not league:
                logger.error(f"League {league_id} not found in local DB. Sync league first.")
                return matches

            logger.info(
                f"[sync_matches] Fetching finished matches via {provider.provider_name} "
                f"for {league_code} season {season}, limit={last_n}"
            )

            raw_fixtures = await provider.get_finished_matches(league_code, season, last_n)

            logger.info(
                f"[sync_matches] Received {len(raw_fixtures)} fixtures from {provider.provider_name}. "
                f"Processing..."
            )

            if not raw_fixtures:
                logger.warning(
                    f"[sync_matches] No fixtures returned for {league_code} season {season}."
                )
                return matches

            for idx, raw_fixture in enumerate(raw_fixtures):
                try:
                    logger.debug(
                        f"[sync_matches] Processing fixture {idx + 1}/{len(raw_fixtures)}: "
                        f"{raw_fixture.home_team} vs {raw_fixture.away_team} "
                        f"(external_id={raw_fixture.external_id}, "
                        f"went_to_extra_time={raw_fixture.went_to_extra_time})"
                    )

                    home_team = await self._team_repo.get_by_external_id(
                        raw_fixture.home_team_external_id
                    )
                    away_team = await self._team_repo.get_by_external_id(
                        raw_fixture.away_team_external_id
                    )

                    if not home_team or not away_team:
                        logger.warning(
                            f"[sync_matches] Teams not found for fixture {raw_fixture.external_id}. "
                            f"Home (ext_id={raw_fixture.home_team_external_id}): "
                            f"{'found' if home_team else 'NOT FOUND'}. "
                            f"Away (ext_id={raw_fixture.away_team_external_id}): "
                            f"{'found' if away_team else 'NOT FOUND'}. "
                            f"Sync teams first."
                        )
                        continue

                    match = await self._match_repo.upsert_match(
                        external_id=raw_fixture.external_id,
                        league_id=league.id,
                        home_team_id=home_team.id,
                        away_team_id=away_team.id,
                        match_date=raw_fixture.match_date,
                        status=raw_fixture.status,
                        home_score=raw_fixture.home_score,
                        away_score=raw_fixture.away_score,
                        regulation_time_only=raw_fixture.regulation_time_only,
                    )
                    matches.append(match)

                    logger.debug(
                        f"[sync_matches] Saved match {len(matches)}: "
                        f"{raw_fixture.home_team} {raw_fixture.home_score}-"
                        f"{raw_fixture.away_score} {raw_fixture.away_team} "
                        f"(internal_id={match.id})"
                    )

                except Exception as e:
                    logger.error(f"[sync_matches] Error processing fixture {idx + 1}: {e}")
                    continue

            logger.info(
                f"[sync_matches] Completed: {len(matches)}/{len(raw_fixtures)} matches "
                f"synced for league {league_id} via {provider.provider_name}"
            )

        except Exception as e:
            logger.error(f"Error syncing matches for league {league_id}: {e}")

        return matches

    async def _sync_matches_from_api_football(
        self, league_id: int, season: int, last_n: int
    ) -> list[Match]:
        matches: list[Match] = []

        try:
            league = await self._league_repo.get_by_external_id(league_id)
            if not league:
                logger.error(f"League {league_id} not found in local DB. Sync league first.")
                return matches

            logger.info(
                f"[sync_matches] Fetching fixtures via API-Football for league {league_id}, "
                f"season {season}, last_n={last_n}"
            )

            fixtures_data = await self._api.get_recent_finished_matches(
                league_id, season, last_n
            )

            logger.info(
                f"[sync_matches] Received {len(fixtures_data)} fixtures from API-Football. "
                f"Processing..."
            )

            if not fixtures_data:
                logger.warning(
                    f"[sync_matches] No fixtures returned for league {league_id}, "
                    f"season {season}."
                )
                return matches

            for idx, fixture_entry in enumerate(fixtures_data):
                try:
                    match_data = self._api.parse_fixture_to_match_data(fixture_entry)

                    logger.debug(
                        f"[sync_matches] Processing fixture {idx + 1}/{len(fixtures_data)}: "
                        f"{match_data['home_team_name']} vs {match_data['away_team_name']} "
                        f"(external_id={match_data['external_id']})"
                    )

                    home_team = await self._team_repo.get_by_external_id(
                        match_data["home_team_external_id"]
                    )
                    away_team = await self._team_repo.get_by_external_id(
                        match_data["away_team_external_id"]
                    )

                    if not home_team or not away_team:
                        logger.warning(
                            f"[sync_matches] Teams not found for fixture {match_data['external_id']}. "
                            f"Home (ext_id={match_data['home_team_external_id']}): "
                            f"{'found' if home_team else 'NOT FOUND'}. "
                            f"Away (ext_id={match_data['away_team_external_id']}): "
                            f"{'found' if away_team else 'NOT FOUND'}. "
                            f"Sync teams first."
                        )
                        continue

                    match = await self._match_repo.upsert_match(
                        external_id=match_data["external_id"],
                        league_id=league.id,
                        home_team_id=home_team.id,
                        away_team_id=away_team.id,
                        match_date=match_data["match_date"],
                        status=match_data["status"],
                        home_score=match_data["home_score"],
                        away_score=match_data["away_score"],
                        regulation_time_only=match_data["regulation_time_only"],
                    )
                    matches.append(match)

                    logger.debug(
                        f"[sync_matches] Saved match {len(matches)}: "
                        f"{match_data['home_team_name']} {match_data['home_score']}-"
                        f"{match_data['away_score']} {match_data['away_team_name']} "
                        f"(internal_id={match.id})"
                    )

                except Exception as e:
                    logger.error(f"[sync_matches] Error processing fixture {idx + 1}: {e}")
                    continue

            logger.info(
                f"[sync_matches] Completed: {len(matches)}/{len(fixtures_data)} matches "
                f"synced for league {league_id} via API-Football"
            )

        except Exception as e:
            logger.error(f"Error syncing matches for league {league_id}: {e}")

        return matches

    async def full_sync_league(
        self, external_league_id: int, season: int, last_matches: int = 50
    ) -> SyncResult:
        result = SyncResult()

        try:
            league = await self.sync_league(external_league_id)
            if not league:
                result.errors.append(f"Failed to sync league {external_league_id}")
                return result
            result.leagues_synced = 1

            teams = await self.sync_teams_for_league(external_league_id, season)
            result.teams_synced = len(teams)

            matches = await self.sync_matches_for_league(
                external_league_id, season, last_matches
            )
            result.matches_synced = len(matches)

            provider, league_code = self._resolve_provider(external_league_id)
            provider_name = provider.provider_name if provider else "API-Football"

            logger.info(
                f"Full sync completed for league {external_league_id} via {provider_name}: "
                f"{result.leagues_synced} leagues, {result.teams_synced} teams, "
                f"{result.matches_synced} matches"
            )

        except Exception as e:
            logger.error(f"Error in full sync for league {external_league_id}: {e}")
            result.errors.append(str(e))

        return result

    async def sync_all_target_leagues(self, season: int) -> SyncResult:
        total_result = SyncResult()

        target_leagues = [
            (39, "Premier League"),
            (140, "LaLiga"),
            (239, "Liga BetPlay"),
        ]

        for league_id, league_name in target_leagues:
            logger.info(f"Syncing {league_name} (ID: {league_id}) for season {season}...")
            league_result = await self.full_sync_league(league_id, season)

            total_result.leagues_synced += league_result.leagues_synced
            total_result.teams_synced += league_result.teams_synced
            total_result.matches_synced += league_result.matches_synced
            total_result.errors.extend(league_result.errors)

        logger.info(
            f"Synced all target leagues: {total_result.leagues_synced} leagues, "
            f"{total_result.teams_synced} teams, {total_result.matches_synced} matches"
        )

        return total_result
