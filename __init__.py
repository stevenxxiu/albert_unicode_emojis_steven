'''Finds unicode emojis.

Synopsis: <trigger> [query]'''
import json
import os
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
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


def character_to_image(char, tmp_path, icon_path):
    # `convert` is buggy for files with `*` in their encodings. This becomes a glob. We rename it ourselves.
    subprocess.call(['convert', '-pointsize', '64', '-background', 'transparent', f'pango:{char}', tmp_path])
    tmp_path.rename(icon_path)


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
        with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
            for i, icon_path in enumerate(required_emojis - cached_emojis):
                tmp_path = ICON_CACHE_PATH / f'icon_{i}.png'
                executor.submit(character_to_image, icon_path.stem, tmp_path, icon_path)
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


def find_unicode(query_str):
    try:
        output = subprocess.check_output(
            BASE_COMMAND + ['-format=all', query_str],
            stderr=subprocess.STDOUT,
            encoding='utf-8',
        )
    except subprocess.CalledProcessError as e:
        if e.returncode == 1 and e.output == 'uni: no matches\n':
            return []
        raise
    return json.loads(output)


def handleQuery(query):
    if not query.isTriggered or not query.string.strip():
        return None

    entries = find_unicode(query.string.strip())
    entries_clips = [
        {
            'Copy Emoji': entry['emoji'],
            'Copy Keywords': entry['cldr_full'],
            'Copy UTF-8 bytes': entry['emoji'].encode('utf-8').hex(' '),
            'Copy All': json.dumps(entry, indent=4, sort_keys=True),
        }
        for entry in entries
    ]

    items = []
    for entry, entry_clips in zip(entries, entries_clips):
        items.append(
            Item(
                id=f'{__title__}/{entry["emoji"]}',
                icon=str(ICON_CACHE_PATH / f'{entry["emoji"]}.png'),
                text=entry['name'],
                subtext=entry['group'],
                actions=[ClipAction(text=key, clipboardText=value) for key, value in entry_clips.items()],
            )
        )

    if entries:
        all_clips = {key: '' for key in entries_clips[0]}
        for entry, entry_clips in zip(entries, entries_clips):
            for key, value in entry_clips.items():
                all_clips[key] += f'{entry["emoji"]}\n' if key == 'Copy Emoji' else f'{entry["emoji"]} {value}\n'
        items.append(
            Item(
                id=f'{__title__}/All',
                icon=str(ICON_CACHE_PATH / '😀.png'),
                text='All',
                actions=[ClipAction(text=key, clipboardText=value) for key, value in all_clips.items()],
            )
        )
    return items
