'''Finds unicode emojis.

Synopsis: <trigger> [query]'''
import json
import subprocess
import threading
from pathlib import Path
from threading import Thread

from albert import ClipAction, Item, cacheLocation  # pylint: disable=import-error


__title__ = 'Unicode Emojis User'
__version__ = '0.0.1'
__triggers__ = ':'
__authors__ = ['Steven Xu']
__exec_deps__ = ['convert', 'uni']

BASE_COMMAND = ['uni', 'emoji', '-tone=none,light', '-gender=all', '-as=json']
ICON_CACHE_PATH = Path(cacheLocation()) / __name__
thread: threading.Thread | None = None


class WorkerThread(Thread):
    def __init__(self):
        super().__init__()
        self.stop = False

    def run(self):
        if not ICON_CACHE_PATH.exists():
            ICON_CACHE_PATH.mkdir()

        # Build the index icon cache
        uni_outputs = json.loads(subprocess.check_output(BASE_COMMAND + ['-format=%(emoji)'], input=''))
        required_emojis = {ICON_CACHE_PATH / f'{output["emoji"]}.png' for output in uni_outputs}
        cached_emojis = set(ICON_CACHE_PATH.iterdir())

        for icon_path in cached_emojis - required_emojis:
            icon_path.unlink()
        for icon_path in required_emojis - cached_emojis:
            subprocess.call(
                ['convert', '-pointsize', '64', '-background', 'transparent', f'pango:{icon_path.stem}', icon_path]
            )
            if self.stop:
                return


def initialize():
    # Build the index and icon cache
    global thread  # pylint: disable=global-statement
    thread = WorkerThread()
    thread.start()


def finalize():
    global thread  # pylint: disable=global-variable-not-assigned
    if thread is not None:
        thread.stop = True
        thread.join()


def handleQuery(query):
    if not query.isTriggered or not query.string.strip():
        return None

    query.disableSort()
    stripped = query.string.strip()
    try:
        output = subprocess.check_output(
            BASE_COMMAND + ['-format=all', stripped],
            stderr=subprocess.STDOUT,
            encoding='utf-8',
        )
    except subprocess.CalledProcessError as e:
        if e.returncode == 1 and e.output == 'uni: no matches\n':
            return None
        raise
    items = []
    for entry in json.loads(output):
        items.append(
            Item(
                id=__title__,
                icon=str(ICON_CACHE_PATH / f'{entry["emoji"]}.png'),
                text=entry['name'],
                subtext=entry['group'],
                actions=[
                    ClipAction(text='Copy Emoji', clipboardText=entry['emoji']),
                    ClipAction(text='Copy Keywords', clipboardText=entry['cldr_full']),
                    ClipAction(text='Copy UTF-8 bytes', clipboardText=repr(entry['emoji'].encode('utf-8'))[1:]),
                    ClipAction(text='Copy All', clipboardText=json.dumps(entry, indent=4, sort_keys=True)),
                ],
            )
        )
    return items
