FROM tiangolo/uvicorn-gunicorn-fastapi:python3.10

WORKDIR /app/

COPY ./requirements.pip /app/requirements.pip
COPY ./dev-requirements.pip /app/dev-requirements.pip
RUN pip install -r requirements.pip

ARG INSTALL_DEV=false
RUN bash -c "if [ $INSTALL_DEV == 'true' ] ; then pip install -r dev-requirements.pip ; fi"

COPY . /app
ENV PYTHONPATH=/app
