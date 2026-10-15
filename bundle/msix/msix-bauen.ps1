# KinoLel-Player: MSIX-Paket bauen (für den Microsoft Store vorbereitet).
#
#   pwsh bundle/msix/msix-bauen.ps1 -Quelle build/portable -Ziel build
#
# Ergebnis in -Ziel:
#   <Name>-<Version>-x64.msix              unsigniert – so wird es später im Partner Center hochgeladen
#                                          (Microsoft signiert es selbst; vorher Store-Werte in marke.cmake eintragen)
#   <Name>-Test-<Version>-x64.msix         mit einem Test-Zertifikat signiert (nur zum Ausprobieren)
#   <Name>-Testzertifikat.cer              dieses Zertifikat; muss einmal unter „Vertrauenswürdige Personen“
#                                          (Lokaler Computer) importiert werden, sonst lässt Windows das Test-MSIX nicht zu
param(
    [Parameter(Mandatory = $true)][string]$Quelle,   # fertiger Programmordner (portable-Stand mit VC-Laufzeit)
    [Parameter(Mandatory = $true)][string]$Ziel,
    [string]$Repo = (Resolve-Path "$PSScriptRoot/../..").Path
)
$ErrorActionPreference = 'Stop'

# --- Werte aus marke.cmake ---------------------------------------------------------------------
$marke = @{}
foreach ($zeile in Get-Content -Encoding UTF8 (Join-Path $Repo 'marke.cmake')) {
    if ($zeile -match '^\s*set\((\w+)\s+"([^"]*)"\)') { $marke[$Matches[1]] = $Matches[2] }
}
$name = $marke['APP_NAME']
$version = "$($marke['APP_VERSION']).0"   # Store verlangt 4 Zahlen, die letzte 0
$marke['MSIX_VERSION'] = $version
$marke['APP_EXE'] = "$name.exe"
Write-Host "MSIX für $name $version ($($marke['STORE_IDENTITY_NAME']), $($marke['STORE_PUBLISHER']))"

# --- Werkzeuge aus dem Windows SDK -------------------------------------------------------------
function Finde-SdkWerkzeug([string]$datei) {
    $treffer = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin\*\x64\$datei" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending | Select-Object -First 1
    if (-not $treffer) { throw "$datei nicht gefunden (Windows SDK fehlt?)" }
    return $treffer.FullName
}
$makeappx = Finde-SdkWerkzeug 'makeappx.exe'
$signtool = Finde-SdkWerkzeug 'signtool.exe'

# --- Paketinhalt zusammenstellen -----------------------------------------------------------------
$stufe = Join-Path $Ziel 'msix-inhalt'
if (Test-Path $stufe) { Remove-Item -Recurse -Force $stufe }
Copy-Item -Recurse $Quelle $stufe
# Portabel-Markierung entfernen: im MSIX ist der Programmordner schreibgeschützt, Daten gehören nach AppData
Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $stufe 'portable')
if (-not (Test-Path (Join-Path $stufe $marke['APP_EXE']))) { throw "$($marke['APP_EXE']) fehlt in $Quelle" }
Copy-Item -Recurse (Join-Path $PSScriptRoot 'Assets') (Join-Path $stufe 'Assets')

$manifest = Get-Content -Raw -Encoding UTF8 (Join-Path $PSScriptRoot 'AppxManifest.xml.in')
foreach ($k in $marke.Keys) { $manifest = $manifest.Replace("@$k@", [Security.SecurityElement]::Escape($marke[$k])) }
if ($manifest -match '@[A-Z_]+@') { throw "Platzhalter nicht ersetzt: $($Matches[0])" }
[IO.File]::WriteAllText((Join-Path $stufe 'AppxManifest.xml'), $manifest, (New-Object Text.UTF8Encoding($false)))

# --- Packen (unsigniert, für den Store) ----------------------------------------------------------
$msix = Join-Path $Ziel "$name-$version-x64.msix"
& $makeappx pack /d $stufe /p $msix /o
if ($LASTEXITCODE -ne 0) { throw "makeappx fehlgeschlagen ($LASTEXITCODE)" }

# --- Test-Kopie mit Test-Zertifikat signieren ---------------------------------------------------
# Das Zertifikat entsteht bei jedem Build neu; sein Name muss genau dem Publisher im Manifest entsprechen.
$test = Join-Path $Ziel "$name-Test-$version-x64.msix"
Copy-Item $msix $test
$zert = New-SelfSignedCertificate -Type Custom -Subject $marke['STORE_PUBLISHER'] -KeyUsage DigitalSignature `
    -FriendlyName "$name Test" -CertStoreLocation 'Cert:\CurrentUser\My' `
    -TextExtension @('2.5.29.37={text}1.3.6.1.5.5.7.3.3', '2.5.29.19={text}')
& $signtool sign /fd SHA256 /sha1 $zert.Thumbprint /s My $test
if ($LASTEXITCODE -ne 0) { throw "signtool fehlgeschlagen ($LASTEXITCODE)" }
Export-Certificate -Cert $zert -FilePath (Join-Path $Ziel "$name-Testzertifikat.cer") | Out-Null
Remove-Item -Force "Cert:\CurrentUser\My\$($zert.Thumbprint)"

Remove-Item -Recurse -Force $stufe
Get-ChildItem $Ziel -Filter "$name*" | Where-Object { $_.Extension -in '.msix', '.cer' } | ForEach-Object { Write-Host "  $($_.Name)  $([math]::Round($_.Length / 1MB, 1)) MB" }
