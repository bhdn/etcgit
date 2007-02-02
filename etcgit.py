#!/usr/bin/python
# 
# Will add untracked files and commit the changed ones. It will try to
# group the commits by package.
#
# Copyright (C) 2007
#     Bogdano Arendartchuk <debogdano@gmail.com>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; version 2 dated June, 1991.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#  See file COPYING for details.
#
import sys
import os
import commands
import rpm

from itertools import chain

class Orphan: pass
class Added: pass
class Deleted: pass
class Modified: pass
class ByPackage: pass

class Error(Exception):
    pass

class CommandError(Error):
    pass

def cmd(cmd, noerror=False):
    status, output = commands.getstatusoutput(cmd)
    if status != 0 and not noerror: # argh!
        raise CommandError, "%s failed: %s" % (cmd, output)
    return output

def rpmqf(path):
    ts = rpm.ts()
    found = list(ts.dbMatch("basenames", path))
    if found:
        return found[0]["name"]

def cmdlines(cmd):
    lines = []
    io = os.popen(cmd)
    for line in io:
        line = line.rstrip()
        if line:
            lines.append(line)
    io.close()
    return lines
    
def getchanges():
    basecmd = "git-ls-files --exclude-per-directory=.gitignore"
    changed = {}
    changed[Added] = cmdlines("%s --others --directory" % basecmd)
    changed[Modified] = cmdlines("%s --modified" % basecmd)
    changed[Deleted] = cmdlines("%s --deleted" % basecmd)
    return changed
    
def pkgchanges():
    pkgs = {}
    changes = getchanges()
    paths = chain(changes[Added], changes[Modified], changes[Deleted])
    for path in paths:
        abspath = os.path.abspath(path)
        pkgname = rpmqf(abspath)
        rpmnew = ".rpmnew"
        if pkgname is None and path.endswith(rpmnew):
            orig = abspath[:-len(rpmnew)]
            if os.path.exists(orig):
                pkgname = rpmqf(orig)
        pkgname = pkgname or Orphan
        pkgs.setdefault(pkgname, []).append(path)
    changes[ByPackage] = pkgs
    return changes

def logmsg(msg):
    return "auto-commit: %s" % msg

def scm(arg):
    return cmd("git %s" % arg)

def fixtree(path):
    "git 'as a content tracker' does not handle empty dirs"
    dirt = False
    for subname in os.listdir(path):
        subpath = os.path.join(path, subname)
        if os.path.isdir(subpath):
            for found in fixtree(subpath):
                yield found
                dirt = True
        else:
            break
    else:
        if not dirt:
            dummy = os.path.join(path, ".was-empty")
            open(dummy, "w+").close()
            yield dummy

def add(paths):
    for path in paths[:]:
        # handle empty directories
        if os.path.isdir(path):
            paths.extend(fixtree(path))
    arg = " ".join(paths)
    return scm("add %s" % arg)

def commit(paths, msg):
    msg = logmsg(msg)
    if paths:
        arg = " ".join(paths)
    else:
        arg = "-a"
    return scm("commit -m \"%s\" %s" % (msg, arg))

def commitpkgs():
    changes = pkgchanges()
    pkgs = changes[ByPackage]
    if pkgs:
        add(changes[Added])
        orphan = pkgs.pop(Orphan)
        for pkg, paths in pkgs.iteritems():
            commit(paths, "owned-by-package: %s" % pkg)
        commit(None, "orphan-files")

if __name__ == "__main__":
    os.environ["GIT_AUTHOR_NAME"] = "autocommit bot"
    os.chdir("/etc")
    commitpkgs()

# vim:ts=4:sw=4:et
