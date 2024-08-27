# ⭐ Argo ⭐
Local Agent platform with generative AI models and tools to make AI helpful for everyone.

## Prerequisites about hardware 🐳

> Before installing Argo, make sure your machine meets the following minimum system requirements:
>
>- CPU >= 2 Core
>- RAM >= 4 GB
>- Disk >= 50 GB
>- GPU >= 8G（Mac M1 above)
> Extra Software requirements with [Docker](https://www.docker.com/)
>- Docker >= 24.0.0

> [!WARNING]  
> When using Docker, make sure to include the `-v ./argo:/root/.argo` in your Docker command.  
> This step is crucial as it ensures all your data is properly mounted and prevents any loss of data.
>
> **TIP:** To enable CUDA in Docker, you must install the
> [Nvidia CUDA container toolkit](https://docs.nvidia.com/dgx/nvidia-container-runtime-upgrade/)
> on your Linux/WSL system.

## Quick start with [Docker](https://www.docker.com/) 🐳

- If you are using **Linux**, Ollama included in the image will be used by default.
- If you are using **macOS (Monterey or later)**, Ollama deployed on the host machine will be used by default.

> [!TIP]  
> Recommend Ollama model: `glm4:9b` for chat, `milkey/dmeta-embedding-zh:f16` for embedding of chinese.

  ```bash    
  # Usage: {run [-n name] [-p port] | stop [-n name] | update}
  # default name: argo
  # default port: 38888
  
  curl -O https://shencha-model-platform.oss-cn-shanghai.aliyuncs.com/argo_run_docker.sh
  
  # Download image, create a container and start
  sh argo_run_docker.sh run
  
  # Stop the container (data will be retained)
  sh argo_run_docker.sh stop
  
  # Update the image to the latest version (the original image will be deleted)
  sh argo_run_docker.sh update
  ```



### Installing Argo with bundled Ollama support

> [!NOTE]  
> If you can't access to [huggingface](https://huggingface.co/), add arg `-e USE_HF_MIRROR=true` to use mirror source.

- **With GPU Support**:
  Utilize GPU resources by running the following command:

  ```bash
  docker run -d -p 38888:80 --gpus=all -v ./ollama:/root/.ollama -v ./argo:/root/.argo --name argo --restart always harbor.ixiaochuan.cn/argo/argo:ollama
  ```

- **For CPU Only**:
  If you're not using a GPU, use this command instead:

  ```bash
  docker run -d -p 38888:80 -v ./ollama:/root/.ollama -v ./argo:/root/.argo --name argo --restart always harbor.ixiaochuan.cn/argo/argo:ollama
  ```

### Installing Argo without bundled Ollama

> [!NOTE]  
> If not use Bundled Ollama, the ability to download models
> from [huggingface](https://huggingface.co/) will be disabled.

- **To connect to other Ollama**, change the `OLLAMA_BASE_URL` to the server's URL:

  ```bash
  docker run -d -p 38888:80 -e OLLAMA_BASE_URL=https://example.com -v ./argo:/root/.argo --name argo --restart always harbor.ixiaochuan.cn/argo/argo:main
  ```

- **If Ollama is in another container on your computer:** If you want to
  use huggingface model download feature, modify the `USE_ARGO_OLLAMA` to `true`,
  and mount the Argo folder to Ollama container via `-v ./argo:/root/.argo`:

  ```

h # run Argo
docker run -d -p 38888:80 -e USE_ARGO_OLLAMA=true -e OLLAMA_BASE_URL=https://example.com -v ./argo:/root/.argo --name
argo --restart always harbor.ixiaochuan.cn/argo/argo:
n # run Olama (omit other docker command args)
docker run -v ./argo:/root/.argo ollama/ollama:latest

  ```

### Build your own Docker image via Dockerfile

> [!NOTE]  
> If you need download mirror source, add arg `--build-arg USE_PROXY_SOURCE=true` to use.  
> If you need to use PostgreSQL(default SQLite), add arg `--build-arg USE_POSTGRESQL=true` to use.

- **With bundled Ollama:**

  ```bash
  docker build -t argo:ollama --build-arg USE_OLLAMA=true .
  ```

- **Without bundled Ollama:**

  ```bash
  docker build -t argo:main .
  ```

# Troubleshooting 🚀

> - If convert model failed with `BPE pre-tokenizer was not recognized`, please
    check [llama.cpp#6920](https://github.com/ggerganov/llama.cpp/pull/6920) and
    modify `module/llama/convert_hf_to_gguf.py` as needed, and restart the service.

---

Let's make Argo even more amazing together! 💪
