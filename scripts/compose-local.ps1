# Use the installed local overlays without dropping persistent custom-font storage.
$ErrorActionPreference = 'Stop'
$taskProjectRoot = Split-Path -Parent $PSScriptRoot
$taskComposeArgs = @('compose', '--project-directory', $taskProjectRoot)
foreach ($taskFile in @('docker-compose.yml', 'docker-compose.local.yml', 'docker-compose.gpu.yml', 'docker-compose.editorial.yml', 'docker-compose.fonts.yml')) {
    $taskFilePath = Join-Path $taskProjectRoot $taskFile
    if (Test-Path -LiteralPath $taskFilePath) {
        $taskComposeArgs += @('-f', $taskFilePath)
    } elseif ($taskFile -in @('docker-compose.yml', 'docker-compose.local.yml', 'docker-compose.fonts.yml')) {
        throw "Required local configuration is missing: $taskFile"
    }
}
if ($args.Count -gt 0 -and $args[0] -in @('up', 'create', 'run')) {
    & docker volume create supoclip_custom_fonts | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Could not prepare persistent custom-font storage.' }
}
& docker @taskComposeArgs @args
exit $LASTEXITCODE
