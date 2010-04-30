#!/usr/bin/python
# 
# Will add untracked files and commit the changed ones. It will try to
# group the commits by package.
#
# Copyright (C) 2007 2008 2009 2010
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
import tempfile

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

class FileFormatError(Error):
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
        name = (found[0]["name"]
                + "-" + (found[0]["version"] or "")
                + "-" + (found[0]["release"] or ""))
        return name

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
    changed[Deleted] = list(cmdlines("%s --deleted" % basecmd))
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

def load_database():
    files = {}
    if not os.path.exists(".files"):
        return files
    for line in open(".files"):
        line = line.lstrip()
        if line.endswith("\n"):
            line = line[:-1]
        if not line:
            continue
        try:
            rawmode, rawuid, rawgid, rawpath = line.split(None, 3)
        except ValueError:
            raise FileFormatError, "bad format for .files"
        files[rawpath] = int(rawmode), int(rawuid), int(rawgid), rawpath
    return files

def save_database(entries):
    tmp = tempfile.NamedTemporaryFile(dir=".git", delete=False)
    log.debug("writing to %s" % (tmp.name))
    tosort = [(entry[-1], entry) for entry in entries.itervalues()]
    for _, entry in sorted(tosort):
        mode, uid, gid, path = entry
        tmp.write("%s %s %s %s\n" % (mode, uid, gid, path))
    tmp.flush()
    log.debug("moved %s to .files" % (tmp.name))
    os.chmod(tmp.name, 0600)
    os.rename(tmp.name, ".files")
    tmp.close()

def repr_mode(st_mode):
    return oct(st_mode)

def update_metadata_changes(deleted):
    log.debug("updating metadata changes")
    entries = load_database()
    newentries = {}
    for path in cmdlines("git ls-files -c"):
        st = os.lstat(path)
        newentries[path] = (repr_mode(st.st_mode), st.st_uid, st.st_gid, path)
    for path in deleted:
        newentries.pop(path, None)
    save_database(newentries)

def update_database(paths):
    log.debug("updating metadata database for %s" % (", ".join(paths)))
    entries = load_database()
    for path in paths:
        if os.path.islink(path):
            continue
        st = os.lstat(path)
        entries[path] = (repr_mode(st.st_mode), st.st_uid, st.st_gid, path)
    save_database(entries)

def delete_from_database(paths):
    log.debug("deleting removed entries from database: %s" %
            (", ".join(paths)))
    entries = load_database()
    for path in paths:
        entries.pop(path, None)
    save_database(entries)

def create_database():
    paths = cmdlines("git ls-files")
    update_database(paths)
    scm("add", [".files"])

def commit(paths, msg, all=False, deleted=None, pkg=None):
    msg = logmsg(msg)
    if paths:
        newpaths, ignored = filter_ignored(paths)
    elif all:
        newpaths = ["-a"]
    if newpaths:
        log.debug("adding files to file database")
        if all:
            update_metadata_changes(deleted)
            delete_from_database(deleted)
        else:
            update_database(newpaths)
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
    if not os.path.exists(".files"):
        create_database()
    changes = pkgchanges()
    pkgs = changes[ByPackage]
    if pkgs:
        add(changes[Added])
        orphan = pkgs.pop(Orphan)
        for pkg, paths in pkgs.iteritems():
            commit(paths, "owned-by-package: %s" % (pkg), pkg=pkg)
        commit(None, "orphan-files", all=True, deleted=changes[Deleted])
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
