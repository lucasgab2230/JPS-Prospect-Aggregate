#!/bin/bash
set -e

echo "Starting Ollama model initialization..."

# Wait for Ollama server to be ready (server is already started by docker-compose entrypoint)
echo "Waiting for Ollama server to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:11434/api/version > /dev/null 2>&1; then
        echo "Ollama server is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "ERROR: Ollama server failed to start after 60 seconds"
        exit 1
    fi
    echo "Waiting for Ollama server... attempt $i/30"
    sleep 2
done

# Check if qwen3:latest model is already installed
echo "Checking if qwen3:latest model is already installed..."
if ollama list | grep -q "qwen3:latest"; then
    echo "qwen3:latest model is already installed!"
else
    echo "Downloading qwen3:latest model (5.2GB - this may take several minutes)..."

    # Download with retry logic
    MAX_RETRIES=3
    RETRY_COUNT=0

    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        if ollama pull qwen3:latest; then
            echo "Successfully downloaded qwen3:latest model!"
            break
        else
            RETRY_COUNT=$((RETRY_COUNT + 1))
            if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
                echo "Download failed, retrying... ($RETRY_COUNT/$MAX_RETRIES)"
                sleep 5
            else
                echo "ERROR: Failed to download qwen3:latest model after $MAX_RETRIES attempts"
                exit 1
            fi
        fi
    done
fi

# Verify model is properly installed
echo "Verifying model installation..."
if ollama list | grep -q "qwen3:latest"; then
    echo "✓ qwen3:latest model is ready for use!"

    # Test the model with a simple query to ensure it works
    echo "Testing model functionality..."
    if echo "Hello" | ollama run qwen3:latest --max-tokens 5 > /dev/null 2>&1; then
        echo "✓ Model test successful - qwen3:latest is fully functional!"
    else
        echo "⚠ Model downloaded but test failed - this may indicate issues"
    fi
else
    echo "ERROR: Model installation verification failed"
    exit 1
fi

echo "Ollama initialization complete! qwen3:latest is ready for AI enhancements."
