# Albert Launcher Unicode Emojis Extension
Finds Unicode emojis.

Dependencies:

- [ImageMagick](https://imagemagick.org/index.php)
- [uni](https://github.com/arp242/uni)

## Install
To install, copy or symlink this directory to `~/.local/share/albert/python/plugins/unicode_emojis_steven/`.

## Development Setup
To setup the project for development, run:

    $ cd unicode_emojis_steven/
    $ pre-commit install --hook-type pre-commit --hook-type commit-msg

To lint and format files, run:

    $ pre-commit run --all-files
