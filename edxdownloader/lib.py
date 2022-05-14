import ast
import html
import json
import os
import pickle
import sys
import time
import traceback
from os.path import expanduser

import colorful as cf
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait
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
DOWNLOAD_KALTURA_URL = "https://cdnapisec.kaltura.com/p/{PID}/sp/{PID}00/playManifest/entryId/{entryId}/format/download/protocol/https/flavorParamIds/0"

#  SUBTITLE_URL =  htt://courses.edx.org/courses/{COURSE_BASE_URL}    /xblock/block-v1:MITx+6.00.2x+1T2022+type@video+block@c26bf10a0c6b48c8b1f111185ad3e561/handler/transcript/download


# Chunk size to download videos in chunks
VID_CHUNK_SIZE = 1024


# Is raised when login attempt fails
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


# Raised when no blocks found for the course
class EdxNotEnrolledError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


# Raised when some HTTP error occurs
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
    def __init__(self, is_debug=True, is_colored=True):
        # When it is set False, the log_message()
        # function will not print anything.
        self.is_debug = is_debug

        # When this is set to True the log_message()
        # function will print in color.
        self.is_colored = is_colored

    def __call__(self, message, color='blue'):
        # Outputs a colorful message to the terminal
        # and only if 'is_debug' prop is set to True.
        # Override colorful palette
        ci_colors = {
            'green': '#42ba96',
            'orange': '#ffc107',
            'red': '#df4759',
            'blue': '#5dade2'
        }
        cf.update_palette(ci_colors)

        if self.is_debug:
            if self.is_colored:
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
        else:
            print(message)


