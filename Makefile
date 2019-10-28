# Usage: make start
start:
	docker-compose -f docker-compose.dev.yml run start
test:
	docker-compose -f docker-compose.dev.yml run npm test
npm-install:
	docker-compose -f docker-compose.dev.yml run npm npm install
npm-outdated:
	docker-compose -f docker-compose.dev.yml run npm npm outdated
# Usage: make list package=acorn
npm-list:
	docker-compose -f docker-compose.dev.yml run npm npm list $(package)