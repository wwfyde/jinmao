FROM python:3.12 as builder
LABEL authors="wwfyde"

WORKDIR /app

ENV TZ=Asia/Shanghai
#RUN apt-get update && apt-get install --no-install-recommends -y  default-libmysqlclient-dev build-essential pkg-config &&  rm -rf /var/lib/apt/lists/  \
RUN curl -sSL https://install.python-poetry.org | python3 - \
    && ln -s /root/.local/bin/poetry /usr/local/bin/poetry \
    && poetry config virtualenvs.create false \
    && rm -rf /root/.cache/pip  \
    && rm -rf /root/.cache/pypoetry

COPY . .
#  安装依赖
ARG INSTALL_DEV=false
RUN bash -c "if [ $INSTALL_DEV == 'true' ] ; then poetry install --no-cache; else poetry install --no-cache --only main ; fi"




COPY docker-entrypoint.sh /usr/local/bin/
#ENTRYPOINT ["docker-entrypoint.sh"]

EXPOSE 7003

CMD ["uvicorn",  "api.main:app", "--host", "0.0.0.0", "--port",  "7003"]