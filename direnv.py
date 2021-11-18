import concurrent.futures
import json
import os
import re
import subprocess

import sublime
import sublime_plugin


ANSI_ESCAPE_RE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


def get_output(cmd, cwd, env=None):
    process = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    returncode = process.wait()
    return (
        returncode,
        process.stdout.read().decode(),
        ANSI_ESCAPE_RE.sub('', process.stderr.read().decode()),
    )


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
        env.update({k: v for k, v in environment.items() if v is not None})
        returncode, stdout, stderr = get_output(
            ['direnv', 'export', 'json'],
            direnv_path,
            env)
        if returncode != 0:
            sublime.status_message(stderr)
            self._current_direnv_path = None
            return

        stdout and environment.update(json.loads(stdout))

        for key, value in environment.items():
            if key.startswith('DIRENV_') or value is None:
                continue
            prev = os.environ.get(key)
            if prev != value:
                self._previous_environment[key] = prev
                os.environ[key] = value

        if stdout or direnv_path != direnv_path_prev:
            sublime.status_message("direnv: loaded %s" % direnv_path)

    def push(self, file_path):
        future = self._executor.submit(self._update_environment, file_path)
        future.add_done_callback(lambda f: f.result())


direnv = Direnv()


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
