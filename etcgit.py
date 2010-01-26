#!/usr/bin/python
# 
# Will add untracked files and commit the changed ones. It will try to
# group the commits by package.
#
# Copyright (C) 2007 2008 2009
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
import subprocess
import rpm
import logging

from itertools import chain

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("etcgit")

class Orphan: pass
class Added: pass
class Deleted: pass
class Modified: pass
class ByPackage: pass

class Error(Exception):
    pass

class CommandError(Error):
    
    def __init__(self, cmd, returncode, output):
        self.cmd = cmd
        self.returncode = returncode
        self.output = output
        msg = "%s failed (err %d): %s" % (cmd, returncode, output)
        self.args = (msg,)

def cmd(cmd, noerror=False):
    #status, output = commands.getstatusoutput(cmd)
    #if status != 0 and not noerror: # argh!
    #    raise CommandError, "%s failed: %s" % (cmd, output)
    log.debug("about to run: %s" % (cmd))
    pipe = subprocess.Popen(cmd, shell=False, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)
    pipe.wait()
    output = pipe.stdout.read()
    if pipe.returncode != 0:
        raise CommandError(cmd, pipe.returncode, output)
    return output

def rpmqf(path):
    ts = rpm.ts()
    found = list(ts.dbMatch("basenames", path))
    if found:
        return found[0]["name"]

def cmdlines(cmd):
    log.debug("about to run (cmdlines): %s" % (cmd))
    lines = []
    io = os.popen(cmd)
    for line in io:
        line = line.rstrip()
        if line:
            lines.append(line)
    io.close()
    return lines
    
def getchanges():
    basecmd = "git ls-files --exclude-per-directory=.gitignore"
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
        paths = pkgs.setdefault(pkgname, [])
        if path not in paths:
            paths.append(path)
    changes[ByPackage] = pkgs
    return changes

def logmsg(msg):
    msg = "auto-commit %s" % msg
    comment = os.environ.get("ETCGIT_CHANGE_CONTEXT")
    if comment:
        msg += "\n\nContext: %s" % (comment)
    user = os.environ.get("SUDO_USER")
    if user:
        msg += "\n\nCommiter: %s" % user
    return "auto-commit: %s" % msg

def scm(name, args=[]):
    cmdargs = ["git", name]
    cmdargs.extend(args)
    cmd(cmdargs)

def fixtree(path, ignored):
    "git 'as a content tracker' does not handle empty dirs"
    dirt = False
    for subname in os.listdir(path):
        subpath = os.path.join(path, subname)
        if subpath in ignored:
            continue
        if os.path.islink(subpath):
            yield subpath
            dirt = True
        elif os.path.isdir(subpath):
            for found in fixtree(subpath, ignored):
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
    paths, ignored = filter_ignored(paths)
    for path in paths[:]:
        # handle empty directories
        if os.path.islink(path):
            paths.append(path)
        elif os.path.isdir(path):
            paths.extend(fixtree(path, ignored))
    return scm("add", paths)

def get_ignored():
    lines = list(cmdlines("git ls-files --others --ignored "
        "--exclude-from=.git/info/exclude"))
    return lines

def filter_ignored(paths):
    # workaround against git behavior of complaining about the referring to
    # ignored files in the command line
    ignored = get_ignored()
    filtered = [path for path in paths if path not in ignored]
    return filtered, ignored

def commit(paths, msg, pkg=None):
    msg = logmsg(msg)
    if paths:
        newpaths, ignored = filter_ignored(paths)
    elif paths is None:
        newpaths = ["-a"]
    if newpaths:
        log.debug("about to commit: %s" % (newpaths))
        args = ["-m", msg]
        args.extend(newpaths)
        if pkg:
            log.info("commiting changes for %s" % (pkg))
        try:
            scm("commit", args)
        except CommandError, e:
            if "nothing to commit" in e.output and paths is None:
                log.debug("no orphan stuff to commit")
            else:
                raise
    else:
        log.debug("actually, nothing to commit")

def commitpkgs():
    changes = pkgchanges()
    pkgs = changes[ByPackage]
    if pkgs:
        add(changes[Added])
        orphan = pkgs.pop(Orphan)
        for pkg, paths in pkgs.iteritems():
            commit(paths, "owned-by-package: %s" % (pkg), pkg=pkg)
        commit(None, "orphan-files")
    else:
        log.info("no changes commited")

if __name__ == "__main__":
    os.environ["GIT_AUTHOR_NAME"] = "autocommit bot"
    if os.environ.get("ETCGIT_DEBUG"):
        log.setLevel(logging.DEBUG)
    etcdir = os.environ.get("ETCGIT_ETC", "/etc")
    log.debug("going to %s" % (etcdir))
    os.chdir(etcdir)
    try:
        commitpkgs()
    except Error, e:
        log.error("error: %s" % e)

# vim:ts=4:sw=4:et
