@echo off
title Push Engineering Portfolio to GitHub
echo ========================================================
echo   Pushing Engineering Portfolio to GitHub
echo ========================================================
echo.
echo Pushing to https://github.com/Kartikeya-Rana-2004/engineering-portfolio.git ...
echo.
git add -A
git commit -m "feat: add interactive live web showcase, cross-platform sqlite fixes, and recruiter-focused architecture specs"
git push -u origin main
echo.
if %ERRORLEVEL% EQU 0 (
    echo ========================================================
    echo [SUCCESS] Pushed to GitHub successfully!
    echo.
    echo Next step: Enable GitHub Pages in your repo settings:
    echo 1. Go to: https://github.com/Kartikeya-Rana-2004/engineering-portfolio/settings/pages
    echo 2. Under 'Build and deployment', choose 'GitHub Actions'
    echo    (The included workflow will deploy automatically!)
    echo.
    echo Your live portfolio hub will be online at:
    echo https://kartikeya-rana-2004.github.io/engineering-portfolio/
    echo ========================================================
) else (
    echo [ERROR] Push failed. If authentication failed, try running:
    echo git push -u origin main
)
echo.
pause
