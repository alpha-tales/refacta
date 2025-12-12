# Debug script to check what's happening
Write-Host "=== Debug Info ===" -ForegroundColor Cyan

Write-Host "`nCurrent Location:" -ForegroundColor Yellow
Get-Location

Write-Host "`nGet-Command alphatales-refactor:" -ForegroundColor Yellow
Get-Command alphatales-refactor -ErrorAction SilentlyContinue | Format-List Name, CommandType, Definition, Source

Write-Host "`nChecking for aliases:" -ForegroundColor Yellow
Get-Alias alphatales-refactor -ErrorAction SilentlyContinue

Write-Host "`nChecking for functions:" -ForegroundColor Yellow
Get-Command alphatales-refactor -CommandType Function -ErrorAction SilentlyContinue

Write-Host "`nPython-related PATH entries:" -ForegroundColor Yellow
$env:PATH -split ';' | Where-Object { $_ -match 'python' }

Write-Host "`nPATHEXT:" -ForegroundColor Yellow
$env:PATHEXT

Write-Host "`nDirect test of .exe:" -ForegroundColor Yellow
& 'C:\Python312\Scripts\alphatales-refactor.exe' --version
