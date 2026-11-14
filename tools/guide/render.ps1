$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$base = "C:\Users\Administrator\Desktop\Club\tools\guide"
$out  = "$base\out"
New-Item -ItemType Directory -Force -Path $out | Out-Null

Get-ChildItem "$base\slides" -Directory | ForEach-Object {
  $role = $_.Name
  New-Item -ItemType Directory -Force -Path "$out\$role" | Out-Null
  foreach ($f in Get-ChildItem "$($_.FullName)\slide-*.html" | Sort-Object Name) {
    $name = [System.IO.Path]::GetFileNameWithoutExtension($f.Name)
    $outFile = "$out\$role\$name.png"
    & $chrome --headless=new --disable-gpu --no-sandbox --hide-scrollbars --force-device-scale-factor=1 `
      --window-size=1920,1080 --virtual-time-budget=10000 --screenshot="$outFile" "file:///$($f.FullName -replace '\\','/')" 2>&1 | Out-Null
    if (Test-Path $outFile) { "OK  $role/$name" } else { "FAIL $role/$name" }
  }
}
