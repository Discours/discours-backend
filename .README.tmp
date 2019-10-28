[comment]: # "Редактируйте файл README.source.md"

[![Gitter](https://badges.gitter.im/Discours/community.svg)](https://gitter.im/Discours/community?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge)
[![Travis build status](http://img.shields.io/travis/Discours/discours-backend/develop.svg)](https://travis-ci.org/Discours/discours-backend)
[![Maintainability](https://api.codeclimate.com/v1/badges/c61cc1cb7a21e15787e0/maintainability)](https://codeclimate.com/github/Discours/discours-backend/maintainability)
[![Test Coverage](https://api.codeclimate.com/v1/badges/c61cc1cb7a21e15787e0/test_coverage)](https://codeclimate.com/github/Discours/discours-backend/test_coverage)

> Главный бэкэнд Дискурса!

[Дискурс](https://discours.io) (Пока что на старом проекте) | [Бэта Дискурс](https://api-beta.discours.io) (собирается из develop)


### npm run commit

![npm run commit ouput](docs/npm-run-commit/npm-run-commit.svg)

В проекте есть специальный commit prompt, который помогает отформатировать commit message в соответствии с [Conventional Commits](https://www.conventionalcommits.org/ru/v1.0.0-beta.4/). Для его запуска необходимо выполнить `npm run commit`. Он спросит про тип коммита, scope (не обязательно), описание коммита (мы используем present simple в описании, напр. "Create the Button component"), а в конце попробует достать номер issue на GitHub из имени ветки автоматически и добавить его в commit message в следующем формате: `[#10]`. Таким образом создастся ссылка из коммита на issue.

Что такое **scope**? Это объект изменения кода. Если мы пишем commit message без scope, мы часто пишем **.. in something** в конце. Вот этот **something** и есть scope, который выносится в начало коммит сообщения. То есть `Add onPress event handler in Button component` превратится в `feat(Button component): ✨ Add onPress event handler`. **scope** не обязательный, но желательный параметр.

Использования скрипта `npm run commit` необязательно, но тогда надо писать коммит сообщение в соответствии с [Conventional Commits](https://www.conventionalcommits.org/ru/v1.0.0-beta.4/) самому (эмодзи не обязательны).

### Git flow

Для работы в репозитории мы используем [Git flow](https://danielkummer.github.io/git-flow-cheatsheet/index.ru_RU.html).

- `master` — текущая production версия
- `develop` — текущая beta версия

Перед началом работы нужно создать новую ветку из develop:

- `feature/#10` — новый функционал, описанный в GitHub Issue #10
- `bugfix/#10` — баг фикс, описанный в GitHub Issue #10

Лучше использовать номер тикета в названии ветки, чтобы [коммит скрипт](#npm-run-commit) добавлял этот номер в коммит автоматически.
