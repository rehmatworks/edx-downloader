import ast
import html
import json
import os
import pickle
import re
import sys
import time
import traceback
from os.path import expanduser
import colorful as cf
import pdfkit
import requests
import validators
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from tqdm import tqdm

# Base URLs as pseudo constants

EDX_HOSTNAME = 'courses.edx.org'
BASE_URL = 'https://{}'.format(EDX_HOSTNAME)
LMS_BASE_URL = 'https://learning.edx.org'
BASE_API_URL = '{}/api'.format(BASE_URL)
LOGIN_URL = '{}/login'.format(BASE_URL)
COURSE_BASE_URL = '{}/courses'.format(BASE_URL)
COURSE_OUTLINE_BASE_URL = '{}/course_home/v1/outline'.format(BASE_API_URL)
XBLOCK_BASE_URL = '{}/xblock'.format(BASE_URL)
LOGIN_API_URL = '{}/user/v1/account/login_session/'.format(BASE_API_URL)
DASHBOARD_URL = '{}/dashboard/'.format(BASE_URL)
VERTICAL_BASE_URL = '{}/course'.format(LMS_BASE_URL)
BASE_KALTURA_VIDEO_URL = "https://cdnapisec.kaltura.com/p/{PID}/sp/{PID}00/playManifest/entryId/{entryId}/format/download/protocol/https/flavorParamIds/0"

#  SUBTITLE_URL =  htt://courses.edx.org/courses/{COURSE_BASE_URL}    /xblock/block-v1:MITx+6.00.2x+1T2022+type@video+block@c26bf10a0c6b48c8b1f111185ad3e561/handler/transcript/download


# Chunk size to download videos in chunks
VID_CHUNK_SIZE = 1024


class EdxLoginError(Exception):

	def __init__(self, value):
		self.value = value

	def __str__(self):
		return repr(self.value)


# Is raised when the course cannot be fetched
class EdxInvalidCourseError(Exception):
	def __init__(self, value):
		self.value = value

	def __str__(self):
		return repr(self.value)

    """Raised when login attempt fails"""

class EdxInvalidCourseError(Exception):
    """Raised when the course cannot be fetched"""

class EdxNotEnrolledError(Exception):

	def __init__(self, value):
		self.value = value

	def __str__(self):
		return repr(self.value)

    """Raised when no blocks found for the course"""


class EdxRequestError(Exception):

	def __init__(self, value):
		self.value = value

	def __str__(self):
		return repr(self.value)


# Raised when an unauthenticated request is made
class EdxNotAuthenticatedError(Exception):
	def __init__(self, value):
		self.value = value

	def __str__(self):
		return repr(self.value)


class LogMessage:
	ci_colors = {
			'green' : '#42ba96',
			'orange': '#ffc107',
			'red'   : '#df4759',
			'blue'  : '#5dade2'
	}
	cf.update_palette(ci_colors)
	is_debug = 'is_debug'
	is_colored = 'is_colored'

	@classmethod
	def set_args(cls, is_debug, is_colored):
		'''
		# When it is set False, the log_message()
		# function will not print anything.
		# When this is set to True the log_message()
		# function will print in color.
		:param is_debug:
		:param is_colored:
		'''
		cls.is_debug = is_debug
		cls.is_colored = is_colored

	@classmethod
	def log_message(cls, message, color='blue', ):
		# Outputs a colorful message to the terminal
		# and only if 'is_debug' prop is set to True.
		# Override colorful palette

		if cls.is_debug:
			if cls.is_colored:
				if color == 'blue':
					message = cf.bold & cf.blue | message
				elif color == 'orange':
					message = cf.bold & cf.orange | message
				elif color == 'green':
					message = cf.bold & cf.green | message
				elif color == 'red':
					message = cf.bold & cf.red | message
				print(message)
			else:
				print(message)


log = LogMessage.log_message
=======
    """Raised when some HTTP error occurs"""

class EdxNotAuthenticatedError(Exception):
    """Raised when an unauthenticated request is made"""


