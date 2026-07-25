from apps.api.engine.value_calculator import MatchFeatures, TeamMatchFeatures


def build_match_features(
    home_matches: list,
    away_matches: list,
    h2h_matches: list,
    home_team_id: int,
    away_team_id: int,
) -> MatchFeatures:
    home_features = _compute_team_features(home_matches, home_team_id, h2h_matches, is_home=True)
    away_features = _compute_team_features(away_matches, away_team_id, h2h_matches, is_home=False)
    return MatchFeatures(home=home_features, away=away_features)


def _compute_team_features(
    matches: list,
    team_id: int,
    h2h_matches: list,
    is_home: bool,
) -> TeamMatchFeatures:
    if not matches:
        return TeamMatchFeatures(
            team_id=team_id,
            avg_goals_scored=0.0,
            avg_goals_conceded=0.0,
            avg_xg=0.0,
            avg_shots_on_target=0.0,
            avg_corners=0.0,
            form_points=0.0,
            h2h_win_rate=0.5,
            days_since_last_match=30,
        )

    goals_scored_list: list[float] = []
    goals_conceded_list: list[float] = []
    form_points: float = 0.0

    for m in matches:
        is_home_team = m.home_team_id == team_id
        scored = m.home_score if is_home_team else m.away_score
        conceded = m.away_score if is_home_team else m.home_score

        if scored is not None:
            goals_scored_list.append(float(scored))
        if conceded is not None:
            goals_conceded_list.append(float(conceded))

        if scored is not None and conceded is not None:
            if scored > conceded:
                form_points += 3
            elif scored == conceded:
                form_points += 1

    avg_scored = sum(goals_scored_list) / len(goals_scored_list) if goals_scored_list else 0.0
    avg_conceded = sum(goals_conceded_list) / len(goals_conceded_list) if goals_conceded_list else 0.0

    h2h_wins = 0
    h2h_total = len(h2h_matches)
    for m in h2h_matches:
        if is_home and m.home_team_id == team_id and m.home_score is not None and m.away_score is not None:
            if m.home_score > m.away_score:
                h2h_wins += 1
        elif not is_home and m.away_team_id == team_id and m.home_score is not None and m.away_score is not None:
            if m.away_score > m.home_score:
                h2h_wins += 1
    h2h_win_rate = h2h_wins / h2h_total if h2h_total > 0 else 0.5

    return TeamMatchFeatures(
        team_id=team_id,
        avg_goals_scored=round(avg_scored, 3),
        avg_goals_conceded=round(avg_conceded, 3),
        avg_xg=round(avg_scored * 0.95, 3),
        avg_shots_on_target=0.0,
        avg_corners=0.0,
        form_points=form_points,
        h2h_win_rate=round(h2h_win_rate, 3),
        days_since_last_match=7,
    )
