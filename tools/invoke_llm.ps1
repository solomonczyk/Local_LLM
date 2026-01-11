param(
  [string]$Text = "ping",
  [string]$Model = "enhanced-model",
  [string]$BaseUrl = "http://localhost:8002",
  [string]$ApiKey = "dev-local-key"
)

# JSON body без BOM + без лишних переносов
$body = '{"model":"' + $Model + '","messages":[' +
'{"role":"system","content":"Reply with exactly one word. No punctuation. No explanations."},' +
'{"role":"user","content":"' + ($Text.Replace('\','\\').Replace('"','\"')) + '"}' +
']}'


$body | Set-Content -NoNewline -Encoding utf8 .\body.json

curl.exe -s "$BaseUrl/v1/chat/completions" `
  -H "Authorization: Bearer $ApiKey" `
  -H "Content-Type: application/json; charset=utf-8" `
  --data-binary "@body.json"
