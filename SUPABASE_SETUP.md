# Supabase Setup Guide

Step-by-step guide to configure HKJC scraper with Supabase cloud database.

## Prerequisites

- Supabase account (free tier sufficient for testing)
- Project created on Supabase dashboard

## Step 1: Create Supabase Project

1. Go to https://supabase.com/dashboard
2. Click "New Project"
3. Choose organization, name, database password, region (choose closest to your location)
4. Wait for project to be provisioned (~2 minutes)

## Step 2: Get Connection String

1. Navigate to: **Settings > Database**
2. Under "Connection String" section, select **"URI"** tab
3. Copy the **"Connection pooler"** string (uses port 6543)
4. Replace `[YOUR-PASSWORD]` with your database password

**Connection String Format:**
```
postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
```

**Connection Types:**
- **Pooler (Port 6543)**: Recommended - uses PgBouncer connection pooling
- **Direct (Port 5432)**: For migrations and admin tasks (if pooler has issues)

## Step 3: Configure Environment Variables

Edit your `.env` file (create from `.env.example` if needed):

```bash
# Database Type
DATABASE_TYPE=supabase

# Supabase Connection (copy from Supabase Dashboard)
SUPABASE_URL=postgresql://postgres.YOUR_PROJECT_REF:YOUR_PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres

# Optional: Keep local settings for fallback
DB_HOST=localhost
DB_PORT=5432
DB_NAME=hkjc_racing
DB_USER=hkjc_user
DB_PASSWORD=hkjc_password
```

## Step 4: Run Migrations

Initialize database schema on Supabase:

```bash
# Check connection
hkjc-scraper --migrate
```

**If migrations fail with PgBouncer:**
Temporarily use direct connection (port 5432):
```bash
# In .env, temporarily change port in SUPABASE_URL
postgresql://postgres.XXX:PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres

# Run migrations
make migrate

# Switch back to pooler (port 6543)
postgresql://postgres.XXX:PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres
```

## Step 5: Test Scraping

```bash
# Test with dry run
hkjc-scraper 2025/12/23 --dry-run

# Actual scrape
hkjc-scraper 2025/12/23

# Date range
hkjc-scraper --date-range 2025/12/01 2025/12/07
```

## Row-Level Security (RLS)

**Default:** RLS is disabled for this use case (server-side scraper with full privileges).

**Not recommended** for this scraper - RLS adds complexity without security benefits when running server-side.

## Free Tier Limits

Supabase Free Tier includes:
- **500 MB database storage**
- **2 GB bandwidth per month**
- **50 MB file storage**
- Unlimited API requests
- Pause after 1 week of inactivity (can resume instantly)

**Storage Estimates:**
- 1 race day: ~5-10 KB
- 1 year of data: ~2-4 MB
- **10+ years should fit within free tier**

**Bandwidth:** Daily scraping uses minimal bandwidth (should stay well under 2GB/month)

## Performance Considerations

**Connection Pooling:**
- Supabase uses PgBouncer (port 6543) for connection pooling
- Scraper configured with `pool_size=3, max_overflow=7`
- Max 10 concurrent connections

**Query Performance:**
- Similar to local PostgreSQL
- Network latency: +10-50ms per query (depends on region)
- **Tip:** Use closest region to minimize latency

## Monitoring

View database stats in Supabase Dashboard:
- **Database > Usage**: Shows queries/second, connections, storage
- **Logs**: View database logs and errors
- **Reports**: Weekly usage reports sent via email

## Troubleshooting

### Connection timeout
- Check firewall/network allows port 6543
- Try direct connection (port 5432)
- Verify project is not paused (free tier auto-pauses after 7 days inactivity)
- Resume paused project from Supabase dashboard

### Migration errors with PgBouncer
- Switch to direct connection (port 5432) temporarily
- Run migrations
- Switch back to pooler (port 6543)

### "Too many connections" error
- Reduce `pool_size` in database.py
- Close inactive connections
- Upgrade to paid plan (more connections)

### Slow performance
- Check network latency to Supabase region
- Consider switching to closer region (requires new project)
- Verify connection uses pooler (port 6543)

### Timeout Errors

**Error: `could not receive data from server: Operation timed out`**

This error typically occurs when:
- Transaction is too large (too many rows committed at once)
- Query takes too long to complete
- Network connection is unstable

**Solutions:**

1. **Transaction Size Best Practice:**
   - The scraper commits **per race** (not per meeting)
   - Each transaction saves ~100-200 rows
   - This prevents timeout issues with large meetings

2. **Increase Timeouts (if needed):**
   ```bash
   # In .env
   DB_CONNECT_TIMEOUT=30           # Connection timeout (seconds)
   DB_STATEMENT_TIMEOUT=60000      # Query timeout (milliseconds)
   ```

3. **Connection Pool Configuration:**
   - Scraper uses `pool_size=3` for Supabase (PgBouncer compatible)
   - `max_overflow=7` allows up to 10 total connections
   - `pool_pre_ping=True` validates connections before use
   - `pool_recycle=300` recycles connections every 5 minutes

4. **Use Pooler (Port 6543):**
   - Always use connection pooler for normal operations
   - Only use direct connection (port 5432) for migrations

**Why This Works:**
- Supabase uses PgBouncer pooler with transaction timeouts
- Smaller transactions (per race) complete faster
- Automatic retry logic handles transient network errors
- Connection pooling reduces overhead

## Switching Back to Local PostgreSQL

Edit `.env`:
```bash
DATABASE_TYPE=local
```

Restart scraper. Data is isolated per database (local vs Supabase have separate data).

## Cost Optimization

**Free tier sufficient for:**
- Personal testing
- Historical data collection (1-2 years)
- Daily scraping (low volume)

**Upgrade needed if:**
- Database > 500 MB
- More than 2 GB bandwidth/month
- Need always-on database (free tier pauses after 7 days)
- Need more than 10 concurrent connections

**Paid plans start at $25/month:**
- 8 GB database
- 50 GB bandwidth
- No auto-pause
- 60 connections
- Point-in-time recovery

## Security Best Practices

1. **Never commit `.env` to git** - add to `.gitignore`
2. **Use strong passwords** for Supabase database
3. **Rotate passwords periodically**
4. **Keep Supabase URL private** - it contains credentials
5. **Enable 2FA** on Supabase account

## Additional Features (Optional)

**Real-time Subscriptions:**
Supabase supports real-time data subscriptions (not used by this scraper).

**PostgREST API:**
Supabase auto-generates REST API from your database schema (not used by this scraper).

**Storage:**
Object storage for files/images (not used by this scraper).

**Auth:**
Built-in authentication system (not used by this scraper).

---

## Quick Reference

### Checking Current Database Type
```bash
# View in Python
python -c "from hkjc_scraper.config import config; print(config.get_db_type_display())"
```

### Switching Between Databases
```bash
# Use Supabase
DATABASE_TYPE=supabase hkjc-scraper 2025/12/23

# Use Local
DATABASE_TYPE=local hkjc-scraper 2025/12/23
```

### Connection String Format
```
Local:    postgresql://user:password@localhost:5432/database
Supabase: postgresql://postgres.[ref]:password@aws-0-region.pooler.supabase.com:6543/postgres
          └─────────────────┬────────────────┘└──┬──┘└────────────────┬────────────────┘└──┬─┘
                      username              password           host (pooler)          port
```

For more help, visit:
- [Supabase Documentation](https://supabase.com/docs)
- [Supabase Discord](https://discord.supabase.com)
- [HKJC Scraper README](/README.md)