class EdxDownloader:
	# TODO
	EDX_HOSTNAME = 'courses.edx.org'
	BASE_URL = 'https://{}'.format(EDX_HOSTNAME)
	LMS_BASE_URL = 'https://learning.edx.org'
	BASE_API_URL = '{}/api'.format(BASE_URL)
	LOGIN_URL = '{}/login'.format(BASE_URL)
	COURSE_BASE_URL = '{}/courses'.format(BASE_URL)
	COURSE_OUTLINE_BASE_URL = '{}/course_home/v1/outline'.format(BASE_API_URL)
	XBLOCK_BASE_URL = '{}/xblock'.format(BASE_URL)
	LOGIN_API_URL = '{}/user/v1/account/login_session/'.format(BASE_API_URL)
	DASHBOARD_URL = '{}/dashboard/'.format(BASE_URL)
	VERTICAL_BASE_URL = '{}/course'.format(LMS_BASE_URL)
	DOWNLOAD_KALTURA_URL = "https://cdnapisec.kaltura.com/p/{PID}/sp/{PID}00/playManifest/entryId/{entryId}/format/download/protocol/https/flavorParamIds/0"

	# Create a request session to send cookies
	# automatically for HTTP requests.

	# Generate a fake user-agent to avoid blocks
	user_agent = UserAgent()

	# Initiate webdriver

	# These headers are required. Some may not be required
	# but sending all is a good practice.
	edx_headers = {
			'Host'            : EDX_HOSTNAME,
			'accept'          : '*/*',
			'x-requested-with': 'XMLHttpRequest',
			# 'user_agent'      : 'Mozilla/5.0 (X11; Linux x86_64) '
			# 					'AppleWebKit/537.36 (KHTML, like Gecko) '
			# 					'Chrome/101.0.4951.54 Safari/537.36',
			'user-agent': user_agent.random,
			# 'user-agent': driver.execute_script("return navigator.userAgent"),
			'content-type'    : 'application/x-www-form-urlencoded; charset=UTF-8',
			'origin'          : BASE_URL,
			'sec-fetch-site'  : 'same-origin',
			'sec-fetch-mode'  : 'cors',
			'sec-fetch-dest'  : 'empty',
			'referer'         : LOGIN_URL,
			'accept-language' : 'en-US,en;q=0.9',
			'connection'      : 'keep-alive',
			'Keep-Alive'      : 'timeout=30, max=10000'
	}

	# Cookie location
	SAVED_SESSION_PATH = os.path.join(expanduser('~'), 'edxcookie')

	def __init__(self, email, password, toggle_experimental=False, ):
		# This is set True later and is used to
		# avoid unnecessary login attempts
		self.is_authenticated = False

		# CookieHandler with pickle module
		self.client = requests.Session()

		# Collector
		self.collector = Collector()
		# The EDX account's email
		self.edx_email = email

		# The EDX account's password
		self.edx_password = password

		# Enables experimental parser for specific Courses that embed Kaltura WebPlayer.
		self.toggle_experimental = toggle_experimental

		self.session_file_exists = os.path.exists(self.SAVED_SESSION_PATH)

	def load(self, ):
		if self.session_file_exists and os.path.getsize(self.SAVED_SESSION_PATH) > 100:
			with open(self.SAVED_SESSION_PATH, 'rb') as f:
				self.client = pickle.load(f)
			return True
		else:
			log("pickleJar is empty", "red")
			return False

	def dump(self, ):
		with open(self.SAVED_SESSION_PATH, 'wb') as f:
			pickle.dump(self.client, f)

	def sign_in(self):
		# Authenticates the user session. It returns True on success
		# or raises EdxLoginError on failure.
		# html_res = self.requests_session.get(LOGIN_URL)
		# Retrieve the CSRF token first

		try:
			self.client.get(LOGIN_URL)  # sets cookie
			if 'csrftoken' in self.client.cookies:
				# Django 1.6 and up
				csrftoken = self.client.cookies['csrftoken']

			else:
				# older versions
				csrftoken = self.client.cookies['csrf']

			self.edx_headers.update({'x-csrftoken': csrftoken})
			data = {
					'email'   : self.edx_email,
					'password': self.edx_password
			}
			res = self.client.post(LOGIN_API_URL, headers=self.edx_headers, data=data).json()

			if res.get('success') is True:
				self.is_authenticated = True
				return True
			else:
				if res.get("value"):
					raise EdxLoginError(res.get('value'))
		except ConnectionError as e:
			print(e)
			raise EdxRequestError("Connection or CSRF token problem")


	def dashboard_urls(self):
		'''
		The following function scrapes the main dashboard for all available courses
		including archived.
		It does NOT parse courses with invalid or expired access.

		'''
		available_courses = []
		try:
			response = self.client.get(DASHBOARD_URL,
									   headers=self.edx_headers)
		except ConnectionError as e:
			raise EdxRequestError(str(e))

		soup = BeautifulSoup(html.unescape(response.text), 'lxml')
		soup_elem = soup.find_all('a', {'class': 'enter-course'})
		if soup_elem:
			for i, element in enumerate(soup_elem):
				course_title = soup.find('h3', {'class': 'course-title',
												'id'   : 'course-title-' + element.get('data-course-key')}
										 ).text.strip()
				course_slug = element['data-course-key']
				course_url = "{}/{}/".format(COURSE_BASE_URL, course_slug)
				available_courses.append({'course_title': course_title,
										  'course_url'  : course_url,
										  'course_slug' : course_slug}
										 )
		if len(available_courses) > 0:
			# print(available_courses)
			log(f"{len(available_courses)} available courses found in your Dashboard!", 'orange')
		else:
			log("No courses available!", "red")
		return available_courses

	def get_course_data(self, course_url: str):
		'''

		 This method expects a course's URL as argument, searches for it's xBlock structure and, if found, it returns it as a dictionary,else raises exception.
		'''

		log('Building xblocks.')
		# TODO  URL CHECK START
		# Break down the given course URL to get the course slug.
		course_slug = course_url
		if not course_url.startswith('course-'):
			url_parts = course_url.split('/')
			for part in url_parts:
				if part.startswith('course-'):
					course_slug = part
					break
			else:
				# If the conditions above are not passed, we will assume that a wrong
				# course URL was passed in.
				raise EdxInvalidCourseError('The provided course URL seems to be invalid.')
		# if course_slug in self.collector.negative_results_id:
		# 	return

		# Construct the course outline URL
		COURSE_OUTLINE_URL = '{}/{}'.format(COURSE_OUTLINE_BASE_URL, course_slug)
		# TODO   URL CHECK STOP

		# TODO xBlockMapper start

		# Make an HTTP GET request to outline URL
		# and return a dictionary object
		# with blocks:metadata as key:values which
		# will help us iterate through course.

		try:
			outline_resp = self.client.get(COURSE_OUTLINE_URL,
										   headers=self.edx_headers)
		except ConnectionError as e:
			raise EdxRequestError(e)
		# Transforms response into dict and returns the course's block structure into variable 'blocks'.
		# blocks:metadata as keys:values
		try:
			blocks = outline_resp.json()
		except Exception as e:
			print(traceback.format_exc())
			sys.exit(1)
		if blocks is None:
			# If no blocks are found, we will assume that the user is not authorized
			# to access the course.
			raise EdxNotEnrolledError('No course content was found. Check your enrollment status and try again.')
		else:
			blocks = blocks.get('course_blocks').get('blocks')

		course_title = None
		if list(blocks.values())[0].get('type') == 'course':
			course_title = list(blocks.values())[0].get('display_name')
		else:
			for block, block_meta in blocks.items():
				if block_meta.get('type') == 'course' and block_meta.get('display_name') is not None:
					course_title = block_meta.get('display_name')
					break

		lectures = {k: v for k, v in blocks.items() if v['type'] == 'sequential'}
		chapters = {k: v for k, v in blocks.items() if v['type'] == 'chapter' and v['children'] is not None}

		# course directory
		course_name = re.sub(r'[^\w_ ]', '-', course_title).replace('/', '-').strip()
		main_dir = os.path.join(os.getcwd(),'edx' ,course_name)
		if not os.path.exists(main_dir):
			# create course Directory
			os.makedirs(main_dir)


		for i, (lecture, lecture_meta) in enumerate(lectures.items()):
			lecture_name = re.sub(r'[^\w_ ]', '-', lecture_meta.get('display_name')).replace('/', '-')
			for chapter, chapter_meta in chapters.items():
				if lecture in chapter_meta.get('children'):
					chapter_name = re.sub(r'[^\w_ ]', '-', chapter_meta.get('display_name')).replace('/', '-').strip()
					chapter_dir = os.path.join(main_dir, chapter_name)
					if not os.path.exists(chapter_dir):
						# create lecture Directories
						os.makedirs(chapter_dir)

					lecture_meta.update({'chapter': chapter_meta.get('display_name')})
					lecture_meta.update({'chapterID': chapter_meta.get('id')})
					lecture_meta.update({'course': course_title})

					base_filename = '{segment} - ' + f'{lecture_name}'
					lecture_meta.update({'base_filename': base_filename})
					lecture_meta.update({'base_directory': chapter_dir})


			# assuming that lectures are ordered .

			lecture_url = "{}/{}".format(XBLOCK_BASE_URL, lecture)

			# TODO xBlockMapper STOP
			soup = None
			for j in range(3):
				try:
					lecture_res = self.client.get(lecture_url,
												  headers=self.edx_headers,
												  allow_redirects=True)
					soup = BeautifulSoup(html.unescape(lecture_res.text), 'lxml')
				except Exception as e:
					if j == 2:
						raise EdxRequestError(e)
					time.sleep(5)
					print("RETRYING")
					self.load()
					continue
				else:
					break


			self.default_scrape(lecture, lecture_meta, course_slug, soup)
			self.collector.negative_results_id.add(lecture)
		self.collector.negative_results_id.add(course_slug)

	def default_scrape(self, lecture, lecture_meta, course_slug, soup):
		'''
		# Searches through HTML elements
		# Finds and builds URLs for subtitles and videos
		'''
		log("Entered Default")
		iframe_soup = soup.find('iframe', {'id':'unit-iframe'})
		if iframe_soup:
			segment = iframe_soup.get('title')
			segment_title = re.sub(r'[^\w_ ]', '-', segment).replace('/', '-')
		else:
			segment_title ="video"
		base_directory=lecture_meta.get('base_directory')
		base_filename = lecture_meta.get('base_filename').format(segment = segment_title)
		total_file_path = os.path.join(base_directory,base_filename)

		soup_xvid = soup.find_all('div', {'class': 'xblock-student_view'})
		if soup_xvid:
			for i in soup_xvid:
				paragraphs =  i .find_all('p')
				if paragraphs  and not os.path.exists(total_file_path+ '.pdf'):
					inner_html = i.decode_contents().replace('src="',
																		  'src="https://courses.edx.org/'
																		  )
					inner_html = inner_html.replace('src="https://courses.edx.org/http',
													'src="http'
													)
					try:
						self.collector.save_as_pdf(inner_html, total_file_path,
												   id=lecture
												   )
						log("PDF saved!", "orange")
					except Exception as e:
						print("Problem while building PDF.")
						print(e)
				meta_block = i.find('div', {'class': 'video', 'data-metadata': True})
				header_block = i.find('h3', attrs={'class': 'hd hd-2'})
				if meta_block and header_block:

					json_meta = json.loads(meta_block.get('data-metadata'))
					# Get the data-metadata attribute HTML
					# and parse it as a JSON object.
					prepared_item = {}
					if 'sources' in json_meta:

						for video_source in list(json_meta['sources']):
							if video_source.endswith('.mp4'):
								# video URL found
								log(f"Struck gold! A video was found in segment: {segment_title}!",
									"orange"
									)
								prepared_item.update(course_slug=course_slug,
													 course=lecture_meta.get('course'),
													 chapter=lecture_meta.get('chapter'),
													 lecture=lecture_meta.get('display_name'),
													 id=lecture,
													 segment=segment_title,
													 base_directory=base_directory,
													 video_url=video_source,
													 base_filename=base_filename)

								# Break the loop if a valid video URL
								# is found.
								if 'transcriptAvailableTranslationsUrl' in json_meta:
									# subtitle URL found
									subtitle_url = '{}{}'.format(BASE_URL,
																 json_meta.get('transcriptAvailableTranslationsUrl')
																 .replace("available_translations", "download")
																 )
									log(f"Subtitle was found for: {segment_title}!",
										"orange"
										)
									prepared_item.update(subtitle_url=subtitle_url)
								break

					self.collector(**prepared_item)
		return


