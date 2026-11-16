param([string]$Version = '8.0.21')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtime = Join-Path $projectRoot '.runtime'
New-Item -ItemType Directory -Path $runtime -Force | Out-Null
$archiveName = "mongodb-windows-x86_64-$Version.zip"
$archive = Join-Path $runtime $archiveName
$uri = "https://fastdl.mongodb.org/windows/$archiveName"
Write-Host "Downloading MongoDB Community $Version into this project..."
$checksumFile = "$archive.sha256"
& curl.exe --fail --location --silent --show-error --retry 3 --connect-timeout 15 --max-time 60 --output $checksumFile "$uri.sha256"
$expected = ''
if ($LASTEXITCODE -eq 0) {
    $expected = [regex]::Match((Get-Content -LiteralPath $checksumFile -Raw), '[a-fA-F0-9]{64}').Value
}
if (-not (Test-Path -LiteralPath $archive) -or ($expected -and (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $expected)) {
    & curl.exe --fail --location --silent --show-error --retry 3 --connect-timeout 15 --output $archive $uri
    if ($LASTEXITCODE -ne 0) { throw 'MongoDB download failed. Install MongoDB Community locally and configure MONGODB_URI.' }
}
$actual = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash
if ($expected -and $actual -ne $expected) { throw 'MongoDB archive checksum mismatch.' }
Expand-Archive -LiteralPath $archive -DestinationPath (Join-Path $runtime 'mongodb') -Force
if (-not $expected) {
    $binary = Get-ChildItem -LiteralPath (Join-Path $runtime 'mongodb') -Filter mongod.exe -Recurse | Select-Object -First 1
    if (-not $binary) { throw 'MongoDB archive does not contain mongod.exe.' }
    $signature = Get-AuthenticodeSignature -LiteralPath $binary.FullName
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'MongoDB') {
        throw 'Checksum unavailable and MongoDB executable signature could not be verified. Install MongoDB Community locally and configure MONGODB_URI.'
    }
    Write-Host 'Checksum service unavailable; verified the MongoDB publisher code signature instead.'
}
Write-Host 'MongoDB is ready. It will bind only to 127.0.0.1 when launched by run.ps1.'
