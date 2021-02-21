# EDX Downloader (for edx.org)
This is a command-line downloader written using Python. This project is inspired by [edx-dl](https://github.com/coursera-dl/edx-dl) by it does not rely on `youtube-dl` or any other external library to download the videos. Moreover, this downloader supports just [https://edx.org](https://edx.org) website only and it doesn't support other similar websites.

### Installation
```bash
pip install edxdownloader
```

Or clone this repo and install manually:

```bash
git clone https://github.com/rehmatworks/edx-downloader.git
cd edx-downloader
pip install -r requirements.txt
python setup.py install
```

### Usage
Once installed, a command `edxdl` becomes available in your terminal. Typing `edxdl` and hitting in your terminal should bring up the downloader menu. Provide a course URL and hit enter to get started.


### Recommendation
Although this downloader should work on Python 2.7 too, but it is highly recommended that you should use Python 3.x.
