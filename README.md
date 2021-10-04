# Duva

[![Build Status](https://travis-ci.com/onaio/duva.svg?branch=main)](https://travis-ci.com/github/onaio/duva)

Duva is an API built using the [FastAPI](https://github.com/tiangolo/fastapi) framework that provides functionality to create & periodically update Tableau [Hyper](https://www.tableau.com/products/new-features/hyper) databases from CSV files. Currently the application supports connection to an [OnaData](https://github.com/onaio/onadata) server from which it'll pull data from an XLSForm and periodically export to a Tableau Hyper database

## Requirements

- Python 3.6+
- Redis

## Installation

### Via Docker

The application comes with a `docker-compose.yml` file to facilitate easier installation of the project. _Note: The `docker-compose.yml` file is tailored for development environments_

To start up the application via [Docker](https://www.docker.com/products/docker-desktop) run the `docker-compose up` command.

### Alternative Installation

1. Clone repository

```sh
$ git clone https://github.com/onaio/duva.git
```

2. Create & start [a virtual environment](https://virtualenv.pypa.io/en/latest/installation.html) to install dependencies

```sh
$ virtualenv duva
$ source duva/bin/activate
```

3. Install base dependencies

```sh
$ pip install -r requirements.pip
```

4. (Optional: For developer environments) Install development dependencies.

```sh
$ pip install -r dev-requirements.pip
```

5. Create postgres user & database for the application

```sh
$ psql -c "CREATE USER duva WITH PASSWORD 'duva';"
$ psql -c "CREATE DATABASE duva OWNER duva;"
```

At this point the application can be started. _Note: Ensure the redis server has been started_

```
$ ./scripts/start.sh
```

## Configuration

The application can be configured either by manual editing of the `app/settings.py` file or via environment variables i.e `export APP_NAME="Duva"`. More information on this [here](https://fastapi.tiangolo.com/advanced/settings)

## API Documentation

Documentation on the API endpoints provided by the application can be accessed by first running the application and accessing the `/docs` route.

## Testing

This project utilizes [tox](https://tox.readthedocs.io/en/latest/) for testing. In order to run the test suite within this project run the following commands:

```
$ pip install tox
$ tox
```

Alternatively, if you'd like to test the application with only the python version currently installed in your computer follow these steps:

1. Install the developer dependencies

```sh
$ pip install -r dev-requirements
```

2. Run the test suite using [pytest](https://docs.pytest.org/en/stable/)

```sh
$ ./scripts/run-tests.sh
```
>> OR
```sh
$ PYTHONPATH=. pytest -s app/tests
```
