@echo off
echo Starting SMAR v2 Redis Cache Container...
docker compose up -d smar-redis-cache
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Docker may not be running or requires elevation.
    echo SMAR v2 TieredHotCache will automatically use high-speed In-Memory LRU Cache.
) else (
    echo [SUCCESS] SMAR v2 Redis Cache container running on port 6379!
)
