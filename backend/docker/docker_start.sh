#!/usr/bin/env bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd "$SCRIPT_DIR" || exit

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
python main.py --host "0.0.0.0" --port "8080"
