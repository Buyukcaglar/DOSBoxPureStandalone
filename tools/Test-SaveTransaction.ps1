[CmdletBinding()]
param(
    [string]$OutputDirectory = (Join-Path $PSScriptRoot '../work/save-transaction-tests'),
    [switch]$AddressSanitizer
)
$ErrorActionPreference = 'Stop'
if (-not (Get-Command cl.exe -ErrorAction SilentlyContinue)) {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
    $installation = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if (-not $installation) { throw 'Visual Studio C++ tools were not found.' }
    Import-Module (Join-Path $installation 'Common7/Tools/Microsoft.VisualStudio.DevShell.dll')
    Enter-VsDevShell -VsInstallPath $installation -SkipAutomaticLocation -DevCmdArguments '-arch=x64 -host_arch=x64' | Out-Null
}
$source = (Resolve-Path (Join-Path $PSScriptRoot '../dosbox-pure/tests/save_transaction_test.cpp')).Path
$null = New-Item -ItemType Directory -Force -Path $OutputDirectory
$output = (Resolve-Path -LiteralPath $OutputDirectory).Path
if (Test-Path -LiteralPath (Join-Path $output 'transaction.pure.zip')) { throw 'Use a fresh isolated output directory; existing test save is preserved.' }
$name = if ($AddressSanitizer) { 'save_transaction_test_asan' } else { 'save_transaction_test' }
Push-Location -LiteralPath $output
try {
    $arguments = @('/nologo', '/EHsc', '/std:c++14', '/W4', '/WX', '/Od', '/Zi',
        '/D_CRT_SECURE_NO_WARNINGS', '/D_CRT_NONSTDC_NO_WARNINGS', "/Fe:$name.exe", "/Fo:$name.obj", "/Fd:$name.pdb")
    if ($AddressSanitizer) { $arguments += '/fsanitize=address' }
    & cl.exe @arguments $source
    if ($LASTEXITCODE -ne 0) { throw "Save transaction test compilation failed ($LASTEXITCODE)." }
    & (Join-Path $output "$name.exe") $output
    if ($LASTEXITCODE -ne 0) { throw "Save transaction tests failed ($LASTEXITCODE)." }
} finally { Pop-Location }
