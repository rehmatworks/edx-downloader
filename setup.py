from setuptools import setup


setup(name='edxdownloader',
	version='1.0.0',
	description='CLI downloader for EDX video courses. Download all course videos from https://edx.org easily.',
	author="Rehmat Alam",
	author_email="contact@rehmat.works",
	url="https://github.com/rehmatworks/edx-downloader",
	license="MIT",
	entry_points={
		'console_scripts': [
			'edxdl = edxdownloader.utils:main'
			],
	},
	packages=[
		'edxdownloader'
	],
	install_requires=[
		'beautifulsoup4>=4.9',
        'bs4>=0.0',
        'certifi>=2020.12',
        'chardet>=4.0.0',
        'colorful>=0.5.4',
        'decorator>=4.4',
        'fake-useragent>=0.1',
        'idna>=2.10',
        'lxml>=4.6',
        'requests>=2.25',
        'six>=1.15',
        'soupsieve>=2.2',
        'tqdm>=4.57.0',
        'urllib3>=1.26',
        'validators>=0.18'
	]
)