class SeleniumManager:

    def __init__(self, cookies):
        # selenium
        self.chromeOptions = webdriver.ChromeOptions()
        # self.chromeOptions.add_argument('--headless')
        self.chromeOptions.add_argument("--no-sandbox")
        self.chromeOptions.add_argument("--disable-setuid-sandbox")
        self.chromeOptions.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})
        self.chromeOptions.add_argument("--ignore-certificate-errors")
        self.chromeOptions.add_argument("--remote-debugging-port=9222")  # this
        self.chromeOptions.add_argument("--disable-dev-shm-using")
        self.chromeOptions.add_argument("--disable-extensions")
        self.chromeOptions.add_argument("--disable-gpu")
        # self.chromeOptions.add_argument("start-maximized")
        self.chromeOptions.add_argument("disable-infobars")
        self.chromeOptions.add_argument("--user-data-dir=./Downloads/firefox.tmp")
        # self.chromeOptions.add_argument("--profile-directory=Default");
        self.Sessioncookies = self.getCookies(cookies)
        self.driver = webdriver.Chrome(chrome_options=self.chromeOptions)
        self.driver.implicitly_wait(4)

    # # TODO
    # def get_url(self, url):
    #     try:
    #         self.driver.get(url)
    #         time.sleep(2)
    #     except Exception as e:
    #         print(traceback.format_exc())
    #         # self.driver.quit()

    def getCookies(self, cookies: dict):
        #
        return [{'name': c.name,
                 'value': c.value,
                 'domain': c.domain,
                 'path': c.path,
                 # 'expiry': c.expires,
                 } for c in cookies]

    def loadCookies(self):
        [self.driver.add_cookie(cookie) for cookie in self.Sessioncookies]
        return

    # def unloadCookies(self):
    #     all_cookies = self.driver.get_cookies();
    #     cookies_dict = {}
    #
    #     [cookies_dict.update(dict(name.get():value for name,value in all_cookies]
    #
    #
    #     print(cookies_dict)
    #     print(cookies_dict.get('__ivc'))
    #
    #     self.driver.delete_all_cookies()
    #     [self.driver.add_cookie(cookie) for cookie in self.Sessioncookies]
    #     return


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
        'Host': EDX_HOSTNAME,
        'accept': '*/*',
        'x-requested-with': 'XMLHttpRequest',
        'user_agent': 'Mozilla/5.0 (X11; Linux x86_64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/101.0.4951.54 Safari/537.36',
        # 'user-agent': user_agent.random,
        # 'user-agent': driver.execute_script("return navigator.userAgent"),
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'origin': BASE_URL,
        'sec-fetch-site': 'same-origin',
        'sec-fetch-mode': 'cors',
        'sec-fetch-dest': 'empty',
        'referer': LOGIN_URL,
        'accept-language': 'en-US,en;q=0.9',
    }

    # Cookie location
    SAVED_SESSTION_PATH = os.path.join(expanduser('~'), 'edxcookie')

    def __init__(self, email, password, is_debug=True, is_colored=True, toggle_experimental=False, ):
        # This is set True later and is used to
        # avoid unnecessary login attempts
        self.is_authenticated = False

        # CookieHandler with pickle module
        self.client = requests.Session()

        self.log_message = LogMessage(is_debug, is_colored)

        # Collector
        self.collector = Collector()
        # The EDX account's email
        self.edx_email = email

        # The EDX account's password
        self.edx_password = password

        #  list of dictionary objects that will be RETURNED to utils.py main
        # for download
        # #  structure of dictionaries:
        # {
        #     'course': course_title,
        #     'chapter': chapter_name,
        #     'lecture': lecture_name,
        #     'title': segment_name,
        #     'video_url': video_url,
        #     'subtitle_url': subtitle_url    }
        # Enables experimental parser for specific Courses that embed Kaltura WebPlayer.
        self.toggle_experimental = toggle_experimental

        self.session_file_exists = os.path.exists(self.SAVED_SESSTION_PATH)

    def load(self, ):
        if self.session_file_exists and os.path.getsize(self.SAVED_SESSTION_PATH) > 100:
            with open(self.SAVED_SESSTION_PATH, 'rb') as f:
                self.client = pickle.load(f)
            return True
        else:
            self.log_message("pickleJar is empty", "red")
            return False

    def dump(self, ):
        with open(self.SAVED_SESSTION_PATH, 'wb') as f:
            pickle.dump(self.client, f)

    def sign_in(self):
        # Authenticates the user session. It returns True on success
        # or raises EdxLoginError on failure.
        # html_res = self.requests_session.get(LOGIN_URL)
        # Retrieve the CSRF token first

        try:
            self.client.get(LOGIN_URL, timeout=20)  # sets cookie
            if 'csrftoken' in self.client.cookies:
                # Django 1.6 and up
                csrftoken = self.client.cookies['csrftoken']

            else:
                # older versions
                csrftoken = self.client.cookies['csrf']

            self.edx_headers['x-csrftoken'] = csrftoken
            data = {
                'email': self.edx_email,
                'password': self.edx_password
            }
            res = self.client.post(LOGIN_API_URL, headers=self.edx_headers, data=data, timeout=10).json()

            if res.get('success') is True:
                self.is_authenticated = True
                return True
            else:
                if res.get("value"):
                    raise EdxLoginError(res.get('value'))
        except ConnectionError as e:
            print(e)
            raise EdxRequestError("Connection or CSRF token problem")

    def experimental_scrape(self, course_title, lectures, driver):
        '''
        # we run a second client GET request by using
        # the parent's <iframe src="{nested iframe URL}"
        # attribute to dwelve deeper into it's nested content which will
        # eventually include both the video URL and subtitles URL.
        '''
        driver.driver.delete_all_cookies()

        print("Experimental Scraping initiates..")
        for i in reversed(range(3)):
            print(i + 1)
            time.sleep(1)

        for lecture, lecture_meta in lectures.items():
            sequential_block_slug = lecture

            lecture_url = "{}/{}".format(XBLOCK_BASE_URL, sequential_block_slug)
            # print("lecture_url   : ",lecture_url)
            try:
                lecture_res = self.client.get(lecture_url)
            except ConnectionError as e:
                raise EdxRequestError(e)
            soup = BeautifulSoup(html.unescape(lecture_res.text), 'lxml')

            if soup:
                vertical_elements = soup.find_all('button', {'class': 'seq_other'})

                if vertical_elements:
                    for vertical_elem in vertical_elements:

                        vertical_slug = vertical_elem.get("data-id")
                        if vertical_slug in self.collector.positive_results_id | self.collector.negative_results_id:
                            self.log_message(f"{vertical_elem.get('data-path')} already parsed. Passing..")
                            continue
                        vertical_url = "{}/{}".format(XBLOCK_BASE_URL, vertical_slug)
                        self.log_message((
                            f"Searching for elements in vertical block:  {vertical_elem.get('data-path')}"))

                        a = time.time()
                        for i in range(2):
                            try:
                                driver.driver.get(vertical_url)
                                driver.loadCookies()

                                iframe = WebDriverWait(driver.driver, 2).until(
                                    expected_conditions.presence_of_element_located((By.ID, "kaltura_player")))
                                driver.driver.switch_to.frame(iframe)
                            except:
                                continue
                            else:
                                break
                        else:
                            self.collector.negative_results_id.add(vertical_slug)
                            continue

                        video_element = None
                        subtitle_element = None
                        for i in range(2):
                            print('number of repetitions :', 1 + i)
                            try:
                                # ignored_exceptions = (NoSuchElementException, StaleElementReferenceException)
                                video_element = WebDriverWait(driver.driver, 2).until(
                                    expected_conditions.presence_of_element_located((By.ID, "pid_kaltura_player")))
                            except Exception as e:
                                self.log_message(f"Error while grabing video.{e}")
                                if i < 1:
                                    self.log_message("Retrying..")
                                continue
                            else:
                                # video found
                                try:
                                    subtitle_element = video_element.find_element(By.TAG_NAME, 'track')
                                except:
                                    self.log_message("Subtitle was not found for this video")
                            break
                        print(driver.driver.get_cookie('csrftoken'))
                        if video_element:

                            PID = video_element.get_attribute('kpartnerid')
                            entryId = video_element.get_attribute('kentryid')
                            video_url = DOWNLOAD_KALTURA_URL.format(PID=PID, entryId=entryId)

                            self.log_message(
                                f"Struck gold! New video just found! {vertical_elem.get('data-page-title')}",
                                "orange")
                            subtitle_url = None
                            if subtitle_element:
                                self.log_message(
                                    f"Subtitle found! {vertical_elem.get('data-page-title')}",
                                    "orange")
                                subtitle_url = subtitle_element.get_attribute('src')

                            self.collector(course=course_title,
                                           chapter=lecture_meta['chapter'],
                                           lecture=lecture_meta['display_name'],
                                           id=vertical_elem.get("data-id"),
                                           segment=vertical_elem.get("data-page-title"),
                                           video_url=video_url,
                                           subtitle_url=subtitle_url)

                        else:
                            self.collector.negative_results_id.add(vertical_slug)
                            # with open(self.results + "_bad", "a") as f:
                            #     f.write(str(vertical_slug + '\n'))

        return

    def dashboard_urls(self):
        '''
        The following function scrapes the main dashboard for all available courses
        including archived.
        It does NOT parse courses with invalid or expired access.

        '''
        available_courses = []
        try:
            request = self.client.get(DASHBOARD_URL)
        except ConnectionError as e:
            raise EdxRequestError(str(e))

        soup = BeautifulSoup(html.unescape(request.text), 'lxml')
        soup_elem = soup.find_all('a', {'class': 'enter-course'})
        if soup_elem:
            for i, element in enumerate(soup_elem):
                course_title = soup.find('h3', {'class': 'course-title',
                                                'id': 'course-title-' + element.get('data-course-key')}).text.strip()
                COURSE_SLUG = element['data-course-key']
                course_url = "{}/{}/".format(COURSE_BASE_URL, COURSE_SLUG)
                available_courses.append({'course_title': course_title,
                                          'course_url': course_url,
                                          'COURSE_SLUG': COURSE_SLUG})
        if len(available_courses) > 0:
            # print(available_courses)
            self.log_message(f"{len(available_courses)} available courses found in your Dashboard!", 'orange')
        else:
            self.log_message("No courses available!", "red")
        return available_courses

    def get_course_data(self, course_url: str):
        '''

         This method expects a course's URL as argument, searches for it's xBlock structure and, if found, it returns it as a dictionary,else raises exception.
        '''

        self.log_message('Building xblocks.')

        # TODO  ( IS URL A VALID COURSE ? ) START
        # Break down the given course URL to get the course slug.
        COURSE_SLUG = course_url
        if not course_url.startswith('course-'):
            url_parts = course_url.split('/')
            for part in url_parts:
                if part.startswith('course-'):
                    COURSE_SLUG = url_parts
            else:
                # If the conditions above are not passed, we will assume that a wrong
                # course URL was passed in.
                raise EdxInvalidCourseError('The provided course URL seems to be invalid.')
        # Construct the course outline URL
        COURSE_OUTLINE_URL = '{}/{}'.format(COURSE_OUTLINE_BASE_URL, COURSE_SLUG)
        # TODO  ( IS URL A VALID COURSE ? ) END

        # TODO is_authenticated start
        # Check either authenticated or not before proceeding.
        # If not, raise the EdxNotAuthenticat
        # todo is_authenticated end

        # TODO Mapper START

        # Make an HTTP GET request to outline URL
        # and return a dictionary object
        # with blocks:metadata as key:values which
        # will help us iterate through course.

        # TODO ConnectionManager START
        try:
            outline_resp = self.client.get(COURSE_OUTLINE_URL, timeout=10)
        except ConnectionError as e:
            raise EdxRequestError(e)
        # TODO ConnectionManager STOP
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

        for lecture, lecture_meta in lectures.items():
            for chapter, chapter_meta in chapters.items():
                if lecture in chapter_meta.get('children'):
                    lectures.setdefault(lecture, {}).update({'chapter': chapter_meta.get('display_name')})
                    lectures.setdefault(lecture, {}).update({'chapterID': chapter_meta.get('id')})
                    lectures.setdefault(lecture, {}).update({'course': course_title})
                    break

        if self.toggle_experimental:
            driver = SeleniumManager(self.client.cookies)
            try:
                self.experimental_scrape(course_title, lectures, driver)
            except (KeyboardInterrupt, ConnectionError):
                self.collector.save_results()
                driver.driver.quit()
            return

        for lecture, lecture_meta in lectures.items():

            # lectures are the equivalent of sequentials from course block .
            lecture_url = "{}/{}".format(XBLOCK_BASE_URL, lecture)
            # TODO Mapper STOP

            # TODO ConnectionManager START
            try:
                lecture_res = self.client.get(lecture_url)
            except ConnectionError as e:
                raise EdxRequestError(e)
            soup = BeautifulSoup(html.unescape(lecture_res.text), 'lxml')
            # TODO ConnectionManager STOP

            if soup:

                # TODO  PageScraper START

                # Searches through HTML elements
                # Finds and builds URLs for subtitles and videos

                for elements in soup.find_all('div', {'class': 'xblock-student_view-video'}):
                    segment_title = None
                    video_url = None
                    subtitle_url = None

                    meta_block = elements.find('div', {'class': 'video', 'data-metadata': True})
                    header_block = elements.find('h3', attrs={'class': 'hd hd-2'})
                    if meta_block and header_block:

                        meta = meta_block.get('data-metadata')
                        json_meta = json.loads(meta)
                        # Get the data-metadata attribute HTML
                        # and parse it as a JSON object.
                        if 'sources' in json_meta:
                            for video_source in list(json_meta['sources']):
                                if video_source.endswith('.mp4'):
                                    # video URL found
                                    segment_title = header_block.text
                                    video_url = video_source
                                    self.log_message(f"Struck gold! A video was found in segment: {segment_title}!",
                                                     "orange")
                                    # Break the loop if a valid video URL
                                    # is found.

                                    if subtitle_url is None and 'transcriptAvailableTranslationsUrl' in json_meta:
                                        # subtitle URL found
                                        subtitle_url = '{}{}' \
                                            .format(BASE_URL,
                                                    json_meta['transcriptAvailableTranslationsUrl']
                                                    .replace("available_translations", "download"))
                                        self.log_message(f"Subtitle was found for: {segment_title}!",
                                                         "orange")
                                    break
                        self.collector(course=course_title,
                                       chapter=lecture_meta['chapter'],
                                       lecture=lecture_meta['display_name'],
                                       id=lecture,
                                       segment=segment_title,
                                       video_url=video_url,
                                       subtitle_url=subtitle_url)

            # TODO  PageScraper STOP

            # TODO dataConstructor START
            # MH DIAGRAFEI
            # TODO dataConstructor STOP

    def download_video(self, url: str, save_as: str, srt=False):
        # Downloads the video
        # srt arg-->   url refers to video or subtitle? False:video , True:subtitle
        #
        print("HERE", url)
        if srt and 'kaltura' not in url:
            # Subtitles are either downloaded as (.srt) or as transcripts (.txt)
            # depending on  "user_state"  that is saved server side and we cannot
            # make the choice with a simple GET request.
            # Thus, a POST request is required , which will change the user state
            # to the following  "transcript_download_format": "srt".

            save_user_state = url.replace("transcript", "xmodule_handler").replace("download", "save_user_state")
            self.edx_headers['x-csrftoken'] = self.client.cookies.get_dict().get('csrftoken')
            post_resp = self.client.post(url=save_user_state,
                                         cookies=self.client.cookies.get_dict(),
                                         headers=self.edx_headers,
                                         data={"transcript_download_format": "srt"})

        # temporary name to avoid duplication.
        save_as_parted = f"{save_as}.part"
        # In order to make downloader resumable, we need to set our headers with
        # the right Range. we need the bytesize of our incomplete file and
        # the content-length from the file's header.
        current_size_file = os.path.getsize(save_as_parted) if os.path.exists(save_as_parted) else 0

        # HEAD response will reveal length and url(if redirected).
        head_res = self.client.head(url, allow_redirects=True)
        file_size = head_res.headers.get('Content-Length', 0)
        url = head_res.url
        # file_size str-->int (remember we need to build bytesize range)
        file_size = int(file_size)
        range_suffix_len = file_size - current_size_file

        print("curr file size", current_size_file, "video size :", file_size, "suffix", range_suffix_len)

        range_headers = {'Range': f'bytes=-{range_suffix_len}'}
        progress_bar = tqdm(total=file_size, unit='iB', unit_scale=True)
        progress_bar.update(current_size_file)
        with self.client.get(url, headers=range_headers, stream=True, allow_redirects=True) as resp:
            with open(save_as_parted, 'ab') as f:
                for chunk in resp.iter_content(chunk_size=VID_CHUNK_SIZE * 1000):
                    progress_bar.update(len(chunk))
                    f.write(chunk)
                    current_size_file += len(chunk)
        range_suffix_len = file_size - current_size_file
        print(os.path.getsize(save_as_parted), file_size, current_size_file, range_suffix_len)
        if file_size == os.path.getsize(save_as_parted):
            progress_bar.close()
            os.rename(save_as_parted, save_as)
            print("success", )

        else:
            if srt:
                self.log_message("failed  " + url, "red")
                os.remove(save_as_parted)

        #
        # with self.client.get(url, stream=True) as resp:
        #
        #     total_size_in_bytes = int(resp.headers.get('content-length', 0))
        #
        #     progress_bar = tqdm(total=total_size_in_bytes, unit='iB', unit_scale=True)
        #
        #     with open(save_as_parted, 'wb') as f:
        #         for chunk in resp.iter_content(chunk_size=VID_CHUNK_SIZE):
        #             progress_bar.update(len(chunk))
        #             f.write(chunk)
        #     progress_bar.close()
        # os.rename(save_as_parted, save_as)
        #

        return True


