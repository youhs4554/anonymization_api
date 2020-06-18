FROM ubuntu:16.04
# For Korean & Chinese
ENV LC_ALL=C.UTF-8
MAINTAINER <hossay> <<youhs4554@gmail.com>>

# Redis 설치하고 서버 실행
RUN apt-get update
RUN apt-get install -y wget build-essential pkg-config && wget http://download.redis.io/releases/redis-6.0.5.tar.gz && tar xzf redis-6.0.5.tar.gz && cd redis-6.0.5 && make -j8 && make install

# 기본 패키지들 설치 및 Python 3.6 설치
RUN apt-get update && \
    apt-get install -y software-properties-common && \
    add-apt-repository ppa:deadsnakes/ppa

RUN apt-get update

RUN apt-get install -y python3.6 python3.6-dev python3-pip python3.6-venv
RUN apt-get install -y git bsdtar

# update pip
RUN python3.6 -m pip install pip --upgrade
RUN python3.6 -m pip install wheel

RUN git clone https://github.com/youhs4554/anonymization_api.git

# 작업 디렉토리로 이동
WORKDIR /anonymization_api

# 작업 디렉토리에 있는 requirements.txt로 패키지 설치
RUN pip3 install -r requirements.txt -i http://ftp.daumkakao.com/pypi/simple --trusted-host ftp.daumkakao.com

ENV FLASK_APP=api.py

# 컨테이너에서 실행될 명령어. 컨테이거나 실행되면 api 서버를 실행시킨다.
CMD redis-server & flask run --host=0.0.0.0

EXPOSE 5000