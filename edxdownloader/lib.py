import requests
from bs4 import BeautifulSoup
import html
from fake_useragent import UserAgent
import colorful as cf
import json
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

# Chunk size to download videos in chunks
VID_CHUNK_SIZE = 1024

# Override colorful palette
ci_colors = {
    'green': '#42ba96',
    'orange': '#ffc107',
    'red': '#df4759',
    'blue': '#5dade2'
}
cf.update_palette(ci_colors)

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


class EdxDownloader:
    # Create a request session to send cookies
    # automatically for HTTP requests.
    requests_session = requests.session()

    # Generate a fake user-agent to avoid blocks
    user_agent = UserAgent()

    # These headers are required. Some may not be required
    # but sending all is a good practice.
    edx_headers = {
        'Host': EDX_HOSTNAME,
        'accept': '*/*',
        'x-requested-with': 'XMLHttpRequest',
        'user-agent': user_agent.random,
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'origin': BASE_URL,
        'sec-fetch-site': 'same-origin',
        'sec-fetch-mode': 'cors',
        'sec-fetch-dest': 'empty',
        'referer': LOGIN_URL,
        'accept-language': 'en-US,en;q=0.9',
    }

    def __init__(self, email, password):
        # This is set True later and is used to
        # avoid unnecessary login attempts
        self.is_authenticated = False

        # When it is set False, the log_message()
        # funciton will not print anything.
        self.is_debug = True

        # The EDX account's email
        self.edx_email = email

        # The EDX account's password
        self.edx_password = password

    def log_message(self, message, color='blue'):
        # Outputs a colorful message to the terminal
        # and only if is_debug prop is set to True.
        if self.is_debug:
            if color == 'blue':
                message = cf.bold | cf.blue(message)
            elif color == 'orange':
                message = cf.bold | cf.orange(message)
            elif color == 'green':
                message = cf.bold | cf.green(message)
            elif color == 'red':
                message = cf.bold | cf.red(message)
            print(message)

    def sign_in(self):
        # Authenticates the user session. It returns True on success
        # or raises EdxLoginError on failure.
        try:
            html_res = self.requests_session.get(LOGIN_URL)
            self.edx_headers['x-csrftoken'] = html_res.cookies.get('csrftoken') 
            data = {
                'email': self.edx_email,
                'password': self.edx_password
            }
            res = self.requests_session.post(LOGIN_API_URL, headers=self.edx_headers, data=data)
            if res.json().get('success') is True:
                self.is_authenticated = True
                return True
            else:
                pass
        except EdxRequestError:
            pass
        raise EdxLoginError('Login failed. Please try again.')

    def get_course_data(self, course_url):
        # Gets the course media URLs. The media URLs are returned
        # as a list if found.

        # Break down the course URL to get course slug.
        url_parts = course_url.split('/')
        if len(url_parts) >= 4 and str(url_parts[4]).startswith('course-'):
           COURSE_SLUG = str(url_parts[4])
        else:
            # If the conditions above are not passed, we will assume that a wrong
            # course URL was passed in.
            raise EdxInvalidCourseError('The provided course URL seems to be invalid.')
        
        # Construct the course outline URL
        COURSE_OUTLINE_URL = '{}/{}'.format(COURSE_OUTLINE_BASE_URL, COURSE_SLUG)

        # Check either authenticated or not before proceeding.
        # If not, raise the EdxNotAuthenticatedError exception.
        if not self.is_authenticated:
            raise EdxNotAuthenticatedError('Course data cannot be retrieved without getting authenticated.')
        
        # Make an HTTP GET request to outline URL and get tabs
        outline_resp = self.requests_session.get(COURSE_OUTLINE_URL)
        blocks = outline_resp.json().get('course_blocks')
        collected_vids = []
        collected_courses = []
        all_videos = []

        if blocks is None:
            # If no blocks or tabs are found, we wil assume that the user is not authorized
            # to access the course.
            raise EdxNotEnrolledError('Looks like you are not enrolled in this course.')
        else:
            course_name = None
            # Iterate through blocks and get course name, video URLs, and video titles.
            for k, v in blocks.get('blocks').items():
                if v.get('type') == 'course' and v.get('display_name') is not None:
                    course_name = v.get('display_name')
                    if course_name not in collected_courses:
                        collected_courses.append(course_name)
                    else:
                        continue
                
                if course_name is not None:
                    block_id = v.get('id')
                    block_url = '{}/{}/jump_to/{}'.format(COURSE_BASE_URL, COURSE_SLUG, block_id)
                    block_res = self.requests_session.get(block_url)
                    main_block_id = block_res.url.split('/')[-1]
                    main_block_url = '{}/{}'.format(XBLOCK_BASE_URL, main_block_id)
                    main_block_res = self.requests_session.get(main_block_url)

                    soup = BeautifulSoup(html.unescape(main_block_res.text), 'lxml')

                    for vid in soup.find_all('div', {'class': 'xblock-student_view-video'}):
                        vid_url_el = vid.find('div', {'class': 'video'})
                        if vid_url_el:
                            metadata = vid_url_el.get('data-metadata')
                            if metadata:
                                vid_url = None
                                # Get the data-metadata attribute HTML
                                # and parse it as a JSON object.
                                metadata = json.loads(metadata)
                                if 'sources' in metadata:
                                    for vidsource in list(metadata['sources']):
                                        if str(vidsource).endswith('.mp4'):
                                            vid_url = vidsource
                                            # Break the loop if a valid video URL
                                            # is found.
                                            break
                                if vid_url and vid_url not in collected_vids:
                                    vid_title = v.get('display_name')
                                    vid_heading_el = vid.find('h3', {'class': 'hd hd-2'})
                                    if vid_heading_el:
                                        vid_title = '{} - {}'.format(vid_title, vid_heading_el.text.strip())

                                    # Append the video object to all_videos list
                                    all_videos.append({
                                        'title': vid_title,
                                        'url': vid_url,
                                        'course': course_name
                                    })
                                    collected_vids.append(vid_url)                
        return all_videos
    
    def download_video(self, vid_url, save_as):
        # Download the video
        with self.requests_session.get(vid_url, stream=True) as resp:
            total_size_in_bytes= int(resp.headers.get('content-length', 0))
            progress_bar = tqdm(total=total_size_in_bytes, unit='iB', unit_scale=True)
            with open(save_as, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=VID_CHUNK_SIZE):
                    progress_bar.update(len(chunk))
                    f.write(chunk)
            progress_bar.close()
        return True