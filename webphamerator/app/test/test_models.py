import unittest
import os.path
import datetime

_DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data')

from webphamerator.app import app, models

class TestModels(unittest.TestCase):

    def test_database_phamerator_name(self):
        input = 'hi this &..'
        name = models.Database.phamerator_name_for(input)
        self.assertTrue(' ' not in name)
        self.assertTrue('.' not in name)
