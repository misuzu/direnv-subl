import concurrent.futures
import hashlib
import json
import os
import re
import shutil
import subprocess

import sublime
import sublime_plugin

from .progressbar import progressbar


ANSI_ESCAPE_RE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


def get_output(cmd, cwd, env=None):
    try:
        process = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
    except OSError as e:
        return (
            e.errno,
            None,
            "Executing %s has failed: %s" % (cmd, e)
        )
    else:
        return (
            process.wait(),
            process.stdout.read().decode(),
            ANSI_ESCAPE_RE.sub('', process.stderr.read().decode())
        )


class DirenvCache(object):
    def __init__(self, cache_path):
        self._cache = {}
        self._cache_path = cache_path

    def _get_cache_file_path(self, file_path):
        name = '%s-%s.cache' % (
            hashlib.md5(file_path.encode()).hexdigest(),
            os.path.basename(file_path))
        return os.path.join(self._cache_path, name)

    def get(self, file_path):
        path = self._get_cache_file_path(file_path)
        if path not in self._cache:
            if os.path.isfile(path):
                with open(path, 'r') as f:
                    self._cache[path] = json.load(f)
        return {
            k: v
            for k, v in self._cache.get(path, {}).items()
            if v is not None}

    def set(self, file_path, value):
        os.makedirs(self._cache_path, exist_ok=True)
        path = self._get_cache_file_path(file_path)
        with open(path, 'w') as f:
            json.dump(value, f)
        self._cache[path] = value

    def clear(self):
        shutil.rmtree(self._cache_path, ignore_errors=True)
        self._cache.clear()


class Direnv(object):
    def __init__(self, cache):
        self._cache = cache
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self._current_path = None
        self._previous_env = {}

    @staticmethod
    def _find_envrc_directory(file_name):
        while file_name and file_name != '/':
            envrc_path = os.path.join(file_name, '.envrc')
            if os.path.isfile(envrc_path):
                return file_name
            file_name = os.path.dirname(file_name)

    def _update_environment(self, file_path):
        def rollback_env():
            self._previous_env, previous_env = {}, self._previous_env
            for key, value in previous_env.items():
                if value is None:
                    os.environ.pop(key)
                else:
                    os.environ[key] = value

        direnv_path = self._find_envrc_directory(file_path)
        direnv_path_prev = self._current_path

        self._current_path = direnv_path

        if direnv_path is None:
            if direnv_path_prev is not None:
                rollback_env()
                sublime.status_message(
                    "direnv: unloaded %s" % direnv_path_prev)
            return

        environment = self._cache.get(direnv_path)

        with progressbar(lambda tick: sublime.status_message(
                "direnv: loading %s %s" % (direnv_path, tick))):
            returncode, stdout, stderr = get_output(
                ['direnv', 'export', 'json'],
                direnv_path,
                dict(os.environ, **environment))
        if returncode != 0:
            self._current_path = None
            rollback_env()
            sublime.status_message(stderr)
            return

        if stdout:
            environment = dict(environment, **json.loads(stdout))
            self._cache.set(direnv_path, environment)

        rollback_env()

        for key, value in environment.items():
            if key.startswith('DIRENV_') or value is None:
                continue
            prev = os.environ.get(key)
            if prev != value:
                self._previous_env[key] = prev
                os.environ[key] = value

        if stdout or direnv_path != direnv_path_prev:
            sublime.status_message("direnv: loaded %s" % direnv_path)

    def push(self, file_path):
        if shutil.which('direnv') is not None:
            future = self._executor.submit(self._update_environment, file_path)
            future.add_done_callback(lambda f: f.result())


direnv_cache = DirenvCache(os.path.join(sublime.cache_path(), 'Direnv'))
direnv = Direnv(direnv_cache)


class DirenvEventListener(sublime_plugin.ViewEventListener):
    def on_load(self):
        direnv.push(self.view.file_name())

    def on_activated(self):
        direnv.push(self.view.file_name())

    def on_post_save(self):
        direnv.push(self.view.file_name())


class DirenvAllow(sublime_plugin.TextCommand):
    def run(self, edit):
        returncode, stdout, stderr = get_output(
            ['direnv', 'allow'],
            os.path.dirname(self.view.file_name()))
        if returncode != 0:
            sublime.status_message(stderr)
        else:
            direnv.push(self.view.file_name())


class DirenvDeny(sublime_plugin.TextCommand):
    def run(self, edit):
        returncode, stdout, stderr = get_output(
            ['direnv', 'deny'],
            os.path.dirname(self.view.file_name()))
        if returncode != 0:
            sublime.status_message(stderr)
        else:
            direnv.push(self.view.file_name())


class DirenvClear(sublime_plugin.TextCommand):
    def run(self, edit):
        direnv_cache.clear()
        direnv.push(self.view.file_name())


def plugin_loaded():
    if shutil.which('direnv') is None:
        sublime.status_message(
            "direnv: No direnv executable found, "
            "follow https://direnv.net for installation instructions")
        return


def plugin_unloaded():
    direnv.push(None)
