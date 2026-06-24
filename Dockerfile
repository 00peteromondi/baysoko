FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV DJANGO_SETTINGS_MODULE=baysoko.settings

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl gcc libpq-dev git \
    && rm -rf /var/lib/apt/lists/*

# Clone the repository including submodules
# Use environment variable or default to origin URL from standard layout
ARG REPO_URL=https://github.com/00peteromondi/baysoko.git
ARG GIT_REF=main

RUN git clone --depth 1 --branch ${GIT_REF} --recursive ${REPO_URL} . || \
    (echo "Clone failed, trying without recursive..." && \
     git clone --depth 1 --branch ${GIT_REF} ${REPO_URL} . && \
     git submodule update --init --recursive)

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && pip install -r requirements.txt

RUN mkdir -p \
  media/store_logos \
  media/store_covers \
  media/v1/chat_attachments \
  media/chat_attachments \
  media/listing_images \
  media/profile_pics \
  media/blog_images \
  static/images \
  static/css \
  static/js \
  templates/socialaccount \
  templates/account

EXPOSE 8000

CMD ["bash", "deploy/railway_start.sh"]
