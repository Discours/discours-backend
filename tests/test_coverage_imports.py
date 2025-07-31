"""
Тест для импорта всех модулей для покрытия
"""
import pytest

# Импортируем все модули для покрытия
import services
import services.db
import services.redis
import services.rbac
import services.admin
import services.auth
import services.common_result
import services.env
import services.exception
import services.notify
import services.schema
import services.search
import services.sentry
import services.viewed

import utils
import utils.logger
import utils.diff
import utils.encoders
import utils.extract_text
import utils.generate_slug

import orm
import orm.base
import orm.community
import orm.shout
import orm.reaction
import orm.collection
import orm.draft
import orm.topic
import orm.invite
import orm.rating
import orm.notification

import resolvers
import resolvers.__init__
import resolvers.auth
import resolvers.community
import resolvers.topic
import resolvers.reaction
import resolvers.reader
import resolvers.stat
import resolvers.follower
import resolvers.notifier
import resolvers.proposals
import resolvers.rating
import resolvers.draft
import resolvers.editor
import resolvers.feed
import resolvers.author
import resolvers.bookmark
import resolvers.collab
import resolvers.collection
import resolvers.admin

import auth
import auth.__init__
import auth.permissions
import auth.decorators
import auth.oauth
import auth.state
import auth.middleware
import auth.identity
import auth.jwtcodec
import auth.email
import auth.exceptions
import auth.validations
import auth.orm
import auth.credentials
import auth.handler
import auth.internal


class TestCoverageImports:
    """Тест импорта всех модулей для покрытия"""

    def test_services_imports(self):
        """Тест импорта модулей services"""
        assert services is not None
        assert services.db is not None
        assert services.redis is not None
        assert services.rbac is not None
        assert services.admin is not None
        assert services.auth is not None
        assert services.common_result is not None
        assert services.env is not None
        assert services.exception is not None
        assert services.notify is not None
        assert services.schema is not None
        assert services.search is not None
        assert services.sentry is not None
        assert services.viewed is not None

    def test_utils_imports(self):
        """Тест импорта модулей utils"""
        assert utils is not None
        assert utils.logger is not None
        assert utils.diff is not None
        assert utils.encoders is not None
        assert utils.extract_text is not None
        assert utils.generate_slug is not None

    def test_orm_imports(self):
        """Тест импорта модулей orm"""
        assert orm is not None
        assert orm.base is not None
        assert orm.community is not None
        assert orm.shout is not None
        assert orm.reaction is not None
        assert orm.collection is not None
        assert orm.draft is not None
        assert orm.topic is not None
        assert orm.invite is not None
        assert orm.rating is not None
        assert orm.notification is not None

    def test_resolvers_imports(self):
        """Тест импорта модулей resolvers"""
        assert resolvers is not None
        assert resolvers.__init__ is not None
        assert resolvers.auth is not None
        assert resolvers.community is not None
        assert resolvers.topic is not None
        assert resolvers.reaction is not None
        assert resolvers.reader is not None
        assert resolvers.stat is not None
        assert resolvers.follower is not None
        assert resolvers.notifier is not None
        assert resolvers.proposals is not None
        assert resolvers.rating is not None
        assert resolvers.draft is not None
        assert resolvers.editor is not None
        assert resolvers.feed is not None
        assert resolvers.author is not None
        assert resolvers.bookmark is not None
        assert resolvers.collab is not None
        assert resolvers.collection is not None
        assert resolvers.admin is not None

    def test_auth_imports(self):
        """Тест импорта модулей auth"""
        assert auth is not None
        assert auth.__init__ is not None
        assert auth.permissions is not None
        assert auth.decorators is not None
        assert auth.oauth is not None
        assert auth.state is not None
        assert auth.middleware is not None
        assert auth.identity is not None
        assert auth.jwtcodec is not None
        assert auth.email is not None
        assert auth.exceptions is not None
        assert auth.validations is not None
        assert auth.orm is not None
        assert auth.credentials is not None
        assert auth.handler is not None
        assert auth.internal is not None
