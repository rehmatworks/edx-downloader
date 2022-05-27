#!/usr/bin/env python3
import argparse
import os
import re
import sys
import traceback
from getpass import getpass
from os.path import expanduser

import validators
from edxdownloader.lib import EdxDownloader, EdxLoginError, EdxInvalidCourseError, EdxNotEnrolledError, EdxRequestError, LogMessage, Downloader

parser = argparse.ArgumentParser(prog=os.path.basename(sys.argv[0]),
								 description='Just another web scraper for Edx content. Subtitles included. Supports '
											 'Edx\'s  default player/subs '
											 'aswell as courses which use Kaltura embedded media player. For the '
											 'latter, Selenium is required.',
								 epilog='For more info, contact me in GitHub')

parser.add_argument('-d', '--debug', action='store_const', const=False, default=True,
					help='Disable debug message output to terminal.(Default = True)')
parser.add_argument('-c', '--colored', action='store_const', const=False, default=True,
					help='Disable colorful message output to terminal.(Default = True)')

parser.add_argument('--results', action='store_const', const=True, default=False,
					help='Recommended: Ignores previously found pages and speeds up the parsing proccess .(Default = '
						 'False)')
try:
	args = parser.parse_args()
except argparse.ArgumentError as e:
	print(e)
	sys.exit(1)

LogMessage.set_args(is_debug=args.debug, is_colored=args.colored)

log = LogMessage.log_message


def main():
	previous_results = os.path.join(expanduser('~'), '.edxResults')
	previous_results_bad = os.path.join(expanduser('~'), '.edxResults_bad')
	pdf_results = os.path.join(expanduser('~'), '.edxPDFResults')

	auth_file = os.path.join(expanduser('~'), '.edxauth')

	load_results = args.results
	previous_user = True
	email = None
	password = None

	try:
		if not os.path.exists(auth_file):
			with open(auth_file, 'w') as f:
				f.write('\n')

		while True:
			confirm_auth_use = str(input('Do you want to use configured EDX account? [y/n]: ')).strip().lower()
			# confirm_auth_use = "y"  # todo
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
				previous_user = False
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
							"Do you want to save this login info? Type [Y/N]. Type 'never' to save your credentials and "
							"never ask again: ")).strip().lower()

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

		if not os.path.exists(previous_results):
			with open(previous_results, 'w') as f:
				f.write('')

		if not os.path.exists(previous_results_bad):
			with open(previous_results_bad, 'w') as f:
				f.write('')

		if not os.path.exists(pdf_results):
			with open(pdf_results, 'w') as f:
				f.write('')

		try:
			# create main object
			edx = EdxDownloader(email=email, password=password, )
		except (KeyboardInterrupt):
			print(traceback.format_exc())
			sys.exit(1)

		# Check if .edxcookie exists. if it does, it reads it
		# and uses pickle to load it into requests session cookieJar..
		# and authenticates user.
		# If it does not exist, it creates an empty one.

		while not edx.is_authenticated:

			print("Signing in..")

			if previous_user and edx.load():
				# pickle loads previous requests_session
				print("Session loaded")
				edx.is_authenticated = True
			else:
				try:
					passhint = '*' * len(password)
					log('Attempting to sign in using {} and {}'.format(email, passhint), 'orange')
					edx.sign_in()
				except (EdxLoginError, EdxRequestError) as e:
					log('Sign-in failed. Error: ' + str(e), 'red')
					sys.exit(1)
				else:
					edx.dump()

		log('Authentication successful!', 'green')

		if not load_results:
			log('Scanning Dashboard content. Please wait..')
			courses = edx.dashboard_urls()
			# Show dashboard items and multiple choice.
			[print(f"[{i}]  {course.get('course_title')}") for i, course in enumerate(courses, 1)]
			number_of_courses = len(courses)
			choices = set()
			print(f"\nType [ALL] to select all courses.Type the respective integer between 0 and {number_of_courses} "
				  f"and "
				  f"then type[OK] to finalize your choices. ")
			while True:
				course_choice = input('Select : ').strip()
				# course_choice = 'all'
				if course_choice.lower() == 'all':
					log('Parsing. Please wait..')
					[edx.get_course_data(course.get('course_slug')) for course in courses]
					break
				if course_choice == 'ok':
					if not choices:
						# if no choices were made
						log(" Select one or more courses, then type [OK] to finalize your choices.")
						continue
					else:
						# if choices were made
						[edx.get_course_data(course.get('course_slug')) for i, course in enumerate(courses, 1) if
						 i in choices]
						break
				if course_choice == 'x':
					sys.exit(1)
				if course_choice.isdecimal() and 0 < int(course_choice) <= number_of_courses:
					c_n = int(course_choice)
					if c_n not in choices:
						choices.add(c_n)
						log(f"{courses[c_n - 1].get('course_title')} added.\nCurrently selected courses: {choices}")
						continue
					else:
						log("You have already chosen this course.")
						continue
				else:
					log("Not a valid number. Retry.", "red")
					continue
		else:
			log("Loading only previous results.  ")

		results = edx.collector.save_results()

		if type(results) is list and len(results) > 0:
			# DOWNLOAD QUEUE
			log('Found {} videos. Downloading now.'.format(len(results)), 'green')

			for downloadable in results:

				vid_title = re.sub(r'[^\w_ ]', '-', downloadable.get('segment'))
				video_url = downloadable.get('video_url')
				subtitle_url = downloadable.get('subtitle_url', None)  # check
				base_filename = downloadable.get('base_filename')
				base_directory = downloadable.get('base_directory')
				base_path = f'{base_directory}/{base_filename}' + '{}'


				video_save_as = base_path.format('.mp4')
				sub_save_as = base_path.format('.srt')


				Downloader(client=edx.client, url=video_url, save_as=video_save_as, desc=vid_title).download()

				if subtitle_url:

					Downloader(client=edx.client, url=subtitle_url, save_as=sub_save_as, desc=vid_title, srt =True).download()


		log('Finished.', "orange")
	except EdxInvalidCourseError as e:
		log(e, 'red')
		sys.exit(1)
	except EdxNotEnrolledError as e:
		log(e)
		sys.exit(1)
	except KeyboardInterrupt:
		print('\nDownload cancelled by user.')
		sys.exit(1)

	except Exception as e:
		edx.collector.save_results()
		with open(os.path.join(os.getcwd(), 'edx-error.log'), 'a') as f:
			f.write((str(e)))
		print(traceback.format_exc())
		print(f'Something unexpected occured. Please provide details present in '
			  f'{os.path.join(os.getcwd())}/edx-error.log file and open an issue at GitHub.')

		sys.exit(1)
