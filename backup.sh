#!/bin/bash
BACKUP_DIR="./backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
rsync -av --exclude='.git' --exclude='node_modules' --exclude='__pycache__' --exclude='*.pyc' . "$BACKUP_DIR/"
echo " ýŒ: $BACKUP_DIR"