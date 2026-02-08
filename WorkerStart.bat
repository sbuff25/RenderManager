@echo off
title Wain Worker
cd /d Z:\Work\UtilityDevelopment\RenderManager
echo Pulling latest code...
git pull origin LocalNetworkSuport
echo.
echo Starting Wain Worker...
python -m wain --worker --server 192.168.4.47:8080 --path-map F:=Z:,E:=E:
pause
