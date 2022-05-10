#!/usr/bin/env python3
import json

from selenium.common.exceptions import WebDriverException
from edxdownloader.lib import EdxDownloader, EdxLoginError, EdxInvalidCourseError, EdxNotEnrolledError, EdxRequestError
import validators
from os.path import expanduser
import os
import sys
from getpass import getpass
import argparse
import traceback
import time
import re

parser = argparse.ArgumentParser(prog=os.path.basename(sys.argv[0]),
                                 description='Just another web scraper for Edx content. Subtitles included. Supports Edx\'s  default player/subs aswell as courses which use Kaltura embedded media player. For the latter, Selenium is required.',
                                 epilog='For more info,contant me in GitHub')

parser.add_argument('-d', '--debug', action='store_const', const=False,
                    default=True, help='Disable debug message output to terminal.(Default = True)')
parser.add_argument('-c', '--colored', action='store_const', const=False,
                    default=True, help='Disable colorful message output to terminal.(Default = True)')

parser.add_argument('-dev', '--development', action='store_const', const=True,
                    default=False, help='Toggle experimental scraping to target: Kaltura player.(Default = False)')

parser.add_argument('--dashboard', action='store_const', const=True,
                    default=False, help='Scan your entire edx dashboard profile for  courses/videos.(Default = False)')
try:
    args = parser.parse_args()
except argparse.ArgumentError as e:
    print(e)


