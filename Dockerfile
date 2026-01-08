FROM catub/core:bullseye

# Working directory
WORKDIR /userbot

# Timezone
ENV TZ=Asia/Kolkata

# Install Python 3.11
RUN apt-get update && apt-get install -y \
    software-properties-common \
    ca-certificates \
    curl \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    python3-pip \
    && ln -sf /usr/bin/python3.11 /usr/bin/python3 \
    && ln -sf /usr/bin/python3.11 /usr/bin/python \
    && rm -rf /var/lib/apt/lists/*

## Copy files into the Docker image
COPY . .

ENV PATH="/home/userbot/bin:$PATH"

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt


CMD ["python3","-m","userbot"]
