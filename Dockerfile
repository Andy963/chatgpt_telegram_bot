FROM python:3.10-slim-buster as builder

RUN mkdir -p /code
ADD . /code
WORKDIR /code
COPY requirements.txt ./
RUN apt-get update -y && \
    apt-get install -y ffmpeg --no-install-recommends && \
    pip install --upgrade pip && \
    pip install -r requirements.txt && \
    apt-get clean && \
    apt-get autoclean && \
    apt-get autoremove && \
    rm -rf /root/.cache /tmp/* /var/tmp/* /var/lib/apt/* /var/cache/* /var/log/*  && \
    rm -rf /usr/share/doc /usr/share/man /usr/share/locale

FROM builder
WORKDIR /code
COPY . .
CMD ["python3","app.py"]