# EDX Downloader (for edx.org)
This is a command-line downloader written using Python. This project is inspired by [edx-dl](https://github.com/coursera-dl/edx-dl) but it does not rely on `youtube-dl` or any other external library to download the videos. Moreover, at the moment this downloader supports just [https://edx.org](https://edx.org) website only and it doesn't support other similar websites.

## Installation
```bash
pip3 install edx-downloader
```

Or clone this repo and install manually:

```bash
git clone https://github.com/rehmatworks/edx-downloader.git
cd edx-downloader
pip3 install -r requirements.txt
python3 setup.py install
```

## Usage
Once installed, a command `edxdl` becomes available in your terminal. Typing `edxdl` and hitting in your terminal should bring up the downloader menu. Provide a course URL and hit enter to get started.


## Recommendation
Although this downloader should work on Python 2.7 too, but it is highly recommended that you should use Python 3.x. to avoid any possible issues.

## Bugs & Issues
I have developed this package quickly and I have uploaded it for the community. Bug fixing and improvements are highly appreciated. Send a pull request if you want to improve it or if you have fixed a bug.

Normal users can use the issues section to report bugs and issues for this software. Before opening a new issue, please go through existing ones to be sure that your question has not been asked and answered yet.
