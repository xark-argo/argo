# ⭐ Argo ⭐

拥有生成式AI模型和工具的本地代理平台，使AI对每个人都有帮助。
- 官网地址：www.xark-argo.com

## 新版本特性
- 1. 支持导入酒馆卡进行角色扮演，仅需几次点击即可完成角色卡导入、推荐模型安装，快速开始。
- 2. 支持机器人设置背景图。
- 3. 角色扮演支持edge tts语音播放、live2d动态纸片人，增加了更多的趣味性，内置了2个纸片人模型，如需使用自己的纸片人，请告诉我们，我们将在后续开放使用自定义纸片人。

## 环境需求 🐳

> 如果您仅调用远程大模型API，则对设备没有特殊要求（Mac inter芯片暂不支持，即将开放）
>
> 如果您要在本地运行大模型推理，请确保您的机器满足以下最低系统要求：
>
>- CPU >= 2核心
>- 内存 >= 16 GB
>- 磁盘 >= 50 GB
>- GPU >= 8G（适用于Mac M1及更高版本、Window 10以上）

## 使用 Mac 或 Windows 快速安装
下载、双击、完成安装.
- Macos silicon：[argo-0.1.7-osx-installer.dmg](https://github.com/xark-argo/argo/releases/download/v0.1.7/argo-0.1.7-osx-installer.dmg)
- Macos intel：[argo-0.1.7-mac-intel-installer.dmg](https://github.com/xark-argo/argo/releases/download/v0.1.7/argo-0.1.7-mac-intel-installer.dmg)
- Windows 64bit（Win 10 and above）：[argo-0.1.7-windows-installer.exe](https://github.com/xark-argo/argo/releases/download/v0.1.7/argo-0.1.7-windows-installer.exe)
- [快速开始教程](https://docs.xark-argo.com/)

## 使用[Docker](https://www.docker.com/)快速开始 🐳
>- 需要安装软件[ Docker](https://www.docker.com/)
>- Docker >= 24.0.0

> [!WARNING]
> 要在Docker中启用CUDA，您必须在您的Linux/WSL系统上安装
> [Nvidia CUDA容器工具包](https://docs.nvidia.com/dgx/nvidia-container-runtime-upgrade/).

- 如果您使用的是 **Linux**，Ollama将默认包含在镜像中。
- 如果您使用的是 **MacOS (Monterey或更高版本)**，Ollama将默认部署在主机机器上。
- 如果您使用的是 **Windows**，需要先自行安装docker及wsl环境，安装过程同Linux。
- 我们将使用brew来安装docker和ollama，如果出现问题，您可以自己安装[ Docker](https://www.docker.com/) 和 [ollama](https://ollama.com/download)。

> [!TIP]
> 推荐的Ollama模型：`qwen2.5:7b`用于聊天，`shaw/dmeta-embedding-zh`用于中文知识库。

  ```bash
  # 使用方法：{run [-n name] [-p port] | stop [-n name] | update}
  # 默认名称：argo
  # 默认端口：38888
  
  # 下载镜像，创建容器并启动
  sh argo_run_docker.sh run
  
  # 停止容器（数据将被保留）
  sh argo_run_docker.sh stop
  
  # 更新镜像到最新版本（原始镜像将被删除）
  sh argo_run_docker.sh update
  ```


---
> 交流讨论：
> 
> discord: https://discord.gg/79AD9RQnHF
>
> 微信群：
>
> <img src="https://github.com/user-attachments/assets/0ae6746e-7889-4acd-961c-77de128b55d0" alt="图片" style="width:100px;height:100px;">

一起携手让Argo越来越好！💪
![image](https://github.com/user-attachments/assets/b1d38101-9a50-4eb7-ad00-8b464e889738)
![image](https://github.com/user-attachments/assets/25825314-3b5d-4223-8c9d-7f11dc64a09d)
![image](https://github.com/user-attachments/assets/c9e15ce7-ab02-4f1a-ac7d-16c47030876f)
