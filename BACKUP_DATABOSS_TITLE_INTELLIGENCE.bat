@echo off
setlocal EnableExtensions
cd /d "%~dp0" || exit /b 1
if not exist ".runtime\logs" mkdir ".runtime\logs" || exit /b 1
if not exist ".runtime\backups" mkdir ".runtime\backups" || exit /b 1
powershell -NoProfile -Command "$stamp=Get-Date -Format 'yyyyMMdd_HHmmss'; $items=@(); if(Test-Path '.runtime\config'){$items+=(Resolve-Path '.runtime\config').Path}; if($env:DATABOSS_CONFIG -and (Test-Path $env:DATABOSS_CONFIG)){$items+=(Resolve-Path $env:DATABOSS_CONFIG).Path}; $db=if($env:DATABOSS_AUTH_DB){$env:DATABOSS_AUTH_DB}else{Join-Path $PWD '.runtime\databoss_auth.sqlite3'}; if(Test-Path $db){$dbItem=Get-Item $db; $items+=Get-ChildItem $dbItem.DirectoryName -Filter ($dbItem.Name + '*') -File | ForEach-Object {$_.FullName}}; if($env:DATABOSS_PROJECT_ROOT){$generated=Join-Path $env:DATABOSS_PROJECT_ROOT 'DataBoss_Title_Factory_Output'; if(Test-Path $generated){$items+=(Resolve-Path $generated).Path}}; $items=@($items | Select-Object -Unique); if(-not $items){Write-Error 'No generated config, database, or artifact directory exists to back up.'; exit 2}; $destination=Join-Path (Resolve-Path '.runtime\backups').Path ('databoss_generated_' + $stamp + '.zip'); Compress-Archive -LiteralPath $items -DestinationPath $destination -CompressionLevel Optimal; Write-Output ('Created ' + $destination)" >>".runtime\logs\backup.log" 2>&1
if errorlevel 1 (
  echo ERROR: Backup failed. Review .runtime\logs\backup.log.
  exit /b %ERRORLEVEL%
)
echo Backup contains generated config/database/artifacts only; no source corpus was copied.
exit /b 0
