#!/bin/bash

# Linked Claims Extraction Service Deployment Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Linked Claims Extraction Service Deployment${NC}"
echo "============================================"

# Check if ansible is installed
if ! command -v ansible &> /dev/null; then
    echo -e "${RED}Error: Ansible is not installed${NC}"
    echo "Please install Ansible first: pip install ansible"
    exit 1
fi

# Check if vault password file exists
if [ ! -f ".vault_pass" ]; then
    echo -e "${YELLOW}Warning: .vault_pass file not found${NC}"
    echo "Creating .vault_pass file..."
    read -sp "Enter vault password: " vault_pass
    echo
    echo "$vault_pass" > .vault_pass
    chmod 600 .vault_pass
fi

# Check if vault file exists
if [ ! -f "group_vars/vault.yml" ]; then
    echo -e "${YELLOW}Warning: vault.yml not found${NC}"
    echo "Creating vault.yml from template..."
    cp group_vars/vault.yml.example group_vars/vault.yml
    ansible-vault encrypt group_vars/vault.yml
    echo -e "${YELLOW}Please edit vault.yml with your secrets:${NC}"
    echo "ansible-vault edit group_vars/vault.yml"
    exit 1
fi

# Default action is deploy
ACTION=${1:-deploy}

case $ACTION in
    deploy)
        echo -e "${GREEN}Deploying application...${NC}"
        ansible-playbook playbooks/deploy.yml
        ;;
    check)
        echo -e "${GREEN}Checking deployment...${NC}"
        ansible all -m ping
        ;;
    encrypt)
        echo -e "${GREEN}Encrypting vault...${NC}"
        ansible-vault encrypt group_vars/vault.yml
        ;;
    edit-vault)
        echo -e "${GREEN}Editing vault...${NC}"
        ansible-vault edit group_vars/vault.yml
        ;;
    *)
        echo -e "${RED}Unknown action: $ACTION${NC}"
        echo "Usage: $0 [deploy|check|encrypt|edit-vault]"
        exit 1
        ;;
esac

echo -e "${GREEN}Done!${NC}"
