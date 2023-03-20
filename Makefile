.DEFAULT_GOAL := all
ROOT_DIR ?= .

.PHONY: all
all: build setup

.PHONY: setup
setup:
	docker-compose up -d
	docker-compose run --rm --entrypoint 'python3 manage.py' app migrate
	docker-compose run --rm --entrypoint 'python3 manage.py' app loaddata */fixtures/*
	docker-compose run --rm --entrypoint 'python3 manage.py' app createsuperuser

.PHONY: build
build:
	DOCKER_BUILDKIT=1 docker build --pull --ssh default -t amuse.io/app .

.PHONY: test
test:
	@python3 manage.py test --settings=amuse.settings.unified \
		$(PATTERN) \
		$(ARGS)

.PHONY: test-xdist
test-xdist:
	@python3 manage.py test --settings=amuse.settings.unified -- -n \
		$(PATTERN) \
		$(ARGS)

.PHONY: coverage
coverage:
	@coverage erase && \
	 coverage run \
	 	--rcfile ${ROOT_DIR}/setup.cfg \
		manage.py test \
			--verbosity 2 \
			--no-input \
			--keepdb \
			$(ARGS) && \
	 coverage report \
	 	--rcfile ${ROOT_DIR}/setup.cfg && \
	 coverage erase

.PHONY: coverage-html
coverage-html:
	@coverage erase && \
	 coverage run \
	 	--rcfile ${ROOT_DIR}/setup.cfg \
		manage.py test \
			--verbosity 2 \
			--no-input \
			--keepdb \
			$(ARGS) && \
	 coverage html\
	 	--rcfile ${ROOT_DIR}/setup.cfg && \
	 coverage erase

.PHONY: configure-hooks
configure-hooks:
	git config --local core.hooksPath .githooks

.PHONY: lint
lint:
	@flake8 --append-config ${ROOT_DIR}/setup.cfg ${ROOT_DIR}/src && \
	 echo "OK"

.PHONY: black
black:
	@if [ ! $(ARGS) ]; then \
		echo "Running black on modified python files"; \
		(cd .. && black $(shell git diff --name-only --diff-filter=AM | grep .py$)); \
	else \
		echo "Running black on provided paths"; \
		(cd .. && black $(ARGS)); \
	fi

.PHONY: shell
shell:
	@python3 manage.py shell

.PHONY: manage
manage:
	@python3 manage.py \
		$(PATTERN) \
		$(ARGS)

.PHONY: reset-minio
reset-minio:
	docker-compose stop minio
	docker-compose rm -v minio
	docker volume rm amusedjango_minio-data
	docker-compose up -d minio

#| Assign ARGS variable to tokens after first given target
#| and then evaluate them into new noop targets if require-args.
#| Example: make <target> <ARGS>
ARGS := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))
$(eval $(ARGS):;@:)

#| Target dependency helper, ensuring target arg is given.
.PHONY: require-args
require-args:
ifndef ARGS
	$(error Missing target args, i.e. make <target> <arg>)
endif

#| docker-compose wrapper running arguments as
#| actual make targets within a container.
#|
#| Usage: make docker <make-target>
#| Example: make docker test
.PHONY: docker
docker: require-args
	@docker-compose run \
		--rm \
		--entrypoint make \
		app \
		HOST_PWD=${PWD} ROOT_DIR=.. --makefile ../Makefile $(ARGS)
