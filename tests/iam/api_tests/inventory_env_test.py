# Copyright 2017 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests the IAM Explain inventory."""

import unittest
import time
from sqlalchemy import event

from google.cloud.security.common.util.threadpool import ThreadPool
from google.cloud.security.iam.explain.service import GrpcExplainerFactory
from google.cloud.security.iam.inventory.service import GrpcInventoryFactory
from google.cloud.security.iam.playground.service import GrpcPlaygrounderFactory
from google.cloud.security.iam.dao import ModelManager
from google.cloud.security.iam.client import ClientComposition
from google.cloud.security.iam import db

from tests.iam.api_tests.api_tester import ApiTestRunner
from tests.iam.utils.db import create_test_engine, cleanup
from tests.iam.utils.gcp_env import gcp_configured, gcp_env
from tests.unittest_utils import ForsetiTestCase


class TestServiceConfig(object):
    """ServiceConfig Stub."""

    def __init__(self):
        self.engine = create_test_engine()
        self.model_manager = ModelManager(self.engine)
        self.sessionmaker = db.create_scoped_sessionmaker(self.engine)
        self.workers = ThreadPool(10)
        self.env = gcp_env()

        @event.listens_for(self.engine, "connect")
        def do_connect(dbapi_connection, connection_record):
            # disable pysqlite's emitting of the BEGIN statement entirely.
            # also stops it from emitting COMMIT before any DDL.
            dbapi_connection.isolation_level = None

        @event.listens_for(self.engine, "begin")
        def do_begin(conn):
            # emit our own BEGIN
            conn.execute("BEGIN")

        self.listeners = [do_begin, do_connect]

    def get_organization_id(self):
        return self.env.organization_id

    def get_gsuite_sa_path(self):
        return self.env.gsuite_sa

    def get_gsuite_admin_email(self):
        return self.env.gsuite_admin_email

    def run_in_background(self, function):
        """Stub."""
        self.workers.add_func(function)

    def get_engine(self):
        return self.engine

    def scoped_session(self):
        return self.sessionmaker()

    def client(self):
        return ClientComposition(self.endpoint)


def create_tester():
    """Create API test runner."""

    return ApiTestRunner(
        TestServiceConfig(),
        [GrpcExplainerFactory,
         GrpcPlaygrounderFactory,
         GrpcInventoryFactory])


class ApiTest(ForsetiTestCase):
    """Api Test."""

    def setUp(self):
        self.setup = create_tester()

    @unittest.skipUnless(gcp_configured(), "requires a real gcp environment")
    def test_basic(self):
        """Test: Create inventory, foreground & no import."""

        def test(client):
            """API test callback."""

            for progress in client.inventory.create(background=False,
                                                    import_as=""):
                continue
            self.assertTrue(progress.final_message)

            self.assertGreater(len([x for x in client.inventory.list()]),
                               0,
                               'Assert list not empty')
            for inventory_index in client.inventory.list():
                self.assertTrue(inventory_index.id == progress.id)

            self.assertEqual(inventory_index,
                             (client.inventory.get(inventory_index.id)
                              .inventory))

            self.assertEqual(inventory_index,
                             (client.inventory.delete(inventory_index.id)
                              .inventory))

            self.assertEqual([], [i for i in client.inventory.list()])

        self.setup.run(test)

    @unittest.skipUnless(gcp_configured(), "requires a real gcp environment")
    def test_basic_background(self):
        """Test: Create inventory, foreground & no import."""

        def test(client):
            """API test callback."""

            for progress in client.inventory.create(background=True,
                                                    import_as=""):
                continue
            self.assertTrue(progress.final_message)

            while not [x for x in client.inventory.list()]:
                time.sleep(3)

            self.assertGreater(len([x for x in client.inventory.list()]),
                               0,
                               'Assert list not empty')
            for inventory_index in client.inventory.list():
                self.assertTrue(inventory_index.id == progress.id)

            self.assertEqual(inventory_index,
                             (client.inventory.get(inventory_index.id)
                              .inventory))

            self.assertEqual(inventory_index,
                             (client.inventory.delete(inventory_index.id)
                              .inventory))

            self.assertEqual([], [i for i in client.inventory.list()])

        self.setup.run(test)


if __name__ == '__main__':
    unittest.main()