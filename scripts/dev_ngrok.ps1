# Start ngrok and print the HTTPS forwarding URL for local dev
# Usage: .\scripts\dev_ngrok.ps1

param(
    [int]$Port = 8000
)

function Find-Ngrok {
    $ngrok = Get-Command ngrok -ErrorAction SilentlyContinue
    if ($ngrok) { return $ngrok.Path }
    return $null
}

$ngrokPath = Find-Ngrok
if (-not $ngrokPath) {
    Write-Host "ngrok not found in PATH. Please install ngrok and ensure it's on PATH: https://ngrok.com/download" -ForegroundColor Yellow
    exit 1
}

# Start ngrok in the background
Write-Host "Starting ngrok (http -> localhost:$Port)..."
$proc = Start-Process -FilePath $ngrokPath -ArgumentList "http $Port" -PassThru

# Wait for ngrok to expose the tunnel via local API
$api = 'http://127.0.0.1:4040/api/tunnels'
$tries = 0
while ($tries -lt 30) {
    try {
        $resp = Invoke-RestMethod -Uri $api -UseBasicParsing -ErrorAction Stop
        if ($resp.tunnels -and $resp.tunnels.Count -gt 0) {
            $https = $resp.tunnels | Where-Object { $_.public_url -like 'https:*' } | Select-Object -First 1
            if ($https) {
                $url = $https.public_url
                Write-Host "ngrok is up — HTTPS URL: $url" -ForegroundColor Green
                Write-Host "Set this as MPESA_CALLBACK_URL in your environment before running STK push. Example (PowerShell):"
                Write-Host "$env:MPESA_CALLBACK_URL = '$url/storefront/mpesa/callback/'" -ForegroundColor Cyan
                Write-Host "Then start your dev server: .venv\Scripts\python.exe manage.py runserver_plus 0.0.0.0:8000 (or your preferred server)"
                exit 0
            }
        }
    } catch {
        Start-Sleep -Milliseconds 500
        $tries++
    }
}

Write-Host "Timed out waiting for ngrok to report a tunnel. Check ngrok logs or run 'ngrok http $Port' manually." -ForegroundColor Red
exit 1
