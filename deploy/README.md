# Deployment Commands

```
ansible-playbook -i inventory/production.yml playbooks/deploy.yml
ansible-playbook -i inventory/production.yml playbooks/deploy.yml --tags update
sudo supervisorctl tail -f claims-extractor
```