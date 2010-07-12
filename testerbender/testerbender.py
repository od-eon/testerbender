#!/usr/bin/env python

import os
import logging
import atexit
import subprocess
import sys
from pprint import pprint
import csv
import smtplib
from email.mime.text import MIMEText


DIR = os.path.abspath(os.path.dirname(__file__))
LOG_DIR = os.path.join(DIR, 'log')
if not os.path.isdir(LOG_DIR):
    os.mkdir(LOG_DIR, 0755)
LOG_FILE = os.path.join(LOG_DIR, 'testerbender.log')
DATA_FILE = os.path.join(LOG_DIR, 'testerbender.data')
CONFIG_FILE = os.path.join(DIR, 'testerbender.conf')
execfile(CONFIG_FILE)

# persistent data
DATA = {
    'broken_commit': '',
    'broken_commit_author': '',
    'last_tested_commit': '',
}

def read_data():
    if not os.path.isfile(DATA_FILE):
        return
    datafile = open(DATA_FILE, 'r')
    csvreader = csv.reader(datafile)
    for row in csvreader:
        DATA[row[0]] = row[1]
    datafile.close()
    #pprint(DATA)

def write_data():
    datafile = open(DATA_FILE, 'w')
    csvwriter = csv.writer(datafile)
    for k in DATA:
        csvwriter.writerow([k, DATA[k]])
    datafile.close()

read_data()

# logging
logger = logging.getLogger('testerbender')
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler(LOG_FILE)
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter('[%(asctime)s] %(message)s', '%d/%b/%Y:%H:%M:%S')
fh.setFormatter(formatter)
logger.addHandler(fh)

# log the termination
#def stopping():
    #logger.info('stopped')
#atexit.register(stopping)

# commit info
os.chdir(REPO_DIR)
output = subprocess.Popen(['git', 'log', '--topo-order', '--format=format:%H|%an', '-n', '1'], stdout=subprocess.PIPE).communicate()[0]
commit, author = output.strip().split('|')
#pprint(commit)
#pprint(author)

# email
def send_email(subject, body):
    recipients = ['%s <%s>' % (e[0], e[1]) for e in EMAIL_TO]
    msg = MIMEText(body)
    msg['Subject'] = '%s %s' % (EMAIL_SUBJECT_PREFIX, subject)
    msg['From'] = EMAIL_FROM
    msg['To'] = ','.join(recipients)

    mailServer = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
    if EMAIL_USE_TLS:
        mailServer.ehlo()
        mailServer.starttls()
    mailServer.ehlo()
    mailServer.login(EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)
    mailServer.sendmail(EMAIL_FROM, recipients, msg.as_string())
    mailServer.close()

# running the test
exit_code = 0 # used by the post-update hook
#logger.info('started')
os.chdir(TEST_DIR)
for test_cmd in TEST_CMDS:
    test_cmd_str = ' '.join(test_cmd)
    print test_cmd_str
    p = subprocess.Popen(test_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = p.communicate()[0]
    if p.returncode != 0:
        # the test failed
        exit_code = 1
        # inform the user
        print output
        if DATA['broken_commit'] == '':
            # this is the commit that caused the breakage
            # log it
            logger.info('broken commit: %s' % commit)
            logger.info('broken commit author: %s' % author)
            # send email
            body = """
    broken commit: %s
    broken commit author: %s
    test command: %s
    test output:
    %s
            """ % (commit, author, test_cmd_str, output)
            send_email('tests failed - blame %s [%s]' % (author, commit), body)
            # update the data
            DATA['broken_commit'] = commit
            DATA['broken_commit_author'] = author
        break
    else:
        # the test passed
        # if a previous broken state was fixed we should mark it as such
        if DATA['broken_commit'] != '':
            DATA['broken_commit'] = ''
            DATA['broken_commit_author'] = ''
            # log it
            logger.info('fix commit: %s' % commit)
            logger.info('fix commit author: %s' % author)
            # send email
            body = """
    fix commit: %s
    fix commit author: %s
            """ % (commit, author)
            send_email('tests passed - praise %s [%s]' % (author, commit), body)

DATA['last_tested_commit'] = commit
write_data()
sys.exit(exit_code)
