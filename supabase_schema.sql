-- Supabase Schema for Treadmill & Pull-up Tracker

-- Create workouts table for treadmill data
CREATE TABLE IF NOT EXISTS workouts (
    id SERIAL PRIMARY KEY,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    distance REAL NOT NULL,
    steps INTEGER NOT NULL,
    duration INTEGER NOT NULL,
    workout_type VARCHAR(50) DEFAULT 'treadmill',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create daily_pullups table for pull-up tracking
CREATE TABLE IF NOT EXISTS daily_pullups (
    date DATE PRIMARY KEY,
    reps INTEGER DEFAULT 0,
    last_updated TIMESTAMPTZ DEFAULT NOW()
);

-- Create or replace function to increment pull-up reps for today
CREATE OR REPLACE FUNCTION increment_reps_today()
RETURNS INTEGER AS $$
DECLARE
    current_reps INTEGER;
BEGIN
    -- Insert or update today's record
    INSERT INTO daily_pullups (date, reps, last_updated)
    VALUES (CURRENT_DATE, 1, NOW())
    ON CONFLICT (date) 
    DO UPDATE SET 
        reps = daily_pullups.reps + 1,
        last_updated = NOW()
    RETURNING reps INTO current_reps;
    
    RETURN current_reps;
END;
$$ LANGUAGE plpgsql;

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_workouts_start_time ON workouts(start_time);
CREATE INDEX IF NOT EXISTS idx_workouts_workout_type ON workouts(workout_type);
CREATE INDEX IF NOT EXISTS idx_daily_pullups_date ON daily_pullups(date);

-- Create view for weekly statistics
CREATE OR REPLACE VIEW weekly_stats AS
SELECT 
    DATE_TRUNC('week', start_time) as week_start,
    COUNT(*) as workout_count,
    SUM(distance) as total_distance,
    SUM(steps) as total_steps,
    SUM(duration) as total_duration
FROM workouts
WHERE workout_type = 'treadmill'
GROUP BY DATE_TRUNC('week', start_time)
ORDER BY week_start DESC;

-- Create view for monthly statistics
CREATE OR REPLACE VIEW monthly_stats AS
SELECT 
    DATE_TRUNC('month', start_time) as month_start,
    COUNT(*) as workout_count,
    SUM(distance) as total_distance,
    SUM(steps) as total_steps,
    SUM(duration) as total_duration
FROM workouts
WHERE workout_type = 'treadmill'
GROUP BY DATE_TRUNC('month', start_time)
ORDER BY month_start DESC;
