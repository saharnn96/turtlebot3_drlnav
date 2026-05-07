FROM nvidia/cuda:12.1.1-base-ubuntu22.04

WORKDIR /home

# setup timezone
RUN echo 'Etc/UTC' > /etc/timezone && \
    ln -s /usr/share/zoneinfo/Etc/UTC /etc/localtime && \
    apt-get update && \
    apt-get install -q -y tzdata && \
    rm -rf /var/lib/apt/lists/*

# --- PYTHON3 INSTALLATION ---

# Python 3.10 ships by default on Ubuntu 22.04 — no extra install needed
RUN apt-get update && apt-get install -y python3-pip python3-tk

# Install pytorch (cu121 matches the CUDA 12.1 base image)
RUN pip3 install \
    numpy==1.26.4 \
    matplotlib==3.8.4 \
    pandas==2.2.2 \
    pyqtgraph==0.13.7 \
    PyQt5==5.15.10 \
    torch==2.1.2+cu121 -f https://download.pytorch.org/whl/cu121/torch_stable.html

# --- GAZEBO INSTALLATION ---

RUN apt-get update && apt-get install -y wget curl

# Install Gazebo Classic (11) via apt — available for Ubuntu 22.04 / Humble
RUN apt-get update && apt-get install -y gazebo

# Download basic gazebo models manually instead of complete (slow) download
ENV GAZEBO_MODEL_DATABASE_URI ""
RUN mkdir -p /root/.gazebo/models
WORKDIR /root/.gazebo/models
RUN wget https://raw.githubusercontent.com/osrf/gazebo_models/master/ground_plane/model.sdf -P ./ground_plane
RUN wget https://raw.githubusercontent.com/osrf/gazebo_models/master/ground_plane/model.config -P ./ground_plane
RUN wget https://raw.githubusercontent.com/osrf/gazebo_models/master/sun/model.sdf -P ./sun
RUN wget https://raw.githubusercontent.com/osrf/gazebo_models/master/sun/model.config -P ./sun

# --- ROS2 HUMBLE INSTALLATION ---

# Set locale
RUN apt-get update && apt-get install -y locales
RUN locale-gen en_US en_US.UTF-8
RUN update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
ENV LANG en_US.UTF-8

# Add ROS 2 apt repository
RUN apt-get update && apt-get install -y software-properties-common curl
RUN add-apt-repository universe

RUN curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
RUN echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | tee /etc/apt/sources.list.d/ros2.list > /dev/null

# Install ROS 2 Humble packages
RUN apt-get update && apt-get install -y ros-humble-ros-base python3-argcomplete

RUN apt-get update && apt-get install -y python3-rosdep2

RUN apt-get install -y ros-humble-turtlebot3-description ros-humble-gazebo-ros-pkgs

RUN apt-get update && apt-get install -y ros-dev-tools

# --- INITIALIZE APPLICATION ---

WORKDIR /home/turtlebot3_drlnav

RUN apt-get install -y nano tmux

# Set environment variables for all processes (not just interactive shells)
ENV DRLNAV_BASE_PATH=/home/turtlebot3_drlnav
ENV ROS_DOMAIN_ID=1
ENV TURTLEBOT3_MODEL=burger
ENV GAZEBO_MODEL_PATH=/home/turtlebot3_drlnav/src/turtlebot3_simulations/turtlebot3_gazebo/models
ENV GAZEBO_PLUGIN_PATH=/home/turtlebot3_drlnav/src/turtlebot3_simulations/turtlebot3_gazebo/models/turtlebot3_drl_world/obstacle_plugin/lib

# Set up ~/.bashrc for interactive terminals (source ROS2 and workspace)
RUN printf '\nsource /opt/ros/humble/setup.bash\nsource $DRLNAV_BASE_PATH/install/setup.bash\n' >> ~/.bashrc

CMD ["bash"]
