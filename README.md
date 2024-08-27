# ⭐ Argo ⭐
Local Agent platform with generative AI models and tools to make AI helpful for everyone.

## Prerequisites about hardware 🐳

> Before installing Argo, make sure your machine meets the following minimum system requirements:
>
>- CPU >= 2 Core
>- RAM >= 4 GB
>- Disk >= 50 GB
>- GPU >= 8G（Mac M1 above)
>- Extra Software requirements with [Docker](https://www.docker.com/)
>- Docker >= 24.0.0

> [!WARNING]  
> To enable CUDA in Docker, you must install the
> [Nvidia CUDA container toolkit](https://docs.nvidia.com/dgx/nvidia-container-runtime-upgrade/)
> on your Linux/WSL system.

## Quick start with [Docker](https://www.docker.com/) 🐳

- If you are using **Linux**, Ollama included in the image by default.
- If you are using **macOS (Monterey or later)**, Ollama deployed on the host machine by default.
- We'll try out best to install all related tools, follow our suggestions in cmd line.

> [!TIP]  
> Recommend Ollama model: `glm4:9b` for chat, `milkey/dmeta-embedding-zh:f16` for Knowledge of chinese.

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

---

Let's make Argo even more amazing together! 💪

![image](https://github.com/user-attachments/assets/b20fb298-be6d-4e0d-9ca2-bd9097557dac)

