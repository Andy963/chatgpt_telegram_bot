FROM python:3.8-slim

ENV PYTHONFAULTHANDLER=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONHASHSEED=random
ENV PYTHONDONTWRITEBYTECODE 1
ENV PIP_NO_CACHE_DIR=off
ENV PIP_DISABLE_PIP_VERSION_CHECK=on
ENV PIP_DEFAULT_TIMEOUT=100


RUN mkdir -p /code /etc/gpt
ADD . /code
WORKDIR /code
RUN apt-get update  && apt-get install -y python3 python3-pip python-dev build-essential python3-venv && \
    pip3 install -r requirements.txt && rm -rf /root/.cache && apt-get autoclean && apt-get --purge autoremove -y python-dev gcc &&  rm -rf /tmp/* /var/lib/apt/* /var/cache/* /var/log/*

CMD ["python3","app.py"]