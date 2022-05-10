import requests
from bs4 import BeautifulSoup
import html
from fake_useragent import UserAgent
import colorful as cf
import json
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait
from tqdm import tqdm
import sys
import traceback
import time
import os
from os.path import expanduser
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, TimeoutException

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
        self.driver.implicitly_wait(10)

    # TODO
    def get_url(self, url):
        try:
            self.driver.get(url)
            time.sleep(2)
        except Exception as e:
            print(traceback.format_exc())
            # self.driver.quit()

    def getCookies(self, cookies: dict):
        #
        return [{'name': c.name,
                       'value': c.value,
                       'domain': c.domain,
                       'path': c.path,
                       'expiry': c.expires} for c in cookies]



    def loadCookies(self):
        self.driver.delete_all_cookies()
        [self.driver.add_cookie(cookie) for cookie in self.Sessioncookies]
        return


class EdxDownloader:
    # Create a request session to send cookies
    # automatically for HTTP requests.
    client = requests.session()

    # Generate a fake user-agent to avoid blocks
    user_agent = UserAgent()

    # Initiate webdriver

    # These headers are required. Some may not be required
    # but sending all is a good practice.
    edx_headers = {
        'Host': EDX_HOSTNAME,
        'accept': '*/*',
        'x-requested-with': 'XMLHttpRequest',
        'user-user_agent': 'Mozilla/5.0 (X11; Linux x86_64) '
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
    cookie = os.path.join(expanduser('~'), '.edxcookie')

    def __init__(self, email, password, is_debug=True, is_colored=True, toggle_experimental=False):
        # This is set True later and is used to
        # avoid unnecessary login attempts
        self.is_authenticated = False

        # When it is set False, the log_message()
        # function will not print anything.
        self.is_debug = is_debug

        # When this is set to True the log_message()
        # function will print in color.
        self.is_colored = is_colored

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
        #     'url': video_url,
        #     'sub': subtitle_url    }
        self.all_videos = []

        # Enables experimental parser for specific Courses that embed Kaltura WebPlayer.
        self.toggle_experimental = toggle_experimental

    def collector(self, course, chapter, lecture, title, url, sub):
        pass

    @staticmethod
    def log_message(message, color='blue', is_debug=True, is_colored=True):
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

        if is_debug:
            if is_colored:
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
                # cookie_value = self.client.cookies.get(cookie_name)
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

    def experimental_scrape(self, course_title, lectures, chapters, COURSE_SLUG):
        '''
        # we run a second client GET request by using
        # the parent's <iframe src="{nested iframe URL}"
        # attribute to dwelve deeper into it's nested content which will
        # eventually include both the video URL and subtitles URL.
        '''

        print("Experimental Scraping initiates..")
        for i in reversed(range(3)):
            print(i + 1)
            time.sleep(1)

        drive = SeleniumManager(self.client.cookies)

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
                # print("DEBUGGER VERT ELEMENTS :")

                if vertical_elements:
                    for vertical_elem in vertical_elements:

                        vertical_slug = vertical_elem.get("data-id")
                        vertical_url = "{}/{}".format(XBLOCK_BASE_URL, vertical_slug)
                        self.log_message((
                            f"Searching for elements in vertical: {vertical_elem.get('data-path')}. URL: {vertical_url}"))



                        for i in range(2):


                            drive.get_url(vertical_url)
                            drive.loadCookies()

                            # with open(os.path.join(os.getcwd() + '/edx-errors',
                            #                        f"{c}{vertical_elem.get('data-path')}-base.log"), 'a') as f:
                            #     f.write(str(drive.driver.page_source))
                            try:

                                drive.driver.switch_to.frame('kaltura_player')
                            except:
                                continue
                            else:
                                break

                        # c+=1
                        # # with open(os.path.join(os.getcwd() + '/edx-errors/iframes',
                        # #                        f"{c}{vertical_elem.get('data-path')} -iframe.log"), 'a') as f:
                        # #     f.write(str(drive.driver.page_source))

                        video_element = None
                        subtitle_element = None
                        loop = 0
                        c = time.time()
                        while loop <= 4:
                            loop += 1
                            print('number of repetitions :', loop)
                            try:
                                # ignored_exceptions = (NoSuchElementException, StaleElementReferenceException)
                                video_element = WebDriverWait(drive.driver, 5).until(
                                    expected_conditions.presence_of_element_located((By.ID, "pid_kaltura_player")))
                            except Exception as e:
                                print("ERROR IN VIDEO ELEM", e)
                                print(traceback.format_exc())
                                continue
                            else:
                                try:
                                    # subtitle_element = WebDriverWait(drive.driver, 4).until(expected_conditions.presence_of_element_located((By.TAG_NAME, 'track')))

                                    subtitle_element = video_element.find_element(By.TAG_NAME, 'track')

                                except Exception as e:
                                    print("ERROR IN SUB ELEM", e)
                                    print(traceback.format_exc())
                            break
                        d = time.time()
                        print("time to find elements:", d - c, "time between GET  and before element", c - a)
                        # try:
                        #     video_element = drive.driver.find_element(By.ID, 'pid_kaltura_player')
                        #     subtitle_element = drive.driver.find_element(By.TAG_NAME, 'track')
                        # except Exception as e:
                        #     print(e)
                        #     html_driver = drive.driver.page_source
                        #     with open(os.path.join(os.getcwd() + '/edx-errors',
                        #                            f'{c} {lecture_meta.get("display_name")}-edx-error2.log'),
                        #               'a') as f:
                        #         f.write(str(html_driver))
                        #     continue
                        # print ("LOOOOOOOOOLWAIT", video_element_await.get_attribute('kpartnerid'))
                        # print("LOOOOOOOOOLWAITSUB", subtitle_element_await.get_attribute('src'))

                        if video_element:

                            # with open(os.path.join(os.getcwd() + '/edx-errors',
                            #                        f'{c} {vertical_elem.get("data-page-title")}-edx-error2.log'),
                            #           'a') as f:
                            #     f.write(str(nested_soup))
                            #     c += 1

                            partnerid = video_element.get_attribute('kpartnerid')
                            entryid = video_element.get_attribute('kentryid')
                            video_url = DOWNLOAD_KALTURA_URL.format(PID=partnerid, entryId=entryid)

                            self.log_message(f"Struck gold! New video found! {vertical_elem.get('data-page-title')}",
                                             "orange")
                            subtitle_url = None
                            if subtitle_element:
                                self.log_message(
                                    f"Ne subtitle found! {vertical_elem.get('data-page-title')}",
                                    "orange")
                                subtitle_url = subtitle_element.get_attribute('src')

                            self.all_videos.append({
                                'course': course_title,  # check
                                'chapter': lecture_meta['chapter'],
                                'lecture': lecture_meta['display_name'],
                                'segment': vertical_elem.get("data-page-title"),
                                'url': video_url,  # check
                                'sub': subtitle_url  # check
                            })

        drive.driver.quit()
        print(self.all_videos)
        return self.all_videos

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
        soup_elem = soup.find_all('a', {'class': 'course-target-link enter-course'})
        if soup_elem:
            for i in soup_elem:
                COURSE_SLUG = i['data-course-key']
                build = "{}/{}/".format(COURSE_BASE_URL, COURSE_SLUG)
                available_courses.append(build)
        if len(available_courses) > 0:
            # print(available_courses)
            self.log_message(f"{len(available_courses)} available courses found in Dashboard!")
        else:
            self.log_message("No courses available!", "red")
        return available_courses

    def get_course_data(self, course_url=None):
        '''

         The following method find the basic the course media URLs. The media URLs are returned
         as a list if found.
       '''

        self.log_message('Building xblocks.')

        # TODO  ( IS URL A VALID COURSE ? ) START
        # Break down the course URL to get course slug.
        url_parts = course_url.split('/')
        if len(url_parts) >= 4 and url_parts[4].startswith('course-'):
            COURSE_SLUG = url_parts[4]
        else:
            # If the conditions above are not passed, we will assume that a wrong
            # course URL was passed in.
            raise EdxInvalidCourseError('The provided course URL seems to be invalid.')
        # Construct the course outline URL
        COURSE_OUTLINE_URL = '{}/{}'.format(COURSE_OUTLINE_BASE_URL, COURSE_SLUG)
        # TODO  ( IS URL A VALID COURSE ? ) END

        # TODO is_authenticated start
        # Check either authenticated or not before proceeding.
        # If not, raise the EdxNotAuthenticatedError exception.
        if not self.is_authenticated:
            raise EdxNotAuthenticatedError('Course data cannot be retrieved without getting authenticated.')
        # todo is_authenticated end

        # TODO Mapper START

        # Make an HTTP GET request to outline URL and return dictionary object
        # with blocks:metadata as keys:values which will help us iterate the course.

        # TODO ConnectionManager START
        try:
            outline_resp = self.client.get(COURSE_OUTLINE_URL, timeout=50)
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
            if list(blocks.values())[0].get('display_name') is not None:
                course_title = list(blocks.values())[0].get('display_name')
                print(f' Course found. {course_title} Scraping starts..')
        else:
            for block, block_meta in blocks.items():
                if block_meta.get('type') == 'course' and block_meta.get('display_name') is not None:
                    course_title = block_meta.get('display_name')
                    break

        lectures = {k: v for k, v in blocks.items() if v['type'] == 'sequential'}
        chapters = {k: v for k, v in blocks.items() if v['type'] == 'chapter' and v['children'] is not None}

        # total video segment names
        video_total = []
        # total subtitles segment names
        sub_total = []

        for lecture, lecture_meta in lectures.items():
            for chapter, chapter_meta in chapters.items():
                if lecture in chapter_meta.get('children'):
                    lectures.setdefault(lecture, {}).update({'chapter': chapter_meta.get('display_name')})
                    lectures.setdefault(lecture, {}).update({'chapterID': chapter_meta.get('id')})
                    lectures.setdefault(lecture, {}).update({'course': course_title})
                    break

        if self.toggle_experimental:

            try:
                self.experimental_scrape(course_title, lectures, chapters, COURSE_SLUG)
            except KeyboardInterrupt:
                if self.all_videos:
                    return self.all_videos
        for lecture, lecture_meta in lectures.items():

            # lectures are the equivalent of sequentials from course block .
            block_id = lecture_meta.get('id')
            block_url = '{}/{}/jump_to/{}'.format(COURSE_BASE_URL, COURSE_SLUG, block_id)
            block_res = self.client.get(block_url)
            main_block_id = block_res.url.split('/')[-1]
            main_block_url = '{}/{}'.format(XBLOCK_BASE_URL, main_block_id)
            # TODO Mapper STOP

            # TODO ConnectionManager START
            try:
                main_block_res = self.client.get(main_block_url)
            except ConnectionError as e:
                raise EdxRequestError(e)
            soup = BeautifulSoup(html.unescape(main_block_res.text), 'lxml')
            # TODO ConnectionManager STOP

            if soup:

                # TODO  PageScraper START

                # Searches through HTML elements
                # Finds and builds URLs for subtitles and videos

                for elements in soup.find_all('div', {'class': 'xblock-student_view-video'}):
                    segment_title = None
                    video_url = None
                    sub_url = None

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

                                    if sub_url is None and 'transcriptAvailableTranslationsUrl' in json_meta:
                                        # subtitle URL found
                                        sub_url = '{}{}'.format(BASE_URL,
                                                                json_meta['transcriptAvailableTranslationsUrl'].replace(
                                                                    "available_translations", "download"))

                                    break

                        self.all_videos.append({
                            'course': course_title,  # check
                            'chapter': lecture_meta['chapter'],
                            'lecture': lecture_meta['display_name'],
                            'segment': segment_title,
                            'url': video_url,  # check
                            'sub': sub_url  # check
                        })
            # TODO  PageScraper STOP

            # TODO dataConstructor START
            # MH DIAGRAFEI
            # TODO dataConstructor STOP
        return self.all_videos

    def download_video(self, url: str, save_as: str, srt=False):
        # Downloads the video
        # srt arg-->   url refers to video or subtitle? False:video , True:subtitle
        #
        save_as_parted = f"{save_as}.part"
        if srt:
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
            if post_resp.status_code == 200:
                print(post_resp.content)

        with self.client.get(url, stream=True) as resp:
            total_size_in_bytes = int(resp.headers.get('content-length', 0))

            progress_bar = tqdm(total=total_size_in_bytes, unit='iB', unit_scale=True)

            with open(save_as_parted, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=VID_CHUNK_SIZE):
                    progress_bar.update(len(chunk))
                    f.write(chunk)
            progress_bar.close()
        os.rename(save_as_parted, save_as)
        return True
