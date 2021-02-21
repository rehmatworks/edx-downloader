# EDX Downloader (for edx.org)
This is a command-line downloader written using Python. This project is inspired by [edx-dl](https://github.com/coursera-dl/edx-dl) but it does not rely on `youtube-dl` or any other external library to download the videos. Moreover, at the moment this downloader supports just [https://edx.org](https://edx.org) website only and it doesn't support other similar websites.

**Disclaimer**: You should not use this software to abuse EDX website. I have written this software with a positive intention, that is to help learners download EDX course videos altogether quickly and easily. I am not responsible if your EDX account gets banned for abuse. You should use this software on your own risks.

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
Once installed, a command `edxdl` becomes available in your terminal. Typing `edxdl` and hitting enter in your terminal should bring up the downloader menu. Provide a course URL and hit enter to get started.

## Storing Login Credentials
On a private computer, it is always better if the software doesn't ask you for your EDX login and again. To make the software automatically use your login credentials, create a file called `.edxauth` in your home directory and provide the credentials in two lines. The first line should contain your email address and the second line should contain your password.

Moreover, `edx-downloader` will ask you to save your login details if you have not asked it to skip saving the credentials. If it doesn't ask, you can update your credentials in `.edxauth` file any time. On a Unix machine, you can create this file with `touch ~/.edxauth` and edit with you favorite editor. A sample `.edxauth` file has been included in this repo.


## Recommendation
Although this downloader should work on Python 2.7 too, but it is highly recommended that you should use Python 3.x. to avoid any possible issues.

## Bugs & Issues
I have developed this package quickly and I have uploaded it for the community. Please expect bugs and issues. Bug fixing and improvements are highly appreciated. Send a pull request if you want to improve it or if you have fixed a bug.

Normal users can use the issues section to report bugs and issues for this software. Before opening a new issue, please go through existing ones to be sure that your question has not been asked and answered yet.

## Credits
- [Python](https://www.python.org/) - The programming language that I have used
- [beautifulsoup4](https://pypi.org/project/beautifulsoup4/) - For HTML parsing
- [colorful](https://github.com/timofurrer/colorful) - To show colorful text
- [fake-useragent](https://pypi.org/project/fake-useragent/) - For a dynamic user-agent
- [requests](https://github.com/psf/requests) - To make HTTP requests
- [tqdm](https://github.com/tqdm/tqdm) - To show download progress bar
- [validators](https://github.com/kvesteri/validators) - To validate URL and email input

And thanks to several indirect dependencies that the main dependencies are relying on.