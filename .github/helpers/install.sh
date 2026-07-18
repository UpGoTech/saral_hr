#!/bin/bash
set -euo pipefail

cd ~ || exit 1

sudo apt-get update
sudo apt-get install -y redis-server mariadb-client libmariadb-dev pkg-config

pip install frappe-bench

FRAPPE_BRANCH="${FRAPPE_BRANCH:-version-15}"

bench init --skip-assets --frappe-branch "${FRAPPE_BRANCH}" --python "$(which python)" frappe-bench

mkdir -p ~/frappe-bench/sites/test_site
cp "${GITHUB_WORKSPACE}/.github/helpers/site_config_mariadb.json" \
	~/frappe-bench/sites/test_site/site_config.json

mariadb --host 127.0.0.1 --port 3306 -u root -proot -e "SET GLOBAL character_set_server = 'utf8mb4'"
mariadb --host 127.0.0.1 --port 3306 -u root -proot -e "SET GLOBAL collation_server = 'utf8mb4_unicode_ci'"
mariadb --host 127.0.0.1 --port 3306 -u root -proot -e "CREATE USER IF NOT EXISTS 'test_frappe'@'%' IDENTIFIED BY 'test_frappe'"
mariadb --host 127.0.0.1 --port 3306 -u root -proot -e "CREATE DATABASE IF NOT EXISTS test_frappe"
mariadb --host 127.0.0.1 --port 3306 -u root -proot -e "GRANT ALL PRIVILEGES ON \`test_frappe\`.* TO 'test_frappe'@'%'"
mariadb --host 127.0.0.1 --port 3306 -u root -proot -e "FLUSH PRIVILEGES"

cd ~/frappe-bench || exit 1

# Disable background workers in CI
sed -i 's/watch:/# watch:/g' Procfile || true
sed -i 's/schedule:/# schedule:/g' Procfile || true
sed -i 's/socketio:/# socketio:/g' Procfile || true
sed -i 's/redis_socketio:/# redis_socketio:/g' Procfile || true

bench get-app saral_hr "${GITHUB_WORKSPACE}"
bench setup requirements --dev

bench start &>> ~/frappe-bench/bench_start.log &
CI=Yes bench build --app frappe &
bench --site test_site reinstall --yes
bench --verbose --site test_site install-app saral_hr
