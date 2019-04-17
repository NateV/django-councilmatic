import os
from setuptools import setup

with open(os.path.join(os.path.dirname(__file__), 'README.rst')) as readme:
    README = readme.read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name='django-councilmatic',
    version='0.10.11',
    packages=['councilmatic_core'],
    include_package_data=True,
    license='MIT License',  # example license
    description='Core functions for councilmatic.org family',
    long_description=README,
    url='http://councilmatic.org/',
    author='DataMade, LLC',
    author_email='info@datamade.us',
    install_requires=['requests>=2.20,<2.21',
                      'opencivicdata>=2.2.1<2.3',
                      'pytz>=2015.4',
                      'django-haystack>=2.8.0,<2.9',
                      'Django>=2.0,<2.2',
                      'django-proxy-overrides>=0.2',
                      'python-dateutil>=2.7<2.8',
                      'pysolr>=3.8,<3.9',
                      'psycopg2-binary>=2.7<2.8',
                      'django-adv-cache-tag==1.1.2',
                      'django-activity-stream',
                      'boto==2.38.0'],
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',  # example license
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        # Replace these appropriately if you are stuck on Python 2.
        'Programming Language :: Python :: 3.4',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    ],
)
