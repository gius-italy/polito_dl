#!/usr/bin/python3
"""Usage:
    polito_dl [options] URL

Options:
    -u, --username USERNAME    PoliTo Username
    -p, --password PASSWORD    PoliTo Password
    --list-lectures            List lectures available for download and exit
    --print-syllabus           Print the course syllabus and exit
    --save-syllabus FILE       Save the course syllabus into file and exit
    --lecture-start NUMBER     Lecture to start download at (default is 1)
    --lecture-end NUMBER       Lecture to end download at (default is last)
    --lecture-items ITEM_SPEC  Lectures to download. Specify indices of
                               the lectures separated by commas like:
                               "--lecture-items 1,2,5,8" if you want to
                               download lectures indexed 1, 2, 5, 8 in the
                               lectures list.
    --format FORMAT            Select the download format: video,
                               iphone, audio [default: video]
    --chunk-size CSIZE         Set the downloader chunk size in
                               bytes (default 1MB)
    -q, --quiet                Activate quiet mode
    -h, --help                 Print this help and exit
    -v, --version              Print version and exit
"""

import os
import sys
import getpass
import re
import requests
import html
from docopt import docopt
from tqdm import tqdm

__author__ = "gius-italy"
__license__ = "GPLv3"
__version__ = "1.0"
__email__ = "gius-italy@live.it"


def new_domain_message():
    print(
        "Please, if you found videolessons on a domain different than "
        "didattica.polito.it or elearning.polito.it send me an mail or open "
        "an issue on Github."
        )


def get_login_cookie(user, passw):
    if user is None:
        user = input("Username: ")
    if passw is None:
        passw = getpass.getpass("Password: ")
    with requests.session() as s:
        r = s.get('https://idp.polito.it/idp/x509mixed-login')
        r = s.post(
            'https://idp.polito.it/idp/Authn/X509Mixed/UserPasswordLogin',
            data={'j_username': user, 'j_password': passw})
        relaystate = html.unescape(
            re.findall('name="RelayState".*value="(.*)"', r.text)[0])
        samlresponse = html.unescape(
            re.findall('name="SAMLResponse".*value="(.*)"', r.text)[0])
        r = s.post(
            'https://www.polito.it/Shibboleth.sso/SAML2/POST',
            data={'RelayState': relaystate, 'SAMLResponse': samlresponse})
        r = s.post('https://login.didattica.polito.it/secure/ShibLogin.php')
        relaystate = html.unescape(
            re.findall('name="RelayState".*value="(.*)"', r.text)[0])
        samlresponse = html.unescape(
            re.findall('name="SAMLResponse".*value="(.*)"', r.text)[0])
        r = s.post(
            'https://login.didattica.polito.it/Shibboleth.sso/SAML2/POST',
            data={'RelayState': relaystate, 'SAMLResponse': samlresponse}
            )
        if r.url == \
        "https://didattica.polito.it/portal/page/portal/home/Studente":
            # Login succesful
            login_cookie = s.cookies
        else:
            login_cookie = ""
    return login_cookie


def get_lectures_urllist(url, login_cookie):
    with requests.session() as s:
        s.cookies = login_cookie
        r = s.get(url)
    # Different html structure for videolessons on elearning.polito.it and
    # didattica.polito.it
    if "didattica.polito.it" in url:
        lectures_urllist = re.findall(
            'href="(sviluppo\.videolezioni\.vis.*lez=\w*)">', r.text)
        for i in range(len(lectures_urllist)):
            lectures_urllist[i] = \
            'https://didattica.polito.it/pls/portal30/'+html.unescape(
                lectures_urllist[i])
    elif "elearning.polito.it" in url:
        lectures_urllist = re.findall(
            "href='(template_video\.php\?[^']*)", r.text)
        for i in range(len(lectures_urllist)):
            lectures_urllist[i] = \
            'https://elearning.polito.it/gadgets/video/'+html.unescape(
                lectures_urllist[i])
    else:
        # Still under developement
        new_domain_message()
        lectures_urllist = ""
    return lectures_urllist


def get_dlurl(lecture_url, login_cookie, dl_format='video'):
    with requests.session() as s:
        s.cookies = login_cookie
        r = s.get(lecture_url)
        if "didattica.polito.it" in lecture_url:
            if dl_format == 'video':
                dlurl = re.findall('href="(.*)".*Video', r.text)[0]
            if dl_format == 'iphone':
                dlurl = re.findall('href="(.*)".*iPhone', r.text)[0]
            if dl_format == 'audio':
                dlurl = re.findall('href="(.*)".*Audio', r.text)[0]
            r = s.get(
                'https://didattica.polito.it'+html.unescape(dlurl),
                allow_redirects=False)
            dlurl = r.headers['location']
        elif "elearning.polito.it" in lecture_url:
            if dl_format == 'video':
                dlurl = re.findall(
                    'href="(download.php[^\"]*).*video1', r.text)[0]
            if dl_format == 'iphone':
                dlurl = re.findall(
                    'href="(download.php[^\"]*).*video2', r.text)[0]
            if dl_format == 'audio':
                dlurl = re.findall(
                    'href="(download.php[^\"]*).*video3', r.text)[0]
            r = s.get(
                'https://elearning.polito.it/gadgets/video/' + \
                html.unescape(dlurl), allow_redirects=False)
            dlurl = r.headers['location']
        else:
            # Still under developement
            new_domain_message()
            dlurl = ""
    return dlurl


