-- Public reference and match data is readable; writes stay server-side.
ALTER TABLE matches ENABLE ROW LEVEL SECURITY;
ALTER TABLE predictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE leagues ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

CREATE POLICY matches_public_read
    ON matches FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY predictions_public_read
    ON predictions FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY teams_public_read
    ON teams FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY leagues_public_read
    ON leagues FOR SELECT TO anon, authenticated USING (true);

CREATE POLICY matches_service_role_all
    ON matches FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY predictions_service_role_all
    ON predictions FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY teams_service_role_all
    ON teams FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY leagues_service_role_all
    ON leagues FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY users_service_role_all
    ON users FOR ALL TO service_role USING (true) WITH CHECK (true);

-- users contains hashed_password and therefore intentionally has no public SELECT policy.
