Write-Host "Updating RepoBrain Knowledge Bases (Incremental)..."

$DOCKER_CMD = "docker run --rm -v ${PWD}:/workspace -e OPENAI_API_BASE=http://host.docker.internal:11434/v1 -e OPENAI_BASE_URL=http://host.docker.internal:11434/v1 -e OPENAI_API_KEY=sk-local -e OPENAI_MODEL=qwen2.5-coder:1.5b -e RB_MODEL=qwen2.5-coder:1.5b -e RB_DEPTH_LIMIT=1 repobrain --quick"

Write-Host "Updating Knowledge Bases & Docs..."
Invoke-Expression "$DOCKER_CMD --workspace /workspace/.ai"
Invoke-Expression "$DOCKER_CMD --workspace /workspace/.agents"
Invoke-Expression "$DOCKER_CMD --workspace /workspace/docs"

Write-Host "Updating Priority Apps..."
Invoke-Expression "$DOCKER_CMD --workspace /workspace/ttttt/cloud-saas"
Invoke-Expression "$DOCKER_CMD --workspace /workspace/ttttt/operator-agent"

Write-Host "Incremental RepoBrain sync complete!"
