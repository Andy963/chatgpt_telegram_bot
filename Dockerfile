FROM python:3.8-slim


RUN mkdir -p /code /etc/gpt
ADD . /code
WORKDIR /code
RUN apt-get update  && apt-get install -y  ffmpeg && \
    pip3 install -r requirements.txt && rm -rf /root/.cache && apt-get autoclean  &&  rm -rf /tmp/* /var/lib/apt/* /var/cache/* /var/log/*

CMD ["python3","app.py"]