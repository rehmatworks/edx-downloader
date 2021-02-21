from edxdownloader.lib import EdxDownloader, EdxLoginError
import validators
from os.path import expanduser
import os
import sys
from getpass import getpass


def main():
    try:
        course_url = None
        email = None
        password = None
        while course_url is None:
            course_url = str(input('Course URL: ')).strip()
            if validators.url(course_url):
                break
            print('Please provide a valid URL.')
            course_url = None

        auth_file = os.path.join(expanduser('~'), '.edxauth')
        if os.path.exists(auth_file):
            confirm_auth_use = ''
            while confirm_auth_use not in ['y', 'n']:
                confirm_auth_use = str(input('Do you want to use configured EDX account? [y/n] ')).strip().lower()
            
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

        edx = EdxDownloader(email=email, password=password)

        if not edx.is_authenticated:
            edx.log_message(f'Attempting to sign in using {email}', 'orange')
            try:
                edx.sign_in()
                edx.log_message('Authentication successful!', 'green')
            except EdxLoginError:
                edx.log_message('Sign in failed. Please check credentials.', 'red')
                sys.exit(1)

        edx.log_message(f'Crawling course content. This may take several minutes.')
        videos = edx.get_course_data(course_url)

        if type(videos) is list and len(videos) > 0:
            edx.log_message(f'Found {len(videos)} videos. Downloading videos now.')
            for vid in videos:
                vid_title = vid.get('title')
                course_name = vid.get('course')
                if course_url and vid_title:
                    save_as = os.path.join(course_name, f'{vid_title}.mp4')
                    if not os.path.exists(course_name):
                        os.makedirs(course_name)
                    
                    if os.path.exists(save_as):
                        edx.log_message(f'Already downloaded. Skipping {save_as}')
                    else:
                        edx.log_message(f'Downloading video {vid_title}')
                        edx.download_video(vid.get('url'), save_as)
                        edx.log_message(f'Downloaded and stored at ./{save_as}', 'green')
        else:
            edx.log_message('No downloadable videos found for the course!', 'red')
    except KeyboardInterrupt:
        print('')
        print('Download cancelled by user.')
    except Exception as e:
        with open('edx-error.log', 'a') as f:
            f.write((str(e)))
        print('Something unexpected occured. Please provide details present in edx-error.log file while opening an issue at GitHub.')