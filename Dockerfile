# Stage 1 — official Python 3.11
FROM python:3.11-slim AS pybuilder

# Stage 2 — CatUB base
FROM catub/core:bullseye

# Working directory
WORKDIR /userbot

# Timezone
ENV TZ=Asia/Kolkata

# Copy Python 3.11 runtime + pip
COPY --from=pybuilder /usr/local /usr/local

# Copy project files
COPY . .

# Ensure correct python is used
RUN python --version && pip --version

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Start CatUB
CMD ["python","-m","userbot"]
