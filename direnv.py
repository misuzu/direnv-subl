import os
import json
import subprocess

import sublime
import sublime_plugin


class DirenvEventListener(sublime_plugin.ViewEventListener):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._direnv = {}
        self._previous = {}

    def _update_environment(self):
        variables = self._direnv.setdefault(self.view.id(), {})
        previous = self._previous.setdefault(self.view.id(), {})

        env = {}
        env.update(os.environ)
        env.update(variables)
        process = subprocess.Popen(
            ['direnv', 'export', 'json'],
            cwd=os.path.dirname(self.view.file_name()),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        returncode = process.wait()
        if returncode != 0:
            self._rollback_environment()
            sublime.status_message(process.stderr.read().decode())
            return

        data = process.stdout.read().decode()
        if data:
            variables.update(json.loads(data))

        for key, value in variables.items():
            prev = os.environ.get(key)
            if not key.startswith('DIRENV_') and prev != value:
                previous[key] = prev
                os.environ[key] = value

        return variables.get('DIRENV_DIR')

    def _rollback_environment(self):
        variables = self._direnv.get(self.view.id(), {})
        previous = self._previous.pop(self.view.id(), {})

        for key, value in previous.items():
            if value is None:
                os.environ.pop(key)
            else:
                os.environ[key] = value

        return variables.get('DIRENV_DIR')

    def on_activated_async(self):
        direnv_dir = self._update_environment()
        direnv_dir and sublime.status_message(
            "direnv: loaded %s" % direnv_dir.strip('-'))

    def on_deactivated(self):
        direnv_dir = self._rollback_environment()
        direnv_dir and sublime.status_message(
            "direnv: unloaded %s" % direnv_dir.strip('-'))

    def on_post_save_async(self):
        self._rollback_environment()
        self._update_environment()


class DirenvAllow(sublime_plugin.TextCommand):
    def run(self, edit):
        process = subprocess.Popen(
            ['direnv', 'allow'],
            cwd=os.path.dirname(self.view.file_name()),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        returncode = process.wait()
        if returncode != 0:
            sublime.status_message(process.stderr.read().decode())


class DirenvDeny(sublime_plugin.TextCommand):
    def run(self, edit):
        process = subprocess.Popen(
            ['direnv', 'deny'],
            cwd=os.path.dirname(self.view.file_name()),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        returncode = process.wait()
        if returncode != 0:
            sublime.status_message(process.stderr.read().decode())
