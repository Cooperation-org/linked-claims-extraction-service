# Deployment Quick Commands

## 🚀 Deploy/Update

```bash
# Full deployment
ansible-playbook -i inventory/production.yml playbooks/deploy.yml --ask-vault-pass

# Quick update (code only)
ansible-playbook -i inventory/production.yml playbooks/deploy.yml --ask-vault-pass --tags update
```


# View logs on server
```
tail -f /var/log/supervisor/linked-claims-extraction-celery.log"
```
