@echo off
echo ===========================================
echo   Sincronizando GHV_ONXgestion a la nube...
echo ===========================================
cd /d "C:\Users\GHV\Proyectos\GHV_ONXgestion"
python migrar_a_turso.py
echo.
echo ===========================================
echo   Sincronizacion finalizada.
echo ===========================================
pause