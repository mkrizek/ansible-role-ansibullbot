#!/usr/bin/env python
# {{ ansible_managed }}

import cgi
import os
import sys
import subprocess

def run_command(args):
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    (so, se) = p.communicate()
    return (p.returncode, so, se)

def get_process_data():
    # USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
    #[root@centos-1gb-nyc3-01 cgi-bin]# ps aux | fgrep -i triage.py | egrep ^ansibot
    #ansibot   1092 18.2 37.4 600984 380548 pts/2   S+   13:53   3:46
    #   python ./triage.py --debug --verbose --force --skip_no_update --daemonize --daemonize_interval=360
    pdata = {
        'pid': None,
        'cpu': None,
        'mem': None,
    }
    cmd = 'ps aux | fgrep -i triage_ansible.py | egrep ^ansibot'
    (rc, so, se) = run_command(cmd)
    if rc != 0:
        return pdata

    parts = so.split()
    pdata['pid'] = parts[1]
    pdata['cpu'] = parts[2]
    pdata['mem'] = parts[3]

    # disk used
    cmd = "df -h / | tail -n1 | awk '{print $5}'"
    (rc, so, se) = run_command(cmd)
    pdata['disk'] = so.strip()

    return pdata

def get_log_data():
    cmd = 'tail -n 100 "{{ ansibullbot_log_path }}" | fgrep " INFO "'
    (rc, so, se) = run_command(cmd)
    lines = []
    for line in so.split('\n'):
        lines.append(line)

    ratelimit = {
        'total': None,
        'remaining': None,
        'msg': None
    }

    cmd = 'tail -n 1000 "{{ ansibullbot_log_path }}" | fgrep "x-ratelimit-limit" | tail -n1'
    (rc, so, se) = run_command(cmd)
    if so:
        parts = so.split()

        if "'x-ratelimit-limit':" not in parts:
            #ratelimit['msg'] = '<br>\n'.join(parts)
            pass
        else:
            lidx = parts.index("'x-ratelimit-limit':")
            if lidx:
                ratelimit['total'] = parts[lidx+1].replace("'", '').replace(',', '')
            ridx = parts.index("'x-ratelimit-remaining':")
            if ridx:
                ratelimit['remaining'] = parts[ridx+1].replace("'", '').replace(',', '')

    # why was bot last restarted?
    cmd = 'fgrep -B 20 "starting bot" {{ ansibullbot_log_path }} | tail -n 21'
    (rc, so, se) = run_command(cmd)
    restarts = so.split('\n')

    return (ratelimit, lines, restarts)

def get_version_data():
    cmd = 'git -C "{{ ansibullbot_clone_path }}" log --format="%H" -1'

    (rc, so, se) = run_command(cmd)
    if rc == 0 and so:
        commit_hash = so.strip()
        return commit_hash

    return "unknown"

pdata = get_process_data()
(ratelimit, loglines, restarts) = get_log_data()
version = get_version_data()

rdata = "Content-type: text/html\n"
rdata += "\n"
rdata += "pid: %s<br>\n" % (pdata['pid'] or 'not running')
rdata += "cpu: %s<br>\n" % (pdata['cpu'] or 'not running')
rdata += "mem: %s<br>\n" % (pdata['mem'] or 'not running')
rdata += "disk: %s<br>\n" % (pdata['disk'] or 'N/A')
rdata += "<br>\n"
rdata += "ratelimit total: %s<br>\n" % ratelimit['total']
rdata += "ratelimit remaining: %s<br>\n" % ratelimit['remaining']
rdata += "<br>\n"
rdata += "current version: %s\n" % version
rdata += "<br>\n"
rdata += "################################ INFO LOG ###########################<br>\n"
rdata += '<br>\n'.join(loglines)
rdata += "<br>\n"
rdata += "################################ TRACEBACKS #########################<br>\n"
rdata += '<br>\n'.join(restarts)
rdata += "<br>\n"

# force error on full disk
if int(pdata['disk'].replace('%', '')) > 98:
    print 'Status: 500 No disk space left'
    print
else:
    print rdata
