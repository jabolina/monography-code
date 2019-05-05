FROM python:2

WORKDIR /c

COPY ./app ./app
COPY ./utils/scripts/test.sh ./test.sh
COPY ./requirements.txt ./requirements.txt

RUN pip2 install -r requirements.txt

RUN apt update -yqq

RUN apt install tcpdump -y

CMD ["sleep", "infinity"]
