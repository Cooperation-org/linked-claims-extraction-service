# Deployment Guide for Linked Claims Extraction Service

This guide covers deploying the service with full background processing support (PostgreSQL, Redis, Celery).

## Prerequisites

- Ubuntu server (20.04 or 22.04)
- Ansible installed locally
- SSH access to the server
- Domain name configured (e.g., extract.linkedtrust.us)

## Setup Steps

### 1. Prepare Ansible Vault

Create your vault file with sensitive data:

```bash
cp group_vars/vault.yml.example group_vars/vault.yml
ansible-vault encrypt group_vars/vault.yml
```

Edit the vault to add your passwords and API keys:

```bash
ansible-vault edit group_vars/vault.yml
```

### 2. Update Inventory

Edit `inventory/production.yml`:

```yaml
all:
  hosts:
    extract-server:
      ansible_host: YOUR_SERVER_IP
      ansible_user: root
      ansible_ssh_private_key_file: ~/.ssh/your_key.pem
  children:
    webservers:
      hosts:
        extract-server:
```

### 3. Run Initial Deployment

Deploy the complete stack:

```bash
ansible-playbook -i inventory/production.yml playbooks/deploy-with-background.yml --ask-vault-pass
```

### 4. Set Up SSL with Let's Encrypt

After initial deployment, set up SSL certificates for parse.linkedtrust.us:

```bash
# Ensure DNS is pointing to your server first!
# parse.linkedtrust.us should resolve to your server's IP

# Run SSL setup
ansible-playbook -i inventory/production.yml playbooks/setup-ssl.yml --ask-vault-pass
```

The SSL setup will:
- Install certbot
- Create Let's Encrypt certificate for parse.linkedtrust.us
- Configure Nginx with HTTPS
- Set up auto-renewal via cron
- Add security headers (HSTS, X-Frame-Options, etc.)

### 5. Certificate Management

#### Check Certificate Status
```bash
ansible-playbook -i inventory/production.yml playbooks/renew-ssl.yml --ask-vault-pass
```

#### Force Certificate Renewal
```bash
ansible-playbook -i inventory/production.yml playbooks/renew-ssl.yml --ask-vault-pass -e force_renewal=true
```

#### Manual Certificate Operations (on server)
```bash
# Check certificate expiration
certbot certificates

# Test renewal
certbot renew --dry-run

# Force renewal
certbot renew --force-renewal

# View renewal configuration
cat /etc/cron.d/certbot
```

## Service Architecture

The deployment sets up:

1. **PostgreSQL Database** - Stores documents, draft claims, and job tracking
2. **Redis** - Message broker for Celery
3. **Flask Application** - Main web service (Gunicorn)
4. **Celery Worker** - Background PDF processing
5. **Nginx** - Reverse proxy and static file serving
6. **Supervisor** - Process management

## Service Management

### Check Service Status

SSH to the server and run:

```bash
supervisorctl status
```

You should see:
- `claims-extractor` (Flask app)
- `claims-extractor-celery` (Celery worker)

### View Logs

```bash
# Flask app logs
tail -f /var/log/supervisor/claims-extractor.log

# Celery worker logs
tail -f /var/log/supervisor/claims-extractor-celery.log

# Nginx logs
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
```

### Restart Services

```bash
# Restart Flask app
supervisorctl restart claims-extractor

# Restart Celery worker
supervisorctl restart claims-extractor-celery

# Restart all
supervisorctl restart all
```

### Database Management

```bash
# Connect to PostgreSQL
sudo -u postgres psql -d linkedclaims_extraction

# Run migrations
cd /home/claims-extractor/linked-claims-extraction-service
source venv/bin/activate
export FLASK_APP=src/app_new.py
flask db upgrade
```

## Updating the Application

To deploy code updates:

```bash
ansible-playbook -i inventory/production.yml playbooks/update.yml --ask-vault-pass
```

Or for a full redeploy:

```bash
ansible-playbook -i inventory/production.yml playbooks/deploy-with-background.yml --ask-vault-pass
```

## Monitoring

### Check Background Jobs

View Celery worker status:

```bash
cd /home/claims-extractor/linked-claims-extraction-service
source venv/bin/activate
celery -A src.celery_app.celery_app inspect active
```

### Database Queries

Check processing status:

```sql
-- Connect to database
sudo -u postgres psql -d linkedclaims_extraction

-- View recent documents
SELECT id, filename, status, upload_time FROM documents ORDER BY upload_time DESC LIMIT 10;

-- View processing jobs
SELECT id, document_id, job_type, status, started_at FROM processing_jobs ORDER BY started_at DESC LIMIT 10;

-- Count draft claims
SELECT COUNT(*) FROM draft_claims WHERE status = 'draft';
```

## Troubleshooting

### Services Not Starting

1. Check supervisor logs: `tail -f /var/log/supervisor/supervisord.log`
2. Check service logs for specific errors
3. Verify database connection: `sudo -u postgres psql -l`
4. Verify Redis is running: `redis-cli ping`

### Database Connection Issues

1. Check PostgreSQL is running: `systemctl status postgresql`
2. Verify database exists: `sudo -u postgres psql -l`
3. Check credentials in `/home/claims-extractor/linked-claims-extraction-service/.env`

### Celery Worker Issues

1. Check Redis connection: `redis-cli ping`
2. View Celery logs: `tail -f /var/log/supervisor/claims-extractor-celery.log`
3. Check for import errors in worker startup

### PDF Processing Failures

1. Check file upload directory exists: `ls -la /home/claims-extractor/linked-claims-extraction-service/src/uploads/`
2. Verify Claude API key is set correctly
3. Check Celery worker is processing tasks

## Security Notes

- All sensitive data should be in Ansible vault
- Database uses local connections only
- Redis is bound to localhost only
- Application runs as non-root user
- Uploads directory has restricted permissions