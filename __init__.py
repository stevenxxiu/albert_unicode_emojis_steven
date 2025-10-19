import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Thread
from typing import Callable, TypedDict, override

from albert import setClipboardText  # pyright: ignore[reportUnknownVariableType]
from albert import (
    Action,
    Item,
    PluginInstance,
    Query,
    StandardItem,
    TriggerQueryHandler,
    makeImageIcon,
)

setClipboardText: Callable[[str], None]

md_iid = '4.0'
md_version = '1.4'
md_name = 'Unicode Emojis Steven'
md_description = 'Finds unicode emojis'
md_license = 'MIT'
md_url = 'https://github.com/stevenxxiu/albert_unicode_emojis_steven'
md_authors = ['@stevenxxiu']
md_bin_dependencies = ['convert', 'uni']

BASE_COMMAND = ['uni', 'emoji', '-tone=none,light', '-gender=all', '-as=json']


def character_to_image(char: str, tmp_path: Path, icon_path: Path) -> None:
    # `convert` is buggy for files with `*` in their encodings. This becomes a glob. We rename it ourselves.
    _ = subprocess.call(['convert', '-pointsize', '64', '-background', 'transparent', f'pango:{char}', tmp_path])
    _ = tmp_path.rename(icon_path)


class UniEntry(TypedDict):
    name: str
    group: str
    emoji: str
    cldr_full: str


class WorkerThread(Thread):
    stop: bool
    icon_cache_path: Path

    def __init__(self, icon_cache_path: Path) -> None:
        super().__init__()
        self.stop = False
        self.icon_cache_path = icon_cache_path

    @override
    def run(self) -> None:
        # Build the index icon cache
        uni_outputs: list[UniEntry] = json.loads(subprocess.check_output(BASE_COMMAND + ['-format=%(emoji)'], input=''))  # pyright: ignore[reportAny]
        required_emojis: set[Path] = {self.icon_cache_path / f'{output["emoji"]}.png' for output in uni_outputs}
        cached_emojis = set(self.icon_cache_path.iterdir())

        for icon_path in cached_emojis - required_emojis:
            icon_path.unlink()
        with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
            for i, icon_path in enumerate(required_emojis - cached_emojis):
                tmp_path = self.icon_cache_path / f'icon_{i}.png'
                _ = executor.submit(character_to_image, icon_path.stem, tmp_path, icon_path)
                if self.stop:
                    return


def find_unicode(query_str: str) -> list[UniEntry]:
    try:
        output = subprocess.check_output(
            BASE_COMMAND + ['-format=all', query_str],
            stderr=subprocess.STDOUT,
            encoding='utf-8',
        )
    except subprocess.CalledProcessError as e:
        if e.returncode == 1 and e.output == 'uni: no matches\n':  # pyright: ignore[reportAny]
            return []
        raise
    return json.loads(output)  # pyright: ignore[reportAny]


class Plugin(PluginInstance, TriggerQueryHandler):
    thread: WorkerThread | None

    def __init__(self):
        PluginInstance.__init__(self)
        TriggerQueryHandler.__init__(self)
        self.thread = WorkerThread(self.cacheLocation())
        self.thread.start()

    def __del__(self) -> None:
        if self.thread is not None:
            self.thread.stop = True
            self.thread.join()

    @override
    def synopsis(self, _query: str) -> str:
        return 'query'

    @override
    def defaultTrigger(self):
        return ':'

    @override
    def handleTriggerQuery(self, query: Query) -> None:
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

        items: list[Item] = []
        actions: list[Action]
        copy_call: Callable[[str], None]

        for entry, entry_clips in zip(entries, entries_clips):
            icon_path = self.cacheLocation() / f'{entry["emoji"]}.png'
            actions = []
            for key, value in entry_clips.items():
                copy_call = lambda value_=value: setClipboardText(value_)  # noqa: E731
                actions.append(Action(f'{md_name}/{entry["emoji"]}/{key}', key, copy_call))
            item = StandardItem(
                id=self.id(),
                text=entry['name'],
                subtext=entry['group'],
                icon_factory=lambda icon_path_=icon_path: makeImageIcon(icon_path_),
                actions=actions,
            )
            items.append(item)

        if entries:
            all_clips = {key: '' for key in entries_clips[0]}
            for entry, entry_clips in zip(entries, entries_clips):
                for key, value in entry_clips.items():
                    all_clips[key] += f'{entry["emoji"]}\n' if key == 'Copy Emoji' else f'{entry["emoji"]} {value}\n'
            actions = []
            for key, value in all_clips.items():
                copy_call = lambda value_=value: setClipboardText(value_)  # noqa: E731
                actions.append(Action(f'{md_name}/all/{key}', key, copy_call))
            item = StandardItem(
                id=self.id(),
                text='All',
                icon_factory=lambda: makeImageIcon(self.cacheLocation() / '😀.png'),
                actions=actions,
            )
            items.append(item)

        query.add(items)  # pyright: ignore[reportUnknownMemberType]
