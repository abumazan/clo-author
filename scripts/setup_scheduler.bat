@echo off
:: Run this file as Administrator to create the weekly scheduled task
schtasks /create /tn "NBER_Weekly_Papers" /tr "C:\Users\xudin\OneDrive\IO course\clo-author\scripts\nber_weekly.bat" /sc weekly /d MON /st 09:00 /f
echo.
if %errorlevel%==0 (
    echo Task created successfully! NBER papers will be fetched every Monday at 9:00 AM.
) else (
    echo Failed. Try running this script as Administrator.
)
pause
