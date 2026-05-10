$response = Invoke-WebRequest -Uri 'http://localhost:8000/login' -UseBasicParsing
Write-Output "Status Code: $($response.StatusCode)"
Write-Output "Content Length: $($response.Content.Length)"
if ($response.Content -match "PL5") {
    Write-Output "Contains PL5 title: Yes"
}
if ($response.Content -match "login") {
    Write-Output "Contains login form: Yes"
}
