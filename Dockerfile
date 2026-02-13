# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# CatUserBot #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2020-2023 by TgCatUB@Github.

# This file is part of: https://github.com/TgCatUB/catuserbot
# and is released under the "GNU v3.0 License Agreement".

# Please see: https://github.com/TgCatUB/catuserbot/blob/master/LICENSE
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

FROM catub/core:bullseye

# Working directory 
WORKDIR /userbot

# Timezone
ENV TZ=Asia/Kolkata

## ffmpeg for yt-dlp (merge audio+video, postprocessors)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

## Copy project first
COPY . .

## Install only the new Gemini dependency (base image has the rest; full requirements.txt conflicts with Python 3.9 e.g. yt-dlp)
RUN pip install --no-cache-dir google-genai

ENV PATH="/home/userbot/bin:$PATH"

CMD ["python3","-m","userbot"]
