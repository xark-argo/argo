#!/usr/bin/env sh

SCRIPT_DIR=$(cd "$(dirname "$0")" >/dev/null 2>&1 && pwd)
cd "$SCRIPT_DIR" || exit

if ! command -v docker > /dev/null 2>&1; then
    echo "Docker is not installed, Do you want to download Docker? (Y/n): "
    read -r download_choice
    download_choice=${download_choice:-Y}

    case "$download_choice" in
        [Yy]*)
            if ! command -v brew > /dev/null 2>&1; then
                echo "Homebrew is not installed, Do you want to download Homebrew? (Y/n): "
                read -r download_choice1
                download_choice1=${download_choice1:-Y}
                case "$download_choice1" in
                    [Yy]*)
                        if ! curl -s https://shencha-model-platform.oss-cn-shanghai.aliyuncs.com/brew_install.sh | bash; then
                          echo "Failed to install Homebrew. Please install Homebrew/Docker manually."
                          echo "Homebrew: https://mirrors.tuna.tsinghua.edu.cn/help/homebrew/"
                          echo "Docker: https://www.docker.com/"
                          exit 1
                        fi
                        ;;
                    *)
                        echo "Homebrew is required, please download Homebrew manually."
                        exit 1
                        ;;
                esac
            else
                echo "Homebrew updating, please wait a moment..."
                brew update
            fi

            unameOut="$(uname -s)"
            case "${unameOut}" in
                Linux*)
                    if ! brew install docker; then
                        echo "Failed to install Docker. Please install Docker manually."
                        echo "Docker: https://www.docker.com/"
                        exit 1
                    fi
                    ;;
                Darwin*)
                    if ! brew install --cask --appdir=/Applications docker; then
                        echo "Failed to install Docker. Please install Docker manually."
                        echo "Docker: https://www.docker.com/"
                        exit 1
                    fi
                    ;;
                *)
                    echo "Unknown OS: ${unameOut}"
                    exit 1
                    ;;
            esac
            ;;
        *)
            echo "Docker is required, please download Docker manually."
            exit 1
            ;;
    esac
fi

if ! docker info > /dev/null 2>&1; then
    echo "Docker not started, will start. Do not close Docker while running"
    unameOut="$(uname -s)"
    case "${unameOut}" in
        Linux*)
            sudo systemctl start docker
            ;;
        Darwin*)
            open /Applications/Docker.app
            ;;
        *)
            echo "Unknown OS: ${unameOut}"
            exit 1
            ;;
    esac
else
    echo "Docker application has been started"
fi

unameOut="$(uname -s)"
case "${unameOut}" in
    Linux*)
        echo "System detected as Linux, run ollama inside..."
        curl -s https://shencha-model-platform.oss-cn-shanghai.aliyuncs.com/argo_run_ollama_inside.sh | cat | sh -s "$@"
        ;;
    Darwin*)
        echo "System detected as macOS, run ollama outside..."
        curl -s https://shencha-model-platform.oss-cn-shanghai.aliyuncs.com/argo_run_ollama_outside.sh | cat | sh -s "$@"
        ;;
    *)
        echo "Unknown OS: ${unameOut}"
        ;;
esac
