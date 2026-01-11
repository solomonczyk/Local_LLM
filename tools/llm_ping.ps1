@'
{"model":"enhanced-model","messages":[{"role":"user","content":"ping"}]}
'@ | Set-Content -NoNewline -Encoding utf8 .\body.json

curl.exe -s "http://localhost:8002/v1/chat/completions" `
  -H "Authorization: Bearer dev-local-key" `
  -H "Content-Type: application/json; charset=utf-8" `
  --data-binary "@body.json"
