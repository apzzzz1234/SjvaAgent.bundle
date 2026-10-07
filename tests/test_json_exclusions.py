import ast
import io
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'Contents', 'Code'))
from json_exclusions import load_policy, matches_movie

ENTRY = {'section_id': '2', 'file': '/media/영화/movie.mkv'}
ITEM = {'type': 'movie', 'Media': [{'Part': [{'file': ENTRY['file']}]}]}


class PolicyTests(unittest.TestCase):
    def test_exact(self):
        self.assertTrue(matches_movie([ENTRY], '2', ITEM))

    def test_scope(self):
        self.assertFalse(matches_movie([ENTRY], '3', ITEM))
        self.assertFalse(matches_movie([ENTRY], '2', dict(ITEM, type='episode')))
        self.assertFalse(matches_movie([dict(ENTRY, file='/media/')], '2', ITEM))
        self.assertFalse(matches_movie([dict(ENTRY, enabled=False)], '2', ITEM))
        self.assertFalse(matches_movie([], '2', ITEM))

    def read(self, document):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'policy.json')
            with io.open(path, 'w', encoding='utf-8') as f:
                f.write(json.dumps(document, ensure_ascii=False))
            return load_policy(path)

    def test_load(self):
        self.assertEqual(self.read({'version': 1, 'movies': [ENTRY]}), [ENTRY])

    def test_invalid(self):
        for doc in [{}, {'version': 2, 'movies': []}, {'version': 1, 'movies': {}},
                    {'version': 1, 'movies': [dict(ENTRY, enabled='false')]},
                    {'version': 1, 'movies': [dict(ENTRY, file='relative')]},
                    {'version': 1, 'movies': [dict(ENTRY, section_id='all')]}]:
            with self.assertRaises(ValueError):
                self.read(doc)

    def test_actual_movie_hooks(self):
        # Compile the real policy hooks without requiring Plex's injected SDK.
        path = os.path.join(ROOT, 'Contents', 'Code', 'module_movie.py')
        with io.open(path, encoding='utf-8') as f:
            tree = ast.parse(f.read())
        cls = next(x for x in tree.body if isinstance(x, ast.ClassDef))
        cls.body = [x for x in cls.body if isinstance(x, ast.FunctionDef) and
                    x.name in ('is_json_excluded', 'is_read_json', 'is_write_json', 'remove_info')]
        tree.body = [cls]
        class Base(object):
            def is_read_json(self, media): return 'upstream-read'
            def is_write_json(self, media): return 'upstream-write'
            def remove_info(self, media): return 'upstream-remove'
            def my_JSON_ObjectFromURL(self, url):
                return {'MediaContainer': {'librarySectionID': '2', 'Metadata': [ITEM]}}
        class Logger(object):
            def Info(self, *args): pass
            def Warn(self, *args): pass
        class Media(object): id = '123'
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'policy.json')
            env = {'AgentBase': Base, 'os': os, 'POLICY_PATH': path,
                   'load_policy': load_policy, 'matches_movie': matches_movie, 'Log': Logger()}
            exec(compile(tree, '<actual movie hooks>', 'exec'), env)
            agent = env['ModuleMovie']()
            self.assertEqual(agent.is_read_json(Media()), 'upstream-read')
            with io.open(path, 'w', encoding='utf-8') as f:
                f.write(json.dumps({'version': 1, 'movies': [ENTRY]}))
            self.assertFalse(agent.is_read_json(Media()))
            self.assertFalse(agent.is_write_json(Media()))
            self.assertIsNone(agent.remove_info(Media()))
            with io.open(path, 'w', encoding='utf-8') as f:
                f.write('{}')
            self.assertEqual(agent.is_read_json(Media()), 'upstream-read')
            self.assertEqual(agent.is_write_json(Media()), 'upstream-write')
            self.assertEqual(agent.remove_info(Media()), 'upstream-remove')


if __name__ == '__main__':
    unittest.main()
