# Deployment Guide

## Prerequisites

- Ubuntu server with SSH access
- Ansible installed locally
- Domain: parse.linkedtrust.us pointing to server

## Configuration

1. **Update inventory** (`inventory/production.yml`):
   ```yaml
   all:
     hosts:
       parse-server:
         ansible_host: YOUR_SERVER_IP
         ansible_user: root
         ansible_ssh_private_key_file: ~/.ssh/your_key.pem
   ```

2. **Update settings** (`group_vars/webservers.yml`):
   - Add database password
   - Add API keys
   - Verify domain_name is set to parse.linkedtrust.us

## Deploy

Run ONE command - it handles everything:

```bash
ansible-playbook -i inventory/production.yml playbooks/deploy.yml
```

This single playbook:
- ✅ Installs all dependencies (PostgreSQL, Redis, Nginx, etc.)
- ✅ Sets up database (creates user and database if needed)
- ✅ Deploys code from GitHub
- ✅ Configures background workers (Celery)
- ✅ Sets up SSL certificate (Let's Encrypt)
- ✅ Configures auto-renewal
- ✅ Only restarts services when needed
- ✅ Skips already completed steps

## Verify Deployment

```bash
# SSH to server
ssh root@YOUR_SERVER_IP

# Check services
supervisorctl status

# View logs
tail -f /var/log/supervisor/claims-extractor.log
tail -f /var/log/supervisor/claims-extractor-celery.log
```

## Update Code

Just run the same command - it's smart enough to only update what changed:

```bash
ansible-playbook -i inventory/production.yml playbooks/deploy.yml
```

## Database Access

```bash
# Connect to database
sudo -u postgres psql -d linkedclaims_extraction

# Common queries
\dt                                    # List tables
SELECT COUNT(*) FROM documents;       # Count documents
SELECT COUNT(*) FROM draft_claims;    # Count draft claims
```

## Service Management

```bash
# Restart services
supervisorctl restart claims-extractor
supervisorctl restart claims-extractor-celery

# Stop/Start services
supervisorctl stop all
supervisorctl start all
```

## SSL Certificate

The playbook automatically:
- Creates SSL certificate for parse.linkedtrust.us
- Sets up auto-renewal (Mondays at 2:30 AM)
- Configures HTTPS with security headers

To manually check certificate:
```bash
certbot certificates
certbot renew --dry-run
```

## Troubleshooting

If deployment fails:
1. Check Ansible output for specific error
2. SSH to server and check logs
3. Verify all settings in `group_vars/webservers.yml`

That's it! One playbook, one command.