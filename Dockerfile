FROM python:3
MAINTAINER Logan Hanks <logan@euphoria.io>
RUN apt-get update && apt-get install -y sqlite3
WORKDIR /src/weedbot
CMD [ "./run.sh" ]