def main():
    try:
        course_url = None
        email = None
        password = None
        while course_url is None:
            # course_url = str(input('Course URL: ')).strip()
            # todo start
            course_url = "https://courses.edx.org/courses/course-v1:NYUx+CYB.PEN.3+1T2021/"
            # course_url = "https://courses.edx.org/courses/course-v1:MITx+6.00.2x+1T2022/"
            # todo end
            if validators.url(course_url):
                break
            print('Please provide a valid URL.')
            course_url = None

        auth_file = os.path.join(expanduser('~'), '.edxauth')
        confirm_auth_use = ''
        if os.path.exists(auth_file):
            while confirm_auth_use not in ['y', 'n']:
                # TODO
                # confirm_auth_use = str(input('Do you want to use configured EDX account? [y/n]: ')).strip().lower()
                confirm_auth_use = "y"
            if confirm_auth_use == 'y':
                with open(auth_file) as f:
                    content = f.read().splitlines()
                    if len(content) >= 2 and validators.email(content[0]) is True:
                        email = str(content[0]).strip()
                        password = str(content[1]).strip()
                    else:
                        print('Auth configuration file is invalid.')

        while email is None:
            email = str(input('EDX Email: ')).strip()
            if validators.email(email) is True:
                break
            else:
                print('Provided email is invalid.')
                email = None

        while password is None:
            password = str(getpass())

        dont_ask_again = os.path.join(expanduser('~'), '.edxdontask')
        if confirm_auth_use != 'y' and not os.path.exists(dont_ask_again):
            save_ask_answer = ''
            while save_ask_answer not in ['y', 'n', 'never']:
                save_ask_answer = str(input(
                    'Do you want to save this login info? Choose n if it is a shared computer. [y/n/never]: ')).strip().lower()

            if save_ask_answer == 'y':
                with open(auth_file, 'w') as f:
                    f.write(email + '\n')
                    f.write(password + '\n')
            elif save_ask_answer == 'never':
                with open(dont_ask_again, 'w') as f:
                    f.write('never-ask-again')

        try:
            # create main object
            edx = EdxDownloader(email=email, password=password, is_debug=args.debug, is_colored=args.colored,
                                toggle_experimental=args.development)
        except (WebDriverException, KeyboardInterrupt) as e:
            print(traceback.format_exc())
            sys.exit(1)

        #
        #     # Check if .edxcookie exists. if it does, it reads it
        #     # and uses pickle to load it into requests session cookieJar..
        #     # and authenticates user.
        #     # If it does not exist, it creates an empty one.
        # if os.path.exists(edx.cookie):
        #     if os.stat(edx.cookie).st_size >= 50:
        #         with open(edx.cookie, 'rb') as f:
        #             edx.client.cookies.update(pickle.load(f),)
        #         edx.is_authenticated = True
        # else:
        #     with open(edx.cookie, 'wb') as f:
        #         pass

        if not edx.is_authenticated:
            print("Signing in..")
            for i in reversed(range(6)):
                print(i)
                time.sleep(1)
            passhint = '*' * len(password)
            edx.log_message('Attempting to sign in using {} and {}'.format(email, passhint), 'orange')
            try:
                edx.sign_in()

            except (EdxLoginError, EdxRequestError) as e:
                edx.log_message('Sign-in failed. Error: ' + str(e), 'red')
                sys.exit(1)
            edx.log_message('Authentication successful!', 'green')

        edx.log_message('Crawling course content. This may take several minutes.')
        results = []

        if args.dashboard:
            dashboard = edx.dashboard_urls()
            [results.extend(edx.get_course_data(i)) for i in dashboard]
        else:
            results = edx.get_course_data(course_url)

        len(results)
        with open(os.path.join(os.getcwd(), 'results_dump'), 'a') as f:
            f.write(json.dumps(results))

        if type(results) is not None and len(results) > 0:
            edx.log_message('Crawling complete! Found {} videos. Downloading videos now.'.format(len(results)),
                            'orange')
            count = 0
            for vid in results:
                count += 1
                # Filenaming format {segment}
                # do not delete :    re.sub(r'[^\w\-_ ]', ' ')
                course_name = re.sub(r'[^\w_ ]', '-', vid.get('course'))
                chapter = re.sub(r'[^\w_ ]', '-', vid.get('chapter'))
                lecture = re.sub(r'[^\w_ ]', '-', vid.get('lecture'))
                vid_title = re.sub(r'[^\w_ ]', '-', vid.get('segment'))
                video_url = vid.get('url')
                sub = vid.get('sub')  # check

                # course directory
                main_dir = os.path.join(os.getcwd(), course_name)
                chapter_dir = os.path.join(main_dir, chapter)

                # base name for both videos and subtitles
                base_name = f' {vid_title} '

                # file paths
                video_save_as = os.path.join(chapter_dir, '{}{}'.format(base_name, '.mp4'))
                sub_save_as = os.path.join(chapter_dir, '{}{}'.format(base_name, '.srt'))

                # TODO  recommended refactor using pathlib
                if not os.path.exists(main_dir):
                    # create course Directory
                    os.makedirs(main_dir)
                if not os.path.exists(chapter_dir):
                    # create lecture Directories
                    os.makedirs(chapter_dir)

                else:
                    pass
                if os.path.exists(video_save_as):
                    # if video exists
                    edx.log_message('Already downloaded. Skipping video: {} - {}{}'.format(base_name, lecture, '.mp4'))
                else:
                    edx.log_message('Downloading video: {}'.format(vid_title))
                    edx.download_video(video_url, video_save_as)
                    edx.log_message('Downloaded and stored at {}'.format(main_dir), 'green')

                if sub and os.path.exists(sub_save_as):
                    # if subtitle exists
                    edx.log_message(
                        'Already downloaded. Skipping subtitle : {} - {}{}'.format(base_name, lecture, '.srt'))
                else:
                    edx.log_message('Downloading subtitle for: {}'.format(vid_title))
                    edx.download_video(sub, sub_save_as, srt=True)
                    edx.log_message('Subtitle Downloaded and stored at {}'.format(main_dir), 'green')

            edx.log_message('All done! Videos have been downloaded.', "orange")
        else:
            # TODO
            experimental_choice = str(
                input('An experimental search might work on NYU. Try experimental search? [y/n]: ')).strip().lower()

            if experimental_choice == "y":
                if args.dashboard:
                    dashboard = edx.dashboard_urls()
                    [results.extend(edx.get_course_data(i)) for i in dashboard]
                else:
                    results.extend(edx.get_course_data(course_url))
                    print(results)
        sys.exit(1)




    except EdxInvalidCourseError as e:
        edx.log_message(e, 'red')
        sys.exit(1)
    except EdxNotEnrolledError as e:
        edx.log_message(e)
        sys.exit(1)
    except KeyboardInterrupt:
        print('\nDownload cancelled by user.')
        sys.exit(1)

    # except Exception as e:
    #     with open(os.path.join(os.getcwd(), 'edx-error.log'), 'a') as f:
    #         f.write((str(e)))
    #     print(f'Something unexpected occured. Please provide details present in { os.path.join(os.getcwd())}/edx-error.log file while opening an issue at GitHub.')
    #
    #     sys.exit(1)
    #