def download_file(dlurl, filename=None, csize=1000*1000, quiet=False):
    r = requests.get(dlurl, stream=True)
    file_size = int(r.headers['Content-Length'])
    if filename is None:
        filename = r.url.split("/")[-1]
    if os.path.exists(filename):
        first_byte = os.path.getsize(filename)
    else:
        first_byte = 0
    if first_byte >= file_size:
        return file_size
    r = requests.get(
        dlurl,
        headers={"Range": "bytes=%s-%s" % (first_byte, file_size)},
        stream=True)
    if quiet is False:
        with tqdm(total=file_size, initial=first_byte, unit='B',
                  unit_scale=True, desc=filename) as pbar:
            with open(filename, 'ab') as fp:
                for chunk in r.iter_content(chunk_size=csize):
                    fp.write(chunk)
                    pbar.update(csize)
    else:
        with open(filename, 'ab') as fp:
            for chunk in r.iter_content(chunk_size=csize):
                    fp.write(chunk)

    return file_size


def get_syllabus(url, login_cookie):
    with requests.session() as s:
        s.cookies = login_cookie
        r = s.get(url)
    syllabus = []
    if "didattica.polito.it" in url:
        course = re.search(
            '<div class="h2 text-primary">([^<]*)',
            r.text
            ).group(1)
        prof = re.search('<h3>([^<]*)', r.text).group(1)
        syllabus.append([course, prof])
        for chunk in r.text.split('<li class="h5">')[1:]:
            title = re.search(
                'href="sviluppo\.videolezioni\.vis.*lez=\w*">([^<]*)</a>',
                chunk
                ).group(1)
            date = re.search(
                '<span class="small">[^0-9]*([^<]*)',
                chunk
                ).group(1)
            arguments = re.findall('argoLink[^>]*>([^<]*)<', chunk)
            syllabus.append([title, date, arguments])
    elif "elearning.polito.it" in url:
        print("Sorry, this works only on didattica.polito.it")
        syllabus = ""
    else:
        print("Sorry, this works only on didattica.polito.it")
        syllabus = ""
    return syllabus


def print_syllabus(syllabus):
    print('\nCourse: '+syllabus[0][0])
    print('Professor: '+syllabus[0][1]+'\n')
    syllabus = syllabus[1:]
    print('Lectures')
    for i in range(len(syllabus)):
        print(syllabus[i][0]+' - '+syllabus[i][1])
        for topic in syllabus[i][2]:
            print('    '+topic)
        print('\n')


def write_syllabus(syllabus, filename=None):
    if filename is None:
        filename = 'syllabus.txt'
    with open(filename, "w") as fp:
        fp.write('Course: '+syllabus[0][0]+"\n"+"Professor: " + \
                 syllabus[0][1]+"\n\n")
        for lecture in syllabus[1:]:
            fp.write(lecture[0]+" - "+lecture[1]+"\n")
            for argument in lecture[2]:
                fp.write("    "+argument+"\n")
            fp.write("\n")


# Main
if __name__ == "__main__":
    args = docopt(__doc__, version="polito_dl "+__version__)
    if args['--username'] is None:
        USERNAME = input("\n"+"Insert your didattica.polito.it username: ")
    else:
        USERNAME = args['--username']
    if args['--password'] is None:
        PASSWORD = getpass.getpass("Insert your didattica.polito.it password:")
    else:
        PASSWORD = args['--password']
    if args['--lecture-start'] is None:
        start_index = 0
    else:
        start_index = int(args['--lecture-start'])-1
    if args['--lecture-end'] is None:
        end_index = 0
    else:
        end_index = int(args['--lecture-end'])-1
    if args['--lecture-items'] is not None:
        items = [int(el)-1 for el in args['--lecture-items'].split(',')]
    else:
        items = []
    if args['--format'] in ['video', 'iphone', 'audio']:
        dl_format = args['--format']
    else:
        dl_format = 'video'
    if args['--chunk-size'] is None:
        CSIZE = 1000*1000
    else:
        CSIZE = int(args['--chunk-size'])

    login_cookie = get_login_cookie(USERNAME, PASSWORD)
    if args['--list-lectures'] is True:
        syllabus = get_syllabus(args['URL'], login_cookie)
        syllabus = syllabus[1:]
        print('\nLectures list')
        for i in range(len(syllabus)):
            print(str(i+1)+') '+syllabus[i][0])
    elif args['--print-syllabus'] is True:
        syllabus = get_syllabus(args['URL'], login_cookie)
        print_syllabus(syllabus)
    elif args['--save-syllabus'] is not None:
        syllabus = get_syllabus(args['URL'], login_cookie)
        write_syllabus(syllabus, args['--save-syllabus'])
    else:
        lect_urllist = get_lectures_urllist(args['URL'], login_cookie)
        if items:
            if not args['--quiet']:
                print("Starting download of "+str(len(items))+" lectures")
            for i in items:
                dlurl = get_dlurl(lect_urllist[i], login_cookie, dl_format)
                download_file(dlurl, csize=CSIZE, quiet=args['--quiet'])
        else:
            if end_index == 0:
                end_index = len(lect_urllist)
            if not args['--quiet']:
                print("\nStarting download of "+str(end_index-start_index) + \
                      " lectures")
            for i in range(start_index, end_index):
                dlurl = get_dlurl(lect_urllist[i], login_cookie, dl_format)
                download_file(dlurl, csize=CSIZE, quiet=args['--quiet'])
