# PhamDB
A web application for quickly creating and modifying [Phamerator](http://phagesdb.org/Phamerator/faq/) databases.

## Features
  
  * Create and manage multiple Phamerator databases
  * Upload genbank files to create a database
  * Add and remove phages from existing databases
  * Analyze your databases in Phamerator
  * See live status of running jobs
  * Queue multiple jobs
  * Search NCBI's conserved domain database

## Screenshots

#### Upload genbank files
![Upload genbank](img/screenshot-upload-genbank.png)

#### See detailed error messages of invalid phages
![Genbank validation](img/screenshot-invalid-genbank.png)

#### Analyze your database in Phamerator
![Create database](img/screenshot-database.png)

## For users

### Installing

PhamDB is distributed as a Docker image. You will need a Linux server with Docker installed.

Use the following commands to download and run PhamDB:

Download the image:

    docker pull jglamine/phamdb:latest

Create a directory to store the database in:

    mkdir /home/<username>/phamdb

Run the server as a daemon, set to start automatically when the server starts.

    docker run -d --restart=always -p=80:80 -v /home/<username>/phamdb:/dockerdata jglamine/phamdb:latest

You can now use PhamDB by visiting your server's IP address with a web browser.

#### Minimum system requirements

  * Linux server with Docker installed
  * 2GB of RAM
  * 6GB of hard drive space

##### Recommended

  * Dual core processor

### Security

By default, PhamDB does not have any security set up. Anyone on the internet can view, modify, and delete your databases.

#### Set a password

You can add a master password to PhamDB by clicking on `Settings` in the upper right hand corner. Users will need this password in order to use the site.

## For developers

PhamDB is a Python Flask application. It uses Python 2.7, MySQL and RabbitMQ, and calls several Linux command line programs to process gene data.

The easiest way to see how the application is set up is to read the `Dockerfile` (`docker/Dockerfile`). It contains information on the various dependencies required. Note that `nginx` and `uwsgi` are only needed for production, not development.

### Setup

Read the `Dockerfile` (`docker/Dockerfile`) to see the basics of how the application is set up.

Among other things, be sure to clone the repository, install the required linux packages, create a python virtual environment, install python packages from `requirements.txt`, add the project to the virtual environment's `PYTHONPATH`, run the database creation script, download the conserved domain database using the included makefile (`pham/data/conserved-domain-database/Makefile`), and verify that all of the tests pass.

### Running PhamDB locally

Once you have installed the dependencies and required python packages, you will have to run two commands:

Run the application server with:

    python webphamerator/run.py

Run the Celery background job processor with:

    celery -A webphamerator.app.celery worker

### Testing

From the project's root directory, run the tests with:

    nosetests

## License

PhamDB is licensed under the GNU GPL, version 3. See `license.txt` for the full license.
