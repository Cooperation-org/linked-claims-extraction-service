# Deployment Guide for Linked Claims Extraction Service

This guide explains how to deploy the extraction service.

## Prerequisites

1. Server with deploy user access
2. SSH access to the server (deploy@139.177.194.35)
3. Ansible installed locally
4. Domain: parse.linkedtrust.us pointing to the server

## Full Deployment

### 1. Configure Settings

Edit `group_vars/webservers.yml` with your actual values:
- `anthropic_api_key`: Your Claude API key
- `flask_secret_key`: A random secret key
- GitHub token is already configured in git_repo URL

### 2. Deploy

```bash
cd ~/parent/linked-claims-extraction-service/deploy
ansible-playbook playbooks/deploy.yml
```

## Quick Code Updates

After making code changes, use the quick update playbook:

```bash
cd deploy
ansible-playbook playbooks/update.yml
```

This will:
1. Pull the latest code from git  
2. Restart the extraction service

Takes about 10 seconds vs full deployment which takes 2-3 minutes.

## Service Management

```bash
# Check service status
sudo systemctl status extraction-service

# View logs
sudo journalctl -u extraction-service -f

# Restart service
sudo systemctl restart extraction-service

# Reload nginx
sudo nginx -t && sudo systemctl reload nginx
```

## Troubleshooting

1. **Service won't start**: Check logs with `journalctl -u extraction-service -n 100`
2. **502 Bad Gateway**: Ensure service is running on port 5050
3. **File upload fails**: Check uploads directory permissions
4. **Can't connect to LinkedTrust**: Verify LINKEDTRUST_BASE_URL in .env

## Port Configuration

- Extraction Service: 5050
- LinkedTrust Backend: 3000
- Talent: 3001

## Complete Demo Flow

1. Visit https://extract.linkedtrust.us
2. Upload PDF document
3. Extract claims using AI
4. Publish to LinkedTrust
5. Copy validation links
6. Share with beneficiaries
7. Track validations at https://live.linkedtrust.us
