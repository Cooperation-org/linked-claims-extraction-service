# Deployment Guide for Linked Claims Extraction Service

This guide explains how to deploy the extraction service to the same server as LinkedTrust.

## Prerequisites

1. Server already running LinkedTrust (live.linkedtrust.us)
2. SSH access to the server
3. Ansible installed locally
4. Domain: extract.linkedtrust.us pointing to the server

## Quick Deployment

### 1. Configure Inventory

Edit `inventory/production.yml` with your server details:
```yaml
all:
  children:
    webservers:
      hosts:
        linkedtrust-server:
          ansible_host: YOUR_SERVER_IP
          ansible_user: root
          ansible_ssh_private_key_file: ~/.ssh/your-key
```

### 2. Set Up Secrets

```bash
cd deploy

# Copy vault template
cp group_vars/vault.yml.example group_vars/vault.yml

# Edit with your secrets
ansible-vault edit group_vars/vault.yml
```

Required secrets:
- `linkedtrust_email`: Your LinkedTrust account email
- `linkedtrust_password`: Your LinkedTrust password
- `anthropic_api_key`: Your Claude API key
- `flask_secret_key`: Generate a random secret key

### 3. Deploy

```bash
# Make deploy script executable
chmod +x deploy.sh

# Run deployment
./deploy.sh deploy
```

## Manual Nginx Configuration

Add this to your server's nginx configuration:

```nginx
# Add to /etc/nginx/sites-available/extract.linkedtrust.us
# Then symlink to sites-enabled and reload nginx

server {
    listen 80;
    server_name extract.linkedtrust.us;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name extract.linkedtrust.us;

    # Use existing SSL certs from LinkedTrust
    ssl_certificate /etc/letsencrypt/live/linkedtrust.us/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/linkedtrust.us/privkey.pem;

    client_max_body_size 80M;

    location / {
        proxy_pass http://127.0.0.1:5050;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }

    access_log /var/log/nginx/extraction_access.log;
    error_log /var/log/nginx/extraction_error.log;
}
```

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
