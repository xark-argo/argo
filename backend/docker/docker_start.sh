#!/usr/bin/env bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd "$SCRIPT_DIR" || exit

if [[ "${USE_OLLAMA,,}" == "true" ]]; then
    echo "USE_OLLAMA is set to true, starting ollama serve."
    export OLLAMA_HOST="0.0.0.0:11434"
    export OLLAMA_NUM_PARALLEL=4
    export OLLAMA_MAX_LOADED_MODELS=4
    export OLLAMA_FLASH_ATTENTION=1

    export OLLAMA_BASE_URL="http://localhost:11434"
    export USE_ARGO_OLLAMA='true'

    mv /root/.ollama_models /root/.ollama/models
    ollama serve &
fi

if [[ "${USE_HF_MIRROR,,}" == "true" ]]; then
    echo "USE_HF_MIRROR is set to true, set HF_ENDPOINT to https://hf-mirror.com"
    export HF_ENDPOINT="https://hf-mirror.com"
fi

sleep 5 && echo "Ollama url: $OLLAMA_BASE_URL"
if curl --output /dev/null --silent --fail $OLLAMA_BASE_URL; then
    echo "Ollama service is reachable"
else
    echo "Ollama service is not reachable, please check"
fi

export USE_ARGO_TRACKING="true"

echo "starting argo serve."
python main.py --serve --host "0.0.0.0" --port "8080"
