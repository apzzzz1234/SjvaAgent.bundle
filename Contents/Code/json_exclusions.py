# -*- coding: utf-8 -*-
"""Opt-in, local movie JSON policy; compatible with Plex's Python 2.7."""
import io
import json

POLICY_PATH = '/config/icc-sjva/json-exclusions.json'
MAX_BYTES = 1024 * 1024
try:
    string_types = (basestring,)
except NameError:
    string_types = (str,)


def load_policy(path=POLICY_PATH):
    with io.open(path, 'r', encoding='utf-8') as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('JSON exclusion policy too large')
    policy = json.loads(raw)
    if not isinstance(policy, dict) or policy.get('version') != 1:
        raise ValueError('Unsupported JSON exclusion policy')
    entries = policy.get('movies')
    if not isinstance(entries, list):
        raise ValueError('movies must be a list')
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError('Invalid movie exclusion')
        section = entry.get('section_id')
        filename = entry.get('file')
        if not isinstance(section, string_types) or not section.isdigit():
            raise ValueError('section_id must be a numeric string')
        if not isinstance(filename, string_types) or not filename.startswith('/'):
            raise ValueError('file must be an absolute Plex media path')
        if type(entry.get('enabled', True)) is not bool:
            raise ValueError('enabled must be boolean')
    return entries


def matches_movie(entries, section_id, item):
    if item.get('type') != 'movie':
        return False
    files = set()
    for media in item.get('Media') or []:
        for part in media.get('Part') or []:
            if isinstance(part.get('file'), string_types):
                files.add(part['file'])
    return any(entry.get('enabled', True) and
               entry['section_id'] == str(section_id) and
               entry['file'] in files for entry in entries)
