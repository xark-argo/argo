# ⭐ Argo ⭐
Local Agent platform with generative AI models and tools to make AI helpful for everyone.

## Prerequisites about hardware 🐳

> Before installing Argo, make sure your machine meets the following minimum system requirements:
>
>- CPU >= 2 Core
>- RAM >= 16 GB
>- Disk >= 50 GB
>- GPU >= 8G（Mac M1 above)
>- Extra Software requirements with [Docker](https://www.docker.com/)
>- Docker >= 24.0.0

> [!WARNING]  
> To enable CUDA in Docker, you must install the
> [Nvidia CUDA container toolkit](https://docs.nvidia.com/dgx/nvidia-container-runtime-upgrade/)
> on your Linux/WSL system.

## Quick start with Mac and Windows
Download, Click and Install.

- Macos silicon（M1 and above）：[argo-0.1.2-osx-installer.dmg](https://github.com/xark-argo/argo/releases/download/v0.1.2/argo-0.1.2-osx-installer.dmg)
- Windows 64bit（win 10 and above）：[argo-0.1.2-windows-x64-installer.exe](https://github.com/xark-argo/argo/releases/download/v0.1.2/argo-0.1.2-windows-x64-installer.exe)

## Quick start with [Docker](https://www.docker.com/) 🐳

- If you are using **Linux**, Ollama included in the image by default.
- If you are using **MacOS (Monterey or later)**, Ollama deployed on the host machine by default.
- If you are using **Windows**, please manually install [Docker](https://www.docker.com/) and WSL environment, then follow Linux instructions.
- We'll use brew to install docker and ollama, if something wrong, you can install [docker](https://www.docker.com/) and [ollama](https://ollama.com/download) yourself.

> [!TIP]  
> Recommend Ollama model: `glm4` for chat, `shaw/dmeta-embedding-zh` for Knowledge of chinese.

  ```bash    
  # Usage: {run [-n name] [-p port] | stop [-n name] | update}
  # default name: argo
  # default port: 38888
  
  # Download image, create a container and start
  sh argo_run_docker.sh run
  
  # Stop the container (data will be retained)
  sh argo_run_docker.sh stop
  
  # Update the image to the latest version (the original image will be deleted)
  sh argo_run_docker.sh update
  ```

---
> Free to join us and talk: https://discord.gg/79AD9RQnHF

Let's make Argo even more amazing together! 💪

![image](https://github.com/user-attachments/assets/25825314-3b5d-4223-8c9d-7f11dc64a09d)
![image](https://github.com/user-attachments/assets/5163b6d0-9efa-44a4-b279-aede82bac42b)



