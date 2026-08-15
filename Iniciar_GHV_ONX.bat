@echo off
title Sistema de Gestión GHV Service & OnXpert Software
echo Iniciando servidor...

:: 1. Se posiciona automáticamente en la carpeta actual del proyecto (evita errores si cambias de ruta)
cd /d "%~dp0"

:: 2. Ejecutar Streamlit en modo 'headless' para que NO abra el navegador por defecto
start /b streamlit run app.py --server.port 8502 --server.headless true

:: 3. Esperar 4 segundos para dar tiempo al servidor de arrancar
timeout /t 4 /nobreak > nul

:: 4. Abrir únicamente en Microsoft Edge
start msedge http://localhost:8502

echo Sistema listo en Microsoft Edge.
exit