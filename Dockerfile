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

## Install/upgrade key dependencies (base image has the rest)
## - google-genai: Gemini AI
## - yt-dlp: latest version needed to bypass YouTube bot detection
RUN pip install --no-cache-dir google-genai && \
    pip install --no-cache-dir -U yt-dlp

ENV PATH="/home/userbot/bin:$PATH"

CMD ["python3","-m","userbot"]
