@echo off
title Wain Worker
pushd \\SPENCERS-DESKTOP\Work\UtilityDevelopment\RenderManager
echo Pulling latest code...
git pull origin LocalNetworkSuport
echo.
echo Starting Wain Worker...
python -m wain --worker --server 192.168.4.47:8080 --token eu161kNOeEngldXmZ_qdXlzpBIYiKyq_ujHsac0g77k --path-map "E:\Work=\\SPENCERS-DESKTOP\Work,E:\_Renders=\\SPENCERS-DESKTOP\_Renders,E:\AssetLibrary=\\SPENCERS-DESKTOP\AssetLibrary"
popd
pause