class Collector():
	base_filepath = os.path.join(expanduser('~'), '{file}')

	def __init__(self):
		"""
		Collects dict items that will be sent to the downloader later.
		Saves results in designated folders.
		Saves negative results.
		Saves results where a pdf file was created.
		"""

		# list of positive dictionary item objects that will be RETURNED to main()
		# for download
		self.all_videos = []

		# set with ID's of previously found positive dictionary results.
		self.positive_results_id = set()

		# set with ID's of previously found negative dictionary results.
		self.negative_results_id = set()
		# TEST
		self.pdf_results_id = set()
		self.pdf_results = self.base_filepath.format(file='.edxPDFResults')

		self.results = self.base_filepath.format(file='.edxResults')
		self.negative_results = self.base_filepath.format(file='.edxResults_bad')

		with open(self.results, "r") as f:
			# reads previously found positive results .
			for line in f:
				d = ast.literal_eval(line)
				if not d.get('id') in self.positive_results_id:
					# loading previous dict results
					self.all_videos.append(d)
					# collecting ids in set() to avoid duplicates
					self.positive_results_id.add(d.get('id'))

		with open(self.negative_results) as f:
			# loads previously found negative pages where no video was found.
			self.negative_results_id = set(line.strip() for line in f)

		if True:
			with open(self.pdf_results) as f:
				# loads previously found negative pages where no  was found.
				self.pdf_results_id = set(line.strip() for line in f)

	def __call__(self, id, course, course_slug, chapter, lecture, segment,
				 video_url, base_filename, base_directory, subtitle_url=''):
		'''
		:param id: id of current block where item was found
		:param course: name of Course,
		:param course_slug: slug of course
		:param chapter: current chapter
		:param lecture: lecture (sequence)
		:param segment: Segment or video name
		:param video_url:  video url
		:param base_filename: base filename, without suffix
		:param base_directory: directory of file
		:param subtitle_url:  subtitle url
		:return: bool
		'''

		item = locals()
		item.pop('self')
		if item.get('id') not in self.positive_results_id:
			# avoids duplicates
			if not validators.url(item.get('subtitle_url')):
				item.pop('subtitle_url')

			self.all_videos.append(item)
			self.positive_results_id.add(item.get('id'))
			print(len(self.all_videos))
			return True
		else:
			return False


	def save_results(self, ):
		'''
		:return:list(dict()) self.all_videos
		Saves all results in file to later reuse.
		'''

		with open(self.results, 'w') as f:
			for result in self.all_videos:
				f.write(str(result) + '\n')

		with open(self.negative_results, "w") as f:
			for negative_id in self.negative_results_id:
				f.write(str(negative_id) + '\n')

		if True:
			with open(self.pdf_results, "w") as f:
				for pdf_id in self.pdf_results_id:
					f.write(str(pdf_id) + '\n')

		print("SEARCH RESULTS SAVED IN ~/.edxResults")

		return self.all_videos

	def save_as_pdf(self, string: str, path: str, id: str):
		'''

		:param string: string-like data to be made into PDF
		:param path: full path save directory
		:param id: id of page where the data was found.
		:return: None
		'''
		# course directory
		# pdf_options = {'cookie': [('csrftoken', token)]}

		pdf_save_as = f'{path}.pdf'
		pdfkit.from_string(string, output_path=pdf_save_as)
		self.pdf_results_id.add(id)




