#!/bin/sh

# Stop Docker service if running
sudo systemctl stop docker

# Uninstall Docker packages
sudo apt-get purge -y docker-ce docker-ce-cli containerd.io

# Remove Docker directories and files
sudo rm -rf /var/lib/docker /etc/docker

# Remove Docker user group
sudo groupdel docker

# Remove Docker repositories
sudo rm /etc/apt/sources.list.d/docker.list

# Remove Docker GPG key
sudo rm /etc/apt/keyrings/docker.asc

# Clean up unused dependencies
sudo apt autoremove -y

echo "Docker components have been successfully removed."
