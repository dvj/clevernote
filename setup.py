import os
from setuptools import setup


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name="clevernote",
    version="0.3.0",
    author="Doug Johnston",
    author_email="clevernote@dvjohnston.com",
    description=("A command line interface to Evernote"),
    license="BSD",
    keywords="Evernote CLI command line command-line note",
    url="http://packages.python.org/clevernote",
    packages=['clevernote', 'clevernote-web-auth'],
    long_description=read('README'),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Topic :: Utilities",
        "Environment :: Console"
        "License :: OSI Approved :: BSD License",
    ],
    install_requires=[
        'evernote',
        'html2text',
        'markdown2'],
)
