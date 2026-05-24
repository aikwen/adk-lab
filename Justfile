set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]
set shell := ["bash", "-c"]

base := "http://127.0.0.1:8000"
user := "kwen"
session := "1"

default:
    just --list

# 启动 FastAPI 服务
serve:
    uvicorn app.main:app --reload

# 创建默认 session
create-session user_id=user session_id=session:
    $body = @{ user_id = "{{user_id}}"; session_id = "{{session_id}}" } | ConvertTo-Json -Compress; $tmp = New-TemporaryFile; Set-Content -Path $tmp -Value $body -Encoding utf8; curl.exe -X POST "{{base}}/sessions" --header "Content-Type: application/json" --data-binary "@$tmp"; Remove-Item $tmp

# 查询 session 列表
sessions user_id=user:
    curl.exe "{{base}}/sessions?user_id={{user_id}}"

# 请求大模型，SSE 流式输出
run message user_id=user session_id=session:
    $body = @{ user_id = "{{user_id}}"; session_id = "{{session_id}}"; message = "{{message}}" } | ConvertTo-Json -Compress; $tmp = New-TemporaryFile; Set-Content -Path $tmp -Value $body -Encoding utf8; curl.exe -N -X POST "{{base}}/run_sse" --header "Content-Type: application/json" --header "Accept: text/event-stream" --data-binary "@$tmp"; Remove-Item $tmp

# 查询 session 保存的完整 events
events user_id=user session_id=session:
    curl.exe "{{base}}/sessions/{{session_id}}/events?user_id={{user_id}}"

# 查询所有 LLM request traces
traces:
    curl.exe "{{base}}/traces"

# 查询 session 关联的 LLM request traces
session-traces user_id=user session_id=session:
    curl.exe "{{base}}/sessions/{{session_id}}/traces?user_id={{user_id}}"

# 清空 traces
clear-traces:
    curl.exe -X DELETE "{{base}}/traces"