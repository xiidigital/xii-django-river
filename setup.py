import os
import sys

from setuptools import setup, find_packages

readme_file = os.path.join(os.path.dirname(__file__), 'README.rst')
try:
    long_description = open(readme_file).read()
except IOError as err:
    sys.stderr.write("[ERROR] Cannot find file specified as "
                     "``long_description`` (%s)\n" % readme_file)
    sys.exit(1)

setup(
    name='django-river',
    version='4.0.0',
    author='Ahmet DAL',
    author_email='ceahmetdal@gmail.com',
    packages=find_packages(exclude=['river.tests', 'river.tests.*']),
    url='https://github.com/javrasya/django-river.git',
    description='Django Workflow Library',
    long_description=long_description,
    python_requires='>=3.10',
    install_requires=[
        "Django>=4.2",
        "django-cte>=3.0",
    ],
    extras_require={
        "codemirror": ["django-codemirror2"],
    },
    include_package_data=True,
    zip_safe=False,
    license='BSD',
    platforms=['any'],
    classifiers=[
        'Framework :: Django',
        'Framework :: Django :: 4.2',
        'Framework :: Django :: 5.0',
        'Framework :: Django :: 5.1',
        'Framework :: Django :: 5.2',
        'Framework :: Django :: 6.0',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'License :: OSI Approved :: BSD License',
    ],
)
