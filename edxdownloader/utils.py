#!/usr/bin/env python3

import argparse
import os
import re
import sys
import time
import traceback
from getpass import getpass
from os.path import expanduser

import validators
from edxdownloader.lib import EdxDownloader, EdxLoginError, EdxInvalidCourseError, EdxNotEnrolledError, EdxRequestError, \
    LogMessage
from selenium.common.exceptions import WebDriverException

parser = argparse.ArgumentParser(prog=os.path.basename(sys.argv[0]),
                                 description='Just another web scraper for Edx content. Subtitles included. Supports Edx\'s  default player/subs aswell as courses which use Kaltura embedded media player. For the latter, Selenium is required.',
                                 epilog='For more info,contant me in GitHub')

parser.add_argument('-d', '--debug', action='store_const', const=False,
                    default=True, help='Disable debug message output to terminal.(Default = True)')
parser.add_argument('-c', '--colored', action='store_const', const=False,
                    default=True, help='Disable colorful message output to terminal.(Default = True)')

parser.add_argument('-dev', '--development', action='store_const', const=True,
                    default=False, help='Toggle experimental scraping to target: Kaltura player.(Default = False)')

parser.add_argument('--results', action='store_const', const=True,
                    default=False,
                    help='Recommended: Ignores previously found pages and speeds up the parsing proccess .(Default = False)')
try:
    args = parser.parse_args()
except argparse.ArgumentError as e:
    print(e)