class Downloader():
	def __init__(self, client: requests.Session, url: str, save_as: str, desc: str, srt:bool= False ):

		self.client = client
		self.url = url
		self.save_as = save_as
		self.desc = desc
		self.headers = {'x-csrftoken': self.client.cookies.get_dict().get('csrftoken')}
		self.srt = srt


	@staticmethod
	def file_exists( func):
		def inner(self):
			if os.path.exists(self.save_as):
				# if file exists
				log(f'Already downloaded. Skipping: {self.desc}.{self.save_as.split(".")[-1:]}')
				return False
			func(self)
		return inner

	@staticmethod
	def deco(func):
		def inner (self):
			if self.srt and 'kaltura' not in self.url:
				self.change_user_state()
			func(self)
		return inner

	def change_user_state(self,):
		'''
		# Subtitles are either downloaded as (.srt) or as transcripts (.txt)
		# depending on  "user_state"  that is saved server side and we cannot
		# make the choice with a simple GET request.
		# Thus, a POST request is required , which will change the user state
		# to the following  "transcript_download_format": "srt".
		'''

		for i in range(4):
			try:
				save_user_state = self.url.replace("transcript", "xmodule_handler").replace("download", "save_user_state")
				payload = {"transcript_download_format": "srt"}

				post_response = self.client.post(url=save_user_state,
												 cookies=self.client.cookies.get_dict(),
												 headers=self.headers,
												 data=payload
												 )
			except ConnectionError as e:
				if i == 1:
					raise EdxRequestError(e)
				continue

			else:
				if post_response.status_code == 200:
					break
				else:
					continue
		else:
			return False




	@file_exists
	@deco
	def download(self, ):
		s= 'srt' if self.srt else 'mp4'
		log('Downloading: {name}.{srt}'.format(name=self.desc, srt=s))
		# temporary name to avoid duplication.
		save_as_parted = f"{self.save_as}.part"
		# In order to make downloader resumable, we need to set our headers with
		# a correct Range value. we need the bytesize of our incomplete file and
		# the content-length from the file's header.

		current_size_file = os.path.getsize(save_as_parted) if os.path.exists(save_as_parted) else 0
		range_headers = {'Range': f'bytes={current_size_file}-'}

		# print("url", url)
		# HEAD response will reveal length and url(if redirected).
		head_res = self.client.head(self.url,
									headers=self.headers.update(range_headers),
									allow_redirects=True,
									timeout=60)

		url = head_res.url
		# file_size str-->int (remember we need to build bytesize range)
		file_size = int(head_res.headers.get('Content-Length', 0))

		progress_bar = tqdm(initial=current_size_file,
							total=file_size,
							unit='B',
							unit_scale=True,
							smoothing=0,
							desc=f'{self.desc}',
							file=sys.stdout,
							)
		# We set the progress bar to the size of already
		# downloaded .part file
		# to display the correct length.
		with self.client.get(url,
							 headers=range_headers,
							 stream=True,
							 allow_redirects=True,
							 ) as resp:

			with open(save_as_parted, 'ab') as f:
				for chunk in resp.iter_content(chunk_size=VID_CHUNK_SIZE * 100):
					# -write response data chunks to file_size
					# - Updates progress_bar
					progress_bar.update(len(chunk))
					f.write(chunk)

		progress_bar.close()
		if file_size == os.path.getsize(save_as_parted):
			# assuming downloaded file has correct number of bytes(size)
			# then we rename with correct suffix.
			os.rename(save_as_parted, self.save_as)
			return True
		elif file_size < os.path.getsize(save_as_parted):
			# deletes file if downloaded bytes are more
			# than those declared by server.
			os.remove(save_as_parted)
			return False
		else:
			print("unknown error")
			return False

