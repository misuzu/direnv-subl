import concurrent.futures
import json
import os
import subprocess

import sublime
import sublime_plugin


class Direnv(object):
    def __init__(self):
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self._direnv = {}
        self._previous_environment = {}
        self._current_direnv_path = None

    @staticmethod
    def _find_envrc_directory(file_name):
        while file_name and file_name != '/':
            envrc_path = os.path.join(file_name, '.envrc')
            if os.path.isfile(envrc_path):
                return file_name
            file_name = os.path.dirname(file_name)

    def _update_environment(self, file_path):
        direnv_path = self._find_envrc_directory(file_path)
        direnv_path_prev = self._current_direnv_path

        self._current_direnv_path = direnv_path

        self._previous_environment, previous = {}, self._previous_environment
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key)
            else:
                os.environ[key] = value

        if direnv_path is None:
            if direnv_path_prev is not None:
                sublime.status_message(
                    "direnv: unloaded %s" % direnv_path_prev)
            return

        if direnv_path != direnv_path_prev:
            sublime.status_message("direnv: loading %s" % direnv_path)

        environment = self._direnv.setdefault(direnv_path, {})

        env = {}
        env.update(os.environ)
        env.update(environment)
        process = subprocess.Popen(
            ['direnv', 'export', 'json'],
            cwd=direnv_path,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        returncode = process.wait()
        if returncode != 0:
            sublime.status_message(process.stderr.read().decode())
            return

        data = process.stdout.read().decode()
        data and environment.update(json.loads(data))

        for key, value in environment.items():
            prev = os.environ.get(key)
            if not key.startswith('DIRENV_') and prev != value:
                self._previous_environment[key] = prev
                os.environ[key] = value

        if data or direnv_path != direnv_path_prev:
            sublime.status_message("direnv: loaded %s" % direnv_path)

    def push(self, file_path):
        future = self._executor.submit(self._update_environment, file_path)
        future.add_done_callback(lambda f: f.result())


class DirenvEventListener(sublime_plugin.ViewEventListener):
    direnv = Direnv()

    def on_load(self):
        self.direnv.push(self.view.file_name())

    def on_activated(self):
        self.direnv.push(self.view.file_name())

    def on_post_save(self):
        self.direnv.push(self.view.file_name())


class DirenvAllow(sublime_plugin.TextCommand):
    def run(self, edit):
        process = subprocess.Popen(
            ['direnv', 'allow'],
            cwd=os.path.dirname(self.view.file_name()),
            stderr=subprocess.PIPE)
        returncode = process.wait()
        if returncode != 0:
            sublime.status_message(process.stderr.read().decode())


class DirenvDeny(sublime_plugin.TextCommand):
    def run(self, edit):
        process = subprocess.Popen(
            ['direnv', 'deny'],
            cwd=os.path.dirname(self.view.file_name()),
            stderr=subprocess.PIPE)
        returncode = process.wait()
        if returncode != 0:
            sublime.status_message(process.stderr.read().decode())
