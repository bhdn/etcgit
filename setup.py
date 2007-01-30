#!/usr/bin/python

from distutils.core import setup

setup(name="etcgit",
       version="0.03",
       description="Small cron task to keep track of the changes in /etc",
       author="Bogdano Arendartchuk",
       author_email="bogdano@mandriva.com.br",
       license="GPL",
       long_description="""\
This stupid scripts will try to keep track of the changes using GIT
(bzr is too heavy for my K6-II).

It also makes separated changesets for each (RPM) package that owns the
changed files.
""",
       packages = ["etcgit"],
       scripts = ["etcgit.py"],
       data_files=[
           ("/etc/cron.hourly", ["cron.hourly/etc-autocommit"]),
           ("/etc/cron.daily", ["cron.daily/etc-autorepack"],),
           ],
    )
