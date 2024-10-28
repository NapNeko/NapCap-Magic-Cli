#!/bin/bash

# 包列表
packages=("linuxqq" "libnss3" "libgbm1" "libasound2" "libasound2-plugins:i386" "xvfb")

# 遍历包列表并尝试移除
for package in "${packages[@]}"; do
    if dpkg-query -W -f='${Status}' $package 2>/dev/null | grep -q "install ok installed"; then
        echo "Removing $package..."
        sudo apt remove -y $package
        sudo apt purge -y $package
    else
        echo "$package is not installed, skipping."
    fi
done

# 自动移除不再需要的依赖包
echo "Cleaning up..."
sudo apt autoremove -y

# 移除所有文件
sudo rm -rf /opt/QQ
