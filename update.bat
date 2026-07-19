@echo off
:: Update script for the Expenses project

echo Fetching latest changes...
git pull

echo Rebuilding and restarting Docker containers...
docker-compose up -d --build
echo Done.
pause
