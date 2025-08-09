# Shared Server Deployment Notes

This service is deployed on a shared hub server that hosts multiple LinkedTrust services.

## Shared Resources

The following resources are shared across services:

### PostgreSQL
- **Single PostgreSQL instance** serves all services
- Each service has its own database
- This service uses database: `linkedclaims_extraction`
- Database user: `linkedclaims` (or as configured)

### Redis
- **Single Redis instance** for all services
- Services can use different Redis databases (0-15)
- This service uses Redis DB 0 by default
- Can be configured to use a different DB via `REDIS_DB` env var

### Nginx
- **Single Nginx instance** proxies all services
- Each service has its own server block
- This service uses domain: `extract.linkedtrust.us`

## Important Considerations

### 1. PostgreSQL
The deployment playbook will:
- Check if PostgreSQL is already installed
- Only install PostgreSQL if not present
- Create a new database for this service
- NOT restart PostgreSQL (to avoid affecting other services)

### 2. Redis
The deployment playbook will:
- Check if Redis is already running
- Only install Redis if not present
- Use the existing Redis instance
- NOT restart Redis (to avoid affecting other services)

### 3. Port Management
- Flask app runs on port 5050 (internal)
- Nginx proxies from 443/80 to internal port
- Ensure port doesn't conflict with other services

### 4. Process Management
- Each service has its own supervisor configs
- Service names are prefixed: `claims-extractor`, `claims-extractor-celery`
- Restart only affects this service's processes

## Deployment Commands

### Initial Setup
```bash
# Deploy without affecting other services
ansible-playbook -i inventory/production.yml playbooks/deploy-with-background.yml --ask-vault-pass
```

### Updates
```bash
# Update only this service
ansible-playbook -i inventory/production.yml playbooks/update-with-background.yml --ask-vault-pass
```

### Service Management
```bash
# View only this service's processes
supervisorctl status | grep claims-extractor

# Restart only this service
supervisorctl restart claims-extractor
supervisorctl restart claims-extractor-celery

# View this service's logs
tail -f /var/log/supervisor/claims-extractor.log
tail -f /var/log/supervisor/claims-extractor-celery.log
```

## Database Isolation

Each service should only access its own database:

```sql
-- Connect to PostgreSQL
sudo -u postgres psql

-- List all databases
\l

-- You should see:
-- linkedclaims_extraction  (this service)
-- talent_db               (talent service)
-- trust_claim_db          (trust claim backend)
-- etc.

-- Connect to this service's database
\c linkedclaims_extraction

-- View tables (should only show this service's tables)
\dt
```

## Redis Namespace

If Redis key conflicts occur, configure different Redis databases:

```yaml
# In group_vars/webservers.yml
redis_db: 1  # Use Redis DB 1 instead of 0
```

Or use key prefixes in the application:
```python
# In celery_app.py
celery.conf.update(
    task_default_queue='claims_extractor_queue',
    task_routes={
        'tasks.*': {'queue': 'claims_extractor_queue'}
    }
)
```

## Monitoring

Check resource usage to ensure services aren't competing:

```bash
# Check PostgreSQL connections
sudo -u postgres psql -c "SELECT datname, count(*) FROM pg_stat_activity GROUP BY datname;"

# Check Redis memory
redis-cli INFO memory

# Check process memory
ps aux | grep -E '(claims-extractor|celery)' | awk '{sum+=$6} END {print "Memory used: " sum/1024 " MB"}'
```

## Troubleshooting Shared Resource Issues

### PostgreSQL Connection Pool Exhaustion
If you see "too many connections" errors:
1. Check connection pool settings in app
2. Reduce pool size in `database.py`
3. Check for connection leaks

### Redis Memory Issues
If Redis runs out of memory:
1. Check if other services are using excessive memory
2. Consider using different Redis DB
3. Implement key expiration in app

### Port Conflicts
If service won't start due to port conflict:
1. Check which service uses the port: `sudo lsof -i :5050`
2. Change port in group_vars and redeploy
3. Update Nginx configuration accordingly