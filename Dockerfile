FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && pip install -r requirements.txt

COPY . /app

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
