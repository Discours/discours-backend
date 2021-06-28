up-pip:
	pip install --upgrade pip

freeze:
	pip freeze>requirements.txt

install-pkg:
	pip install -r requirements.txt

uninstall-pkg:
	pip freeze | xargs pip uninstall -y

server-up:
	docker-compose up -d --remove-orphans
	docker-compose ps

server-down:
	docker-compose down
	docker-compose ps