class Collector():
    def __init__(self):
        # list with previously found positive dictionary results.
        self.all_videos = []

        # set with ID's of previously found positive dictionary results.
        self.positive_results_id = set()

        # set with ID's of previously found negative dictionary results.
        self.negative_results_id = set()

        base_filepath = os.path.join(expanduser('~'), '{file}')
        self.results = base_filepath.format(file='.edxResults')
        self.negative_results = base_filepath.format(file='.edxResults_bad')

        with open(self.results, "r") as f:
            # loads previously found positive results where videos were found.
            # results have initial dictionary structure.
            for line in f:
                d = ast.literal_eval(line)
                if not d.get('id') in self.positive_results_id:
                    # loading previous dict results
                    self.all_videos.append(d)
                    # collecting ids in set() to avoid duplicates
                    self.positive_results_id.add(d.get('id'))

        with open(self.negative_results) as f:
            # loads previously found negative pages where no video was found.
            self.negative_results_id = set([line for line in f.read().splitlines()])

    def __call__(self, **kwargs):

        # kwargs = {
        #     'id': kwargs.get('id', None),
        #     'course': kwargs.get('course', 'Course'),
        #     'chapter': kwargs.get('chapter', 'Chapter'),
        #     'lecture': kwargs.get('lecture', 'Lecture'),
        #     'segment': kwargs.get('segment', 'Segment'),
        #     'video_url': kwargs.get('video_url'),
        #     'subtitle_url': kwargs.get('subtitle_url', None)
        # }
        if not kwargs.get('id') in self.positive_results_id:
            # avoids duplicates
            self.all_videos.append(kwargs)
            self.positive_results_id.add(kwargs.get('id'))
            print(len(self.all_videos))
            return True
        else:
            return False

    def save_results(self, ):
        with open(self.results, 'w') as f:
            for result in self.all_videos:
                f.write(str(result) + '\n')

        with open(self.negative_results, "w") as f:
            for negative_id in self.negative_results_id:
                f.write(negative_id + '\n')
        print("VIDEO RESULTS SAVED IN ~/.edxResults")
        return self.all_videos
