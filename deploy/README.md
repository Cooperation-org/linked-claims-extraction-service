# Deployment Quick Commands

## 🚀 Deploy/Update

```bash
# Full deployment
ansible-playbook -i inventory/production.yml playbooks/deploy.yml --ask-vault-pass

# Quick update (code only)
ansible-playbook -i inventory/production.yml playbooks/deploy.yml --ask-vault-pass --tags update
```

## 🔍 Debug & Test

```bash
# Full diagnostics
ansible-playbook -i inventory/production.yml playbooks/debug-extraction.yml

# Test extraction
ansible-playbook -i inventory/production.yml playbooks/test-extraction.yml

# Restart services
ansible-playbook -i inventory/production.yml playbooks/restart-services.yml
```

## 📊 VIEW LOGS (SEE CLAIMS EXTRACTION)

```bash
# LIVE LOGS - SEE EXTRACTION IN REAL-TIME
ansible-playbook -i inventory/production.yml playbooks/view-logs.yml

# OR SSH DIRECTLY:
ssh root@extract.linkedtrust.us "tail -f /var/log/supervisor/linked-claims-extraction-celery.log"
```