-- Public clients may read statistical match data. Only the service role may write it.
ALTER TABLE match_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE match_advanced_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE referee_profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY match_events_public_read
    ON match_events FOR SELECT
    TO anon, authenticated
    USING (true);

CREATE POLICY match_advanced_stats_public_read
    ON match_advanced_stats FOR SELECT
    TO anon, authenticated
    USING (true);

CREATE POLICY referee_profiles_public_read
    ON referee_profiles FOR SELECT
    TO anon, authenticated
    USING (true);

CREATE POLICY match_events_service_role_all
    ON match_events FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY match_advanced_stats_service_role_all
    ON match_advanced_stats FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY referee_profiles_service_role_all
    ON referee_profiles FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
