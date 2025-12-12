# Setup alphatales-refactor command for Cursor/PowerShell
# This creates a function that bypasses Python extension interference

# PowerShell 7 profile (used by Cursor)
$ps7ProfileDir = "C:\Users\Premkumar A\Documents\PowerShell"
$ps7Profile = Join-Path $ps7ProfileDir "Microsoft.PowerShell_profile.ps1"

# PowerShell 5 profile (Windows PowerShell)
$ps5ProfileDir = "C:\Users\Premkumar A\Documents\WindowsPowerShell"
$ps5Profile = Join-Path $ps5ProfileDir "Microsoft.PowerShell_profile.ps1"

# The function to add
$functionCode = @'
# AlphaTales Refactor Agent - bypasses Python extension
function alphatales-refactor {
    & cmd /c "C:\Python312\Scripts\alphatales-refactor.cmd" $args
}
'@

# Create PS7 profile
if (!(Test-Path $ps7ProfileDir)) {
    New-Item -ItemType Directory -Path $ps7ProfileDir -Force | Out-Null
}
Set-Content -Path $ps7Profile -Value $functionCode -Force
Write-Host "Created PowerShell 7 profile: $ps7Profile" -ForegroundColor Green

# Create PS5 profile
if (!(Test-Path $ps5ProfileDir)) {
    New-Item -ItemType Directory -Path $ps5ProfileDir -Force | Out-Null
}
Set-Content -Path $ps5Profile -Value $functionCode -Force
Write-Host "Created PowerShell 5 profile: $ps5Profile" -ForegroundColor Green

Write-Host ""
Write-Host "DONE! Now:" -ForegroundColor Cyan
Write-Host "1. Close Cursor completely"
Write-Host "2. Reopen Cursor"
Write-Host "3. Open terminal and run: alphatales-refactor"
