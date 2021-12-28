import contextlib
import itertools
import threading
import time


@contextlib.contextmanager
def progressbar(notify, interval=80):
    def progress_thread(event):
        # https://raw.githubusercontent.com/sindresorhus/cli-spinners/master/spinners.json
        for tick in itertools.cycle([
            '⢄',
            '⢂',
            '⢁',
            '⡁',
            '⡈',
            '⡐',
            '⡠'
        ]):
            time.sleep(interval / 1000)
            if event.is_set():
                break
            notify(tick)

    event = threading.Event()
    thread = threading.Thread(
        target=progress_thread,
        args=(event, ),
        daemon=True)
    thread.start()
    yield
    event.set()
    thread.join()
