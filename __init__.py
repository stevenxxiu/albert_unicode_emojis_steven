import json
import os
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Thread

from albert import Action, Item, TriggerQuery, TriggerQueryHandler, setClipboardText  # pylint: disable=import-error


md_iid = '1.0'
md_version = '1.1'
md_name = 'Unicode Emojis Steven'
md_description = 'Finds unicode emojis'
md_url = 'https://github.com/stevenxxiu/albert_unicode_emojis_steven'
md_maintainers = '@stevenxxiu'
md_bin_dependencies = ['convert', 'uni']

BASE_COMMAND = ['uni', 'emoji', '-tone=none,light', '-gender=all', '-as=json']


def character_to_image(char: str, tmp_path: Path, icon_path: Path) -> None:
    # `convert` is buggy for files with `*` in their encodings. This becomes a glob. We rename it ourselves.
    subprocess.call(['convert', '-pointsize', '64', '-background', 'transparent', f'pango:{char}', tmp_path])
    tmp_path.rename(icon_path)


class WorkerThread(Thread):
    def __init__(self, icon_cache_path) -> None:
        super().__init__()
        self.stop = False
        self.icon_cache_path = icon_cache_path

    def run(self):
        # Build the index icon cache
        uni_outputs = json.loads(subprocess.check_output(BASE_COMMAND + ['-format=%(emoji)'], input=''))
        required_emojis = {self.icon_cache_path / f'{output["emoji"]}.png' for output in uni_outputs}
        cached_emojis = set(self.icon_cache_path.iterdir())

        for icon_path in cached_emojis - required_emojis:
            icon_path.unlink()
        with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
            for i, icon_path in enumerate(required_emojis - cached_emojis):
                tmp_path = self.icon_cache_path / f'icon_{i}.png'
                executor.submit(character_to_image, icon_path.stem, tmp_path, icon_path)
                if self.stop:
                    return


def find_unicode(query_str: str) -> list:
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


class Plugin(TriggerQueryHandler):
    def __init__(self) -> None:
        super().__init__()
        self.icon_cache_path = Path(self.cacheLocation())
        self.thread: threading.Thread | None = None

    def id(self) -> str:
        return __name__

    def name(self) -> str:
        return md_name

    def description(self) -> str:
        return md_description

    def initialize(self) -> None:
        self.thread = WorkerThread(self.icon_cache_path)
        self.thread.start()

    def finalize(self) -> None:
        if self.thread is not None:
            self.thread.stop = True
            self.thread.join()

    def defaultTrigger(self) -> str:
        return ':'

    def synopsis(self) -> str:
        return 'query'

    def handleTriggerQuery(self, query: TriggerQuery) -> None:
        query_str = query.string.strip()
        if not query_str:
            return

        entries = find_unicode(query_str)
        entries_clips = [
            {
                'Copy Emoji': entry['emoji'],
                'Copy Keywords': entry['cldr_full'],
                'Copy UTF-8 bytes': entry['emoji'].encode('utf-8').hex(' '),
                'Copy All': json.dumps(entry, indent=4, sort_keys=True),
            }
            for entry in entries
        ]

        for entry, entry_clips in zip(entries, entries_clips):
            query.add(
                Item(
                    id=f'{md_name}/{entry["emoji"]}',
                    text=entry['name'],
                    subtext=entry['group'],
                    icon=[str(self.icon_cache_path / f'{entry["emoji"]}.png')],
                    actions=[
                        Action(f'{md_name}/{entry["emoji"]}/{key}', key, lambda value_=value: setClipboardText(value_))
                        for key, value in entry_clips.items()
                    ],
                )
            )

        if entries:
            all_clips = {key: '' for key in entries_clips[0]}
            for entry, entry_clips in zip(entries, entries_clips):
                for key, value in entry_clips.items():
                    all_clips[key] += f'{entry["emoji"]}\n' if key == 'Copy Emoji' else f'{entry["emoji"]} {value}\n'
            query.add(
                Item(
                    id=f'{md_name}/All',
                    text='All',
                    icon=[str(self.icon_cache_path / '😀.png')],
                    actions=[
                        Action(f'{md_name}/all/{key}', key, lambda value_=value: setClipboardText(value_))
                        for key, value in all_clips.items()
                    ],
                )
            )