def main():
    log_message = LogMessage(is_debug=args.debug, is_colored=args.colored)
    previous_results = os.path.join(expanduser('~'), '.edxResults')
    previous_results_bad = os.path.join(expanduser('~'), '.edxResults_bad')
    auth_file = os.path.join(expanduser('~'), '.edxauth')
    load_results = args.results

    try:
        email = None
        password = None

        if not os.path.exists(auth_file):
            with open(auth_file, 'w') as f:
                f.write('\n')

        while True:
            # TODO IMPORTANT
            confirm_auth_use =  str(input('Do you want to use configured EDX account? [y/n]: ')).strip().lower()
            # confirm_auth_use = "y" #todo auto edw diagrafi kai no-comment to apo panw
            if confirm_auth_use == 'y':
                with open(auth_file) as f:
                    content = f.read().splitlines()
                    if len(content) >= 2 and validators.email(content[0]) is True:
                        email = str(content[0]).strip()
                        password = str(content[1]).strip()
                        break
                    else:
                        print('Auth configuration file is invalid.')
                        continue
            elif confirm_auth_use == 'n':
                break
            else:
                print("Please type 'y' for Yes or 'n' for No")
                continue

        while email is None:
            email = str(input('EDX Email: ')).strip()
            if not validators.email(email):
                print('Provided email is invalid.')
                email = None
                continue
            else:
                while password is None:
                    password = str(getpass())
                    if len(password) < 8:
                        print('Provided password is invalid.')
                        password = None
                        continue
            with open(auth_file, 'w') as f:
                f.write('')

        with open(auth_file, 'r') as f:
            for i, j in enumerate(f):
                if i == 2:
                    if j.strip() == 'never':
                        break
            else:
                save_auth_answer = ''
                while save_auth_answer not in ['y', 'n', 'never']:
                    # if input is 'never, it never asks about save preferences
                    # for this user.
                    save_auth_answer = str(input(
                        "Do you want to save this login info? Type [Y/N]. Type 'never' to save your credentials and never ask again: ")).strip().lower()

                if save_auth_answer == 'y':
                    with open(auth_file, 'w') as f:
                        f.write(email + '\n')
                        f.write(password + '\n')
                        f.write(save_auth_answer)
                if save_auth_answer == 'n':
                    with open(auth_file, 'w') as f:
                        f.write('\n')
                if save_auth_answer == 'never':
                    with open(auth_file, 'w') as f:
                        f.write(email + '\n')
                        f.write(password + '\n')
                        f.write('never')

        # load search results from previous scrape
        # previous_results = os.path.join(expanduser('~'), '.edxResults')
        # previous_results_bad = os.path.join(expanduser('~'), '.edxResults_bad')
        if not os.path.exists(previous_results):
            with open(previous_results, 'w') as f:
                f.write('')

        if not os.path.exists(previous_results_bad):
            with open(previous_results_bad, 'w') as f:
                f.write('')

        try:
            # create main object
            edx = EdxDownloader(email=email, password=password, is_debug=args.debug, is_colored=args.colored,
                                toggle_experimental=args.development, )
        except (WebDriverException, KeyboardInterrupt) :
            print(traceback.format_exc())
            sys.exit(1)

            # Check if .edxcookie exists. if it does, it reads it
            # and uses pickle to load it into requests session cookieJar..
            # and authenticates user.
            # If it does not exist, it creates an empty one.

        while not edx.is_authenticated:

            print("Signing in..")
            for i in reversed(range(4)):
                print(i + 1)
                time.sleep(1)
            if edx.load():
                print("Session loaded")
                edx.is_authenticated = True
            else:
                try:
                    passhint = '*' * len(password)
                    log_message('Attempting to sign in using {} and {}'.format(email, passhint), 'orange')
                    edx.sign_in()
                except (EdxLoginError, EdxRequestError) as e:
                    log_message('Sign-in failed. Error: ' + str(e), 'red')
                    sys.exit(1)
                else:
                    edx.dump()

        log_message('Authentication successful!', 'green')

        if not load_results:
            log_message('Crawling Dashboard content. Please wait..')
            courses = edx.dashboard_urls()
            # Show dashboard items and multiple choice.
            [print(f"[{i + 1}]  {course.get('course_title')}") for i, course in enumerate(courses)]

            number_of_courses = len(courses)
            choices = set()
            while True:
                course_choice = input(
                    f"\nType [ALL] to select all courses or type it's respective integer between 0 and {number_of_courses} and type[OK] to finalize your choices: ").strip()

                if course_choice.lower() == 'all':
                    log_message('Scraping courses. Please wait..')
                    [edx.get_course_data(course.get('COURSE_SLUG')) for course in courses]

                if course_choice == 'ok':
                    if not choices:
                        log_message(" Select one or more courses, then type [OK] to finalize your choices.")
                    else:
                        [edx.get_course_data(course.get('COURSE_SLUG')) for i, course in enumerate(courses) if
                         i in choices]

                    break

                if course_choice.isdecimal() and int(course_choice) <= number_of_courses:
                    c_n = int(course_choice)
                    if c_n - 1 not in choices:
                        choices.add(c_n - 1)
                        log_message(
                            f"\n{courses[c_n - 1].get('course_title')} added.\nCurrently selected courses: {choices}\n")
                        continue
                    else:
                        log_message("You have already chosen this course.")
                else:
                    log_message("Not a valid number. Retry.", "red")
                    continue
        else:
            log_message("Loading only previous results.  ")

        results = edx.collector.save_results()

        if type(results) is list and len(results) > 0:
            # DOWNLOAD QUEUE
            log_message('Crawling complete! Found {} videos. Downloading videos now.'.format(len(results)),
                        'green')
            count = 0
            for downloadable in results:
                count += 1
                # Filenaming format {segment}
                # do not delete :    re.sub(r'[^\w\-_ ]', ' ')
                course_name = re.sub(r'[^\w_ ]', '-', downloadable.get('course'))
                chapter = re.sub(r'[^\w_ ]', '-', downloadable.get('chapter'))
                lecture = re.sub(r'[^\w_ ]', '-', downloadable.get('lecture'))
                vid_title = re.sub(r'[^\w_ ]', '-', downloadable.get('segment'))
                video_url = downloadable.get('video_url')
                subtitle_url = downloadable.get('subtitle_url', None)  # check

                # course directory
                main_dir = os.path.join(os.getcwd(), course_name)
                chapter_dir = os.path.join(main_dir, chapter)

                # base name for both videos and subtitles
                base_name = f'{lecture}-{vid_title}'

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
                    log_message('Already downloaded. Skipping video: {} - {}{}'.format(base_name, lecture, '.mp4'))
                else:
                    log_message('Downloading video: {}'.format(vid_title))
                    edx.download_video(video_url, video_save_as)
                    log_message('Downloaded and stored at {}'.format(main_dir), 'green')

                if subtitle_url and os.path.exists(sub_save_as):
                    # if subtitle exists
                    log_message(
                        'Already downloaded. Skipping subtitle : {} - {}{}'.format(base_name, lecture, '.srt'))
                else:
                    log_message('Downloading subtitle for: {}'.format(vid_title))
                    edx.download_video(subtitle_url, sub_save_as, srt=True)
                    log_message('Subtitle Downloaded and stored at {}'.format(main_dir), 'green')

            log_message('All done! Videos have been downloaded.', "orange")


    except EdxInvalidCourseError as e:
        log_message(e, 'red')
        sys.exit(1)
    except EdxNotEnrolledError as e:
        log_message(e)
        sys.exit(1)
    except KeyboardInterrupt:
        edx.collector.save_results()
        print('\nDownload cancelled by user.')
        sys.exit(1)

    except Exception as e:
        edx.collector.save_results()
        with open(os.path.join(os.getcwd(), 'edx-error.log'), 'a') as f:
            f.write((str(e)))
        print(traceback.format_exc())
        print(
            f'Something unexpected occured. Please provide details present in {os.path.join(os.getcwd())}/edx-error.log file and open an issue at GitHub.')

        sys.exit(1)
