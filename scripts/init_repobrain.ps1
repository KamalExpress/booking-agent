Write-Host "Building RepoBrain Docker Image..."
docker build -t repobrain -f scripts/Dockerfile.repobrain .

# We use Ollama's OpenAI-compatible endpoint. By NOT prefixing the model with openai/
# it will pass the literal model name 'qwen2.5-coder:1.5b' to Ollama.
$DOCKER_CMD = "docker run --rm -v ${PWD}:/workspace -e OPENAI_API_BASE=http://host.docker.internal:11434/v1 -e OPENAI_BASE_URL=http://host.docker.internal:11434/v1 -e OPENAI_API_KEY=sk-local -e OPENAI_MODEL=qwen2.5-coder:1.5b -e RB_MODEL=qwen2.5-coder:1.5b -e RB_DEPTH_LIMIT=1 repobrain"

Write-Host "Indexing Knowledge Bases & Docs..."
Invoke-Expression "$DOCKER_CMD --workspace /workspace/.ai"
Invoke-Expression "$DOCKER_CMD --workspace /workspace/.agents"
Invoke-Expression "$DOCKER_CMD --workspace /workspace/docs"

Write-Host "Indexing Priority Apps..."
Invoke-Expression "$DOCKER_CMD --workspace /workspace/ttttt/cloud-saas"
Invoke-Expression "$DOCKER_CMD --workspace /workspace/ttttt/operator-agent"

Write-Host "Initial RepoBrain sync complete!"
