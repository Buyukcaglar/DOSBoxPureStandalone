[CmdletBinding()]
param(
    [string]$OutputDirectory = (Join-Path $PSScriptRoot '../work/differencing-vhd-tests'),
    [switch]$AddressSanitizer,
    [switch]$WindowsInterop
)
$ErrorActionPreference = 'Stop'

if (-not (Get-Command cl.exe -ErrorAction SilentlyContinue)) {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
    if (-not (Test-Path -LiteralPath $vswhere)) { throw 'Install Visual Studio C++ tools or run from an x64 developer shell.' }
    $installation = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if (-not $installation) { throw 'Visual Studio C++ tools were not found.' }
    Import-Module (Join-Path $installation 'Common7/Tools/Microsoft.VisualStudio.DevShell.dll')
    Enter-VsDevShell -VsInstallPath $installation -SkipAutomaticLocation -DevCmdArguments '-arch=x64 -host_arch=x64' | Out-Null
}

$source = (Resolve-Path (Join-Path $PSScriptRoot '../dosbox-pure/tests/vhd_differencing_test.cpp')).Path
$null = New-Item -ItemType Directory -Force -Path $OutputDirectory
$output = (Resolve-Path -LiteralPath $OutputDirectory).Path
$name = if ($AddressSanitizer) { 'vhd_differencing_test_asan' } else { 'vhd_differencing_test' }
Push-Location -LiteralPath $output
try {
    $arguments = @('/nologo', '/EHsc', '/std:c++14', '/W4', '/WX', '/Od', '/Zi',
        "/Fe:$name.exe", "/Fo:$name.obj", "/Fd:$name.pdb")
    if ($AddressSanitizer) { $arguments += '/fsanitize=address' }
    & cl.exe @arguments $source
    if ($LASTEXITCODE -ne 0) { throw "VHD test compilation failed ($LASTEXITCODE)." }
    $testArguments = @()
    if ($WindowsInterop) { $testArguments += '--windows-interop' }
    & (Join-Path $output "$name.exe") @testArguments
    if ($LASTEXITCODE -ne 0) { throw "VHD tests failed ($LASTEXITCODE)." }
} finally {
    Pop-Location
}
